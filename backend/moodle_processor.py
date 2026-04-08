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
                 api_type='none', api_key=None):
        self.source_lang  = source_lang
        self.target_langs = target_langs or ['en', 'pl']
        self.api_type     = api_type
        self.api_key      = api_key

    # ─────────────────────────────────────────────────────────────── translation

    def translate_text(self, html_or_text: str, target_lang: str) -> str:
        if target_lang == self.source_lang or not html_or_text.strip():
            return html_or_text
        if self.api_type == 'openai' and self.api_key:
            return self._openai_translate(html_or_text, target_lang)
        if self.api_type == 'deepl' and self.api_key:
            return self._deepl_translate(html_or_text, target_lang)
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

    def wrap_mlang(self, translations: dict) -> str:
        return ''.join(
            f'{{mlang {lang}}}{txt}{{mlang}}'
            for lang, txt in translations.items() if txt is not None
        )

    # ──────────────────────────────────────────────────── XML content processing

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

            # ── STRATEGY A: CDATA (MUST be checked before {mlang} test) ───────
            # If inner has CDATA, process it (even if the CDATA itself contains
            # {mlang} blocks).  Stripping CDATA would make HTML inside mlang
            # invalid XML, breaking Moodle's restore parser.
            cdata_m = re.match(r'^\s*<!\[CDATA\[(.*)\]\]>\s*$', inner, re.DOTALL)
            if cdata_m:
                return self._strat_cdata(
                    open_tag, cdata_m.group(1), close_tag, change_count)

            # ── STRATEGY B: raw {mlang} blocks ────────────────────────────────
            if '{mlang' in inner:
                return self._strat_mlang(
                    open_tag, inner, close_tag, change_count)

            # ── STRATEGY C: plain text (no angle brackets inside) ─────────────
            stripped = inner.strip()
            if stripped and '<' not in stripped:
                return self._strat_plain(
                    open_tag, stripped, close_tag, change_count)

            return m.group(0)   # raw HTML without wrapper → leave untouched

        new_content = re.sub(outer_re, handle, file_content, flags=re.DOTALL)
        return new_content, change_count[0]

    # ── Strategy A ── CDATA (preserve wrapper) ────────────────────────────────
    def _strat_cdata(self, open_tag, cdata_inner, close_tag, cc):
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
        cc[0] += 1
        return f'{open_tag}<![CDATA[{self.wrap_mlang(translations)}]]>{close_tag}'

    # ── Strategy B ── raw {mlang} blocks ─────────────────────────────────────
    def _strat_mlang(self, open_tag, inner, close_tag, cc):
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
        if new_inner == inner.strip():
            return f'{open_tag}{inner}{close_tag}'
        cc[0] += 1
        return f'{open_tag}{new_inner}{close_tag}'

    # ── Strategy C ── plain text ──────────────────────────────────────────────
    def _strat_plain(self, open_tag, text, close_tag, cc):
        print(f'      [plain] {text[:60]!r}')
        translations = {
            lang: (text if lang == self.source_lang
                   else self.translate_text(text, lang))
            for lang in self.target_langs
        }
        cc[0] += 1
        return f'{open_tag}{self.wrap_mlang(translations)}{close_tag}'

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

        with tarfile.open(input_mbz, 'r:gz') as tar_in, \
             tarfile.open(output_mbz, 'w:gz') as tar_out:

            for member in tar_in:
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
                data = zip_in.read(info.filename)
                if self._should_process(info.filename):
                    new_data = self.process_xml_bytes(data, info.filename)
                    if new_data is not data:
                        processed += 1
                        data = new_data
                zip_out.writestr(info, data)

        print(f'[+] Done! Modified {processed} file(s).')

    # ──────────────────────────────────────────────────── flashcard extraction

    def _strip_html(self, text: str) -> str:
        """Remove markup; decode HTML entities; normalize whitespace."""
        if not text:
            return ''
        # Remove {mlang} markers
        text = re.sub(r'\{mlang[^}]*\}', '', text)
        # Unwrap CDATA
        text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode HTML entities (&nbsp; → \xa0, &amp; → &, etc.)
        text = _html.unescape(text)
        # Normalize ALL whitespace (including non-breaking space U+00A0)
        text = re.sub(r'[\s\u00a0]+', ' ', text).strip()
        return text

    def _is_educational(self, text: str) -> bool:
        if not text or len(text) < 30:
            return False
        if re.match(r'^[aAwWbBiIdDsS]:\d+:\{', text):  # PHP serialized
            return False
        if '$@' in text:                                 # Moodle placeholders
            return False
        if re.match(r'^https?://', text):               # URLs
            return False
        if re.match(r'^[\d\s,.;:/-]+$', text):          # Pure numbers
            return False
        if not re.search(r'[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}', text):
            return False
        if len(text) < 50 and ' ' not in text:          # Code-like strings
            return False
        return True

    def _collect_course_text(self, tmp_path: Path) -> list:
        sections = []
        for xml_file in sorted(tmp_path.rglob('*.xml')):
            if xml_file.name in SKIP_FILES:
                continue
            if xml_file.name in ('grades.xml', 'attempts.xml', 'submissions.xml'):
                continue
            try:
                parser = ET.XMLParser(strip_cdata=False, recover=True)
                root   = ET.parse(str(xml_file), parser).getroot()

                title = ''
                for tag in ('name', 'fullname'):
                    el = root.find(f'.//{tag}')
                    if el is not None and el.text:
                        title = self._strip_html(el.text.strip())
                        if title:
                            break

                parts = []
                for tag in ('intro', 'summary', 'content', 'description'):
                    for el in root.iter(tag):
                        txt_el = el.find('text')
                        raw  = (txt_el.text if txt_el is not None else el.text) or ''
                        clean = self._strip_html(raw)
                        if self._is_educational(clean):
                            parts.append(clean[:1200])

                for el in root.iter('text'):
                    clean = self._strip_html(el.text or '')
                    if self._is_educational(clean):
                        parts.append(clean[:800])

                seen, unique = set(), []
                for p in parts:
                    k = p[:80]
                    if k not in seen:
                        seen.add(k); unique.append(p)

                if title or unique:
                    sections.append({'title': title or xml_file.stem,
                                     'content': ' '.join(unique[:4])})
            except Exception:
                pass
        return sections

    def _ai_generate_flashcards(self, sections: list) -> list:
        if not (self.api_type == 'openai' and self.api_key):
            return []
        blocks = []
        for s in sections[:60]:
            block = f"### {s['title']}"
            if s['content']:
                block += f"\n{s['content'][:900]}"
            blocks.append(block)
        course_text = '\n\n'.join(blocks)
        if len(course_text) > 15000:
            course_text = course_text[:15000] + '\n[...skrócono...]'
        try:
            import json
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model='gpt-4o',
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': (
                        'Jesteś ekspertem od tworzenia materiałów edukacyjnych.\n'
                        'Na podstawie treści kursu Moodle utwórz zestaw fiszek.\n\n'
                        'ZASADY:\n'
                        '• Tylko treść merytoryczna: pojęcia, definicje, procesy, fakty.\n'
                        '• IGNORUJ metadane, ścieżki, kod PHP, puste pola.\n'
                        '• Przód: konkretne pytanie lub pojęcie.\n'
                        '• Tył: jasna odpowiedź (2-4 zdania).\n'
                        '• Źródło: "definicja", "zasada", "proces" lub "przykład".\n'
                        '• 20-35 fiszek; język = język kursu.\n\n'
                        'JSON: {"flashcards":[{"front":"...","back":"...","source":"..."}]}'
                    )},
                    {'role': 'user', 'content': f'Treść kursu:\n\n{course_text}'},
                ],
                max_tokens=4096,
            )
            result = json.loads(resp.choices[0].message.content)
            return [c for c in result.get('flashcards', [])
                    if c.get('front') and c.get('back')]
        except Exception as e:
            print(f'  [!] AI error: {e}')
            return []

    def _basic_extract_flashcards(self, sections: list) -> list:
        cards, seen = [], set()
        for s in sections:
            title   = s['title'].strip()
            content = s['content'].strip()
            if not title or not self._is_educational(content):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            back = content if len(content) <= 400 else content[:397] + '…'
            cards.append({'front': title, 'back': back, 'source': 'extract'})
            if len(cards) >= 60:
                break
        return cards

    def extract_flashcards(self, input_mbz: str) -> list:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            if input_mbz.lower().endswith('.zip'):
                with zipfile.ZipFile(input_mbz, 'r') as z:
                    z.extractall(tmp_path)
            else:
                with tarfile.open(input_mbz, 'r:gz') as t:
                    t.extractall(tmp_path)

            sections = self._collect_course_text(tmp_path)
            useful   = [s for s in sections if self._is_educational(s.get('content', ''))]
            print(f'[*] {len(useful)}/{len(sections)} sections have educational content.')

            if self.api_type == 'openai' and self.api_key:
                print('[*] Calling GPT-4o...')
                cards = self._ai_generate_flashcards(useful)
                if cards:
                    print(f'[+] AI: {len(cards)} flashcards.')
                    return cards
                print('[!] AI returned empty – falling back.')

            cards = self._basic_extract_flashcards(useful)
            print(f'[+] Basic: {len(cards)} flashcards.')
            return cards


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python moodle_processor.py <input.mbz> [output.mbz]')
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else 'translated_course.mbz'
        MoodleMBZProcessor().process_mbz(sys.argv[1], out)
