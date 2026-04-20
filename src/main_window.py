"""Main window for ГолосТекст application - Compact WhisperTyping style."""
import sys
import os
import time
import logging
import logging.handlers
import threading
from typing import Optional

try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QSystemTrayIcon, QMenu, QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6 import sip

from config import Config, MODEL_METADATA
from audio_recorder import AudioRecorder
from transcriber import Transcriber, get_available_backends
from crash_reporter import get_reporter
from notifier import TelegramNotifier
from quality_monitor import QualityMonitor
from hotkeys import HotkeyManager, type_text, safe_paste_text, paste_from_clipboard
from history_manager import HistoryManager
from mouse_handler import MouseButtonHandler
from remote_client import RemoteTranscriptionClient
from widgets import (
    COLORS, COLORS_HEX, COMPACT_HEIGHT, COMPACT_WIDTH,
    RecordButton, CopyButton, SettingsButton, CloseButton, CancelButton,
    ClickableLabel, GradientWidget, TextPopup,
)
from settings_dialog import SettingsDialog

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# Configure logging with rotation
_log_dir = os.path.dirname(os.path.abspath(__file__))
_log_path = os.path.join(os.path.dirname(_log_dir), "debug.log")
_handler = logging.handlers.RotatingFileHandler(
    _log_path, maxBytes=512_000, backupCount=2, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger = logging.getLogger("transkribator")
logger.setLevel(logging.DEBUG)
logger.addHandler(_handler)


class TranscriptionThread(QThread):
    transcription_done = pyqtSignal(str, float)  # Renamed to avoid conflict with QThread.finished
    transcription_error = pyqtSignal(str)

    def __init__(self, transcriber, audio, sample_rate: int):
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled:
                return
            text, duration = self.transcriber.transcribe(self.audio, self.sample_rate)
            if not self._is_cancelled:
                self.transcription_done.emit(text, duration)
        except Exception as e:
            if not self._is_cancelled:
                self.transcription_error.emit(str(e))

    def cancel(self):
        """Mark thread as cancelled to prevent signal emission after stop."""
        self._is_cancelled = True


class HybridTranscriptionThread(QThread):
    """Thread for hybrid transcription: LOCAL first, then remote fallback.

    Strategy:
    1. Try local transcription (Sherpa) first with timeout
    2. If local fails or takes >20 seconds, try remote
    3. If remote also fails, return error
    """
    transcription_done = pyqtSignal(str, float, bool)  # text, duration, is_remote
    transcription_error = pyqtSignal(str)

    def __init__(self, remote_client, transcriber, audio, sample_rate: int, enable_remote: bool = False):
        super().__init__()
        self.remote_client = remote_client
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate
        self._is_cancelled = False
        self._enable_remote = enable_remote  # Allow disabling remote fallback
        # Dynamic timeout: min 30s, or 40% of audio duration (for chunked processing)
        audio_duration_sec = len(audio) / sample_rate
        self._local_timeout = max(30.0, audio_duration_sec * 0.4)

    def run(self):
        try:
            if self._is_cancelled:
                return

            # === STEP 1: Try LOCAL transcription first ===
            local_start = time.time()
            try:
                # Use threading.Timer to implement timeout
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        self.transcriber.transcribe,
                        self.audio,
                        self.sample_rate
                    )

                    try:
                        # Wait for local transcription with timeout
                        text, duration = future.result(timeout=self._local_timeout)

                        if not self._is_cancelled and text:
                            # Local transcription successful!
                            self.transcription_done.emit(text, duration, False)  # is_remote=False
                            return

                    except concurrent.futures.TimeoutError:
                        # Local transcription took too long - cancel and try remote
                        future.cancel()
                        self.transcriber.cancel()
                        logger.debug("Local transcription timeout (%.1fs)", self._local_timeout)
                        raise Exception("Local transcription timeout")

            except Exception as local_error:
                # Local transcription failed - try remote fallback
                if not self._is_cancelled:
                    logger.debug("Local transcription failed: %s", local_error)
                    logger.debug("Trying remote fallback...")

            # === STEP 2: Try REMOTE transcription as fallback (if enabled) ===
            if not self._is_cancelled and self._enable_remote:
                try:
                    remote_start = time.time()
                    text = self.remote_client.transcribe_remote(
                        self.audio,
                        self.sample_rate
                    )
                    duration = time.time() - remote_start

                    if not self._is_cancelled and text:
                        # Remote transcription successful (fallback)
                        self.transcription_done.emit(text, duration, True)  # is_remote=True
                        return
                    else:
                        raise Exception("Remote transcription returned empty text")

                except Exception as remote_error:
                    # Both local and remote failed
                    if not self._is_cancelled:
                        logger.debug("Remote transcription also failed: %s", remote_error)
                        self.transcription_error.emit(f"Local and remote failed: {remote_error}")

            # === Remote fallback disabled or not available ===
            elif not self._is_cancelled:
                logger.debug("Local transcription failed, remote fallback disabled")
                self.transcription_error.emit("Local transcription failed. Enable remote fallback in settings if needed.")

        except Exception as e:
            if not self._is_cancelled:
                logger.debug("HybridTranscriptionThread error: %s", e)
                self.transcription_error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True


class MainWindow(QMainWindow):
    status_update = pyqtSignal(str)
    audio_level_update = pyqtSignal(float)
    _request_toggle = pyqtSignal()  # Thread-safe signal for hotkey/mouse callbacks

    def __init__(self):
        super().__init__()

        self.config = Config.load()
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            on_level_update=self._on_vad_level_update,
            device=self.config.audio_device if self.config.audio_device != -1 else None,
            mic_boost=self.config.mic_boost,
            webrtc_enabled=self.config.webrtc_enabled,
            noise_suppression_level=self.config.noise_suppression_level,
        )
        # Configure auto-stop
        self.recorder.auto_stop_enabled = self.config.auto_stop_enabled
        self.recorder.auto_stop_silence_sec = self.config.auto_stop_silence_sec
        self.recorder.on_auto_stop = self._on_auto_stop

        self.transcriber = Transcriber(
            backend=self.config.backend,
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            language=self.config.language,
            on_progress=self._on_progress,
            enable_post_processing=self.config.enable_post_processing,
            # VAD config
            vad_enabled=self.config.vad_enabled,
            vad_threshold=self.config.vad_threshold,
            min_silence_duration_ms=self.config.min_silence_duration_ms,
            min_speech_duration_ms=self.config.min_speech_duration_ms,
            # User dictionary
            user_dictionary=self.config.user_dictionary,
        )

        self.hotkey_manager = HotkeyManager(on_hotkey=self._on_hotkey)
        self.history_manager = HistoryManager(max_entries=50)
        self._quality_monitor = QualityMonitor(TelegramNotifier())

        # Initialize remote transcription client
        self.remote_client = RemoteTranscriptionClient()

        # Initialize mouse button handler
        self.mouse_handler = MouseButtonHandler(
            button=self.config.mouse_button,
            on_click=self._on_mouse_click
        )

        self._thread: Optional[TranscriptionThread] = None
        self._rec_start = 0.0
        self._rec_duration = 0.0  # Длительность записи
        self._transcription_start = 0.0  # Время начала транскрибации
        self._drag_pos = None
        self._settings = None
        self._recording = False
        self._processing = False  # Защита от повторных вызовов во время обработки
        self._last_toggle_time = 0.0  # Для debounce
        self._last_text = ""
        self._hover = False
        self._shutting_down = False  # Флаг для безопасного завершения
        self._starting = False  # Guard against double start press

        self._setup_ui()
        self._setup_tray()
        self._setup_text_popup()
        self._connect_signals()
        self.hotkey_manager.register(self.config.hotkey)

        # Start mouse handler if enabled
        if self.config.enable_mouse_button:
            try:
                self.mouse_handler.start()
            except Exception:
                # Silently fail if pynput is not available
                pass

        # Preload model immediately (in background thread) to eliminate cold start
        QTimer.singleShot(100, self._load_model)

        # Show onboarding tooltip on first run
        if self.config.first_run:
            QTimer.singleShot(500, self._show_onboarding)

    def _setup_ui(self):
        self.setWindowTitle("ГолосТекст")
        self.setFixedSize(COMPACT_WIDTH, COMPACT_HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central = GradientWidget()
        self.central.setMouseTracking(True)
        self.setCentralWidget(self.central)

        # Telegram channel label - always visible, clickable
        self.brand_label = ClickableLabel("AI Vibes", "https://t.me/ai_vibes_coding_ru", self.central)
        self.brand_label.setStyleSheet(f"""
            QLabel {{
                color: #{COLORS_HEX['text_secondary']};
                font-size: 10px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
                opacity: 0.7;
                letter-spacing: 0.3px;
            }}
        """)
        self.brand_label.setFixedWidth(95)
        self.brand_label.move(8, 8)  # Left side, top

        # Status label - слева снизу (зеркально brand_label)
        self.status_label = QLabel("Готово", self.central)
        self.status_label.setStyleSheet(f"color: #{COLORS_HEX['text_primary']}; font-size: 13px; font-weight: 500;")
        self.status_label.setFixedWidth(85)  # Для "Готово", "Слушаю", "Обработка..."
        self.status_label.move(8, 35)  # Левый нижний угол
        self.status_label.hide()  # Скрыт при запуске, показывается при hover

        # Hotkey hint label - shows hotkey in idle state with low opacity
        hotkey_display = self.config.hotkey.replace("+", "+").upper()
        self.hotkey_label = QLabel(hotkey_display, self.central)
        self.hotkey_label.setStyleSheet(f"""
            color: rgba(140, 160, 180, 128);
            font-size: 9px;
            font-weight: 400;
            background: transparent;
        """)
        self.hotkey_label.setFixedWidth(120)
        self.hotkey_label.move(8, 35)  # Same position as status_label

        # Timer label - справа снизу, на одной высоте со статусом
        self.timer_label = QLabel("", self.central)
        self.timer_label.setStyleSheet(f"""
            color: #{COLORS_HEX['accent_secondary']};
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            font-weight: 500;
        """)
        self.timer_label.setFixedWidth(55)  # Компактный "9.9→9.9с"
        self.timer_label.move(COMPACT_WIDTH - 55 - 8, 35)  # Правый нижний угол (340-55-8=277)
        self.timer_label.hide()

        # Mode indicator (local/remote transcription)
        self.mode_label = QLabel("🏠", self.central)
        self.mode_label.setStyleSheet(f"""
            color: #{COLORS_HEX['accent_secondary']};
            font-size: 18px;
            font-weight: bold;
            background: transparent;
            padding: 2px;
        """)
        self.mode_label.setFixedWidth(30)
        self.mode_label.setFixedHeight(30)
        self.mode_label.setToolTip("Локальная транскрибация")
        # Position above timer, more visible
        self.mode_label.move(COMPACT_WIDTH - 55 - 8 - 22, 5)  # Верхний правый угол
        self.mode_label.hide()

        # Center record button
        self.record_btn = RecordButton(self.central)
        self.record_btn.move((COMPACT_WIDTH - 180) // 2, (COMPACT_HEIGHT - 36) // 2)
        self.record_btn.clicked.connect(self._toggle_recording)

        # VAD level bar removed - caused issues and not needed
        self.vad_level_bar = None

        # Corner buttons (top-right, small)
        btn_y = 6
        btn_spacing = 20

        self.close_btn = CloseButton(self.central)
        self.close_btn.move(COMPACT_WIDTH - 24, btn_y)
        self.close_btn.clicked.connect(self._quit)

        # Cancel button - показывается только во время записи, отменяет запись
        self.cancel_btn = CancelButton(self.central)
        self.cancel_btn.move(COMPACT_WIDTH - 24, btn_y)  # Поверх close_btn
        self.cancel_btn.clicked.connect(self._cancel_recording)
        self.cancel_btn.set_opacity(0.0)  # Скрыт по умолчанию
        self.cancel_btn.hide()

        self.settings_btn = SettingsButton(self.central)
        self.settings_btn.move(COMPACT_WIDTH - 24 - btn_spacing, btn_y)
        self.settings_btn.clicked.connect(self._show_settings)

        self.copy_btn = CopyButton(self.central)
        self.copy_btn.move(COMPACT_WIDTH - 24 - btn_spacing * 2, btn_y)
        self.copy_btn.clicked.connect(self._copy_last)

        self._corner_btns = [self.copy_btn, self.settings_btn, self.close_btn]
        self._set_corner_opacity(0.15)  # Slightly visible in idle state

        # Recording timer
        self._rec_timer = QTimer()
        self._rec_timer.timeout.connect(self._update_timer)

    def _set_corner_opacity(self, opacity: float):
        for btn in self._corner_btns:
            btn.set_opacity(opacity)

    def enterEvent(self, event):
        self._hover = True
        self._set_corner_opacity(0.9)
        # Показываем статус "Готово" при наведении
        if self.status_label.text() == "Готово":
            self.status_label.show()
            self.hotkey_label.hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._set_corner_opacity(0.15)
        # Скрываем статус "Готово" когда мышка ушла
        if self.status_label.text() == "Готово":
            self.status_label.hide()
            if not self._recording and not self._processing:
                self.hotkey_label.show()
        super().leaveEvent(event)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)

        import os as _os
        _ico_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            'Transkribator_icon.ico'
        )
        app_icon = QIcon(_ico_path) if _os.path.exists(_ico_path) else QIcon()
        self.tray.setIcon(app_icon)
        self.setWindowIcon(app_icon)

        menu = QMenu()
        menu.addAction("Показать", self.show)
        menu.addAction("Настройки", self._show_settings)
        self.tray_rec = menu.addAction("Запись", self._toggle_recording)
        menu.addSeparator()
        menu.addAction("Выход", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

    def _setup_text_popup(self):
        """Создаём всплывающую панель для отображения текста."""
        self._text_popup = TextPopup()
        self._text_popup.copy_requested.connect(self._copy_from_popup)
        self._text_popup.text_accepted.connect(self._on_popup_accepted)
        self._text_popup.text_discarded.connect(self._on_popup_discarded)
        self._text_popup.hide()
        self._last_audio = None  # Cached audio for retry

    def _copy_from_popup(self):
        """Копировать текст из всплывающей панели."""
        text = self._text_popup.get_text()
        if text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                self.status_label.setText("Скопировано!")
                self.status_label.show()  # Показываем статус копирования
                QTimer.singleShot(1500, self._restore_status_after_copy)
            except Exception:
                pass

    def _restore_status_after_copy(self):
        """Восстановить статус после копирования."""
        if not self._recording:
            self.status_label.setText("Готово")
            # Скрываем "Готово" если нет hover
            if not self._hover:
                self.status_label.hide()

    def _on_popup_accepted(self, text: str):
        """User accepted (or timeout auto-accepted) text from popup."""
        if not text:
            return
        # Update clipboard with possibly edited text
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
            except Exception:
                pass
        # Auto-paste already handled in _done() immediately after transcription

    def _on_popup_discarded(self):
        """User discarded transcription from popup."""
        self.status_label.setText("Отменено")
        self.status_label.show()
        QTimer.singleShot(1500, self._restore_status_after_copy)

    def _retry_transcription(self):
        """Retry transcription with cached audio."""
        if self._last_audio is None:
            return
        self._text_popup.hide()
        self._processing = True
        self.status_label.setText("Обработка...")
        self.status_label.show()
        self._transcription_start = time.time()
        self._cleanup_thread()
        self._thread = HybridTranscriptionThread(
            self.remote_client,
            self.transcriber,
            self._last_audio,
            self.config.sample_rate,
            enable_remote=getattr(self.config, 'enable_remote_fallback', False)
        )
        self._thread.transcription_done.connect(self._done)
        self._thread.transcription_error.connect(self._error)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        logger.debug("_retry_transcription(): retry started")

    def _show_text_popup(self, text: str):
        """Показать всплывающую панель с текстом сверху окна."""
        if not text:
            return

        # Show audio quality warning if detected
        warning = getattr(self, '_audio_quality_warning', '')
        self._text_popup.set_header(warning)
        self._text_popup.set_text(text)
        # Позиционируем сверху главного окна
        main_pos = self.pos()
        popup_height = self._text_popup.height()

        # Проверяем что popup не уйдет за верх экрана
        screen_geometry = QApplication.screenAt(main_pos).geometry()
        popup_y = main_pos.y() - popup_height - 10
        if popup_y < screen_geometry.top() + 50:
            # Если не помещается сверху, показываем снизу
            popup_y = main_pos.y() + self.height() + 10

        self._text_popup.move(main_pos.x(), popup_y)
        self._text_popup.show_with_timeout(5000)

        # Также Raise для гарантии что окно сверху
        self._text_popup.raise_()

    def _on_auto_stop(self):
        """Called from audio thread when silence exceeds auto_stop threshold."""
        try:
            if not self._shutting_down and self._recording:
                self._request_toggle.emit()
        except RuntimeError:
            pass

    def _show_onboarding(self):
        """Show first-run onboarding tooltip."""
        hotkey = self.config.hotkey.replace("+", "+").upper()
        tip = f"Нажмите {hotkey} или кнопку микрофона для записи.\nНастройки — при наведении справа."
        self._text_popup.set_header("Добро пожаловать!")
        self._show_text_popup(tip)
        self._text_popup._text_edit.setReadOnly(True)
        self._text_popup._accept_btn.hide()
        self._text_popup._copy_btn.hide()
        self._text_popup.show_with_timeout(8000)
        self.config.first_run = False
        self.config.save()

    _NOTIFY_WAV = r"C:\Windows\Media\Windows Notify System Generic.wav"

    def _play_sound(self):
        """Play soft Windows notification .wav file (non-blocking, no PC-speaker fallback)."""
        if not WINSOUND_AVAILABLE or not self.config.sound_feedback:
            return
        winsound.PlaySound(None, winsound.SND_PURGE)  # Cancel previous to prevent overlap
        winsound.PlaySound(
            self._NOTIFY_WAV,
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )

    def _connect_signals(self):
        self.status_update.connect(self._set_status)
        self.audio_level_update.connect(self._set_level)
        # Connect toggle signal for thread-safe hotkey/mouse callbacks
        # This ensures _toggle_recording runs in the main Qt thread
        self._request_toggle.connect(self._toggle_recording, Qt.ConnectionType.QueuedConnection)

    def _load_model(self):
        def _load_with_status():
            self.status_update.emit("Загрузка модели...")
            success = self.transcriber.load_model()
            self.status_update.emit("Готово" if success else "Ошибка загрузки")
        threading.Thread(target=_load_with_status, daemon=True).start()

    def _cleanup_thread(self):
        """Safely cleanup the transcription thread."""
        if self._thread is not None:
            try:
                # Cancel thread to prevent signal emission
                self._thread.cancel()
                # Disconnect signals to prevent callbacks to deleted objects
                try:
                    self._thread.transcription_done.disconnect()
                    self._thread.transcription_error.disconnect()
                    self._thread.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass  # Already disconnected
                # Wait for thread to finish (with timeout)
                if self._thread.isRunning():
                    self._thread.wait(2000)  # 2 second timeout
                # Schedule for deletion
                self._thread.deleteLater()
            except RuntimeError:
                pass  # Thread already deleted
            self._thread = None

    def _on_thread_finished(self):
        """Called when QThread finishes (after run() completes)."""
        # This is called from QThread.finished signal
        # We schedule deleteLater here for safety
        if self._thread is not None and not self._shutting_down:
            try:
                self._thread.deleteLater()
            except RuntimeError:
                pass

    def _on_audio_level(self, level):
        try:
            # Проверяем что окно ещё существует и не закрывается
            if not self._shutting_down and not sip.isdeleted(self):
                self.audio_level_update.emit(min(1.0, level * 10))
        except (RuntimeError, AttributeError):
            pass  # Widget destroyed or shutting down

    def _on_vad_level_update(self, level: float):
        """Update VAD level bar based on audio level (speech detection).

        Args:
            level: Audio level from 0.0 (silence) to 1.0 (loud speech)
        """
        try:
            # Проверяем что окно ещё существует и не закрывается
            if not self._shutting_down and not sip.isdeleted(self):
                # Route audio level to RecordButton visualizer
                self.audio_level_update.emit(min(1.0, level * 10))

                # Convert level to percentage with higher gain for better sensitivity
                # Audio levels are typically very small (0.001-0.1), so we amplify
                percentage = min(100, int(level * 10000))

                # Update the level bar (if exists)
                if self.vad_level_bar:
                    self.vad_level_bar.setValue(percentage)

                # VAD level bar removed - no color changes needed
        except (RuntimeError, AttributeError) as e:
            logger.debug("VAD_UI_ERROR | %s", e)

    def _on_progress(self, msg):
        self.status_update.emit(msg)

    def _on_hotkey(self):
        """Called from hotkey thread - emit signal for thread-safe handling."""
        try:
            if not self._shutting_down:
                self._request_toggle.emit()
        except RuntimeError:
            pass  # Widget destroyed

    def _on_mouse_click(self):
        """Called from mouse handler thread - emit signal for thread-safe handling."""
        try:
            if not self._shutting_down:
                self._request_toggle.emit()
        except RuntimeError:
            pass  # Widget destroyed

    def _toggle_recording(self):
        # Защита от повторных вызовов во время обработки транскрибации
        if self._processing:
            logger.debug("_toggle_recording BLOCKED by _processing flag")
            return

        if self._starting:
            logger.debug("_toggle_recording BLOCKED by _starting flag")
            return

        # Debounce: блокируем только ПОВТОРНЫЙ запуск, не остановку!
        if not self._recording:
            current_time = time.time()
            if current_time - self._last_toggle_time < 0.3:
                logger.debug("_toggle_recording START BLOCKED by debounce (%.3fs)", current_time - self._last_toggle_time)
                return
            self._last_toggle_time = current_time

        logger.debug("_toggle_recording: _recording=%s, _processing=%s", self._recording, self._processing)

        if self._recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        logger.debug("_start() called, _recording=%s, _processing=%s", self._recording, self._processing)
        self._starting = True

        # Reset VAD level bar to silence state (if exists)
        if self.vad_level_bar:
            self.vad_level_bar.setValue(0)

        self._play_sound()  # Play BEFORE opening audio stream to avoid device conflict
        if self.recorder.start():
            self._recording = True
            self._rec_start = time.time()
            self.hotkey_label.hide()
            self.status_label.setText("Слушаю")
            self.status_label.show()  # Показываем статус при записи
            self.timer_label.setText("0.0с")
            self.timer_label.show()
            self.record_btn.set_recording(True)
            self._rec_timer.start(100)
            self.tray_rec.setText("Стоп")

            # Показываем кнопку отмены, скрываем кнопку закрытия
            self.cancel_btn.set_opacity(1.0)
            self.cancel_btn.show()
            self.close_btn.hide()

            self._starting = False
            logger.debug("_start() SUCCESS: recording started")
        else:
            self._starting = False
            logger.debug("_start() FAILED: recorder.start() returned False")

    def _stop(self):
        logger.debug("_stop() called, _recording=%s, _processing=%s", self._recording, self._processing)

        self._recording = False
        self._processing = True  # Блокируем повторные вызовы
        self._rec_timer.stop()

        # Сохраняем время записи
        self._rec_duration = time.time() - self._rec_start

        audio = self.recorder.stop()
        self._last_audio = audio  # Cache for retry
        QTimer.singleShot(200, self._play_sound)  # 200ms for WASAPI to fully release device

        # Check audio quality and prepare warning header
        self._audio_quality_warning = ""
        if self.recorder.clipping_detected:
            self._audio_quality_warning = "⚠ Обнаружено искажение (перегрузка)"
        elif self.recorder.low_signal:
            self._audio_quality_warning = "⚠ Слабый сигнал микрофона"

        self.timer_label.hide()
        self.record_btn.set_recording(False)
        self.tray_rec.setText("Запись")

        # Скрываем кнопку отмены, показываем кнопку закрытия
        self.cancel_btn.hide()
        self.close_btn.show()

        logger.debug("_stop(): audio is None=%s, len=%s", audio is None, len(audio) if audio is not None else 0)

        if audio is None or len(audio) == 0 or self.recorder.get_duration(audio) < 0.5:
            self.status_label.setText("Готово")
            # Скрываем "Готово" если нет hover
            if not self._hover:
                self.status_label.hide()
            self._processing = False  # Разблокируем
            logger.debug("_stop(): audio too short, _processing set to False")
            return

        self.status_label.setText("Обработка...")
        self.status_label.show()  # Показываем статус при обработке
        self._transcription_start = time.time()  # Фиксируем начало транскрибации

        # Cleanup previous thread if exists
        self._cleanup_thread()

        # Use hybrid transcription (LOCAL first, then remote fallback if enabled)
        self._thread = HybridTranscriptionThread(
            self.remote_client,
            self.transcriber,
            audio,
            self.config.sample_rate,
            enable_remote=getattr(self.config, 'enable_remote_fallback', False)
        )
        self._thread.transcription_done.connect(self._done)
        self._thread.transcription_error.connect(self._error)
        self._thread.finished.connect(self._on_thread_finished)  # QThread.finished for cleanup
        self._thread.start()

        logger.debug("_stop(): transcription thread started, _processing=%s", self._processing)

    def _cancel_recording(self):
        """Отменить запись без транскрибации."""
        logger.debug("_cancel_recording() called")

        # Reset VAD level bar to silence state (if exists)
        if self.vad_level_bar:
            self.vad_level_bar.setValue(0)

        if not self._recording:
            return

        # Останавливаем запись и сбрасываем флаги
        self._recording = False
        self._processing = False
        self._rec_timer.stop()

        # Останавливаем рекордер
        self.recorder.stop()

        # Сбрасываем UI
        self.timer_label.hide()
        self.record_btn.set_recording(False)
        self.tray_rec.setText("Запись")
        self.status_label.setText("Отменено")
        self.status_label.show()  # Показываем статус отмены

        # Скрываем кнопку отмены, показываем кнопку закрытия
        self.cancel_btn.hide()
        self.close_btn.show()

        logger.debug("_cancel_recording(): recording cancelled")

    def _update_timer(self):
        elapsed = time.time() - self._rec_start
        self.timer_label.setText(f"{elapsed:.1f}с")

    def _done(self, text, duration, is_remote=False):
        """
        Called when transcription is done.

        Args:
            text: Transcribed text
            duration: Transcription duration in seconds
            is_remote: True if remote transcription was used, False if local fallback
        """
        logger.debug("_done() called, setting _processing=False, text_len=%d, is_remote=%s", len(text), is_remote)

        # Reset VAD level bar to silence state (if exists)
        if self.vad_level_bar:
            self.vad_level_bar.setValue(0)

        # Check if we're shutting down
        if self._shutting_down:
            return

        self._processing = False  # Разблокируем
        self._last_text = text

        # Вычисляем время транскрибации
        transcription_time = time.time() - self._transcription_start

        # Показываем время записи → время транскрибации на 2 секунды
        self.status_label.setText("Готово")
        # Скрываем "Готово" если нет hover
        if not self._hover:
            self.status_label.hide()
        self.timer_label.setText(f"{self._rec_duration:.1f}→{transcription_time:.1f}с")
        self.timer_label.show()

        # Show mode indicator (local/remote)
        logger.debug("Transcription time: %.1fs, is_remote=%s", transcription_time, is_remote)

        try:
            if is_remote:  # Remote transcription successful
                self.mode_label.setText("🌐")
                self.mode_label.setToolTip("Удаленная транскрибация")
                logger.debug("Mode: REMOTE (is_remote=True)")
            elif getattr(self.transcriber, 'last_used_fallback', False):
                # Groq backend fell back to Sherpa
                self.mode_label.setText("⚡")
                self.mode_label.setToolTip("Sherpa (Groq fallback)")
                logger.debug("Mode: FALLBACK (Groq→Sherpa)")
            else:  # Local transcription
                self.mode_label.setText("🏠")
                self.mode_label.setToolTip("Локальная транскрибация")
                logger.debug("Mode: LOCAL (is_remote=False)")
            self.mode_label.show()

            logger.debug("Mode label shown: %s", self.mode_label.text())
        except Exception as e:
            logger.error("Failed to show mode_label: %s", e)

        QTimer.singleShot(5000, self._hide_timer_after_done)  # Changed to 5 seconds

        # Убеждаемся что кнопка закрытия видна (на всякий случай)
        self.cancel_btn.hide()
        self.close_btn.show()

        if self._settings and self._settings.isVisible():
            self._settings.update_stats_display()
            self._settings._update_history_display()

        self.config.update_stats(len(text.split()), self._rec_duration)
        self.history_manager.add_entry(text, duration, self.config.backend, self.config.model_size)
        self._quality_monitor.record_result(
            text_len=len(text),
            audio_duration=self._rec_duration,
            backend=self.config.backend,
            model=self.config.model_size,
        )

        # Авто-копирование в буфер обмена
        if self.config.auto_copy and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
            except Exception:
                pass

        # Auto-paste immediately, then show popup for reference/editing
        if self.config.auto_paste:
            QTimer.singleShot(100, lambda: self._type(text))
        self._show_text_popup(text)

        logger.debug("_done() finished, _processing=%s", self._processing)

    def _hide_timer_after_done(self):
        """Скрыть таймер после показа результата."""
        if not self._recording:
            self.timer_label.hide()
            self.mode_label.hide()
            # Restore hotkey hint when idle
            if not self.status_label.isVisible():
                self.hotkey_label.show()

    def _error(self, err):
        # Check if we're shutting down
        if self._shutting_down:
            return

        self._processing = False  # Разблокируем

        # Map error to user-friendly message
        err_str = str(err).lower()
        if "timeout" in err_str or "timed out" in err_str:
            user_msg = "Превышено время ожидания"
        elif "connection" in err_str or "network" in err_str or "unreachable" in err_str:
            user_msg = "Сервер недоступен"
        elif "model" in err_str or "recognizer" in err_str or "onnx" in err_str:
            user_msg = "Ошибка модели"
        elif "audio" in err_str or "microphone" in err_str:
            user_msg = "Ошибка аудио"
        else:
            user_msg = "Ошибка транскрибации"

        self.status_label.setText("Ошибка")
        self.status_label.show()

        # Show error in popup with retry button
        self._show_error_popup(user_msg)

        # Возвращаем кнопку закрытия при ошибке
        self.cancel_btn.hide()
        self.close_btn.show()

        logger.debug("_error() called: %s -> %s", err, user_msg)
        self._quality_monitor.record_result(
            text_len=0,
            audio_duration=0,
            backend=self.config.backend,
            model=self.config.model_size,
        )

    def _show_error_popup(self, message: str):
        """Show error message in TextPopup with retry button."""
        retry_cb = self._retry_transcription if self._last_audio is not None else None
        self._text_popup.show_error(message, retry_callback=retry_cb)
        main_pos = self.pos()
        popup_height = self._text_popup.height()
        screen_geometry = QApplication.screenAt(main_pos).geometry()
        popup_y = main_pos.y() - popup_height - 10
        if popup_y < screen_geometry.top() + 50:
            popup_y = main_pos.y() + self.height() + 10
        self._text_popup.move(main_pos.x(), popup_y)
        self._text_popup.show_with_timeout(8000)
        self._text_popup.raise_()

    def _type(self, text):
        """Paste or type text based on config.paste_method."""
        try:
            if self.config.paste_method == "clipboard":
                # Safe method: copy to clipboard + Ctrl+Shift+V
                # This doesn't crash terminal apps like Claude Code
                safe_paste_text(text, use_terminal_shortcut=True, delay_before_paste=self.config.paste_delay)
            else:
                # Legacy method: type characters one by one (can crash Claude Code!)
                type_text(text)
        except Exception as e:
            logger.warning("PASTE_TYPE_ERROR | %s", e)

    def _set_status(self, msg):
        self.status_label.setText(msg)
        # "Готово" скрывается без hover, остальные статусы видны всегда
        if msg == "Готово" and not self._hover:
            self.status_label.hide()
        else:
            self.status_label.show()

    def _set_level(self, level):
        if self._recording:
            self.record_btn.set_audio_level(level)

    def _copy_last(self):
        # Приоритет: текст из popup, затем _last_text
        text = self._text_popup.get_text() if self._text_popup.get_text() else self._last_text
        if text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                self.status_label.setText("Скопировано!")
                self.status_label.show()  # Показываем статус копирования
                QTimer.singleShot(1500, self._restore_status_after_copy)
            except Exception:
                pass

    def _show_history(self):
        self._show_settings()
        if self._settings:
            self._settings.tabs.setCurrentIndex(1)

    def _show_settings(self):
        """Show settings dialog."""
        try:
            if not self._settings:
                self._settings = SettingsDialog(self, self.config, self.history_manager)

                # Connect quality profile button group (radio-like behavior)
                profile_ids = {0: "fast", 1: "balanced", 2: "quality"}
                self._settings.quality_profile_group.idClicked.connect(
                    lambda btn_id: self._quality_profile_changed(profile_ids.get(btn_id, "balanced"))
                )

                # Connect backend change to update models
                self._settings.backend_combo.currentIndexChanged.connect(self._backend_changed)

                # Init auto-stop controls
                self._init_auto_stop_controls()

                # Connect sound feedback checkbox
                self._settings.sound_feedback_cb.toggled.connect(self._sound_feedback_changed)

                # Connect mouse button settings
                self._settings.enable_mouse_button_cb.toggled.connect(self._on_mouse_setting_changed)
                self._settings.mouse_button_combo.currentIndexChanged.connect(self._on_mouse_setting_changed)

                # Connect model selection
                self._settings.model_combo.currentIndexChanged.connect(self._model_changed)

            self._settings.move(self.pos().x(), self.pos().y() + self.height() + 10)
            self._settings.show()
            self._settings.raise_()
            # Refresh history and stats on every open (dialog is cached)
            try:
                self._settings._update_history_display()
                self._settings.update_stats_display()
            except Exception:
                pass
        except Exception as e:
            logger.error("SHOW_SETTINGS_FAILED | %s", e, exc_info=True)
            QMessageBox.information(self, "Ошибка", f"Не удалось открыть настройки:\n{e}")

    def _backend_changed(self):
        bid = self._settings.backend_combo.currentData()
        if bid != self.config.backend:
            old_backend = self.config.backend
            old_model = self.config.model_size
            cr = get_reporter()
            if cr:
                cr.set_context("BACKEND_SWITCH", backend=bid, previous_backend=old_backend)
            try:
                self.config.backend = bid
                self._settings.model_combo.blockSignals(True)
                self._settings._update_model_options()
                self._settings.model_combo.blockSignals(False)
                default = {"whisper": "base", "sherpa": "giga-am-v3-ru", "podlodka-turbo": "podlodka-turbo", "groq": "whisper-large-v3-turbo"}.get(bid, "base")
                self.config.model_size = default
                self.config.save()
                self.transcriber.switch_backend(bid, default)
                self._load_model()
                self._update_model_info_label()
            except Exception as e:
                self._settings.model_combo.blockSignals(False)
                logger.error("BACKEND_SWITCH_FAILED | %s", e, exc_info=True)
                self.config.backend = old_backend
                self.config.model_size = old_model
                self.config.save()
                self._settings.model_combo.blockSignals(True)
                self._settings._update_model_options()
                self._settings.model_combo.blockSignals(False)
                self.status_update.emit(f"Ошибка смены бэкенда: {e}")

    def _model_changed(self):
        mid = self._settings.model_combo.currentData()
        if mid and mid != self.config.model_size:
            # Check RAM requirement
            meta = MODEL_METADATA.get(mid, {})
            ram_mb = meta.get("ram_mb", 0)

            if ram_mb > 2000:
                reply = QMessageBox.question(
                    self, "Предупреждение",
                    f"Эта модель требует ~{ram_mb}MB RAM.\n"
                    f"Может работать медленно на старых системах.\n\n"
                    f"Продолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    # Revert to previous model
                    idx = self._settings.model_combo.findData(self.config.model_size)
                    if idx >= 0:
                        self._settings.model_combo.setCurrentIndex(idx)
                    return

            cr = get_reporter()
            if cr:
                cr.set_context("MODEL_SWITCH", backend=self.config.backend, model=mid)
            try:
                self.config.model_size = mid
                self.config.save()
                self.transcriber.switch_backend(self.config.backend, mid)
                self._load_model()
                self._update_model_info_label()
            except Exception as e:
                logger.error("MODEL_SWITCH_FAILED | %s", e, exc_info=True)
                self.status_update.emit(f"Ошибка смены модели: {e}")

    def _update_model_info_label(self):
        """Update model info label below dropdown."""
        if not hasattr(self._settings, 'model_info_label'):
            return

        mid = self.config.model_size
        meta = MODEL_METADATA.get(mid, {})
        ram = meta.get("ram_mb", "?")
        rtf = meta.get("rtf", "?")
        self._settings.model_info_label.setText(f"RAM: ~{ram}MB | RTF: {rtf}x")

    def _lang_changed(self):
        lid = self._settings.lang_combo.currentData()
        self.config.language = lid
        self.config.save()
        self.transcriber.language = lid if lid != "auto" else None

    def _paste_method_changed(self):
        """Handle paste method change."""
        method = self._settings.paste_method_combo.currentData()
        if method and method != self.config.paste_method:
            self.config.paste_method = method
            self.config.save()

    def _top_changed(self, checked):
        self.config.always_on_top = checked
        self.config.save()
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _post_changed(self, checked):
        self.config.enable_post_processing = checked
        self.config.save()
        self.transcriber.enable_post_processing = checked

    def _quality_profile_changed(self, profile: str):
        """Handle quality profile change."""
        try:
            if profile != self.config.quality_profile:
                cr = get_reporter()
                if cr:
                    cr.set_context("QUALITY_PROFILE_CHANGE", profile=profile)
                # Apply profile preset
                self.config.apply_quality_profile(profile)

                # Update transcriber settings
                self.transcriber.switch_backend(self.config.backend, self.config.model_size)
                self.transcriber.vad_threshold = self.config.vad_threshold
                self.transcriber.min_silence_duration_ms = self.config.min_silence_duration_ms
                self.transcriber.enable_post_processing = self.config.enable_post_processing

                # Update UI controls to reflect new values
                if self._settings:
                    # Update backend combo
                    backend_idx = self._settings.backend_combo.findData(self.config.backend)
                    if backend_idx >= 0:
                        self._settings.backend_combo.setCurrentIndex(backend_idx)

                    # Update model combo (will refresh based on backend)
                    self._settings._update_model_options()

                logger.info("QUALITY_PROFILE_CHANGED | %s", profile)
        except Exception as e:
            logger.error("QUALITY_PROFILE_CHANGE_FAILED | %s", e, exc_info=True)

    def _init_vad_controls(self):
        """Initialize VAD controls from config values."""
        # Set threshold slider
        threshold_value = int(self.config.vad_threshold * 100)
        self._settings.vad_threshold_slider.setValue(threshold_value)
        self._settings.vad_threshold_value.setText(f"{self.config.vad_threshold:.2f}")

        # Set silence slider
        self._settings.min_silence_slider.setValue(self.config.min_silence_duration_ms)
        self._settings.min_silence_value.setText(f"{self.config.min_silence_duration_ms}мс")

        # Connect signals
        self._settings.vad_threshold_slider.valueChanged.connect(self._vad_threshold_changed)
        self._settings.min_silence_slider.valueChanged.connect(self._min_silence_changed)

    def _vad_threshold_changed(self, value: int):
        """Handle VAD threshold slider change."""
        threshold = value / 100.0
        self.config.vad_threshold = threshold
        self.config.save()
        self.transcriber.vad_threshold = threshold
        self._settings.vad_threshold_value.setText(f"{threshold:.2f}")

    def _min_silence_changed(self, value: int):
        """Handle min silence duration slider change."""
        self.config.min_silence_duration_ms = value
        self.config.save()
        self.transcriber.min_silence_duration_ms = value
        self._settings.min_silence_value.setText(f"{value}мс")

    def _reset_vad_defaults(self):
        """Reset VAD settings to defaults."""
        self.config.vad_threshold = 0.5
        self.config.min_silence_duration_ms = 800
        self.config.save()
        self.transcriber.vad_threshold = 0.5
        self.transcriber.min_silence_duration_ms = 800

        # Update UI
        self._settings.vad_threshold_slider.setValue(50)
        self._settings.min_silence_slider.setValue(800)

    def _init_noise_controls(self):
        """Initialize noise reduction controls from config values."""
        # Set checkbox
        self._settings.webrtc_enabled_cb.setChecked(self.config.webrtc_enabled)

        # Set noise level slider
        self._settings.noise_level_slider.setValue(self.config.noise_suppression_level)
        self._update_noise_level_label(self.config.noise_suppression_level)

        # Update status indicator
        self._update_noise_status()

        # Connect signals
        self._settings.webrtc_enabled_cb.toggled.connect(self._webrtc_enabled_changed)
        self._settings.noise_level_slider.valueChanged.connect(self._noise_level_changed)

    def _webrtc_enabled_changed(self, checked: bool):
        """Handle WebRTC enabled checkbox change."""
        self.config.webrtc_enabled = checked
        self.config.save()
        self._update_noise_status()

    def _noise_level_changed(self, value: int):
        """Handle noise level slider change."""
        self.config.noise_suppression_level = value
        self.config.save()
        self._update_noise_level_label(value)

    def _update_noise_level_label(self, level: int):
        """Update noise level text label."""
        labels = ["Выкл", "Слабо", "Умеренно", "Сильно", "Очень сильно"]
        self._settings.noise_level_value.setText(labels[level] if 0 <= level < len(labels) else "Умеренно")

    def _update_noise_status(self):
        """Update noise reduction status indicator."""
        if hasattr(self._settings, 'noise_status_label'):
            if self.config.webrtc_enabled:
                self._settings.noise_status_label.setText("(Активно)")
                self._settings.noise_status_label.setStyleSheet(f"color: {COLORS['accent_secondary']};")
            else:
                self._settings.noise_status_label.setText("(Отключено)")
                self._settings.noise_status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")

    def _reset_noise_defaults(self):
        """Reset noise reduction settings to defaults."""
        self.config.webrtc_enabled = True
        self.config.noise_suppression_level = 2
        self.config.save()

        # Update UI
        self._settings.webrtc_enabled_cb.setChecked(True)
        self._settings.noise_level_slider.setValue(2)
        self._update_noise_status()

    def _init_auto_stop_controls(self):
        """Initialize auto-stop controls from config values."""
        self._settings.auto_stop_cb.setChecked(self.config.auto_stop_enabled)
        slider_val = int(self.config.auto_stop_silence_sec * 10)
        self._settings.auto_stop_slider.setValue(slider_val)
        self._settings.auto_stop_value.setText(f"{self.config.auto_stop_silence_sec:.1f}с")

        self._settings.auto_stop_cb.toggled.connect(self._auto_stop_enabled_changed)
        self._settings.auto_stop_slider.valueChanged.connect(self._auto_stop_silence_changed)

    def _sound_feedback_changed(self, checked: bool):
        self.config.sound_feedback = checked
        self.config.save()

    def _auto_stop_enabled_changed(self, checked: bool):
        self.config.auto_stop_enabled = checked
        self.config.save()
        self.recorder.auto_stop_enabled = checked

    def _auto_stop_silence_changed(self, value: int):
        sec = value / 10.0
        self.config.auto_stop_silence_sec = sec
        self.config.save()
        self.recorder.auto_stop_silence_sec = sec
        self._settings.auto_stop_value.setText(f"{sec:.1f}с")

    def _on_mouse_setting_changed(self, value=None):
        """Обновить настройку мыши и перезапустить обработчик."""
        # Update config from UI
        self.config.enable_mouse_button = self._settings.enable_mouse_button_cb.isChecked()
        self.config.mouse_button = self._settings.mouse_button_combo.currentData()
        self.config.save()

        # Restart mouse handler with new settings
        self.mouse_handler.stop()
        if self.config.enable_mouse_button:
            self.mouse_handler.button = self.config.mouse_button
            try:
                self.mouse_handler.start()
            except Exception as e:
                # Silently fail if pynput is not available
                pass

    def _tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show() if not self.isVisible() else self.hide()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def closeEvent(self, e):
        e.ignore()
        self.hide()

    def _quit(self):
        self._shutting_down = True

        # Stop recording if in progress
        if self._recording:
            self._recording = False
            self._rec_timer.stop()
            try:
                self.recorder.stop()
            except Exception:
                pass

        # Cleanup transcription thread
        self._cleanup_thread()

        # Unload model to free memory
        try:
            self.transcriber.unload_model()
        except Exception:
            pass

        self.hotkey_manager.unregister()
        self.mouse_handler.stop()
        self.tray.hide()
        self.config.save()
        QApplication.quit()


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("ГолосТекст")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    return app.exec()
