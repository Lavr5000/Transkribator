"""Main window for ГолосТекст application - Compact WhisperTyping style."""
import sys
import os
import time
import logging
import logging.handlers
import threading
import uuid
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

from .config import Config, MODEL_METADATA
from .audio_recorder import AudioRecorder
from .transcriber import Transcriber, get_available_backends
from .crash_reporter import get_reporter
from . import hotkeys
from .hotkeys import HotkeyManager, type_text, safe_paste_text, paste_from_clipboard
from .history_manager import HistoryManager
from . import versions
from .audio_archive import AudioArchive
from .mouse_handler import MouseButtonHandler
from .widgets import (
    COLORS, COLORS_HEX, COMPACT_HEIGHT, COMPACT_WIDTH,
    RecordButton, CopyButton, SettingsButton, CloseButton, CancelButton,
    ClickableLabel, GradientWidget, TextPopup,
)
from .settings_dialog import SettingsDialog

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
    """Runs one local transcription off the Qt thread.

    Named "hybrid" historically: it used to fall back to a cloud engine and
    to a remote server. Both were removed in 2.4.0 — the app has been
    local-only since 2026-08-24 and made zero network calls after that — so
    the only path left is Sherpa on this machine.
    """
    transcription_done = pyqtSignal(str, float, bool)  # text, duration, is_remote
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
            if self._is_cancelled:
                return
            if text:
                self.transcription_done.emit(text, duration, False)
            else:
                # transcriber.transcribe() already logged the empty_result event.
                self.transcription_error.emit("Пустой результат распознавания")
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
    # Audio device open/close runs in worker threads (WASAPI can stall for
    # minutes and would freeze the GUI thread); results come back via signals
    _start_finished = pyqtSignal(str)  # 'started' | 'warming' | 'error'
    _stop_finished = pyqtSignal(object)  # np.ndarray or None
    _recovery_finished = pyqtSignal(bool)  # WASAPI recovery probe result

    def __init__(self):
        super().__init__()

        self.config = Config.load()
        # Этап 0 (r1-30): research_mode hard-disables paste/clipboard at the
        # hotkeys adapter layer, regardless of call site.
        hotkeys.RESEARCH_MODE_BLOCK = self.config.research_mode
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            on_level_update=self._on_vad_level_update,
            device=self.config.audio_device_legacy_index,
            device_name=self.config.audio_device_name,
            device_hostapi=self.config.audio_hostapi,
            on_device_resolved=self._on_device_resolved,
            mic_boost=self.config.mic_boost,
            webrtc_enabled=self.config.webrtc_enabled,
            noise_suppression_level=self.config.noise_suppression_level,
            capture_wasapi=self.config.capture_wasapi,
        )
        # Configure auto-stop
        self.recorder.auto_stop_enabled = self.config.auto_stop_enabled
        self.recorder.auto_stop_silence_sec = self.config.auto_stop_silence_sec
        self.recorder.on_auto_stop = self._on_auto_stop
        # Warm up the persistent mic stream in the background: on a degraded
        # audio stack the WASAPI open can take 25+ seconds — pay it once at
        # startup, overlapping model load, instead of on every recording
        self.recorder.ensure_stream_async()

        def _make_transcriber(backend, model_size):
            return Transcriber(
                backend=backend,
                model_size=model_size,
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
                legacy_prompt_removed=self.config.legacy_prompt_removed,
            )

        try:
            self.transcriber = _make_transcriber(self.config.backend, self.config.model_size)
        except Exception as e:
            # A stale config.json may point at a backend this install cannot
            # provide (e.g. frozen EXE is sherpa-only). Fall back to the
            # default instead of dying silently on startup.
            logger.error("TRANSCRIBER_INIT_FALLBACK | backend=%s unavailable (%s), using sherpa",
                         self.config.backend, e)
            self.config.backend = "sherpa"
            self.config.model_size = "giga-am-v3-ru-punct"
            self.config.save()
            self.transcriber = _make_transcriber("sherpa", "giga-am-v3-ru-punct")

        self.hotkey_manager = HotkeyManager(on_hotkey=self._on_hotkey)
        self.history_manager = HistoryManager(max_entries=50)
        self.audio_archive = AudioArchive(dpapi_enabled=self.config.audio_archive_dpapi)

        # Initialize mouse button handler
        self.mouse_handler = MouseButtonHandler(
            button=self.config.mouse_button,
            on_click=self._on_mouse_click
        )

        self._thread: Optional[TranscriptionThread] = None
        self._rec_start = 0.0
        self._rec_duration = 0.0  # Длительность записи
        self._transcription_start = 0.0  # Время начала транскрибации
        self._trigger_id = None  # join key with event-log records (Этап 0, r2-8)
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

        # A2: get off a WASAPI→MME fallback instead of staying on MME until the
        # owner notices (2026-09-02: 7 h 40 min / 30 recordings on MME 16 kHz).
        # The timer is armed only when a fallback is actually in effect; the
        # first check waits out the startup warm-up.
        self._recovery_step = 0
        self._recovery_running = False
        self._recovery_timer = QTimer(self)
        self._recovery_timer.setSingleShot(True)
        self._recovery_timer.timeout.connect(self._run_recovery_probe)
        QTimer.singleShot(30_000, self._arm_recovery_if_needed)
        # A missing configured microphone must be visible, not silent.
        QTimer.singleShot(30_000, self._show_device_warning)

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
            self.transcriber,
            self._last_audio,
            self.config.sample_rate,
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

        # Проверяем что popup не уйдет за верх экрана.
        # screenAt() возвращает None, когда окно оказалось за краем экрана
        # (79 % всех падений 26.03–20.08); primaryScreen() тоже None в сеансе
        # без экранов (RDP/headless) — тогда прижим к экрану просто пропускаем.
        screen = QApplication.screenAt(main_pos) or QApplication.primaryScreen()
        popup_y = main_pos.y() - popup_height - 10
        if screen is not None and popup_y < screen.geometry().top() + 50:
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

    def _show_device_warning(self):
        """Surface a stale/absent configured microphone in the status line."""
        warning = getattr(self.recorder, "device_warning", None)
        if warning and not self._recording and not self._processing:
            self.status_update.emit(warning)

    def _on_device_resolved(self, name: str, hostapi: str):
        """A legacy PortAudio index was resolved once — store it as a name."""
        self.config.audio_device_name = name
        self.config.audio_hostapi = hostapi
        self.config.audio_device_legacy_index = -1
        self.config.save()

    # ------------------------------------------------------------------ #
    # A2: WASAPI recovery after an MME fallback                           #
    # ------------------------------------------------------------------ #

    RECOVERY_BACKOFF_MIN = (10, 20, 40, 60)  # capped at 60 min

    @classmethod
    def _recovery_interval_ms(cls, step: int) -> int:
        idx = min(max(step, 0), len(cls.RECOVERY_BACKOFF_MIN) - 1)
        return cls.RECOVERY_BACKOFF_MIN[idx] * 60_000

    def _arm_recovery_if_needed(self):
        """Start (or leave running) the recovery timer iff a fallback is live."""
        if self._shutting_down:
            return
        if not getattr(self.recorder, "capture_fallback_reason", None):
            return
        if self._recovery_timer.isActive() or self._recovery_running:
            return
        delay = self._recovery_interval_ms(self._recovery_step)
        logger.info("RECOVER_ARMED | in %d min | reason=%s",
                    delay // 60_000, self.recorder.capture_fallback_reason)
        self._recovery_timer.start(delay)

    def _run_recovery_probe(self):
        """Timer fired: probe WASAPI in a worker thread, never on the Qt thread."""
        if self._shutting_down or self._recovery_running:
            return
        if not self.recorder.capture_fallback_reason:
            return
        if self._recording or self._processing:
            # Do not touch the device around a dictation — retry the same step.
            self._recovery_timer.start(self._recovery_interval_ms(self._recovery_step))
            return
        deficit = self.recorder.recovery_idle_deficit_s()
        if deficit > 0:
            # Still inside the idle grace — waiting is not a failed attempt,
            # so the backoff must not advance.
            self._recovery_timer.start(int(deficit * 1000) + 1000)
            return

        self._recovery_running = True

        def _worker():
            ok = False
            try:
                ok = self.recorder.try_recover_wasapi()
            except Exception as e:
                logger.error("RECOVER_ERROR | %s: %s", type(e).__name__, e)
            finally:
                self._recovery_finished.emit(bool(ok))

        threading.Thread(target=_worker, daemon=True, name="audio-recover").start()

    def _on_recovery_finished(self, ok: bool):
        """Runs in the Qt thread: reset the backoff on success, advance on failure."""
        self._recovery_running = False
        if ok:
            self._recovery_step = 0
            logger.info("RECOVER_OK | back on WASAPI")
            return
        self._recovery_step = min(self._recovery_step + 1,
                                  len(self.RECOVERY_BACKOFF_MIN) - 1)
        self._arm_recovery_if_needed()

    def _connect_signals(self):
        self.status_update.connect(self._set_status)
        self.audio_level_update.connect(self._set_level)
        # Connect toggle signal for thread-safe hotkey/mouse callbacks
        # This ensures _toggle_recording runs in the main Qt thread
        self._request_toggle.connect(self._toggle_recording, Qt.ConnectionType.QueuedConnection)
        self._start_finished.connect(self._on_start_finished)
        self._stop_finished.connect(self._on_stop_finished)
        self._recovery_finished.connect(self._on_recovery_finished)

    def _load_model(self):
        def _load_with_status():
            self.status_update.emit("Загрузка модели...")
            success = self.transcriber.load_model()
            self.status_update.emit("Готово" if success else "Ошибка загрузки")
        threading.Thread(target=_load_with_status, daemon=True).start()

    def _cleanup_thread(self, timeout_ms: int = 2000):
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
                    self._thread.wait(timeout_ms)
                if self._thread.isRunning():
                    # Still alive after the wait: deleting a running QThread
                    # is undefined behavior — leave it, report not-finished.
                    logger.warning("THREAD_STILL_RUNNING | not deleting live QThread")
                    return False
                # Schedule for deletion
                self._thread.deleteLater()
            except RuntimeError:
                pass  # Thread already deleted
            self._thread = None
        return True

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

        self.status_label.setText("Запуск...")
        self.status_label.show()

        # PlaySound can stall when the audio stack degrades — off the GUI
        # thread. recorder.start() is non-blocking (persistent stream), the
        # SLOW_AUDIO_START warning is a regression signal if it ever fires.
        def _worker():
            t0 = time.time()
            self._play_sound()
            sound_elapsed = time.time() - t0
            result = self.recorder.start()
            total = time.time() - t0
            if total > 1.0:
                logger.warning("SLOW_AUDIO_START | play_sound=%.1fs total=%.1fs", sound_elapsed, total)
            self._start_finished.emit(result)

        threading.Thread(target=_worker, daemon=True, name="audio-start").start()

    def _on_start_finished(self, result: str):
        """Runs in the main Qt thread after recorder.start() returned."""
        if self._shutting_down:
            self._starting = False
            return
        if result == "started":
            self._recording = True
            self._rec_start = time.time()
            self._trigger_id = uuid.uuid4().hex[:12]
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
        elif result == "warming":
            self._starting = False
            self.status_label.setText("Микрофон прогревается — повторите")
            self.status_label.show()
            logger.debug("_start() WARMING: stream not ready yet")
        else:
            self._starting = False
            self.status_label.setText("Ошибка микрофона")
            if not self._hover:
                self.status_label.hide()
            logger.debug("_start() FAILED: recorder.start() returned %s", result)
        # A late re-open may have landed on MME — arm the recovery timer then too.
        self._arm_recovery_if_needed()

    def _stop(self):
        logger.debug("_stop() called, _recording=%s, _processing=%s", self._recording, self._processing)

        self._recording = False
        self._processing = True  # Блокируем повторные вызовы
        self._rec_timer.stop()

        # Сохраняем время записи
        self._rec_duration = time.time() - self._rec_start

        self.status_label.setText("Остановка...")
        self.status_label.show()

        # Device close (WASAPI) can stall — off the GUI thread, same as start
        def _worker():
            t0 = time.time()
            audio = self.recorder.stop()
            if time.time() - t0 > 1.0:
                logger.warning("SLOW_AUDIO_STOP | %.1fs", time.time() - t0)
            self._stop_finished.emit(audio)

        threading.Thread(target=_worker, daemon=True, name="audio-stop").start()

    def _on_stop_finished(self, audio):
        """Runs in the main Qt thread after the audio device closed."""
        if self._shutting_down:
            return
        self._last_audio = audio  # Cache for retry
        QTimer.singleShot(200, self._play_sound)  # 200ms for WASAPI to fully release device

        # Opt-in raw-audio corpus (Этап 0, default off). Runs off the GUI
        # thread — archive I/O must never add to key-release→paste latency.
        if self.config.audio_archive and audio is not None and len(audio) > 0:
            threading.Thread(
                target=lambda: self.audio_archive.save(audio, self.config.sample_rate),
                daemon=True, name="audio-archive-save",
            ).start()

        # Check audio quality and prepare warning header
        self._audio_quality_warning = ""
        if self.recorder.capture_degraded:
            self._audio_quality_warning = "⚠ Микрофон прервался — запись может быть неполной"
        elif self.recorder.clipping_detected:
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

        self._thread = HybridTranscriptionThread(
            self.transcriber,
            audio,
            self.config.sample_rate,
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

        # Останавливаем рекордер (WASAPI close может виснуть — не в GUI-потоке;
        # AudioRecorder._lock сериализует с последующим start)
        threading.Thread(target=self.recorder.stop, daemon=True, name="audio-cancel").start()

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

        logger.debug("Transcription time: %.1fs", transcription_time)

        try:
            self.mode_label.setText("🏠")
            self.mode_label.setToolTip("Локальная транскрибация")
            # Этап 1 (D3): откат WASAPI→MME должен быть виден в UI, а не только
            # в истории. Тултип дополняется, иконка режима не подменяется.
            if self.config.capture_wasapi and self.recorder.capture_rate == self.config.sample_rate:
                self.mode_label.setToolTip(
                    f"{self.mode_label.toolTip()}\nМикрофон: откат на MME 16 кГц "
                    f"({self.recorder.capture_fallback_reason or 'причина не записана'})"
                )
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

        # Схема истории v2 (Этап 0) — собираем поля, известные к моменту
        # завершения транскрибации; audio_duration_s/уровни идут от
        # recorder'а (тот же массив, что был передан на транскрибацию).
        quality_flags = []
        if self.recorder.clipping_detected:
            quality_flags.append("clipping")
        if self.recorder.low_signal:
            quality_flags.append("low_signal")
        if self.recorder.capture_degraded:
            quality_flags.append("capture_degraded")
        # Этап 1 (D3): откат WASAPI→MME должен быть виден, а не молчаливым.
        if self.config.capture_wasapi and self.recorder.capture_rate == self.config.sample_rate:
            quality_flags.append("capture_fallback")
        audio_duration_s = (
            self.recorder.get_duration(self._last_audio) if self._last_audio is not None else None
        )
        self.history_manager.add_entry(
            text, duration, self.config.backend, self.config.model_size,
            audio_duration_s=audio_duration_s,
            rms_dbfs=self.recorder.last_rms_dbfs,
            peak_dbfs=self.recorder.last_peak_dbfs,
            flags=quality_flags,
            dropped_frames=self.recorder.dropped_frames,
            used_fallback=getattr(self.transcriber, "last_used_fallback", False),
            fallback_reason=getattr(self.transcriber, "last_fallback_reason", None),
            device_api=self.recorder.device_api,
            prompt_version=versions.prompt_version(getattr(self.transcriber, "last_prompt_sent", None)),
            dictionary_version=versions.dictionary_version(self.config.user_dictionary),
            trigger_id=self._trigger_id,
        )

        # research_mode (Этап 0, r1-30): experiments must never paste or
        # copy — the adapters below refuse anyway, but the flow is skipped
        # here too so a research run produces no visible side effect at all.
        if not self.config.research_mode:
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

    def _model_changed(self):
        mid = self._settings.model_combo.currentData()
        if self._processing and mid and mid != self.config.model_size:
            self.status_update.emit("Дождитесь окончания транскрибации")
            self._settings.model_combo.blockSignals(True)
            idx = self._settings.model_combo.findData(self.config.model_size)
            if idx >= 0:
                self._settings.model_combo.setCurrentIndex(idx)
            self._settings.model_combo.blockSignals(False)
            return
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
                if not self.transcriber.switch_backend(self.config.backend, mid):
                    raise RuntimeError("транскрибатор занят, попробуйте после окончания")
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
                if self._processing:
                    self.status_update.emit("Дождитесь окончания транскрибации")
                    btn = self._settings.quality_profile_buttons.get(self.config.quality_profile) if self._settings else None
                    if btn is not None:
                        btn.setChecked(True)  # revert; handler no-ops on same profile
                    return
                cr = get_reporter()
                if cr:
                    cr.set_context("QUALITY_PROFILE_CHANGE", profile=profile)
                # Apply profile preset
                self.config.apply_quality_profile(profile)

                # Update transcriber settings. VAD params BEFORE switch_backend:
                # the construction fingerprint includes them, so the rebuild
                # picks up the new values (mutating after would be lost).
                self.transcriber.vad_enabled = self.config.vad_enabled
                self.transcriber.vad_threshold = self.config.vad_threshold
                self.transcriber.min_silence_duration_ms = self.config.min_silence_duration_ms
                self.transcriber.enable_post_processing = self.config.enable_post_processing
                if not self.transcriber.switch_backend(self.config.backend, self.config.model_size):
                    raise RuntimeError("транскрибатор занят, попробуйте после окончания")
                self._load_model()

                # Update UI controls to reflect new values (block signals:
                # combo mutations must not re-fire _backend/_model_changed
                # with intermediate garbage values)
                if self._settings:
                    self._settings.model_combo.blockSignals(True)
                    try:
                        self._settings._update_model_options()
                    finally:
                        self._settings.model_combo.blockSignals(False)

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

        # Stop recording if in progress (bounded ≤2s — no device close here)
        if self._recording:
            self._recording = False
            self._rec_timer.stop()
            try:
                self.recorder.stop()
            except Exception:
                pass

        # Close the persistent stream with a 3s budget: a degraded WASAPI
        # close can take 14s+ — quit never waits for it, process exit reclaims
        close_thread = threading.Thread(target=self.recorder.close_stream, daemon=True)
        close_thread.start()
        close_thread.join(timeout=3.0)
        if close_thread.is_alive():
            logger.warning("AUDIO_CLOSE_INCOMPLETE | stream close still running at quit")

        # Cancel any in-flight transcription, then wait for the worker
        try:
            self.transcriber.cancel()
        except Exception:
            pass
        thread_finished = self._cleanup_thread(timeout_ms=10000)

        # Unload model ONLY when the worker actually finished: unloading
        # under a live native decode corrupts the process. If it is still
        # running after 10s, skip unload — process exit reclaims memory.
        if thread_finished:
            try:
                self.transcriber.unload_model()
            except Exception:
                pass
        else:
            logger.warning("QUIT_SKIP_UNLOAD | transcription still running after 10s wait")

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
