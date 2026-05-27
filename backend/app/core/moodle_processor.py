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
    'course_completion.xml', 'module.xml', 'users.xml', 'files.xml',
}

CONTENT_TAGS = ['name', 'intro', 'summary', 'content', 'description', 'text']
CHUNK_CHARS  = 8000   # max chars per single OpenAI call


class MoodleMBZProcessor:
    def __init__(self, source_lang='en', target_langs=None,
                 api_type='none', api_key=None, cancel_callback=None, progress_callback=None):
        self.source_lang  = source_lang
        self.target_langs = target_langs or ['en', 'pl']
        self.api_type     = api_type
        self.api_key      = api_key
        self.cancel_callback = cancel_callback
        self.progress_callback = progress_callback

    # ─────────────────────────────────────────────────────────────── translation

    def _mask_html_tags(self, text: str) -> tuple[str, list[str]]:
        tags = []
        def replace_tag(match):
            tags.append(match.group(0))
            return f"[[T{len(tags)-1}]]"
        
        # 1. Mask valid HTML/XML-like tags safely (safely ignoring > inside quotes)
        # 2. Mask Moodle placeholders like @@PLUGINFILE@@, @@CONTEXTID@@, etc.
        pattern = r"</?[a-zA-Z!?[][^'\">]*(?:'(?:[^']|\\')*'[^'\">]*|\"(?:[^\"]|\\\")*\"[^'\">]*)*>|@@[A-Z0-9_]+@@"
        masked_text = re.sub(pattern, replace_tag, text)
        return masked_text, tags

    def _unmask_html_tags(self, masked_text: str, tags: list[str]) -> str:
        def restore_tag(match):
            idx = int(match.group(1))
            if 0 <= idx < len(tags):
                return tags[idx]
            return match.group(0)
        
        return re.sub(r"\[\[T(\d+)\]\]", restore_tag, masked_text)

    def translate_text(self, html_or_text: str, target_lang: str) -> str:
        if target_lang == self.source_lang or not html_or_text.strip():
            return html_or_text

        if len(html_or_text) > CHUNK_CHARS:
            parts = re.split(r'(?<=</p>)', html_or_text)
            translated, chunk = [], ''
            for part in parts:
                if len(chunk) + len(part) > CHUNK_CHARS and chunk:
                    translated.append(self._translate_chunk(chunk, target_lang))
                    chunk = part
                else:
                    chunk += part
            if chunk:
                translated.append(self._translate_chunk(chunk, target_lang))
            return ''.join(translated)
        else:
            return self._translate_chunk(html_or_text, target_lang)

    def _translate_chunk(self, content: str, target_lang: str) -> str:
        if getattr(self, '_extract_mode_set', None) is not None:
            self._extract_mode_set.add((content, target_lang))
            return content
            
        cache_key = (content, target_lang)
        if hasattr(self, '_translation_cache') and cache_key in self._translation_cache:
            return self._translation_cache[cache_key]

        if self.api_type == 'deepl' and self.api_key:
            return self._deepl_translate(content, target_lang)

        # Mask HTML tags for LLMs
        masked, tags = self._mask_html_tags(content)

        if self.api_type == 'openai' and self.api_key:
            res = self._openai_call(masked, target_lang)
        elif self.api_type == 'gemini' and self.api_key:
            res = self._gemini_call(masked, target_lang)
        elif self.api_type == 'openrouter' and self.api_key:
            res = self._openrouter_call(masked, target_lang)
        else:
            res = f'[{target_lang}] {masked}'

        unmasked = self._unmask_html_tags(res, tags)
        return unmasked

    def _batch_translate(self, extract_set: set):
        by_lang = {}
        for text, lang in extract_set:
            if lang not in by_lang: by_lang[lang] = []
            if (text, lang) not in self._translation_cache: by_lang[lang].append(text)
                
        # Estimate total batches
        total_batches = 0
        for texts in by_lang.values():
            batch_count = 0
            chars = 0
            for text in texts:
                if len(text) > 4000:
                    total_batches += 1
                else:
                    batch_count += 1
                    chars += len(text)
                    if batch_count >= 20 or chars > 4000:
                        total_batches += 1
                        batch_count = 0
                        chars = 0
            if batch_count:
                total_batches += 1

        processed_batches = 0
        for lang, texts in by_lang.items():
            if not texts: continue
            batch, batch_chars = [], 0
            for text in texts:
                if len(text) > 4000:
                    self._translate_batch_to_cache([text], lang)
                    processed_batches += 1
                    if self.progress_callback and total_batches > 0:
                        p = 10 + int(80 * processed_batches / total_batches)
                        self.progress_callback(p, f"Tłumaczenie ({processed_batches}/{total_batches} partii)...")
                    continue
                batch.append(text)
                batch_chars += len(text)
                if len(batch) >= 20 or batch_chars > 4000:
                    self._translate_batch_to_cache(batch, lang)
                    processed_batches += 1
                    if self.progress_callback and total_batches > 0:
                        p = 10 + int(80 * processed_batches / total_batches)
                        self.progress_callback(p, f"Tłumaczenie ({processed_batches}/{total_batches} partii)...")
                    batch, batch_chars = [], 0
            if batch:
                self._translate_batch_to_cache(batch, lang)
                processed_batches += 1
                if self.progress_callback and total_batches > 0:
                    p = 10 + int(80 * processed_batches / total_batches)
                    self.progress_callback(p, f"Tłumaczenie ({processed_batches}/{total_batches} partii)...")

    def _translate_batch_to_cache(self, texts: list[str], target_lang: str):
        # Mask texts
        masked_texts = []
        texts_tags = []
        for t in texts:
            m, tags = self._mask_html_tags(t)
            masked_texts.append(m)
            texts_tags.append(tags)

        if self.api_type == 'openrouter' and self.api_key:
            results = self._openrouter_batch_call(masked_texts, target_lang)
        elif self.api_type == 'openai' and self.api_key:
            results = self._openai_batch_call(masked_texts, target_lang)
        elif self.api_type == 'gemini' and self.api_key:
            results = self._gemini_batch_call(masked_texts, target_lang)
        else:
            results = []
            
        if len(results) != len(texts):
            # Fallback to single calls
            for t, tags in zip(texts, texts_tags):
                m = self._mask_html_tags(t)[0]
                if self.api_type == 'openrouter':
                    res = self._openrouter_call(m, target_lang)
                elif self.api_type == 'openai':
                    res = self._openai_call(m, target_lang)
                elif self.api_type == 'gemini':
                    res = self._gemini_call(m, target_lang)
                elif self.api_type == 'deepl':
                    res = self._deepl_translate(t, target_lang)
                else:
                    res = f'[{target_lang}] {m}'
                
                unmasked = self._unmask_html_tags(res, tags)
                self._translation_cache[(t, target_lang)] = unmasked
        else:
            for text, result, tags in zip(texts, results, texts_tags):
                unmasked = self._unmask_html_tags(result, tags)
                self._translation_cache[(text, target_lang)] = unmasked

    def _openai_batch_call(self, texts: list[str], target_lang: str) -> list[str]:
        import json
        try: from openai import OpenAI
        except ImportError: return []
        client = OpenAI(api_key=self.api_key)
        system_prompt = (f"You are a professional translator. Translate the given JSON array of strings from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are in the translation and in the same positions. Return ONLY a valid JSON array of strings in the exact same order. Do not wrap in markdown.")
        try:
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': json.dumps(texts, ensure_ascii=False)}],
                temperature=0.1
            )
            res = resp.choices[0].message.content.strip()
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            arr = json.loads(res.strip())
            if isinstance(arr, list) and len(arr) == len(texts): return arr
        except Exception: pass
        return []

    def _gemini_batch_call(self, texts: list[str], target_lang: str) -> list[str]:
        import json
        try: from google import genai
        except ImportError: return []
        client = genai.Client(api_key=self.api_key)
        prompt = (f"You are a professional translator. Translate the following JSON array of strings from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are and in the same positions. Return ONLY a valid JSON array of strings in exact order. Do not wrap in markdown.\n\n{json.dumps(texts, ensure_ascii=False)}")
        try:
            resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            res = resp.text.strip()
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            arr = json.loads(res.strip())
            if isinstance(arr, list) and len(arr) == len(texts): return arr
        except Exception: pass
        return []

    def _openrouter_batch_call(self, texts: list[str], target_lang: str) -> list[str]:
        import json, time
        try: from openai import OpenAI
        except ImportError: return []
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
        system_prompt = (f"You are a professional translator. Translate the given JSON array of strings from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are in the translation and in the same positions. Return ONLY a valid JSON array of strings in the exact same order. Do not wrap in markdown.")
        user_content = json.dumps(texts, ensure_ascii=False)
        free_models = [
            "openai/gpt-oss-120b:free",
            "minimax/minimax-m2.5:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free"
        ]
        
        for model in free_models:
            for attempt in range(2):
                try:
                    if hasattr(self, '_last_or_call'):
                        elapsed = time.time() - self._last_or_call
                        if elapsed < 3.1: time.sleep(3.1 - elapsed)
                    self._last_or_call = time.time()
                    
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_content}],
                        extra_headers={"HTTP-Referer": "https://moodle.agent.local", "X-Title": "Moodle Translator Agent"},
                        temperature=0.1
                    )
                    res = resp.choices[0].message.content.strip()
                    if res.startswith("```json"): res = res[7:]
                    if res.startswith("```"): res = res[3:]
                    if res.endswith("```"): res = res[:-3]
                    arr = json.loads(res.strip())
                    if isinstance(arr, list) and len(arr) == len(texts):
                        print(f'  [✓] OpenRouter BATCH OK ({model}), items: {len(texts)}')
                        return arr
                except Exception as e:
                    err_msg = str(e).lower()
                    print(f'  [!] OpenRouter batch err ({model}): {str(e)[:150]}')
                    if any(kw in err_msg for kw in ['404', '401', 'no endpoints found']): break
                    if any(kw in err_msg for kw in ['429', 'rate limit', '502', '503']): time.sleep(4 * (attempt + 1))
        return []

    def _openai_call(self, content: str, target_lang: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': f'Translate from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are and in the same positions. Return ONLY translated content.'},
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
            result = translator.translate_text(content, target_lang=target_lang.upper(), tag_handling='html')
            return result.text
        except Exception as e:
            print(f'  [!] DeepL error: {e}')
            return content

    def _gemini_call(self, content: str, target_lang: str) -> str:
        import time
        try: from google import genai
        except ImportError: return content
        client = genai.Client(api_key=self.api_key)
        prompt = f'Translate from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are and in the same positions. Return ONLY translated content:\n\n{content}'
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                return resp.text.strip()
            except Exception as e:
                if not any(kw in str(e).lower() for kw in ['429', 'quota', 'rate limit']): return content
                time.sleep(5 * (2 ** attempt))
        return content

    def _openrouter_call(self, content: str, target_lang: str) -> str:
        import time
        try: from openai import OpenAI
        except ImportError: return content

        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
        free_models = [
            "openai/gpt-oss-120b:free",
            "minimax/minimax-m2.5:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free"
        ]

        for model in free_models:
            for attempt in range(2):
                try:
                    if hasattr(self, '_last_or_call'):
                        elapsed = time.time() - self._last_or_call
                        if elapsed < 3.1: time.sleep(3.1 - elapsed)
                    self._last_or_call = time.time()
                    
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {'role': 'system', 'content': f'Translate from {self.source_lang} to {target_lang}. You will see placeholders like [[T0]], [[T1]], etc. Keep them EXACTLY as they are and in the same positions. Return ONLY translated content.'},
                            {'role': 'user', 'content': content},
                        ],
                        extra_headers={"HTTP-Referer": "https://moodle.agent.local", "X-Title": "Moodle Translator Agent"}
                    )
                    if resp.choices[0].message.content:
                        print(f'  [✓] OpenRouter OK ({model})')
                        return resp.choices[0].message.content.strip()
                except Exception as e:
                    err_msg = str(e).lower()
                    print(f'  [!] OpenRouter err ({model}): {str(e)[:150]}')
                    if any(kw in err_msg for kw in ['404', '401', 'no endpoints found']): break
                    if not any(kw in err_msg for kw in ['429', 'rate limit', '502', '503']): break
                    time.sleep(4 * (attempt + 1))
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

    def _is_inside_config_block(self, file_content: str, start_idx: int) -> bool:
        # Search backwards from start_idx up to 1000 characters
        search_start = max(0, start_idx - 1000)
        prefix = file_content[search_start:start_idx]
        
        # Check if the last opened tag among blacklisted config parents is not closed
        for tag in [
            'plugin_config', 'courseformatoption', 'question_category', 
            'setting', 'detail'
        ]:
            opens = list(re.finditer(rf'<{tag}(?:\s+[^>]*)?>', prefix))
            closes = list(re.finditer(rf'</{tag}>', prefix))
            
            if opens:
                last_open = opens[-1].start()
                last_close = closes[-1].start() if closes else -1
                if last_open > last_close:
                    return True
        return False

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
        outer_re = rf'(<{tag}(?:\s+[^>]*)?>)(.*?)(</{tag}>)'

        def handle(m):
            open_tag  = m.group(1)
            inner     = m.group(2)
            close_tag = m.group(3)

            # --- Safety checks to prevent DMLWriteException ---
            if '$@NULL@$' in inner or not inner.strip():
                return m.group(0)

            if self._is_inside_config_block(file_content, m.start()):
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
                    if tag == 'name' and len(new_inner) > 180:
                        return f'{open_tag}{original_inner}{close_tag}'
                    if new_inner != stripped:
                        cc[0] += 1
                    return f'{open_tag}<![CDATA[{new_inner}]]>{close_tag}'
            # Can't find source block → leave untouched (keep CDATA wrapper)
            return f'{open_tag}<![CDATA[{stripped}]]>{close_tag}'

        # Fresh CDATA with no mlang yet
        if getattr(self, '_extract_mode_set', None) is None:
            print(f'      [CDATA] {len(stripped)} chars')
        translations = {
            lang: (stripped if lang == self.source_lang
                   else self.translate_text(stripped, lang))
            for lang in self.target_langs
        }
        new_inner = self.wrap_mlang(translations)
        if tag == 'name' and len(new_inner) > 180:
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

        if getattr(self, '_extract_mode_set', None) is None:
            print(f'      [mlang] from {{{self.source_lang}}} ({len(src_content)} chars)')
        translations = {}
        for lang in self.target_langs:
            if lang == self.source_lang:
                translations[lang] = src_content
            else:
                unescaped = _html.unescape(src_content)
                translated = self.translate_text(unescaped, lang)
                translations[lang] = _html.escape(translated)
                
        new_inner = self.wrap_mlang(translations)
        if tag == 'name' and len(new_inner) > 180:
            return f'{open_tag}{inner}{close_tag}'
            
        if new_inner == inner.strip():
            return f'{open_tag}{inner}{close_tag}'
        cc[0] += 1
        return f'{open_tag}{new_inner}{close_tag}'

    # ── Strategy C ── plain text ──────────────────────────────────────────────
    def _strat_plain(self, open_tag, text, close_tag, cc, tag, original_inner):
        if getattr(self, '_extract_mode_set', None) is None:
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
        if tag == 'name' and len(new_inner) > 180:
            return f'{open_tag}{original_inner}{close_tag}'
            
        cc[0] += 1
        return f'{open_tag}{new_inner}{close_tag}'

    # ──────────────────────────────────────────────────────── archive processing

    @staticmethod
    def _should_process(member_name: str) -> bool:
        """True for XML files not in SKIP_FILES."""
        basename = member_name.rstrip('/').split('/')[-1].lstrip('.')
        return member_name.endswith('.xml') and basename not in SKIP_FILES

    def _scan_and_extract_all(self, input_mbz: str) -> set:
        """Scan through the archive and extract all translatable texts from XML files."""
        extracted_texts = set()
        self._extract_mode_set = extracted_texts

        if input_mbz.lower().endswith('.zip'):
            with zipfile.ZipFile(input_mbz, 'r') as zip_in:
                for info in zip_in.infolist():
                    if self._should_process(info.filename):
                        try:
                            data = zip_in.read(info.filename)
                            content = data.decode('utf-8', errors='replace')
                            for tag in CONTENT_TAGS:
                                self._replace_in_tag(content, tag)
                        except Exception:
                            pass
        else:
            with tarfile.open(input_mbz, 'r:gz') as tar_in:
                for member in tar_in:
                    if member.isfile() and self._should_process(member.name):
                        try:
                            fh = tar_in.extractfile(member)
                            if fh:
                                data = fh.read()
                                content = data.decode('utf-8', errors='replace')
                                for tag in CONTENT_TAGS:
                                    self._replace_in_tag(content, tag)
                        except Exception:
                            pass

        self._extract_mode_set = None
        return extracted_texts

    def process_xml_bytes(self, content_bytes: bytes, name: str) -> bytes:
        """
        Translate XML content given as bytes.
        Returns new bytes (may be same object if no changes made).
        """
        try:
            content = content_bytes.decode('utf-8', errors='replace')
        except Exception:
            return content_bytes

        # Cache is pre-populated globally, so we go straight to the replacement phase
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

    def process_mbz(self, input_mbz: str, output_mbz: str, task_id: str = None):
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
        if self.progress_callback:
            self.progress_callback(5, "Rozpoczynam skanowanie plików kursu...")

        # 1. Global Extraction Phase
        print("[*] Phase 1: Scanning and extracting all translatable texts...")
        global_extract_set = self._scan_and_extract_all(input_mbz)
        
        if self.progress_callback:
            self.progress_callback(10, f"Znaleziono {len(global_extract_set)} elementów. Rozpoczynam tłumaczenie...")

        # 2. Bulk Translation Phase
        if not hasattr(self, '_translation_cache'):
            self._translation_cache = {}
        if global_extract_set:
            print(f"[*] Found {len(global_extract_set)} unique text-language combinations to translate.")
            self._batch_translate(global_extract_set)
        
        if self.progress_callback:
            self.progress_callback(90, "Zapisywanie przetłumaczonego kursu (pakowanie)...")
        
        # Save exported texts JSON if task_id is provided
        if task_id:
            export_data = []
            unique_originals = sorted(list(set(text for text, lang in global_extract_set)))
            for text in unique_originals:
                translations = {}
                for lang in self.target_langs:
                    if lang == self.source_lang:
                        translations[lang] = text
                    else:
                        translations[lang] = self._translation_cache.get((text, lang), f"[{lang}] {text}")
                export_data.append({
                    "original": text,
                    "translations": translations
                })
            
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            export_path = temp_dir / f"texts_{task_id}.json"
            try:
                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                print(f"[✓] Saved extracted texts to {export_path}")
            except Exception as e:
                print(f"[!] Failed to save texts JSON: {e}")

        # 3. Streaming / Replacement Phase
        if input_mbz.lower().endswith('.zip'):
            self._process_zip(input_mbz, output_mbz)
        else:
            self._process_tar(input_mbz, output_mbz)
            
        if self.progress_callback:
            self.progress_callback(100, "Zakończono przetwarzanie.")

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
