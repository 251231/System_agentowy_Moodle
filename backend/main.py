import os
import io
import csv
import shutil
import datetime
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Task, SubTask, User
from auth import get_current_user, create_access_token, verify_password, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from pipeline import PipelineManager
from moodle_processor import MoodleMBZProcessor

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


from worker import run_pipeline_task
# ── endpoints ─────────────────────────────────────────────────────────────────

tasks = {}
@app.get("/")
def root():
    return {"status": "Moodle Agent System API is running"}

@app.post("/auth/register")
def register(user_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    from fastapi import HTTPException
    user = db.query(User).filter(User.username == user_data.username).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"msg": "User created successfully"}

@app.post("/auth/login")
def login(user_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    from fastapi import HTTPException
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/tasks")
async def create_task(
    file: UploadFile = File(...),
    translate:     bool = Form(False),
    generate_h5p:  bool = Form(False),
    source_lang:   str  = Form("en"),
    target_langs:  str  = Form("en,pl"),
    api_type:      str  = Form("none"),
    api_key:       str  = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = {
        "translate":     translate,
        "generate_h5p":  generate_h5p,
        "source_lang":   source_lang,
        "target_langs":  [l.strip() for l in target_langs.split(",")],
        "api_type":      api_type,
        "api_key":       api_key or os.environ.get("OPENAI_API_KEY", ""),
    }

    task = Task(original_filename=file.filename, config=config, user_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)

    input_path  = UPLOAD_DIR / f"{task.id}_{file.filename}"
    output_path = UPLOAD_DIR / f"out_{task.id}_{file.filename}"


    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    run_pipeline_task.delay(str(task.id), str(input_path), str(output_path), config)

    return {"task_id": task.id, "status": "pending"}


@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.created_at.desc()).all()
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
def get_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
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
def download(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
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




# ─────────────────────────────────────────────────────────────────────────────
# Flashcards / AI summarization
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/flashcards")
async def generate_flashcards(
    file: UploadFile = File(...),
    api_type: str = Form("none"),
    api_key: str = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Extract / AI-summarize the course and return flashcards as JSON."""
    task_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{task_id}_{file.filename}"

    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        processor = MoodleMBZProcessor(api_type=api_type, api_key=api_key)
        flashcards = processor.extract_flashcards(str(input_path))
        return {"flashcards": flashcards, "count": len(flashcards)}
    except Exception as e:
        return {"error": str(e), "flashcards": []}
    finally:
        if input_path.exists():
            input_path.unlink()


@app.post("/flashcards-csv")
async def download_flashcards_csv(
    file: UploadFile = File(...),
    api_type: str = Form("none"),
    api_key: str = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Extract flashcards and return as Anki-compatible CSV (semicolon-separated)."""
    task_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{task_id}_{file.filename}"

    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        processor = MoodleMBZProcessor(api_type=api_type, api_key=api_key)
        flashcards = processor.extract_flashcards(str(input_path))

        out = io.StringIO()
        writer = csv.writer(out, delimiter=';')
        writer.writerow(['Front', 'Back', 'Tags'])
        for card in flashcards:
            writer.writerow([card['front'], card['back'], card.get('source', '')])

        return Response(
            content=out.getvalue().encode('utf-8-sig'),
            media_type='text/csv; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="flashcards.csv"'},
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        if input_path.exists():
            input_path.unlink()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
