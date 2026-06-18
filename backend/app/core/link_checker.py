import io
import re
import ssl
import json
import time
import html
import tarfile
import zipfile
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.db.database import SessionLocal
from app.db.models import SubTask

# Skip files that don't contain course content/activities
SKIP_FILES = {
    'moodle_backup.xml', 'completion.xml', 'gradebook.xml', 'groups.xml',
    'outcomes.xml', 'roles.xml', 'filters.xml', 'comments.xml', 'badges.xml',
    'calendarevents.xml', 'competencies.xml', 'contentbank.xml', 'enrolments.xml',
    'scales.xml', 'tags.xml', 'inforef.xml', 'grade_history.xml',
    'course_completion.xml', 'module.xml', 'users.xml', 'files.xml',
}

URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9.\-_~:/?#[\]@!$&\'()*+,;=]+')

def clean_moodle_multilang(text: str) -> str:
    if not text:
        return ""
    
    # 1. Handle {mlang pl}Polski{mlang}{mlang en}English{mlang} syntax
    mlang_pl_matches = re.findall(r'{mlang\s+pl}(.*?){mlang}', text, re.DOTALL)
    if mlang_pl_matches:
        return " ".join(mlang_pl_matches).strip()
    
    # If {mlang} exists but no {mlang pl}, let's remove other mlang tags to keep default/remaining content
    if "{mlang" in text:
        text = re.sub(r'{mlang\s+[^}]+}.*?{mlang}', '', text, flags=re.DOTALL)
        text = re.sub(r'{mlang.*?}', '', text)
    
    # 2. Handle <span lang="pl" class="multilang">Polski</span> syntax
    span_pl_matches = re.findall(r'<span\s+[^>]*lang=["\']pl["\'][^>]*>(.*?)</span>', text, re.DOTALL)
    if span_pl_matches:
        cleaned = [re.sub(r'<[^>]+>', '', m) for m in span_pl_matches]
        return " ".join(cleaned).strip()
        
    # If no pl span but we have class="multilang", remove non-pl spans
    if 'class="multilang"' in text or "class='multilang'" in text:
        text = re.sub(r'<span\s+[^>]*lang=["\'](?!pl)[a-zA-Z\-]+["\'][^>]*>.*?</span>', '', text, flags=re.DOTALL)
        
    # Clean any remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Clean any remaining mlang markers
    text = re.sub(r'{mlang.*?}', '', text)
    
    # Collapse double spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip() or "Nieznana aktywność"

def get_clean_domain(url: str) -> str:
    if not url:
        return ""
    clean = url.strip()
    if "://" in clean:
        clean = clean.split("://", 1)[1]
    if "/" in clean:
        clean = clean.split("/", 1)[0]
    if clean.startswith("www."):
        clean = clean[4:]
    return clean

def get_clean_search_phrase(url: str) -> str:
    domain = get_clean_domain(url)
    if not domain:
        return ""
    
    parts = domain.split('.')
    if not parts:
        return ""
        
    if len(parts) == 1:
        return parts[0]
        
    discard_suffixes = {
        'com', 'org', 'net', 'edu', 'gov', 'mil', 'int', 'biz', 'info', 'name', 
        'pl', 'en', 'de', 'fr', 'uk', 'us', 'ru', 'ch', 'it', 'nl', 'se', 'no',
        'co', 'ltd', 'me', 'io', 'tv', 'cc', 'eu', 'fm', 'am', 'ad', 'ae', 'af'
    }
    
    cleaned_parts = []
    for p in parts:
        if p.lower() not in discard_suffixes:
            cleaned_parts.append(p)
            
    if not cleaned_parts:
        cleaned_parts = [parts[0]]
        
    phrase = " ".join(cleaned_parts)
    phrase = re.sub(r'[-_]', ' ', phrase)
    phrase = re.sub(r'\s+', ' ', phrase).strip()
    return phrase

def _set_subtask_log(task_id: str, agent_name: str, log_msg: str):
    db = SessionLocal()
    try:
        st = db.query(SubTask).filter_by(task_id=task_id, agent_name=agent_name).first()
        if st:
            st.log = log_msg
            db.commit()
    finally:
        db.close()

class MoodleLinkChecker:
    def __init__(self, api_key: str = "", task_id: str = "", progress_callback=None):
        self.api_key = api_key
        self.task_id = task_id
        self.progress_callback = progress_callback
        self.agent_name = "Link Checker"
        
        # Configure SSL to ignore hostname verification and self-signed certificates
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def scan_and_verify(self, input_mbz: str, output_json_path: str):
        """
        Scans the MBZ archive for external links, verifies them in parallel,
        gets AI recommendations for broken links, and saves a JSON report.
        """
        self._log("Rozpoczynam skanowanie archiwum w poszukiwaniu linków...")
        
        # 1. Extract links and their contexts
        links_data = self._extract_links_from_mbz(input_mbz)
        if not links_data:
            self._log("Nie znaleziono żadnych zewnętrznych linków w kursie.")
            report = {
                "summary": {
                    "total": 0,
                    "active": 0,
                    "broken": 0
                },
                "links": []
            }
            self._save_report(report, output_json_path)
            return report

        total_links = len(links_data)
        self._log(f"Znaleziono {total_links} unikalnych linków do sprawdzenia. Weryfikacja aktywności...")

        # 2. Check links in parallel
        verified_links = self._verify_links_parallel(links_data)
        
        # 3. Process broken links and get suggestions
        broken_links = [l for l in verified_links if not l["is_active"]]
        active_count = total_links - len(broken_links)
        
        self._log(f"Weryfikacja zakończona: {active_count} aktywnych, {len(broken_links)} nieaktywnych.")
        
        if broken_links:
            self._log(f"Generowanie sugestii dla {len(broken_links)} niedziałających linków...")
            for idx, item in enumerate(broken_links):
                self._log(f"Przetwarzanie sugestii ({idx + 1}/{len(broken_links)})...")
                llm_context = item["context"]
                if item.get("anchor_text"):
                    llm_context = f"{item['context']} (Tekst linku: \"{item['anchor_text']}\")"
                suggestion = self._get_smart_suggestion(item["url"], llm_context)
                item["suggested_url"] = suggestion.get("suggested_url", "")
                item["reason"] = suggestion.get("reason", "Brak szczegółowego uzasadnienia.")

        # 4. Save report
        report = {
            "summary": {
                "total": total_links,
                "active": active_count,
                "broken": len(broken_links)
            },
            "links": verified_links
        }
        self._save_report(report, output_json_path)
        self._log(f"Raport zapisany pomyślnie. Znaleziono {len(broken_links)} problemów.")
        return report

    def _extract_links_from_mbz(self, input_mbz: str) -> list[dict]:
        """
        Extracts links with contexts from ZIP/TAR MBZ.
        Returns a list of dicts: [{"url": str, "context": str, "file": str}]
        """
        links_map = {} # url -> {context, file}
        activity_map = {} # directory -> (activity title, section title)
        section_dir_map = {} # directory -> section title
        
        # 1. Parse moodle_backup.xml first to extract course sections and activity hierarchies
        backup_xml = ""
        try:
            if input_mbz.lower().endswith('.zip'):
                with zipfile.ZipFile(input_mbz, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('moodle_backup.xml'):
                            backup_xml = zf.read(name).decode('utf-8', errors='replace')
                            break
            else:
                with tarfile.open(input_mbz, 'r:gz') as tf:
                    for member in tf:
                        if member.name.endswith('moodle_backup.xml'):
                            fh = tf.extractfile(member)
                            if fh:
                                backup_xml = fh.read().decode('utf-8', errors='replace')
                            break
        except Exception as e:
            print(f"[Link Checker] Failed to pre-parse moodle_backup.xml: {e}")
            
        if backup_xml:
            # Parse sections mapping: sectionid -> title
            section_map = {}
            sections_matches = re.findall(r'<section>(.*?)</section>', backup_xml, re.DOTALL)
            for s in sections_matches:
                sid_m = re.search(r'<sectionid>(\d+)</sectionid>', s)
                title_m = re.search(r'<title>(.*?)</title>', s, re.DOTALL)
                if sid_m and title_m:
                    sid = sid_m.group(1)
                    title = title_m.group(1).strip()
                    if title.startswith("<![CDATA[") and title.endswith("]]>"):
                        title = title[9:-3]
                    title = clean_moodle_multilang(title)
                    section_map[sid] = title
                    section_dir_map[f"sections/section_{sid}"] = title

            # Parse activities mapping: directory -> (activity title, section title)
            activities_matches = re.findall(r'<activity>(.*?)</activity>', backup_xml, re.DOTALL)
            for a in activities_matches:
                dir_m = re.search(r'<directory>(.*?)</directory>', a)
                title_m = re.search(r'<title>(.*?)</title>', a, re.DOTALL)
                sid_m = re.search(r'<sectionid>(\d+)</sectionid>', a)
                if dir_m and title_m:
                    directory = dir_m.group(1).strip()
                    title = title_m.group(1).strip()
                    if title.startswith("<![CDATA[") and title.endswith("]]>"):
                        title = title[9:-3]
                    title = clean_moodle_multilang(title)
                    
                    sec_title = "Ogólny"
                    if sid_m:
                        sid = sid_m.group(1)
                        sec_title = section_map.get(sid, "Ogólny")
                        
                    activity_map[directory] = (title, sec_title)

        def process_xml_content(content: str, filename: str):
            # Unescape HTML entities first to prevent escaped characters/tags from being part of captured URLs
            content_clean = html.unescape(content)
            
            # Try to resolve location context using course backup structure
            context = None
            filename_clean = filename.replace('\\', '/').strip('./')
            parts = filename_clean.split('/')
            
            if len(parts) >= 2:
                if parts[0] == 'activities':
                    act_dir = f"activities/{parts[1]}"
                    if act_dir in activity_map:
                        act_title, sec_title = activity_map[act_dir]
                        context = f"{sec_title} → {act_title}"
                elif parts[0] == 'sections':
                    sec_dir = f"sections/{parts[1]}"
                    if sec_dir in section_dir_map:
                        sec_title = section_dir_map[sec_dir]
                        context = f"Sekcja: {sec_title}"
            
            # Fallback to local name tag if not resolved
            if not context:
                name_m = re.search(r'<name>(<!\[CDATA\[(.*?)\]\]>|(.*?))</name>', content_clean, re.DOTALL)
                if name_m:
                    cdata = name_m.group(2)
                    plain = name_m.group(3)
                    raw_context = (cdata if cdata is not None else plain or "").strip()
                    context = clean_moodle_multilang(raw_context)
                    
            if not context or context == "Nieznana aktywność":
                context = "Ogólny kurs"
            
            # 1. Search for HTML anchor tags to find URLs with their specific anchor texts
            anchor_pattern = re.compile(
                r'<a\s+[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE
            )
            anchors = anchor_pattern.findall(content_clean)
            for url, anchor_text in anchors:
                url = url.rstrip('.,;:)!?>}"\'')
                if any(kw in url for kw in ["localhost", "127.0.0.1", "@@PLUGINFILE@@", "$@NULL@$"]):
                    continue
                if len(url) < 12:
                    continue
                
                # Clean up anchor text
                clean_anchor = re.sub(r'<[^>]+>', ' ', anchor_text)
                clean_anchor = html.unescape(clean_anchor)
                clean_anchor = re.sub(r'\s+', ' ', clean_anchor).strip()
                
                # Use anchor text if it is descriptive (not empty, not just a URL)
                if not clean_anchor or clean_anchor.startswith("http://") or clean_anchor.startswith("https://") or len(clean_anchor) < 2:
                    clean_anchor = None
                
                if url not in links_map:
                    links_map[url] = {
                        "url": url,
                        "context": context,
                        "anchor_text": clean_anchor,
                        "file": Path(filename).name,
                        "archive_path": filename
                    }
            
            # 2. Find any other raw URLs that were not in anchor tags
            urls = URL_PATTERN.findall(content_clean)
            for url in urls:
                url = url.rstrip('.,;:)!?>}"\'')
                if any(kw in url for kw in ["localhost", "127.0.0.1", "@@PLUGINFILE@@", "$@NULL@$"]):
                    continue
                if len(url) < 12:
                    continue
                    
                if url not in links_map:
                    links_map[url] = {
                        "url": url,
                        "context": context,
                        "file": Path(filename).name,
                        "archive_path": filename
                    }

        try:
            if input_mbz.lower().endswith('.zip'):
                with zipfile.ZipFile(input_mbz, 'r') as zf:
                    for info in zf.infolist():
                        if self._should_process(info.filename):
                            try:
                                content = zf.read(info.filename).decode('utf-8', errors='replace')
                                process_xml_content(content, info.filename)
                            except Exception:
                                pass
            else:
                with tarfile.open(input_mbz, 'r:gz') as tf:
                    for member in tf:
                        if member.isfile() and self._should_process(member.name):
                            try:
                                fh = tf.extractfile(member)
                                if fh:
                                    content = fh.read().decode('utf-8', errors='replace')
                                    process_xml_content(content, member.name)
                            except Exception:
                                pass
        except Exception as e:
            print(f"[Link Checker] Error scanning MBZ: {e}")
            
        return list(links_map.values())

    def _should_process(self, member_name: str) -> bool:
        basename = member_name.rstrip('/').split('/')[-1].lstrip('.')
        return member_name.endswith('.xml') and basename not in SKIP_FILES

    def _verify_single_link(self, item: dict) -> dict:
        """
        Sends HEAD and GET request to check link status.
        """
        url = item["url"]
        is_active = False
        status_code = None
        error_msg = ""
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        }
        
        # Try HEAD request first
        try:
            req = urllib.request.Request(url, headers=headers, method='HEAD')
            with urllib.request.urlopen(req, timeout=7, context=self.ssl_context) as response:
                status_code = response.status
                if status_code < 400:
                    is_active = True
        except urllib.error.HTTPError as e:
            status_code = e.code
            error_msg = f"HTTP Error {e.code}"
        except urllib.error.URLError as e:
            error_msg = str(e.reason)
        except Exception as e:
            error_msg = str(e)
            
        # If HEAD failed, fallback to GET (some servers block HEAD)
        if not is_active:
            try:
                req = urllib.request.Request(url, headers=headers, method='GET')
                with urllib.request.urlopen(req, timeout=7, context=self.ssl_context) as response:
                    status_code = response.status
                    if status_code < 400:
                        is_active = True
                        error_msg = ""
            except urllib.error.HTTPError as e:
                status_code = e.code
                error_msg = f"HTTP Error {e.code}"
            except urllib.error.URLError as e:
                error_msg = str(e.reason)
            except Exception as e:
                error_msg = str(e)

        return {
            "url": url,
            "context": item["context"],
            "anchor_text": item.get("anchor_text"),
            "file": item["file"],
            "archive_path": item.get("archive_path", ""),
            "is_active": is_active,
            "status_code": status_code,
            "error": error_msg if not is_active else None
        }

    def _verify_links_parallel(self, links_data: list[dict]) -> list[dict]:
        results = []
        max_workers = min(15, len(links_data))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(self._verify_single_link, item): item for item in links_data}
            
            completed = 0
            for future in as_completed(future_to_item):
                completed += 1
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    item = future_to_item[future]
                    results.append({
                        "url": item["url"],
                        "context": item["context"],
                        "anchor_text": item.get("anchor_text"),
                        "file": item["file"],
                        "is_active": False,
                        "status_code": None,
                        "error": str(e)
                    })
                
                # Report progress
                if self.progress_callback:
                    p = 20 + int(60 * completed / len(links_data))
                    self.progress_callback(p, f"Sprawdzanie linków ({completed}/{len(links_data)})...")
                    
        return results

    def _get_smart_suggestion(self, dead_url: str, context: str) -> dict:
        """
        Coordinates suggestions by prioritizing OpenRouter LLM (if API key is present),
        and falls back to a clean Google search URL.
        """
        # 1. Try to generate suggestion via OpenRouter LLM if API key is present
        if self.api_key:
            try:
                ai_suggestion = self._get_ai_suggestion(dead_url, context)
                if ai_suggestion and "google.com/search" not in ai_suggestion.get("suggested_url", ""):
                    return ai_suggestion
            except Exception as e:
                print(f"[Link Checker] Error getting AI suggestion: {e}")

        # 2. Fallback to Google Search if LLM failed, wasn't available, or couldn't find a match
        domain_q = get_clean_search_phrase(dead_url) or context
        reason = "Kliknij, aby wyszukać tę witrynę w Google."
        if not self.api_key:
            reason = "Brak klucza API. Kliknij, aby wyszukać tę witrynę w Google."
        return {
            "suggested_url": f"https://www.google.com/search?q={urllib.parse.quote(domain_q)}",
            "reason": reason
        }

    def _search_web_for_alternatives(self, query: str) -> list[str]:
        """
        Queries DuckDuckGo HTML search interface and parses the first few organic links
        to serve as real-world reference links for the LLM.
        """
        if not query or len(query.strip()) < 2:
            return []
            
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({'q': query})
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=6, context=self.ssl_context) as response:
                html_content = response.read().decode('utf-8', errors='replace')
                urls = re.findall(r'href="([^"]+)"', html_content)
                external_urls = []
                for u in urls:
                    if "/l/?kh=" in u or "uddg=" in u:
                        match = re.search(r'uddg=([^&]+)', u)
                        if match:
                            u = urllib.parse.unquote(match.group(1))
                    if u.startswith("http") and "duckduckgo.com" not in u:
                        if u not in external_urls:
                            external_urls.append(u)
                return external_urls[:6]
        except Exception as e:
            print(f"[Link Checker] Web search failed for query '{query}': {e}")
            return []

    def _get_ai_suggestion(self, dead_url: str, context: str) -> dict:
        """
        Uses OpenRouter to recommend a working alternative link.
        """
        clean_domain = get_clean_search_phrase(dead_url) or context
        google_fallback = f"https://www.google.com/search?q={urllib.parse.quote(clean_domain)}"

        # Dynamically query DDG search to find real, active, related links on the fly!
        search_query = get_clean_search_phrase(dead_url)
        if not search_query or len(search_query.strip()) < 3:
            search_query = context
            
        search_results = self._search_web_for_alternatives(search_query)
        search_info = ""
        if search_results:
            search_info = "Wyniki wyszukiwania w sieci dla tej witryny/tematu:\n"
            for r_url in search_results:
                search_info += f"- {r_url}\n"
            search_info += "\nMOŻESZ wybrać jeden z powyższych działających adresów URL jako sugerowany zamiennik (suggested_url), jeśli pasuje do kontekstu.\n\n"

        prompt = (
            f"Jesteś zaawansowanym asystentem ds. weryfikacji i kuracji linków internetowych w kursach edukacyjnych.\n"
            f"Twoim zadaniem jest znalezienie najlepszego, działającego zamiennika dla uszkodzonego (martwego) odnośnika.\n\n"
            f"Dane wejściowe:\n"
            f"- Niedziałający link: {dead_url}\n"
            f"- Kontekst wystąpienia (miejsce w kursie, nazwa zasobu lub tekst linku): {context}\n\n"
            f"{search_info}"
            f"Instrukcje wyboru zamiennika (dla dowolnego tematu z całego internetu):\n"
            f"1. DIRECT EQUIVALENT: Najpierw spróbuj znaleźć bezpośredni, działający odpowiednik tej samej strony lub serwisu. "
            f"Jeśli to oficjalna usługa, marka lub powszechne narzędzie, podaj jej aktualny i poprawny adres URL (np. oficjalną stronę główną lub aktualną stronę dokumentacji).\n"
            f"2. CATEGORY MATCH: Jeśli dana strona, firma lub specyficzny artykuł już nie istnieją, zaproponuj wiodący, stabilny i powszechnie uznawany portal, "
            f"agregator, encyklopedię lub oficjalną bazę wiedzy z tej samej dziedziny (np. dla niedziałających linków branżowych, naukowych, technologicznych, hobbystycznych czy lokalnych usług, "
            f"zasugeruj największy powiązany portal tematyczny lub oficjalny katalog).\n"
            f"3. STRICT SAFEGUARDS AGAINST HALLUCINATIONS:\n"
            f"   - Podawaj wyłącznie w 100% pewne, powszechnie znane i istniejące domeny.\n"
            f"   - Nigdy nie zmyślaj (nie halucynuj) ścieżek URL ani podstron. Jeśli sugerujesz zamiennik, użyj bezpiecznej i działającej strony głównej danej usługi/portalu, chyba że masz absolutną pewność co do poprawności pełnej ścieżki.\n"
            f"4. FALLBACK: Jeśli nie znasz bezpiecznej i wiarygodnej alternatywy, lub temat jest zbyt niszowy/niejednoznaczny, podaj dokładnie ten link do wyszukiwarki Google:\n"
            f"{google_fallback}\n\n"
            f"Zwróć odpowiedź wyłącznie jako poprawny format JSON (bez bloków markdown ```json ... ```) zawierający kluczowe pola:\n"
            f"- \"suggested_url\": \"<pełny, działający i bezpieczny adres URL zamiennika lub powyższy link Google>\"\n"
            f"- \"reason\": \"<krótkie, 1-2 zdaniowe uzasadnienie po polsku, wyjaśniające dlaczego ten link pasuje tematycznie/funkcjonalnie jako zamiennik, lub informacja o odesłaniu do Google z powodu braku pewnej alternatywy>\"\n"
        )

        free_models = [
            "google/gemini-2.5-flash:free",
            "openai/gpt-4o-mini",
            "minimax/minimax-m2.5:free",
            "openrouter/free"
        ]

        try:
            from openai import OpenAI
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
            
            for model in free_models:
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.4,
                        extra_headers={
                            "HTTP-Referer": "https://moodle.agent.local",
                            "X-Title": "Moodle Link Verifier Agent",
                        },
                        timeout=15
                    )
                    if resp.choices and resp.choices[0].message.content:
                        res_text = resp.choices[0].message.content.strip()
                        # clean markdown formatting if present
                        res_text = re.sub(r"^```(?:json)?", "", res_text, flags=re.MULTILINE).strip()
                        res_text = re.sub(r"```$", "", res_text, flags=re.MULTILINE).strip()
                        
                        data = json.loads(res_text)
                        if "suggested_url" in data:
                            return data
                except Exception as e:
                    print(f"[Link Checker] LLM Error ({model}): {e}")
                    
        except Exception as e:
            print(f"[Link Checker] OpenRouter initialization failed: {e}")

        domain_q = get_clean_search_phrase(dead_url) or context
        return {
            "suggested_url": f"https://www.google.com/search?q={urllib.parse.quote(domain_q)}",
            "reason": "Nie udało się pobrać automatycznej sugestii. Kliknij, aby wyszukać tę witrynę w Google."
        }

    def _save_report(self, report: dict, output_path: str):
        try:
            path = Path(output_path)
            path.parent.mkdir(exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Link Checker] Error saving JSON report: {e}")

    def _log(self, msg: str):
        print(f"[Link Checker] {msg}")
        if self.task_id:
            _set_subtask_log(self.task_id, self.agent_name, msg)
