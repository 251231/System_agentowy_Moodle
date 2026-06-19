import os
import re
import json
import shutil
import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.db.models import Task, SubTask, User
from app.api import deps
from app.core.moodle_processor import MoodleMBZProcessor

router = APIRouter()

UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def _set_subtask(db: Session, task_id: str, agent_name: str, status: str, log: str = ""):
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


# ── background job ────────────────────────────────────────────────────────────
def _run_pipeline(task_id: str, input_path: str, output_path: str, config: dict):
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
            _set_subtask(db, task_id, "Translation Processor", "processing")
        if is_extract_texts:
            _set_subtask(db, task_id, "Text Extractor", "processing")

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
                    # Optionally update the subtask log with the current message
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
            # If translation is off, just copy the file over
            shutil.copy2(input_path, output_path)
            if is_extract_texts:
                _set_subtask(db, task_id, "Text Extractor", "processing", "Wydobywanie tekstów z kursu...")
                try:
                    import html as _html
                    global_extract_set = processor._scan_and_extract_all(input_path)
                    raw_texts = set(text for text, lang in global_extract_set)
                    
                    cleaned_texts = []
                    for t in raw_texts:
                        # Strip HTML tags
                        clean = re.sub(r'<[^>]+>', ' ', t)
                        # Unescape entities
                        clean = _html.unescape(clean)
                        # Normalize whitespaces
                        clean = re.sub(r'\s+', ' ', clean).strip()
                        if clean:
                            cleaned_texts.append(clean)
                            
                    source_texts = sorted(list(set(cleaned_texts)))
                    export_data = [{"original": t} for t in source_texts]
                    export_path = UPLOAD_DIR / f"texts_{task_id}.json"
                    with open(export_path, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                    _set_subtask(db, task_id, "Text Extractor", "completed", f"Wyodrębniono {len(source_texts)} unikalnych tekstów.")
                    extract_set = global_extract_set
                except Exception as e:
                    _set_subtask(db, task_id, "Text Extractor", "failed", f"Błąd: {str(e)}")

            if is_h5p:
                # Skanuj kurs aby wydobyć teksty do H5P
                _set_subtask(db, task_id, "H5P Generator", "processing", "Wydobywanie tekstów z kursu...")
                if extract_set:
                    source_texts = list(set(text for text, lang in extract_set))
                else:
                    source_texts = processor.extract_source_texts(input_path)
                    extract_set = set((t, config.get("source_lang", "en")) for t in source_texts)
                print(f"[H5P] Scan: {len(source_texts)} unique texts extracted from MBZ")

        if is_translate:
            _set_subtask(db, task_id, "Translation Processor", "completed", "Tłumaczenie ukończone.")

        if is_h5p:
            _set_subtask(db, task_id, "H5P Generator", "processing", "Generowanie treści H5P...")
            try:
                from app.core.h5p_generator import generate_h5p_quiz_json, create_h5p_archive

                # --- zbierz teksty źródłowe ---
                if extract_set:
                    source_texts = list(set(text for text, lang in extract_set))
                else:
                    source_texts = []

                _set_subtask(db, task_id, "H5P Generator", "processing",
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
                    _set_subtask(db, task_id, "H5P Generator", "completed", f"Wygenerowano treści H5P ({len(questions)} elementów)")
                else:
                    _set_subtask(db, task_id, "H5P Generator", "failed", "Nie udało się wygenerować pytań z podanych tekstów.")
            except Exception as e:
                _set_subtask(db, task_id, "H5P Generator", "failed", f"Błąd: {str(e)}")

        if is_links:
            _set_subtask(db, task_id, "Link Checker", "processing", "Inicjalizacja weryfikacji linków...")
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
                
                # Check if there are any broken links in the newly generated report
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

                _set_subtask(db, task_id, "Link Checker", "completed", f"Weryfikacja linków zakończona sukcesem. Wykryto {broken_count} nieaktywnych linków.")
            except Exception as e:
                _set_subtask(db, task_id, "Link Checker", "failed", f"Błąd: {str(e)}")

        task.status = "completed"
        task.progress = 100
        task.result_filename = Path(output_path).name
        db.commit()
    except Exception as e:
        task = db.query(Task).filter_by(id=task_id).first()
        if task:
            task.status = "failed"
            _set_subtask(db, task_id, "Translation Processor", "failed", str(e))
            db.commit()
        print(f"[Pipeline] Error: {e}")
    finally:
        if Path(input_path).exists():
            Path(input_path).unlink()
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def root():
    return {"status": "Moodle Agent System API is running"}


@router.post("/tasks")
async def create_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    translate:     bool = Form(False),
    generate_h5p:  bool = Form(False),
    check_links:   bool = Form(False),
    extract_texts: bool = Form(False),
    source_lang:   str  = Form("en"),
    target_langs:  str  = Form("en,pl"),
    api_type:      str  = Form("none"),
    api_key:       str  = Form(""),
    h5p_types:        str = Form(""),
    h5p_level:        str = Form("Mieszany (auto)"),
    h5p_amount:       int = Form(5),
    h5p_focus:        str = Form(""),
    h5p_instructions: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    config = {
        "translate":     translate,
        "generate_h5p":  generate_h5p,
        "check_links":   check_links,
        "extract_texts": extract_texts,
        "source_lang":   source_lang,
        "target_langs":  [l.strip() for l in target_langs.split(",")],
        "api_type":      api_type,
        "api_key":       api_key or os.environ.get("OPENAI_API_KEY", ""),
        "h5p_types":        [t.strip() for t in h5p_types.split(",") if t.strip()],
        "h5p_level":        h5p_level,
        "h5p_amount":       h5p_amount,
        "h5p_focus":        [f.strip() for f in h5p_focus.split(",") if f.strip()],
        "h5p_instructions": h5p_instructions,
    }

    # For edge cases where API KEY is not in os.environ yet but maybe another key type
    if not config["api_key"]:
        if api_type == "gemini":
             config["api_key"] = os.environ.get("GEMINI_API_KEY", "")
        elif api_type == "openrouter":
             config["api_key"] = os.environ.get("OPENROUTER_API_KEY", "")

    task = Task(original_filename=file.filename, config=config, owner_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)

    input_path  = UPLOAD_DIR / f"{task.id}_{file.filename}"
    output_path = UPLOAD_DIR / f"out_{task.id}_{file.filename}"

    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    background_tasks.add_task(
        _run_pipeline, task.id, str(input_path), str(output_path), config
    )

    return {"task_id": task.id, "status": "pending"}


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    tasks = db.query(Task).filter(Task.owner_id == current_user.id).order_by(Task.created_at.desc()).all()
    result = []
    for t in tasks:
        has_links_report = (UPLOAD_DIR / f"links_{t.id}.json").exists()
        has_texts_report = (UPLOAD_DIR / f"texts_{t.id}.json").exists()
        result.append({
            "id":                t.id,
            "original_filename": t.original_filename,
            "status":            t.status,
            "progress":          t.progress,
            "h5p_filename":      t.h5p_filename,
            "has_links_report":  has_links_report,
            "has_texts_report":  has_texts_report,
            "config":            t.config,
            "created_at":        t.created_at.isoformat() if t.created_at else None,
            "subtasks": [
                {"agent": s.agent_name, "status": s.status, "log": s.log}
                for s in t.subtasks
            ],
        })
    return result


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t:
        return {"status": "not_found"}
    has_links_report = (UPLOAD_DIR / f"links_{task_id}.json").exists()
    has_texts_report = (UPLOAD_DIR / f"texts_{task_id}.json").exists()
    return {
        "id":                t.id,
        "original_filename": t.original_filename,
        "status":            t.status,
        "progress":          t.progress,
        "h5p_filename":      t.h5p_filename,
        "has_links_report":  has_links_report,
        "has_texts_report":  has_texts_report,
        "config":            t.config,
        "subtasks": [
            {"agent": s.agent_name, "status": s.status, "log": s.log}
            for s in t.subtasks
        ],
    }


@router.get("/tasks/{task_id}/links")
def get_task_links(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t:
        return {"error": "Task not found"}
    
    path = UPLOAD_DIR / f"links_{task_id}.json"
    if not path.exists():
        return {"error": "Links report not found on disk"}
        
    return FileResponse(
        path=path,
        filename=f"links_{t.original_filename.replace('.mbz', '')}.json",
        media_type="application/json",
    )


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t:
        return {"error": "not_found"}
    if t.status == "processing" or t.status == "pending":
        t.status = "cancelled"
        _set_subtask(db, task_id, "Translation Processor", "cancelled", "Anulowano zadanie.")
        db.commit()
        return {"status": "cancelled"}
    return {"status": "cannot_cancel"}


@router.get("/download/{task_id}")
def download(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t or t.status != "completed" or not t.result_filename:
        return {"error": "File not ready or not found"}
    path = UPLOAD_DIR / t.result_filename
    if not path.exists():
        return {"error": "File missing on disk"}
    return FileResponse(
        path=path,
        filename=f"processed_{t.original_filename}",
        media_type="application/octet-stream",
    )


@router.get("/tasks/{task_id}/texts")
def get_task_texts(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t:
        return {"error": "Task not found"}
    
    path = UPLOAD_DIR / f"texts_{task_id}.json"
    if not path.exists():
        return {"error": "Texts file not found on disk"}
        
    return FileResponse(
        path=path,
        filename=f"texts_{t.original_filename.replace('.mbz', '')}.json",
        media_type="application/json",
    )


@router.get("/download-h5p/{task_id}")
def download_h5p(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_active_user)):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t or t.status != "completed" or not t.h5p_filename:
        return {"error": "H5P file not ready or not found"}
    path = UPLOAD_DIR / t.h5p_filename
    if not path.exists():
        return {"error": "File missing on disk"}
    return FileResponse(
        path=path,
        filename=f"h5p_{t.original_filename.replace('.mbz', '.h5p')}",
        media_type="application/zip",
    )


from pydantic import BaseModel
from typing import List

class LinkReplacement(BaseModel):
    url: str
    suggested_url: str
    archive_path: str

class ReplaceLinksRequest(BaseModel):
    replacements: List[LinkReplacement]

def _replace_links_in_archive(archive_path: str, replacements: list) -> int:
    by_file = {}
    for r in replacements:
        ap = r["archive_path"]
        if ap not in by_file:
            by_file[ap] = []
        by_file[ap].append(r)
        
    temp_out = archive_path + ".tmp"
    processed = 0
    
    import copy
    import io
    import html as _html
    import shutil
    import os
    
    if archive_path.lower().endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zip_in, \
             zipfile.ZipFile(temp_out, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for info in zip_in.infolist():
                data = zip_in.read(info.filename)
                if info.filename in by_file:
                    try:
                        content = data.decode('utf-8', errors='replace')
                        modified = False
                        for r in by_file[info.filename]:
                            old_url = r["url"]
                            new_url = r["suggested_url"]
                            if old_url in content:
                                content = content.replace(old_url, new_url)
                                modified = True
                            old_url_esc = _html.escape(old_url)
                            new_url_esc = _html.escape(new_url)
                            if old_url_esc in content:
                                content = content.replace(old_url_esc, new_url_esc)
                                modified = True
                        if modified:
                            data = content.encode('utf-8')
                            processed += 1
                    except Exception as e:
                        print(f"Error replacing in {info.filename}: {e}")
                zip_out.writestr(info, data)
    else:
        import tarfile
        with tarfile.open(archive_path, 'r:gz') as tar_in:
            with tarfile.open(temp_out, 'w:gz', format=tar_in.format) as tar_out:
                for member in tar_in:
                    if not member.isfile():
                        tar_out.addfile(member)
                        continue
                    
                    fh = tar_in.extractfile(member)
                    if fh is None:
                        tar_out.addfile(member)
                        continue
                        
                    original_bytes = fh.read()
                    
                    if member.name in by_file:
                        try:
                            content = original_bytes.decode('utf-8', errors='replace')
                            modified = False
                            for r in by_file[member.name]:
                                old_url = r["url"]
                                new_url = r["suggested_url"]
                                if old_url in content:
                                    content = content.replace(old_url, new_url)
                                    modified = True
                                old_url_esc = _html.escape(old_url)
                                new_url_esc = _html.escape(new_url)
                                if old_url_esc in content:
                                    content = content.replace(old_url_esc, new_url_esc)
                                    modified = True
                            if modified:
                                new_bytes = content.encode('utf-8')
                                new_info = copy.copy(member)
                                new_info.size = len(new_bytes)
                                tar_out.addfile(new_info, io.BytesIO(new_bytes))
                                processed += 1
                            else:
                                tar_out.addfile(member, io.BytesIO(original_bytes))
                        except Exception as e:
                            print(f"Error replacing in {member.name}: {e}")
                            tar_out.addfile(member, io.BytesIO(original_bytes))
                    else:
                        tar_out.addfile(member, io.BytesIO(original_bytes))
                        
    if os.path.exists(temp_out):
        shutil.move(temp_out, archive_path)
    return processed

@router.post("/tasks/{task_id}/replace-links")
def replace_task_links(
    task_id: str,
    req: ReplaceLinksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t or t.status != "completed" or not t.result_filename:
        return {"error": "Task not completed or file not found"}
        
    mbz_path = UPLOAD_DIR / t.result_filename
    if not mbz_path.exists():
        return {"error": "Processed MBZ file not found on disk"}
        
    replacements_list = [r.dict() for r in req.replacements]
    processed_count = _replace_links_in_archive(str(mbz_path), replacements_list)
    
    # Update links_{task_id}.json
    report_path = UPLOAD_DIR / f"links_{task_id}.json"
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            
            # Map replacements for quick lookup
            repl_map = {(r["url"], r["archive_path"]): r["suggested_url"] for r in replacements_list}
            
            for item in report.get("links", []):
                key = (item["url"], item.get("archive_path", ""))
                if key in repl_map:
                    new_url = repl_map[key]
                    item["url"] = new_url
                    item["is_active"] = True
                    item["error"] = None
                    if "suggested_url" in item:
                        del item["suggested_url"]
                    if "reason" in item:
                        del item["reason"]
            
            # Recompute summary
            total = len(report.get("links", []))
            broken = sum(1 for item in report.get("links", []) if not item.get("is_active"))
            active = total - broken
            report["summary"] = {
                "total": total,
                "active": active,
                "broken": broken
            }
            
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating links report JSON: {e}")
            
    # Mark links as approved
    cfg = dict(t.config or {})
    cfg["links_approved"] = True
    t.config = cfg
    db.commit()
            
    return {"status": "success", "replaced_files_count": processed_count}


@router.post("/tasks/{task_id}/approve-links")
def approve_task_links(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    t = db.query(Task).filter_by(id=task_id, owner_id=current_user.id).first()
    if not t:
        return {"error": "Task not found"}
        
    cfg = dict(t.config or {})
    cfg["links_approved"] = True
    t.config = cfg
    db.commit()
    return {"status": "success"}

