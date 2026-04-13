import os
import datetime
from pathlib import Path
from celery import Celery

from database import SessionLocal
from models import Task, SubTask
from pipeline import PipelineManager

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "moodle_workers",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="process_mbz_pipeline")
def run_pipeline_task(task_id: str, input_path: str, output_path: str, config: dict):
    db = SessionLocal()
    
    def _set_subtask(t_id, agent_name, status, log=""):
        st = db.query(SubTask).filter_by(task_id=t_id, agent_name=agent_name).first()
        if not st:
            st = SubTask(task_id=t_id, agent_name=agent_name)
            db.add(st)
        st.status = status
        st.log = log
        if status == "processing":
            st.started_at = datetime.datetime.utcnow()
        if status in ("completed", "failed"):
            st.finished_at = datetime.datetime.utcnow()
        db.commit()

    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return
        
        task.status = "processing"
        db.commit()

        pipeline = PipelineManager(config)

        def on_start(name):
            _set_subtask(task_id, name, "processing")

        def on_done(name, success, log):
            _set_subtask(task_id, name, "completed" if success else "failed", log)

        pipeline.execute(input_path, output_path, on_agent_start=on_start, on_agent_done=on_done)

        task.status = "completed"
        task.result_filename = Path(output_path).name
        db.commit()
    except Exception as e:
        task = db.query(Task).filter_by(id=task_id).first()
        if task:
            task.status = "failed"
            db.commit()
        print(f"[Pipeline Worker] Error: {e}")
    finally:
        if Path(input_path).exists():
            Path(input_path).unlink()
        db.close()
