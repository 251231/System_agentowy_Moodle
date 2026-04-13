from pathlib import Path
import lxml.etree as ET
from agents.base_agent import BaseAgent


class TranslationAgent(BaseAgent):
    """
    Skanuje pliki XML z rozpakowanego MBZ i obudowuje tekst
    w tagi {mlang XX}...{mlang} Moodle'a – dla każdego języka docelowego.
    Tłumaczenie delegowane do OpenAI (GPT-4o), DeepL lub mock (prefix).
    """

    CONTENT_TAGS = {"name", "intro", "summary", "content", "description", "text"}

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_lang  = config.get("source_lang", "en")
        self.target_langs = config.get("target_langs", ["en", "pl"])
        self.api_type     = config.get("api_type", "none")
        self.api_key      = config.get("api_key", "")

    # ── tłumaczenie ────────────────────────────────────────────────────────
    def _translate(self, text: str, lang: str) -> str:
        if lang == self.source_lang:
            return text
        if self.api_type == "openai" and self.api_key:
            return self._openai(text, lang)
        if self.api_type == "deepl" and self.api_key:
            return self._deepl(text, lang)
        return f"[{lang.upper()}] {text}"          # mock fallback

    def _openai(self, text: str, lang: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": (
                        f"You are a professional translator. Translate the Moodle course content "
                        f"from {self.source_lang} to {lang}. "
                        "Keep any HTML tags intact. Return ONLY the translated text."
                    )},
                    {"role": "user", "content": text},
                ]
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[TranslationAgent] OpenAI error: {e}")
            return text

    def _deepl(self, text: str, lang: str) -> str:
        try:
            import deepl
            t = deepl.Translator(self.api_key)
            return t.translate_text(text, target_lang=lang.upper()).text
        except Exception as e:
            print(f"[TranslationAgent] DeepL error: {e}")
            return text

    def _mlang(self, translations: dict) -> str:
        return "".join(f"{{mlang {l}}}{t}{{mlang}}" for l, t in translations.items() if t)

    # ── przetwarzanie XML ───────────────────────────────────────────────────
    def _process_xml(self, path: Path) -> bool:
        try:
            # Odczyt oryginalnych bajtów - wykryjemy kodowanie i format
            raw = path.read_bytes()
            
            parser = ET.XMLParser(strip_cdata=False, recover=True)
            tree   = ET.parse(str(path), parser)
            root   = tree.getroot()
            changed = False
            for tag in self.CONTENT_TAGS:
                for elem in root.iter(tag):
                    if elem.text and elem.text.strip() and "{mlang" not in elem.text:
                        orig = elem.text
                        translations = {l: self._translate(orig, l) for l in self.target_langs}
                        elem.text = self._mlang(translations)
                        changed = True

            if changed:
                # Zapisujemy z ustawieniami zgodnymi z Moodle:
                # - short_empty_elements=False: zachowuje <tag></tag> zamiast <tag/>
                # - xml_declaration=False: nie doklejamy deklaracji jeśli jej nie było
                had_declaration = raw.strip().startswith(b"<?xml")
                tree.write(
                    str(path),
                    encoding="UTF-8",
                    xml_declaration=had_declaration,
                    method="xml",
                    short_empty_elements=False,
                )
            return changed
        except Exception as e:
            print(f"[TranslationAgent] XML error {path.name}: {e}")
            return False

    # ── entry-point ─────────────────────────────────────────────────────────
    def process(self, workspace_path: str) -> tuple[bool, str]:
        count = 0
        for xml_file in Path(workspace_path).rglob("*.xml"):
            if self._process_xml(xml_file):
                count += 1
        return True, f"Przetłumaczono {count} plików XML."
