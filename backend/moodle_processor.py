import os
import tarfile
import zipfile
import shutil
import lxml.etree as ET
from pathlib import Path
import tempfile

class MoodleMBZProcessor:
    def __init__(self, source_lang='en', target_langs=['en', 'pl'], api_type='none', api_key=None):
        self.source_lang = source_lang
        self.target_langs = target_langs
        self.api_type = api_type
        self.api_key = api_key
        # Tags that usually contain user-visible content in Moodle XMLs
        self.content_tags = ['name', 'intro', 'summary', 'content', 'description', 'text']

    def translate_text(self, text, target_lang):
        """Dispatches translation to the selected service or mock."""
        if target_lang == self.source_lang:
            return text
            
        if self.api_type == 'openai' and self.api_key:
            return self._openai_translate(text, target_lang)
        elif self.api_type == 'deepl' and self.api_key:
            return self._deepl_translate(text, target_lang)
        
        return f"[{target_lang}] {text}" # Mock fallback

    def _openai_translate(self, text, target_lang):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"You are a professional translator. Translate the following Moodle course content from {self.source_lang} to {target_lang}. Keep HTML tags intact. Return ONLY the translated text."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return text

    def _deepl_translate(self, text, target_lang):
        try:
            import deepl
            translator = deepl.Translator(self.api_key)
            result = translator.translate_text(text, target_lang=target_lang.upper())
            return result.text
        except Exception as e:
            print(f"DeepL Error: {e}")
            return text

    def wrap_mlang(self, translations):
        """
        Wraps multiple translations into Moodle's mlang format:
        {mlang en}Hello{mlang}{mlang pl}Cześć{mlang}
        """
        result = ""
        for lang, text in translations.items():
            if text:
                result += f"{{mlang {lang}}}{text}{{mlang}}"
        return result

    def process_xml_file(self, file_path):
        """Parses an XML file and updates translatable tags with mlang blocks."""
        try:
            # We use a parser that handles CData and entities gracefully
            parser = ET.XMLParser(strip_cdata=False, recover=True)
            tree = ET.parse(str(file_path), parser)
            root = tree.getroot()

            updated = False
            for tag in self.content_tags:
                for elem in root.iter(tag):
                    # Only translate if there's text and it's not already mlang-wrapped
                    if elem.text and elem.text.strip() and '{mlang' not in elem.text:
                        original = elem.text
                        translations = {}
                        for lang in self.target_langs:
                            translations[lang] = self.translate_text(original, lang)
                        
                        elem.text = self.wrap_mlang(translations)
                        updated = True

            if updated:
                tree.write(str(file_path), encoding='UTF-8', xml_declaration=True, method="xml")
            return updated
        except Exception as e:
            print(f"  [!] Error processing {file_path.name}: {e}")
            return False

    def process_mbz(self, input_mbz, output_mbz):
        """Main workflow: Extract -> Process XMLs -> Repack."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            print(f"[*] Extracting {input_mbz}...")
            if input_mbz.endswith('.zip'):
                with zipfile.ZipFile(input_mbz, 'r') as zip_ref:
                    zip_ref.extractall(tmp_path)
            else:
                # Most MBZ files are .tar.gz
                with tarfile.open(input_mbz, 'r:gz') as tar_ref:
                    tar_ref.extractall(tmp_path)

            print("[*] Scanning and translating XML files...")
            processed_count = 0
            for xml_file in tmp_path.rglob("*.xml"):
                # Skip some system files if necessary, but usually safe to scan all
                if self.process_xml_file(xml_file):
                    processed_count += 1
            
            print(f"[*] Processed {processed_count} XML files.")
            print(f"[*] Packaging new MBZ into {output_mbz}...")
            
            # Repackage as tar.gz (Standard Moodle format)
            with tarfile.open(output_mbz, "w:gz") as tar:
                # Add all files from tmp_path but maintain relative structure
                for file in tmp_path.rglob("*"):
                    tar.add(file, arcname=file.relative_to(tmp_path))

        print("[+] Success!")

if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) < 2:
        print("Usage: python moodle_processor.py <input.mbz> [output.mbz]")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "translated_course.mbz"
        
        processor = MoodleMBZProcessor()
        processor.process_mbz(input_file, output_file)
