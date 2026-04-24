"""
moodle_processor.py — MBZ translation processor
================================================
Key design decisions:
1. STREAM through the tar archive (no full extraction) to preserve EXACT metadata:
   member names (including "./" prefixes), file modes, mtimes, uid/gid, etc.
   Any metadata difference can confuse Moodle's restore step counter.

2. Three-strategy content handler with CORRECT priority:
   CDATA is checked FIRST, even when it contains {mlang} blocks.
   Previous versions checked {mlang} first and SILENTLY REMOVED CDATA wrappers
   from files whose content was like: <content><![CDATA[{mlang en}...]]></content>
   Without the CDATA wrapper, HTML tags inside mlang blocks become invalid XML,
   which breaks Moodle's PHP restore parser and causes "progress() value out of range".

   Priority order:
     A → CDATA  (preserves wrapper, handles mlang-inside-CDATA too)
     B → {mlang} blocks in raw text  (re-translate existing blocks)
     C → plain text  (add new mlang blocks)
"""

import io
import re
import copy
import json
import html as _html
import tarfile
import zipfile
import tempfile
import lxml.etree as ET
from pathlib import Path

# ── Files that MUST NOT be modified ─────────────────────────────────────────
# These control Moodle's restore-step counter; any change → progress() error.
SKIP_FILES = {
    'moodle_backup.xml', 'completion.xml', 'gradebook.xml', 'groups.xml',
    'outcomes.xml', 'roles.xml', 'filters.xml', 'comments.xml', 'badges.xml',
    'calendarevents.xml', 'competencies.xml', 'contentbank.xml', 'enrolments.xml',
    'scales.xml', 'tags.xml', 'inforef.xml', 'grade_history.xml',
    'course_completion.xml', 'module.xml',
}

CONTENT_TAGS = ['name', 'intro', 'summary', 'content', 'description', 'text']
CHUNK_CHARS  = 8000   # max chars per single OpenAI call


class MoodleMBZProcessor:
    def __init__(self, source_lang='en', target_langs=None,
                 api_type='none', api_key=None, cancel_callback=None):
        self.source_lang  = source_lang
        self.target_langs = target_langs or ['en', 'pl']
        self.api_type     = api_type
        self.api_key      = api_key
        self.cancel_callback = cancel_callback

    # ─────────────────────────────────────────────────────────────── translation

    def translate_text(self, html_or_text: str, target_lang: str) -> str:
        if target_lang == self.source_lang or not html_or_text.strip():
            return html_or_text
        if self.api_type == 'openai' and self.api_key:
            return self._openai_translate(html_or_text, target_lang)
        if self.api_type == 'deepl' and self.api_key:
            return self._deepl_translate(html_or_text, target_lang)
        if self.api_type == 'gemini' and self.api_key:
            return self._gemini_translate(html_or_text, target_lang)
        return f'[{target_lang}] {html_or_text}'

    def _openai_translate(self, content: str, target_lang: str) -> str:
        if len(content) <= CHUNK_CHARS:
            return self._openai_call(content, target_lang)
        # Split long HTML at paragraph boundaries
        parts = re.split(r'(?<=</p>)', content)
        translated, chunk = [], ''
        for part in parts:
            if len(chunk) + len(part) > CHUNK_CHARS and chunk:
                translated.append(self._openai_call(chunk, target_lang))
                chunk = part
            else:
                chunk += part
        if chunk:
            translated.append(self._openai_call(chunk, target_lang))
        return ''.join(translated)

    def _openai_call(self, content: str, target_lang: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': (
                        f'You are a professional translator. '
                        f'Translate from {self.source_lang} to {target_lang}. '
                        f'Preserve ALL HTML tags and their attributes exactly. '
                        f'Return ONLY the translated content.'
                    )},
                    {'role': 'user', 'content': content},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f'  [!] OpenAI error: {e}')
            return content

    def _deepl_translate(self, content: str, target_lang: str) -> str:
        try:
            import deepl
            translator = deepl.Translator(self.api_key)
            result = translator.translate_text(
                content, target_lang=target_lang.upper(), tag_handling='html')
            return result.text
        except Exception as e:
            print(f'  [!] DeepL error: {e}')
            return content

    def _gemini_translate(self, content: str, target_lang: str) -> str:
        if len(content) <= CHUNK_CHARS:
            return self._gemini_call(content, target_lang)
        # Split long HTML at paragraph boundaries
        parts = re.split(r'(?<=</p>)', content)
        translated, chunk = [], ''
        for part in parts:
            if len(chunk) + len(part) > CHUNK_CHARS and chunk:
                translated.append(self._gemini_call(chunk, target_lang))
                chunk = part
            else:
                chunk += part
        if chunk:
            translated.append(self._gemini_call(chunk, target_lang))
        return ''.join(translated)

    def _gemini_call(self, content: str, target_lang: str) -> str:
        import time
        import re as _re
        try:
            from google import genai
        except ImportError:
            print('  [!] google-genai not installed')
            return content

        client = genai.Client(api_key=self.api_key)
        prompt = (f'You are a professional translator. '
                  f'Translate from {self.source_lang} to {target_lang}. '
                  f'Preserve ALL HTML tags and their attributes exactly. '
                  f'Return ONLY the translated content:\n\n{content}')

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                return resp.text.strip()
            except Exception as e:
                err_str = str(e)
                print(f'  [!] Gemini error (attempt {attempt+1}/{max_retries}): {err_str[:200]}')

                is_rate_limit = any(kw in err_str.lower() for kw in [
                    '429', 'resourceexhausted', 'quota', 'too many requests', 'rate limit'
                ])

                if not is_rate_limit or attempt == max_retries - 1:
                    return content

                # Try to parse retry-after seconds from error message
                m = _re.search(r'retry[^0-9]{0,20}(\d+)', err_str, _re.IGNORECASE)
                if m:
                    wait_s = max(int(m.group(1)), 5)
                else:
                    wait_s = min(5 * (2 ** attempt), 120)  # 5, 10, 20, 40, 80... max 120s

                print(f'  [!] Rate limit — czekam {wait_s}s (attempt {attempt+1}) ...')
                time.sleep(wait_s)

        return content

    def wrap_mlang(self, translations: dict) -> str:
        return ''.join(
            f'{{mlang {lang}}}{txt}{{mlang}}'
            for lang, txt in translations.items() if txt is not None
        )

    # ──────────────────────────────────────────────────── XML content processing

    # ── Safety Validation ─────────────────────────────────────────────────────
    def _is_translatable(self, text: str) -> bool:
        if not text:
            return False
        # Do not translate serialized PHP objects/arrays
        if re.match(r'^[aAwWbBiIdDsSnoON]:\d+:\{', text[:20]) or text.startswith('b:0;') or text.startswith('b:1;'):
            return False
        # Do not translate URLs
        if re.match(r'^https?://[^\s]+$', text):
            return False
        # Do not translate pure numbers or single special chars
        if re.match(r'^[\d\s,.;:/-]+$', text) or len(text) <= 1:
            return False
        # Do not translate Base64/hashes (long string without spaces)
        if len(text) > 40 and ' ' not in text and '<' not in text:
            return False
        return True

    def _replace_in_tag(self, file_content: str, tag: str):
        """
        Find every <tag>…</tag> in file_content and translate it.
        Returns (new_content, change_count).

        Strategy priority:
          A) CDATA (checked FIRST — even if inner CDATA contains {mlang})
          B) Raw {mlang} blocks   (re-translate existing mlang-wrapped text)
          C) Plain text           (wrap fresh text with mlang blocks)
        """
        change_count = [0]
        outer_re = rf'(<{tag}(?:[^>]*)>)(.*?)(</{tag}>)'

        def handle(m):
            open_tag  = m.group(1)
            inner     = m.group(2)
            close_tag = m.group(3)

            # --- Safety checks to prevent DMLWriteException ---
            if '$@NULL@$' in inner or not inner.strip():
                return m.group(0)
            
            stripped_test = inner.strip()

            # Skip translation of configuration payload strings
            if not self._is_translatable(stripped_test):
                return m.group(0)

            if stripped_test.startswith('{') or stripped_test.startswith('['):
                try:
                    json.loads(stripped_test)
                    return m.group(0) # Valid JSON, translating it will crash Moodle plugin restore
                except Exception:
                    pass
            # --------------------------------------------------

            # ── STRATEGY A: CDATA (MUST be checked before {mlang} test) ───────
            # If inner has CDATA, process it (even if the CDATA itself contains
            # {mlang} blocks).  Stripping CDATA would make HTML inside mlang
            # invalid XML, breaking Moodle's restore parser.
            cdata_m = re.match(r'^\s*<!\[CDATA\[(.*)\]\]>\s*$', inner, re.DOTALL)
            if cdata_m:
                return self._strat_cdata(
                    open_tag, cdata_m.group(1), close_tag, change_count, tag, inner)

            # ── STRATEGY B: raw {mlang} blocks ────────────────────────────────
            if '{mlang' in inner:
                return self._strat_mlang(
                    open_tag, inner, close_tag, change_count, tag)

            # ── STRATEGY C: plain text (no angle brackets inside) ─────────────
            stripped = inner.strip()
            if stripped and '<' not in stripped:
                return self._strat_plain(
                    open_tag, stripped, close_tag, change_count, tag, inner)

            return m.group(0)   # raw HTML without wrapper → leave untouched

        new_content = re.sub(outer_re, handle, file_content, flags=re.DOTALL)
        return new_content, change_count[0]

    # ── Strategy A ── CDATA (preserve wrapper) ────────────────────────────────
    def _strat_cdata(self, open_tag, cdata_inner, close_tag, cc, tag, original_inner):
        stripped = cdata_inner.strip()
        if not stripped:
            return f'{open_tag}<![CDATA[{cdata_inner}]]>{close_tag}'

        # CDATA may itself contain {mlang} → re-translate from source block
        if '{mlang' in stripped:
            src_re = rf'\{{mlang {re.escape(self.source_lang)}\}}(.*?)\{{mlang\}}'
            src_m  = re.search(src_re, stripped, re.DOTALL)
            if src_m:
                src_content = src_m.group(1).strip()
                if src_content:
                    translations = {
                        lang: (src_content if lang == self.source_lang
                               else self.translate_text(src_content, lang))
                        for lang in self.target_langs
                    }
                    new_inner = self.wrap_mlang(translations)
                    if tag == 'name' and len(new_inner) > 255:
                        return f'{open_tag}{original_inner}{close_tag}'
                    if new_inner != stripped:
                        cc[0] += 1
                    return f'{open_tag}<![CDATA[{new_inner}]]>{close_tag}'
            # Can't find source block → leave untouched (keep CDATA wrapper)
            return f'{open_tag}<![CDATA[{stripped}]]>{close_tag}'

        # Fresh CDATA with no mlang yet
        print(f'      [CDATA] {len(stripped)} chars')
        translations = {
            lang: (stripped if lang == self.source_lang
                   else self.translate_text(stripped, lang))
            for lang in self.target_langs
        }
        new_inner = self.wrap_mlang(translations)
        if tag == 'name' and len(new_inner) > 255:
            return f'{open_tag}{original_inner}{close_tag}'
            
        cc[0] += 1
        return f'{open_tag}<![CDATA[{new_inner}]]>{close_tag}'

    # ── Strategy B ── raw {mlang} blocks ─────────────────────────────────────
    def _strat_mlang(self, open_tag, inner, close_tag, cc, tag):
        src_re = rf'\{{mlang {re.escape(self.source_lang)}\}}(.*?)\{{mlang\}}'
        src_m  = re.search(src_re, inner, re.DOTALL)
        if not src_m:
            return f'{open_tag}{inner}{close_tag}'
        src_content = src_m.group(1).strip()
        if not src_content:
            return f'{open_tag}{inner}{close_tag}'

        print(f'      [mlang] from {{{self.source_lang}}} ({len(src_content)} chars)')
        translations = {
            lang: (src_content if lang == self.source_lang
                   else self.translate_text(src_content, lang))
            for lang in self.target_langs
        }
        new_inner = self.wrap_mlang(translations)
        if tag == 'name' and len(new_inner) > 255:
            return f'{open_tag}{inner}{close_tag}'
            
        if new_inner == inner.strip():
            return f'{open_tag}{inner}{close_tag}'
        cc[0] += 1
        return f'{open_tag}{new_inner}{close_tag}'

    # ── Strategy C ── plain text ──────────────────────────────────────────────
    def _strat_plain(self, open_tag, text, close_tag, cc, tag, original_inner):
        print(f'      [plain] {text[:60]!r}')
        translations = {}
        for lang in self.target_langs:
            if lang == self.source_lang:
                translated = text
            else:
                translated = self.translate_text(_html.unescape(text), lang)
                translated = _html.escape(translated)
            translations[lang] = translated

        new_inner = self.wrap_mlang(translations)
        if tag == 'name' and len(new_inner) > 255:
            return f'{open_tag}{original_inner}{close_tag}'
            
        cc[0] += 1
        return f'{open_tag}{new_inner}{close_tag}'

    # ──────────────────────────────────────────────────────── archive processing

    @staticmethod
    def _should_process(member_name: str) -> bool:
        """True for XML files not in SKIP_FILES."""
        basename = member_name.rstrip('/').split('/')[-1].lstrip('.')
        return member_name.endswith('.xml') and basename not in SKIP_FILES

    def process_xml_bytes(self, content_bytes: bytes, name: str) -> bytes:
        """
        Translate XML content given as bytes.
        Returns new bytes (may be same object if no changes made).
        """
        try:
            content = content_bytes.decode('utf-8', errors='replace')
        except Exception:
            return content_bytes

        total_changes = 0
        for tag in CONTENT_TAGS:
            content, n = self._replace_in_tag(content, tag)
            if n:
                print(f'    <{tag}>: {n} replacement(s)')
                total_changes += n

        if total_changes:
            print(f'  [✓] {name} ({total_changes} change(s))')
            return content.encode('utf-8')
        return content_bytes

    def process_mbz(self, input_mbz: str, output_mbz: str):
        """
        Stream through the archive, modifying XML byte content in-place.

        Why streaming instead of extract→process→repack?
        ─────────────────────────────────────────────────
        The extract→repack cycle modifies TarInfo metadata (uid, gid, mtime,
        file modes, name format "./file" vs "file") even when using copy.copy().
        Any of these differences can shift Moodle's restore step counter and
        produce "progress() value out of range".

        Streaming uses the ORIGINAL TarInfo objects for every unchanged member
        and only replaces .size for members whose byte content changed.
        """
        if input_mbz.lower().endswith('.zip'):
            self._process_zip(input_mbz, output_mbz)
        else:
            self._process_tar(input_mbz, output_mbz)

    def _process_tar(self, input_mbz: str, output_mbz: str):
        processed = 0
        print(f'[*] Streaming tar: {input_mbz}')

        with tarfile.open(input_mbz, 'r:gz') as tar_in:
            with tarfile.open(output_mbz, 'w:gz', format=tar_in.format) as tar_out:
                for member in tar_in:
                    if self.cancel_callback:
                        self.cancel_callback()
                    if not member.isfile():
                        # Directories, symlinks, etc. — copy header verbatim
                        tar_out.addfile(member)
                        continue

                    fh = tar_in.extractfile(member)
                    if fh is None:
                        tar_out.addfile(member)
                        continue

                    original_bytes = fh.read()

                    if self._should_process(member.name):
                        print(f'  → {member.name}')
                        new_bytes = self.process_xml_bytes(original_bytes, member.name)
                    else:
                        new_bytes = original_bytes

                    if new_bytes is not original_bytes:
                        # Content changed: update TarInfo size, keep everything else
                        new_info = copy.copy(member)
                        new_info.size = len(new_bytes)
                        
                        # Fix PHP Moodle tar extractor issues by ensuring GNU/USTAR compatibility.
                        # tarfile in Python 3.8+ may auto-generate PAX extended headers during write
                        # if the file is slightly modified, which crashes Moodle's Archive_Tar parser.
                        tar_out.addfile(new_info, io.BytesIO(new_bytes))
                        processed += 1
                    else:
                        tar_out.addfile(member, io.BytesIO(original_bytes))

        print(f'[+] Done! Modified {processed} file(s).')

    def _process_zip(self, input_mbz: str, output_mbz: str):
        processed = 0
        print(f'[*] Processing zip: {input_mbz}')

        with zipfile.ZipFile(input_mbz, 'r') as zip_in, \
             zipfile.ZipFile(output_mbz, 'w', zipfile.ZIP_DEFLATED) as zip_out:

            for info in zip_in.infolist():
                if self.cancel_callback:
                    self.cancel_callback()
                data = zip_in.read(info.filename)
                if self._should_process(info.filename):
                    new_data = self.process_xml_bytes(data, info.filename)
                    if new_data is not data:
                        processed += 1
                        data = new_data
                zip_out.writestr(info, data)

        print(f'[+] Done! Modified {processed} file(s).')

# Removed flashcard extraction logic.


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python moodle_processor.py <input.mbz> [output.mbz]')
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else 'translated_course.mbz'
        MoodleMBZProcessor().process_mbz(sys.argv[1], out)
