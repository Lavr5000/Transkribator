"""FastAPI server for remote audio transcription."""
from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import uuid
import shutil
from pathlib import Path
from transcriber_wrapper import RemoteTranscriber, BASE_DIR

app = FastAPI(
    title="Remote Transcriber Server",
    description="Transcribes audio files using WhisperTyping",
    version="1.0.0"
)

# Initialize transcriber
transcriber = RemoteTranscriber()

# Directories
UPLOADS_DIR = BASE_DIR / "TranscriberServer" / "uploads"
RESULTS_DIR = BASE_DIR / "TranscriberServer" / "results"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/transcribe")
async def transcribe_file(file: UploadFile, background_tasks: BackgroundTasks):
    """
    Upload audio file for transcription.

    Returns task_id for tracking progress.
    """
    task_id = str(uuid.uuid4())

    # Save uploaded file
    upload_path = UPLOADS_DIR / f"{task_id}_{file.filename}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Start transcription in background
    background_tasks.add_task(transcriber.transcribe_async, task_id, upload_path)

    return {
        "task_id": task_id,
        "status": "processing",
        "filename": file.filename
    }


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Check transcription status by task_id."""
    return transcriber.get_status(task_id)


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """Download transcription result as text file."""
    result_path = RESULTS_DIR / f"{task_id}.txt"
    if result_path.exists():
        return FileResponse(
            result_path,
            media_type="text/plain",
            filename=f"transcription_{task_id}.txt"
        )
    raise HTTPException(404, "Result not found")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "transcriber_loaded": transcriber.is_loaded()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
