"""Remote transcription client with automatic fallback support.

Provides client for remote transcription service with health checking,
caching, and automatic error handling for graceful degradation.
"""
import os
import tempfile
import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)


class RemoteTranscriptionClient:
    """Client for remote transcription with automatic fallback."""

    # Server endpoints (Tailscale VPN first, then internet)
    SERVERS = [
        "http://100.102.178.110:8000",  # Tailscale IP (WIN-1FQKL540GRF) - IP updated 2026-01-23
        "http://elated-dhawan-remote.serveo.net:8000"  # Through serveo.net (backup)
    ]

    def __init__(
        self,
        timeout_health: float = 3.0,
        timeout_upload: float = 60.0,
        timeout_poll: float = 10.0,
        cache_ttl: float = 30.0
    ):
        """Initialize remote transcription client.

        Args:
            timeout_health: Timeout for health check (seconds)
            timeout_upload: Timeout for file upload (seconds)
            timeout_poll: Timeout for status polling (seconds)
            cache_ttl: Time-to-live for health check cache (seconds)
        """
        self.session = requests.Session()
        self.timeout_health = timeout_health
        self.timeout_upload = timeout_upload
        self.timeout_poll = timeout_poll
        self.cache_ttl = cache_ttl

        # Health check cache
        self._last_check_time = 0.0
        self._last_check_result = False
        self._cached_server_url = None

        logger.info("RemoteTranscriptionClient initialized")

    def check_server_health(self) -> bool:
        """Check if any server is available (with caching).

        Returns:
            True if at least one server is healthy, False otherwise
        """
        # Check cache first
        now = time.time()
        if now - self._last_check_time < self.cache_ttl:
            logger.debug(f"Using cached health check result: {self._last_check_result}")
            return self._last_check_result

        # Perform actual health check
        for server_url in self.SERVERS:
            try:
                logger.debug(f"Checking server health: {server_url}")
                response = self.session.get(
                    f"{server_url}/health",
                    timeout=self.timeout_health
                )

                if response.status_code == 200:
                    data = response.json()
                    # Server is healthy if it responds (status=200)
                    # transcriber_loaded can be False for testing/fallback
                    self._last_check_result = True
                    self._last_check_time = now
                    self._cached_server_url = server_url
                    logger.info(f"Server healthy: {server_url} (loaded={data.get('transcriber_loaded', False)})")
                    return True

            except requests.exceptions.RequestException as e:
                logger.debug(f"Server {server_url} not available: {e}")
                continue

        # No server available
        self._last_check_result = False
        self._last_check_time = now
        self._cached_server_url = None
        logger.warning("No healthy servers available")
        return False

    def transcribe_remote(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio using remote server.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription fails for any reason
        """
        logger.info("Starting remote transcription...")

        # Check server health first (may use cache)
        if not self.check_server_health():
            raise Exception("No healthy server available")

        if not self._cached_server_url:
            raise Exception("Server URL not available")

        wav_path = None
        try:
            # Save audio to temporary WAV file
            wav_path = self._save_temp_wav(audio, sample_rate)
            logger.info(f"Saved audio to temporary file: {wav_path}")

            # Upload and wait for result
            text = self._upload_and_wait(wav_path)

            logger.info(f"Remote transcription completed, text length: {len(text)}")
            return text

        finally:
            # Clean up temporary file
            if wav_path and wav_path.exists():
                try:
                    wav_path.unlink()
                    logger.debug(f"Deleted temporary file: {wav_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")

    def _save_temp_wav(self, audio: np.ndarray, sample_rate: int) -> Path:
        """Save numpy array to temporary WAV file.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            Path to temporary WAV file
        """
        import soundfile as sf

        # Create temporary file with .wav extension
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        # Save audio as WAV
        sf.write(path, audio, sample_rate)

        logger.debug(f"Saved temporary WAV: {path}")
        return Path(path)

    def _upload_and_wait(self, wav_path: Path) -> str:
        """Upload file to server and wait for transcription result.

        Args:
            wav_path: Path to WAV file

        Returns:
            Transcribed text

        Raises:
            Exception: If upload or transcription fails
        """
        server_url = self._cached_server_url

        # Step 1: Upload file
        logger.info(f"Uploading file to {server_url}/transcribe")

        try:
            with open(wav_path, "rb") as f:
                response = self.session.post(
                    f"{server_url}/transcribe",
                    files={"file": f},
                    timeout=self.timeout_upload
                )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Upload failed: {e}")

        if response.status_code != 200:
            raise Exception(f"Upload failed with status {response.status_code}: {response.text}")

        # Get task_id
        try:
            data = response.json()
            task_id = data["task_id"]
            logger.info(f"Task ID: {task_id}")
        except (ValueError, KeyError) as e:
            raise Exception(f"Invalid response from server: {e}")

        # Step 2: Poll status until completed
        logger.info("Waiting for transcription to complete...")
        start_time = time.time()
        check_interval = 2.0  # seconds

        while True:
            # Check timeout
            if time.time() - start_time > 300:  # 5 minute timeout
                raise Exception("Transcription timeout (5 minutes)")

            try:
                status_response = self.session.get(
                    f"{server_url}/status/{task_id}",
                    timeout=self.timeout_poll
                )
                status = status_response.json()

            except requests.exceptions.RequestException as e:
                raise Exception(f"Status check failed: {e}")

            # Check status
            if status["status"] == "completed":
                elapsed = time.time() - start_time
                logger.info(f"Transcription completed in {elapsed:.1f}s")
                break

            elif status["status"] == "failed":
                error_msg = status.get("error", "Unknown error")
                raise Exception(f"Transcription failed: {error_msg}")

            # Wait before next check
            time.sleep(check_interval)

        # Step 3: Download result
        logger.info(f"Downloading result from {server_url}/result/{task_id}")

        try:
            result_response = self.session.get(
                f"{server_url}/result/{task_id}",
                timeout=self.timeout_poll
            )

            if result_response.status_code != 200:
                raise Exception(f"Failed to download result: {result_response.status_code}")

            text = result_response.text
            logger.info(f"Downloaded result, length: {len(text)}")
            return text

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download result: {e}")
