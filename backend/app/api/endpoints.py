import os
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
        
        _set_subtask(db, task_id, "Translation Processor", "processing")

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
        if config.get("translate"):
            extract_set = processor.process_mbz(input_path, output_path, task_id=task_id)
        else:
            # If translation is off, just copy the file over
            shutil.copy2(input_path, output_path)
            if config.get("generate_h5p"):
                # Skanuj kurs aby wydobyć teksty do H5P
                _set_subtask(db, task_id, "H5P Generator", "processing", "Wydobywanie tekst\u00f3w z kursu...")
                source_texts = processor.extract_source_texts(input_path)
                # Tworzymy fake extract_set kompatybilny z dalszym kodem
                extract_set = set((t, config.get("source_lang", "en")) for t in source_texts)
                print(f"[H5P] Scan: {len(source_texts)} unique texts extracted from MBZ")


        _set_subtask(db, task_id, "Translation Processor", "completed", "Processing completed.")

        if config.get("generate_h5p"):
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

        _set_subtask(db, task_id, "Translation Processor", "completed", "Processing completed.")

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
        result.append({
            "id":                t.id,
            "original_filename": t.original_filename,
            "status":            t.status,
            "progress":          t.progress,
            "h5p_filename":      t.h5p_filename,
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
    return {
        "id":                t.id,
        "original_filename": t.original_filename,
        "status":            t.status,
        "progress":          t.progress,
        "h5p_filename":      t.h5p_filename,
        "subtasks": [
            {"agent": s.agent_name, "status": s.status, "log": s.log}
            for s in t.subtasks
        ],
    }


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
