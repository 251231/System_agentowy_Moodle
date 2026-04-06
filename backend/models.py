import uuid
import datetime
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

def _uuid():
    return str(uuid.uuid4())

class Task(Base):
    __tablename__ = "tasks"

    id              = Column(String, primary_key=True, default=_uuid)
    original_filename = Column(String)
    status          = Column(String, default="pending")   # pending | processing | completed | failed
    result_filename = Column(String, nullable=True)
    config          = Column(JSON, default={})
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)

    subtasks = relationship("SubTask", back_populates="task", cascade="all, delete-orphan")


class SubTask(Base):
    __tablename__ = "subtasks"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    task_id     = Column(String, ForeignKey("tasks.id"))
    agent_name  = Column(String)
    status      = Column(String, default="pending")
    log         = Column(String, nullable=True)
    started_at  = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="subtasks")
