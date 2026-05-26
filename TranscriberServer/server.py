"""FastAPI server for remote audio transcription.

Security model (Tier 1 hardening):
- Bind 127.0.0.1 by default; override only via env REMOTE_BIND_HOST.
- Require X-API-Key header on every endpoint except /health.
  Server refuses to start without REMOTE_API_KEY env.
- Sanitize uploaded filename (uuid + whitelisted extension); user-supplied
  path components never reach the filesystem.
- Reject upload bodies larger than REMOTE_MAX_UPLOAD_MB (default 200).
- Validate task_id matches UUID4 before any filesystem lookup.
- /health does not leak backend/model state.
"""
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException, Header, Request
from fastapi.responses import FileResponse

from transcriber_wrapper import RemoteTranscriber, BASE_DIR

ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".oga"}
DEFAULT_MAX_UPLOAD_MB = 200

API_KEY = os.environ.get("REMOTE_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit(
        "REMOTE_API_KEY env is required to start the transcriber server. "
        "Generate one (e.g. `python -c 'import secrets; print(secrets.token_urlsafe(32))'`) "
        "and set it via `set REMOTE_API_KEY=...` before launching."
    )

try:
    MAX_UPLOAD_BYTES = int(os.environ.get("REMOTE_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024
except ValueError:
    MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024

app = FastAPI(
    title="Remote Transcriber Server",
    description="Transcribes audio files using WhisperTyping",
    version="1.1.0",
)

transcriber = RemoteTranscriber()

UPLOADS_DIR = BASE_DIR / "TranscriberServer" / "uploads"
RESULTS_DIR = BASE_DIR / "TranscriberServer" / "results"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _require_api_key(x_api_key: str) -> None:
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def _validate_task_id(task_id: str) -> str:
    try:
        return str(uuid.UUID(task_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="invalid task_id")


@app.post("/transcribe")
async def transcribe_file(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(default=""),
):
    """Upload audio file for transcription. Returns task_id for tracking."""
    _require_api_key(x_api_key)

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    raw_name = file.filename or "audio"
    safe_ext = Path(raw_name).suffix.lower()
    if safe_ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {safe_ext}")

    task_id = str(uuid.uuid4())
    upload_path = UPLOADS_DIR / f"{task_id}{safe_ext}"

    bytes_written = 0
    with open(upload_path, "wb") as fp:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            if bytes_written > MAX_UPLOAD_BYTES:
                fp.close()
                upload_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="payload too large")
            fp.write(chunk)

    background_tasks.add_task(transcriber.transcribe_async, task_id, upload_path)

    return {"task_id": task_id, "status": "processing"}


@app.get("/status/{task_id}")
async def get_status(task_id: str, x_api_key: str = Header(default="")):
    _require_api_key(x_api_key)
    safe_id = _validate_task_id(task_id)
    return transcriber.get_status(safe_id)


@app.get("/result/{task_id}")
async def get_result(task_id: str, x_api_key: str = Header(default="")):
    _require_api_key(x_api_key)
    safe_id = _validate_task_id(task_id)

    result_path = RESULTS_DIR / f"{safe_id}.txt"
    if result_path.exists():
        return FileResponse(
            result_path,
            media_type="text/plain",
            filename=f"transcription_{safe_id}.txt",
        )
    raise HTTPException(status_code=404, detail="result not found")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    bind_host = os.environ.get("REMOTE_BIND_HOST", "127.0.0.1")
    bind_port = int(os.environ.get("REMOTE_BIND_PORT", "8000"))
    uvicorn.run(app, host=bind_host, port=bind_port)
