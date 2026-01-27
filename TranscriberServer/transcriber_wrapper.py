"""Wrapper for Transcriber class to work with FastAPI server."""
import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base directory - Desktop/Transcriber
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

try:
    from src.transcriber import Transcriber
    logger.info("Transcriber imported successfully")
except ImportError as e:
    logger.error(f"Failed to import Transcriber: {e}")
    raise


class RemoteTranscriber:
    """Wrapper for remote transcription service."""

    def __init__(self):
        """Initialize transcriber with default settings."""
        logger.info("Initializing RemoteTranscriber...")

        try:
            self.transcriber = Transcriber(
                backend="whisper",
                model_size="base",
                device="auto",
                language="auto",
                enable_post_processing=True
            )

            # Load model at startup
            logger.info("Loading Whisper model...")
            self.transcriber.load_model()
            logger.info("Model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize transcriber: {e}")
            raise

        # Create results and uploads directories
        self.results_dir = BASE_DIR / "TranscriberServer" / "results"
        self.uploads_dir = BASE_DIR / "TranscriberServer" / "uploads"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def transcribe_async(self, task_id: str, audio_path: Path):
        """
        Transcribe audio file and save result.

        Args:
            task_id: Unique task identifier
            audio_path: Path to audio file
        """
        try:
            logger.info(f"Task {task_id}: Starting transcription of {audio_path}")

            # Transcribe file
            text, time_taken = self.transcriber.transcribe_file(audio_path)

            logger.info(f"Task {task_id}: Transcription completed in {time_taken:.2f}s")

            # Save result
            result_path = self.results_dir / f"{task_id}.txt"
            result_path.write_text(text, encoding="utf-8")

            # Update status
            self._update_status(
                task_id,
                "completed",
                text=text,
                time_taken=time_taken
            )

            logger.info(f"Task {task_id}: Result saved")

            # Clean up uploaded file
            if audio_path.exists():
                audio_path.unlink()
                logger.info(f"Task {task_id}: Cleaned up uploaded file")

        except Exception as e:
            logger.error(f"Task {task_id}: Error during transcription - {e}")
            self._update_status(task_id, "failed", error=str(e))

    def get_status(self, task_id: str) -> dict:
        """
        Get task status.

        Args:
            task_id: Unique task identifier

        Returns:
            Status dictionary
        """
        status_file = self.results_dir / f"{task_id}.json"
        if status_file.exists():
            return json.loads(status_file.read_text(encoding="utf-8"))
        return {"task_id": task_id, "status": "processing"}

    def is_loaded(self) -> bool:
        """Check if transcriber model is loaded."""
        return self.transcriber.is_loaded if self.transcriber else False

    def _update_status(self, task_id: str, status: str, **kwargs):
        """
        Update task status in JSON file.

        Args:
            task_id: Unique task identifier
            status: Status string (processing, completed, failed)
            **kwargs: Additional status data
        """
        status_file = self.results_dir / f"{task_id}.json"
        data = {
            "task_id": task_id,
            "status": status,
            **kwargs
        }
        status_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
