import os
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Task, User
from app.api import deps
from app.api.schemas import ReplaceLinksRequest
from app.core.pipeline import run_pipeline, set_subtask, UPLOAD_DIR
from app.core.archive_utils import replace_links_in_archive

router = APIRouter()

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
        run_pipeline, task.id, str(input_path), str(output_path), config
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
        set_subtask(db, task_id, "Translation Processor", "cancelled", "Anulowano zadanie.")
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
    processed_count = replace_links_in_archive(str(mbz_path), replacements_list)
    
    report_path = UPLOAD_DIR / f"links_{task_id}.json"
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            
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
