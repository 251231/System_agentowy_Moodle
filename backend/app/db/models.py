import uuid
import datetime
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base

def _uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id              = Column(String, primary_key=True, default=_uuid)
    original_filename = Column(String)
    status          = Column(String, default="pending")
    progress        = Column(Integer, default=0)
    result_filename = Column(String, nullable=True)
    h5p_filename    = Column(String, nullable=True)
    config          = Column(JSON, default={})
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id        = Column(String, ForeignKey("users.id"))

    owner = relationship("User", back_populates="tasks")
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
