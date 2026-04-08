from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import io
import csv
import shutil
import uuid
from pathlib import Path
from moodle_processor import MoodleMBZProcessor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(exist_ok=True)

tasks = {}


@app.get("/")
def read_root():
    return {"status": "Moodle MBZ Translator API is running"}


# ─────────────────────────────────────────────────────────────────────────────
# Translation
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/translate")
async def translate_mbz(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_langs: str = Form("en,pl"),
    api_type: str = Form("none"),
    api_key: str = Form(None),
):
    task_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{task_id}_{file.filename}"
    output_filename = f"translated_{file.filename}"
    output_path = UPLOAD_DIR / f"out_{task_id}_{output_filename}"

    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    tasks[task_id] = {"status": "processing", "file": None}
    langs = [l.strip() for l in target_langs.split(",")]
    processor = MoodleMBZProcessor(
        source_lang=source_lang,
        target_langs=langs,
        api_type=api_type,
        api_key=api_key,
    )

    def run():
        try:
            processor.process_mbz(str(input_path), str(output_path))
            tasks[task_id] = {
                "status": "completed",
                "file": str(output_path),
                "filename": output_filename,
            }
        except Exception as e:
            tasks[task_id] = {"status": "failed", "error": str(e)}
        finally:
            if input_path.exists():
                input_path.unlink()

    background_tasks.add_task(run)
    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})


@app.get("/download/{task_id}")
async def download_file(task_id: str):
    task = tasks.get(task_id)
    if task and task["status"] == "completed":
        return FileResponse(
            path=task["file"],
            filename=task["filename"],
            media_type="application/octet-stream",
        )
    return {"error": "File not ready or not found"}


# ─────────────────────────────────────────────────────────────────────────────
# Flashcards / AI summarization
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/flashcards")
async def generate_flashcards(
    file: UploadFile = File(...),
    api_type: str = Form("none"),
    api_key: str = Form(None),
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
