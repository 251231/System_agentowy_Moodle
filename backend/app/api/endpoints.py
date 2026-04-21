import os
import shutil
import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.db.models import Task, SubTask
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

        processor = MoodleMBZProcessor(
            source_lang=config.get("source_lang", "en"),
            target_langs=config.get("target_langs", ["en", "pl"]),
            api_type=config.get("api_type", "none"),
            api_key=config.get("api_key", ""),
            cancel_callback=check_cancel
        )
        
        if config.get("translate"):
            processor.process_mbz(input_path, output_path)
        else:
            # If translation is off, just copy the file over
            shutil.copy2(input_path, output_path)

        _set_subtask(db, task_id, "Translation Processor", "completed", "Processing completed.")

        task.status = "completed"
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
    source_lang:   str  = Form("en"),
    target_langs:  str  = Form("en,pl"),
    api_type:      str  = Form("none"),
    api_key:       str  = Form(""),
    db: Session = Depends(get_db),
):
    config = {
        "translate":     translate,
        "source_lang":   source_lang,
        "target_langs":  [l.strip() for l in target_langs.split(",")],
        "api_type":      api_type,
        "api_key":       api_key or os.environ.get("OPENAI_API_KEY", ""),
    }

    # For edge cases where API KEY is not in os.environ yet but maybe another key type
    if not config["api_key"] and api_type == "gemini":
         config["api_key"] = os.environ.get("GEMINI_API_KEY", "")

    task = Task(original_filename=file.filename, config=config)
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
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    result = []
    for t in tasks:
        result.append({
            "id":                t.id,
            "original_filename": t.original_filename,
            "status":            t.status,
            "created_at":        t.created_at.isoformat() if t.created_at else None,
            "subtasks": [
                {"agent": s.agent_name, "status": s.status, "log": s.log}
                for s in t.subtasks
            ],
        })
    return result


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    t = db.query(Task).filter_by(id=task_id).first()
    if not t:
        return {"status": "not_found"}
    return {
        "id":                t.id,
        "original_filename": t.original_filename,
        "status":            t.status,
        "subtasks": [
            {"agent": s.agent_name, "status": s.status, "log": s.log}
            for s in t.subtasks
        ],
    }


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    t = db.query(Task).filter_by(id=task_id).first()
    if not t:
        return {"error": "not_found"}
    if t.status == "processing" or t.status == "pending":
        t.status = "cancelled"
        _set_subtask(db, task_id, "Translation Processor", "cancelled", "Anulowano zadanie.")
        db.commit()
        return {"status": "cancelled"}
    return {"status": "cannot_cancel"}


@router.get("/download/{task_id}")
def download(task_id: str, db: Session = Depends(get_db)):
    t = db.query(Task).filter_by(id=task_id).first()
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
