from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text

from app.db.database import engine, Base
from app.api.endpoints import router as api_router
from app.api.auth import router as auth_router

Base.metadata.create_all(bind=engine)

inspector = inspect(engine)

if "tasks" in inspector.get_table_names():
    columns = [col['name'] for col in inspector.get_columns('tasks')]
    with engine.begin() as conn:
        if 'owner_id' not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN owner_id VARCHAR REFERENCES users(id)"))
        if 'progress' not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0"))
        if 'result_filename' not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN result_filename VARCHAR"))
        if 'h5p_filename' not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN h5p_filename VARCHAR"))
        if 'config' not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN config JSON DEFAULT '{}'::json"))

app = FastAPI(title="Moodle Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "alive"}

app.include_router(auth_router, tags=["auth"])
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
