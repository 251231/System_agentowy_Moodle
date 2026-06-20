import os
import re
import json
import shutil
import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Task, SubTask
from app.core.moodle_processor import MoodleMBZProcessor

UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(exist_ok=True)

def set_subtask(db: Session, task_id: str, agent_name: str, status: str, log: str = ""):
    st = db.query(SubTask).filter_by(task_id=task_id, agent_name=agent_name).first()
    if not st:
        st = SubTask(task_id=task_id, agent_name=agent_name)
        db.add(st)
    st.status = status
    st.log = log
    if status == "processing":
        st.started_at = datetime.datetime.utcnow()
    if status in ("completed", "failed"):
        st.finished_at = datetime.datetime.utcnow()
    db.commit()

def run_pipeline(task_id: str, input_path: str, output_path: str, config: dict):
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return
            
        task.status = "processing"
        db.commit()
        
        is_translate = config.get("translate") in (True, "true", "True", "1")
        is_h5p = config.get("generate_h5p") in (True, "true", "True", "1")
        is_links = config.get("check_links") in (True, "true", "True", "1")
        is_extract_texts = config.get("extract_texts") in (True, "true", "True", "1")

        if is_translate:
            set_subtask(db, task_id, "Translation Processor", "processing")
        if is_extract_texts:
            set_subtask(db, task_id, "Text Extractor", "processing")

        def check_cancel():
            db_s = SessionLocal()
            curr = db_s.query(Task).filter_by(id=task_id).first()
            cancelled = curr and curr.status == "cancelled"
            db_s.close()
            if cancelled:
                raise Exception("Przerwano przez uzytkownika.")

        def update_progress(percent: int, msg: str):
            db_p = SessionLocal()
            try:
                t = db_p.query(Task).filter_by(id=task_id).first()
                if t and t.status == "processing":
                    t.progress = percent
                    st = db_p.query(SubTask).filter_by(task_id=task_id, agent_name="Translation Processor").first()
                    if st:
                        st.log = msg
                    db_p.commit()
            finally:
                db_p.close()

        processor = MoodleMBZProcessor(
            source_lang=config.get("source_lang", "en"),
            target_langs=config.get("target_langs", ["en", "pl"]),
            api_type=config.get("api_type", "none"),
            api_key=config.get("api_key", ""),
            cancel_callback=check_cancel,
            progress_callback=update_progress
        )
        
        extract_set = None
        if is_translate:
            extract_set = processor.process_mbz(input_path, output_path, task_id=task_id)
        else:
            shutil.copy2(input_path, output_path)
            if is_extract_texts:
                set_subtask(db, task_id, "Text Extractor", "processing", "Wydobywanie tekstów z kursu...")
                try:
                    import html as _html
                    global_extract_set = processor._scan_and_extract_all(input_path)
                    raw_texts = set(text for text, lang in global_extract_set)
                    
                    cleaned_texts = []
                    for t in raw_texts:
                        clean = re.sub(r'<[^>]+>', ' ', t)
                        clean = _html.unescape(clean)
                        clean = re.sub(r'\s+', ' ', clean).strip()
                        if clean:
                            cleaned_texts.append(clean)
                            
                    source_texts = sorted(list(set(cleaned_texts)))
                    export_data = [{"original": t} for t in source_texts]
                    export_path = UPLOAD_DIR / f"texts_{task_id}.json"
                    with open(export_path, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                    set_subtask(db, task_id, "Text Extractor", "completed", f"Wyodrębniono {len(source_texts)} unikalnych tekstów.")
                    extract_set = global_extract_set
                except Exception as e:
                    set_subtask(db, task_id, "Text Extractor", "failed", f"Błąd: {str(e)}")

            if is_h5p:
                set_subtask(db, task_id, "H5P Generator", "processing", "Wydobywanie tekstów z kursu...")
                if extract_set:
                    source_texts = list(set(text for text, lang in extract_set))
                else:
                    source_texts = processor.extract_source_texts(input_path)
                    extract_set = set((t, config.get("source_lang", "en")) for t in source_texts)
                print(f"[H5P] Scan: {len(source_texts)} unique texts extracted from MBZ")

        if is_translate:
            set_subtask(db, task_id, "Translation Processor", "completed", "Tłumaczenie ukończone.")

        if is_h5p:
            set_subtask(db, task_id, "H5P Generator", "processing", "Generowanie treści H5P...")
            try:
                from app.core.h5p_generator import generate_h5p_quiz_json, create_h5p_archive

                if extract_set:
                    source_texts = list(set(text for text, lang in extract_set))
                else:
                    source_texts = []

                set_subtask(db, task_id, "H5P Generator", "processing",
                             f"Generowanie treści H5P z {len(source_texts)} fragmentów tekstu...")
                print(f"[H5P] Sending {len(source_texts)} text chunks to LLM")

                questions = generate_h5p_quiz_json(
                    source_texts,
                    config.get("api_type", "none"),
                    config.get("api_key", ""),
                    config
                )

                if questions:
                    h5p_filename = f"h5p_{task_id}.h5p"
                    h5p_path = UPLOAD_DIR / h5p_filename
                    create_h5p_archive(questions, str(h5p_path))
                    
                    task.h5p_filename = h5p_filename
                    db.commit()
                    set_subtask(db, task_id, "H5P Generator", "completed", f"Wygenerowano treści H5P ({len(questions)} elementów)")
                else:
                    set_subtask(db, task_id, "H5P Generator", "failed", "Nie udało się wygenerować pytań z podanych tekstów.")
            except Exception as e:
                set_subtask(db, task_id, "H5P Generator", "failed", f"Błąd: {str(e)}")

        if is_links:
            set_subtask(db, task_id, "Link Checker", "processing", "Inicjalizacja weryfikacji linków...")
            try:
                from app.core.link_checker import MoodleLinkChecker
                
                def link_progress_callback(percent: int, msg: str):
                    db_p = SessionLocal()
                    try:
                        st = db_p.query(SubTask).filter_by(task_id=task_id, agent_name="Link Checker").first()
                        if st:
                            st.log = msg
                        db_p.commit()
                    finally:
                        db_p.close()
                
                checker = MoodleLinkChecker(
                    api_key=config.get("api_key", ""),
                    task_id=task_id,
                    progress_callback=link_progress_callback
                )
                links_report_path = UPLOAD_DIR / f"links_{task_id}.json"
                checker.scan_and_verify(input_path, str(links_report_path))
                
                broken_count = 0
                if links_report_path.exists():
                    try:
                        with open(links_report_path, "r", encoding="utf-8") as f:
                            report = json.load(f)
                        broken_count = report.get("summary", {}).get("broken", 0)
                    except Exception:
                        pass
                
                if broken_count == 0:
                    cfg = dict(task.config or {})
                    cfg["links_approved"] = True
                    task.config = cfg
                    db.commit()

                set_subtask(db, task_id, "Link Checker", "completed", f"Weryfikacja linków zakończona sukcesem. Wykryto {broken_count} nieaktywnych linków.")
            except Exception as e:
                set_subtask(db, task_id, "Link Checker", "failed", f"Błąd: {str(e)}")

        task.status = "completed"
        task.progress = 100
        task.result_filename = Path(output_path).name
        db.commit()
    except Exception as e:
        task = db.query(Task).filter_by(id=task_id).first()
        if task:
            task.status = "failed"
            set_subtask(db, task_id, "Translation Processor", "failed", str(e))
            db.commit()
        print(f"[Pipeline] Error: {e}")
    finally:
        if Path(input_path).exists():
            Path(input_path).unlink()
        db.close()
