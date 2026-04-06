import os
import shutil
import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Task, SubTask
from pipeline import PipelineManager

# Inicjalizacja tabel w bazie
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Moodle Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    from database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        task.status = "processing"
        db.commit()

        pipeline = PipelineManager(config)

        def on_start(name):
            _set_subtask(db, task_id, name, "processing")

        def on_done(name, success, log):
            _set_subtask(db, task_id, name, "completed" if success else "failed", log)

        pipeline.execute(input_path, output_path, on_agent_start=on_start, on_agent_done=on_done)

        task.status = "completed"
        task.result_filename = Path(output_path).name
        db.commit()
    except Exception as e:
        task = db.query(Task).filter_by(id=task_id).first()
        if task:
            task.status = "failed"
            db.commit()
        print(f"[Pipeline] Error: {e}")
    finally:
        if Path(input_path).exists():
            Path(input_path).unlink()
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Moodle Agent System API is running"}


@app.post("/tasks")
async def create_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    translate:     bool = Form(False),
    generate_h5p:  bool = Form(False),
    source_lang:   str  = Form("en"),
    target_langs:  str  = Form("en,pl"),
    api_type:      str  = Form("none"),
    api_key:       str  = Form(""),
    db: Session = Depends(get_db),
):
    config = {
        "translate":     translate,
        "generate_h5p":  generate_h5p,
        "source_lang":   source_lang,
        "target_langs":  [l.strip() for l in target_langs.split(",")],
        "api_type":      api_type,
        "api_key":       api_key or os.environ.get("OPENAI_API_KEY", ""),
    }

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


@app.get("/tasks")
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


@app.get("/tasks/{task_id}")
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


@app.get("/download/{task_id}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
