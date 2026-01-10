"""Main window for WhisperTyping application."""
import sys
import time
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QGroupBox, QTabWidget,
    QProgressBar, QSystemTrayIcon, QMenu, QMessageBox,
    QFrame, QSizePolicy, QApplication, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QIcon, QPixmap, QFont, QAction, QColor, QPalette

from .config import Config, WHISPER_MODELS, SHERPA_MODELS, PODLODKA_MODELS, LANGUAGES, BACKENDS
from .audio_recorder import AudioRecorder
from .transcriber import Transcriber, get_available_backends
from .hotkeys import HotkeyManager, type_text

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


# Modern dark theme colors (similar to WhisperTyping)
COLORS = {
    'bg_dark': '#1a1a2e',
    'bg_medium': '#16213e',
    'bg_light': '#0f3460',
    'accent': '#e94560',
    'accent_hover': '#ff6b6b',
    'text_primary': '#ffffff',
    'text_secondary': '#a0a0a0',
    'success': '#4ecca3',
    'warning': '#ffc107',
    'border': '#2d2d44'
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
}}

QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
}}

QLabel#titleLabel {{
    font-size: 18px;
    font-weight: bold;
    color: {COLORS['accent']};
}}

QLabel#statusLabel {{
    font-size: 12px;
    color: {COLORS['text_secondary']};
    padding: 5px;
}}

QPushButton {{
    background-color: {COLORS['bg_light']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

QPushButton:pressed {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton#recordButton {{
    background-color: {COLORS['accent']};
    border: none;
    border-radius: 35px;
    min-width: 70px;
    min-height: 70px;
    max-width: 70px;
    max-height: 70px;
    font-size: 24px;
}}

QPushButton#recordButton:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton#recordButton[recording="true"] {{
    background-color: {COLORS['success']};
}}

QTextEdit {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
    selection-background-color: {COLORS['accent']};
}}

QComboBox {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 12px;
    min-width: 150px;
}}

QComboBox:hover {{
    border-color: {COLORS['accent']};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent']};
    border: 1px solid {COLORS['border']};
}}

QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLORS['border']};
    background-color: {COLORS['bg_medium']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

QGroupBox {{
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}}

QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    background-color: {COLORS['bg_dark']};
}}

QTabBar::tab {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    border-bottom: 2px solid {COLORS['accent']};
}}

QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {COLORS['bg_medium']};
    text-align: center;
    color: {COLORS['text_primary']};
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background-color: {COLORS['bg_medium']};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {COLORS['accent']};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLORS['accent_hover']};
}}

QFrame#separator {{
    background-color: {COLORS['border']};
}}
"""


class TranscriptionThread(QThread):
    """Thread for running transcription."""

    finished = pyqtSignal(str, float)  # text, duration
    progress = pyqtSignal(str)  # status message
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, audio, sample_rate: int):
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate

    def run(self):
        try:
            text, duration = self.transcriber.transcribe(
                self.audio,
                self.sample_rate
            )
            self.finished.emit(text, duration)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    status_update = pyqtSignal(str)
    audio_level_update = pyqtSignal(float)

    def __init__(self):
        super().__init__()

        # Load configuration
        self.config = Config.load()

        # Initialize components
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            on_level_update=self._on_audio_level
        )

        self.transcriber = Transcriber(
            backend=self.config.backend,
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            language=self.config.language,
            on_progress=self._on_transcriber_progress,
            enable_post_processing=self.config.enable_post_processing
        )

        self.hotkey_manager = HotkeyManager(on_hotkey=self._on_hotkey)

        self._transcription_thread: Optional[TranscriptionThread] = None
        self._recording_start_time: float = 0

        # Setup UI
        self._setup_ui()
        self._setup_tray()
        self._connect_signals()

        # Register hotkey
        self._register_hotkey()

        # Load model in background
        QTimer.singleShot(1000, self._load_model_async)

    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("WhisperTyping")
        self.setMinimumSize(400, 500)
        self.resize(450, 550)

        # Set window flags
        if self.config.always_on_top:
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )

        # Apply stylesheet
        self.setStyleSheet(STYLESHEET)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title_label = QLabel("WhisperTyping")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Record button
        record_layout = QHBoxLayout()
        record_layout.addStretch()

        self.record_button = QPushButton("")
        self.record_button.setObjectName("recordButton")
        self.record_button.setProperty("recording", False)
        self.record_button.clicked.connect(self._toggle_recording)
        record_layout.addWidget(self.record_button)

        record_layout.addStretch()
        layout.addLayout(record_layout)

        # Audio level indicator
        self.level_bar = QProgressBar()
        self.level_bar.setMaximum(100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setMaximumHeight(8)
        layout.addWidget(self.level_bar)

        # Hotkey hint
        hotkey_hint = QLabel(f"Hotkey: {self.config.hotkey}")
        hotkey_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_hint.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(hotkey_hint)
        self.hotkey_hint = hotkey_hint

        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Transcription
        transcription_tab = QWidget()
        transcription_layout = QVBoxLayout(transcription_tab)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Transcribed text will appear here...")
        self.text_edit.setMinimumHeight(120)
        transcription_layout.addWidget(self.text_edit)

        # Action buttons
        button_layout = QHBoxLayout()

        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self._copy_text)
        button_layout.addWidget(self.copy_button)

        self.paste_button = QPushButton("Paste")
        self.paste_button.clicked.connect(self._paste_text)
        button_layout.addWidget(self.paste_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_text)
        button_layout.addWidget(self.clear_button)

        transcription_layout.addLayout(button_layout)
        tabs.addTab(transcription_tab, "Transcription")

        # Tab 2: Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        # Backend selection
        backend_group = QGroupBox("Speech Recognition Backend")
        backend_layout = QVBoxLayout(backend_group)

        self.backend_combo = QComboBox()
        for backend_id, backend_name in BACKENDS.items():
            self.backend_combo.addItem(backend_name, backend_id)

        current_backend_idx = list(BACKENDS.keys()).index(self.config.backend)
        self.backend_combo.setCurrentIndex(current_backend_idx)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        backend_layout.addWidget(self.backend_combo)

        settings_layout.addWidget(backend_group)

        # Model selection (dynamically updated based on backend)
        model_group = QGroupBox("Model")
        model_layout = QVBoxLayout(model_group)

        self.model_combo = QComboBox()
        self._update_model_options()  # Populate based on current backend
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo)

        settings_layout.addWidget(model_group)

        # Language selection
        lang_group = QGroupBox("Language")
        lang_layout = QVBoxLayout(lang_group)

        self.lang_combo = QComboBox()
        for lang_id, lang_name in LANGUAGES.items():
            self.lang_combo.addItem(lang_name, lang_id)

        lang_keys = list(LANGUAGES.keys())
        if self.config.language in lang_keys:
            self.lang_combo.setCurrentIndex(lang_keys.index(self.config.language))
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self.lang_combo)

        settings_layout.addWidget(lang_group)

        # Text processing options
        processing_group = QGroupBox("Text Processing")
        processing_layout = QVBoxLayout(processing_group)

        self.post_process_cb = QCheckBox("Enable post-processing")
        self.post_process_cb.setChecked(self.config.enable_post_processing)
        self.post_process_cb.setToolTip("Improve transcription accuracy by fixing common errors")
        self.post_process_cb.toggled.connect(self._on_post_process_changed)
        processing_layout.addWidget(self.post_process_cb)

        settings_layout.addWidget(processing_group)

        # Behavior options
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_copy_cb = QCheckBox("Auto-copy to clipboard")
        self.auto_copy_cb.setChecked(self.config.auto_copy)
        self.auto_copy_cb.toggled.connect(self._on_auto_copy_changed)
        behavior_layout.addWidget(self.auto_copy_cb)

        self.auto_paste_cb = QCheckBox("Auto-paste after transcription")
        self.auto_paste_cb.setChecked(self.config.auto_paste)
        self.auto_paste_cb.toggled.connect(self._on_auto_paste_changed)
        behavior_layout.addWidget(self.auto_paste_cb)

        self.always_top_cb = QCheckBox("Always on top")
        self.always_top_cb.setChecked(self.config.always_on_top)
        self.always_top_cb.toggled.connect(self._on_always_top_changed)
        behavior_layout.addWidget(self.always_top_cb)

        settings_layout.addWidget(behavior_group)
        settings_layout.addStretch()

        tabs.addTab(settings_tab, "Settings")

        # Tab 3: Stats
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        stats_group = QGroupBox("Usage Statistics")
        stats_inner = QVBoxLayout(stats_group)

        self.stats_words = QLabel(f"Total words: {self.config.total_words:,}")
        stats_inner.addWidget(self.stats_words)

        self.stats_recordings = QLabel(f"Recordings: {self.config.total_recordings:,}")
        stats_inner.addWidget(self.stats_recordings)

        saved_mins = self.config.total_seconds_saved / 60
        self.stats_saved = QLabel(f"Time saved: {saved_mins:.1f} minutes")
        stats_inner.addWidget(self.stats_saved)

        stats_layout.addWidget(stats_group)
        stats_layout.addStretch()

        tabs.addTab(stats_tab, "Stats")

    def _setup_tray(self):
        """Setup system tray icon."""
        self.tray_icon = QSystemTrayIcon(self)

        # Create a simple icon (red circle)
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(COLORS['accent']))
        self.tray_icon.setIcon(QIcon(pixmap))

        # Tray menu
        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        record_action = QAction("Start Recording", self)
        record_action.triggered.connect(self._toggle_recording)
        tray_menu.addAction(record_action)
        self.tray_record_action = record_action

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _connect_signals(self):
        """Connect signals."""
        self.status_update.connect(self._update_status)
        self.audio_level_update.connect(self._update_level)

    def _register_hotkey(self):
        """Register the global hotkey."""
        success = self.hotkey_manager.register(self.config.hotkey)
        if success:
            self.hotkey_hint.setText(f"Hotkey: {self.config.hotkey}")
        else:
            self.hotkey_hint.setText("Hotkey registration failed")

    def _load_model_async(self):
        """Load Whisper model in background."""
        def load():
            self.transcriber.load_model()

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _on_audio_level(self, level: float):
        """Handle audio level update."""
        # Scale level for display (0-100)
        scaled = min(100, int(level * 1000))
        self.audio_level_update.emit(scaled)

    def _on_transcriber_progress(self, message: str):
        """Handle transcriber progress update."""
        self.status_update.emit(message)

    def _on_hotkey(self):
        """Handle hotkey press."""
        self._toggle_recording()

    def _toggle_recording(self):
        """Toggle recording state."""
        if self.recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start audio recording."""
        if self.recorder.start():
            self._recording_start_time = time.time()
            self.record_button.setProperty("recording", True)
            self.record_button.style().unpolish(self.record_button)
            self.record_button.style().polish(self.record_button)
            self.status_label.setText("Recording...")
            self.tray_record_action.setText("Stop Recording")

            # Change tray icon color
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(COLORS['success']))
            self.tray_icon.setIcon(QIcon(pixmap))

    def _stop_recording(self):
        """Stop recording and transcribe."""
        audio = self.recorder.stop()

        self.record_button.setProperty("recording", False)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.level_bar.setValue(0)
        self.tray_record_action.setText("Start Recording")

        # Reset tray icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(COLORS['accent']))
        self.tray_icon.setIcon(QIcon(pixmap))

        if audio is None or len(audio) == 0:
            self.status_label.setText("No audio recorded")
            return

        duration = self.recorder.get_duration(audio)
        if duration < 0.5:
            self.status_label.setText("Recording too short")
            return

        # Start transcription in background
        self.status_label.setText("Transcribing...")
        self._transcription_thread = TranscriptionThread(
            self.transcriber,
            audio,
            self.config.sample_rate
        )
        self._transcription_thread.finished.connect(self._on_transcription_done)
        self._transcription_thread.error.connect(self._on_transcription_error)
        self._transcription_thread.start()

    def _on_transcription_done(self, text: str, process_time: float):
        """Handle transcription completion."""
        if not text:
            self.status_label.setText("No speech detected")
            return

        # Update text display
        self.text_edit.setPlainText(text)

        # Update statistics
        word_count = len(text.split())
        recording_duration = time.time() - self._recording_start_time
        self.config.update_stats(word_count, recording_duration)
        self._update_stats_display()

        # Auto-copy
        if self.config.auto_copy and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
            except Exception:
                pass

        # Auto-paste
        if self.config.auto_paste:
            QTimer.singleShot(100, lambda: self._auto_type_text(text))

        self.status_label.setText(f"Done ({process_time:.1f}s, {word_count} words)")

    def _on_transcription_error(self, error: str):
        """Handle transcription error."""
        self.status_label.setText(f"Error: {error}")

    def _auto_type_text(self, text: str):
        """Auto-type the transcribed text."""
        try:
            type_text(text)
        except Exception as e:
            print(f"Auto-type failed: {e}")

    def _copy_text(self):
        """Copy text to clipboard."""
        text = self.text_edit.toPlainText()
        if text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                self.status_label.setText("Copied to clipboard")
            except Exception:
                self.status_label.setText("Copy failed")

    def _paste_text(self):
        """Paste/type the text."""
        text = self.text_edit.toPlainText()
        if text:
            self._auto_type_text(text)
            self.status_label.setText("Text typed")

    def _clear_text(self):
        """Clear the text area."""
        self.text_edit.clear()
        self.status_label.setText("Cleared")

    def _update_status(self, message: str):
        """Update status label."""
        self.status_label.setText(message)

    def _update_level(self, level: int):
        """Update audio level bar."""
        self.level_bar.setValue(int(level))

    def _update_stats_display(self):
        """Update statistics display."""
        self.stats_words.setText(f"Total words: {self.config.total_words:,}")
        self.stats_recordings.setText(f"Recordings: {self.config.total_recordings:,}")
        saved_mins = self.config.total_seconds_saved / 60
        self.stats_saved.setText(f"Time saved: {saved_mins:.1f} minutes")

    def _update_model_options(self):
        """Update model combo box based on selected backend."""
        self.model_combo.clear()

        current_backend = self.backend_combo.currentData()

        if current_backend == "whisper":
            for model_id, model_name in WHISPER_MODELS.items():
                self.model_combo.addItem(model_name, model_id)
        elif current_backend == "sherpa":
            for model_id, model_name in SHERPA_MODELS.items():
                self.model_combo.addItem(model_name, model_id)
        elif current_backend == "podlodka-turbo":
            for model_id, model_name in PODLODKA_MODELS.items():
                self.model_combo.addItem(model_name, model_id)

        # Set current model
        if current_backend == "whisper":
            models = WHISPER_MODELS
        elif current_backend == "sherpa":
            models = SHERPA_MODELS
        elif current_backend == "podlodka-turbo":
            models = PODLODKA_MODELS
        else:
            models = {}

        model_keys = list(models.keys())

        if self.config.model_size in model_keys:
            current_idx = model_keys.index(self.config.model_size)
            self.model_combo.setCurrentIndex(current_idx)
        elif model_keys:
            self.model_combo.setCurrentIndex(0)

    def _on_backend_changed(self, index: int):
        """Handle backend selection change."""
        backend_id = self.backend_combo.currentData()

        if backend_id != self.config.backend:
            self.config.backend = backend_id
            self.config.save()

            # Update model options for new backend
            self._update_model_options()

            # Update default model for new backend
            if backend_id == "whisper":
                default_model = "base"
            elif backend_id == "sherpa":
                default_model = "giga-am-v2-ru"
            elif backend_id == "podlodka-turbo":
                default_model = "podlodka-turbo"
            else:
                default_model = "base"

            self.config.model_size = default_model
            self.config.save()

            # Recreate transcriber with new backend
            self.transcriber.switch_backend(backend_id, default_model)

            self.status_label.setText(f"Backend changed to {backend_id}")

    def _on_model_changed(self, index: int):
        """Handle model selection change."""
        model_id = self.model_combo.currentData()
        if model_id != self.config.model_size:
            self.config.model_size = model_id
            self.config.save()

            # Unload current model and reload
            self.transcriber.unload_model()
            self.transcriber.model_size = model_id
            self.status_label.setText(f"Model changed to {model_id}")
            self._load_model_async()

    def _on_language_changed(self, index: int):
        """Handle language selection change."""
        lang_id = self.lang_combo.currentData()
        self.config.language = lang_id
        self.config.save()
        self.transcriber.language = lang_id if lang_id != "auto" else None

        # Update text processor language
        from .text_processor import AdvancedTextProcessor
        lang_code = lang_id if lang_id != "auto" else "ru"
        self.transcriber.text_processor = AdvancedTextProcessor(
            language=lang_code,
            enable_corrections=self.config.enable_post_processing
        )

    def _on_post_process_changed(self, checked: bool):
        """Handle post-processing toggle."""
        self.config.enable_post_processing = checked
        self.config.save()
        self.transcriber.enable_post_processing = checked
        self.transcriber.text_processor.enable_corrections = checked

    def _on_auto_copy_changed(self, checked: bool):
        """Handle auto-copy toggle."""
        self.config.auto_copy = checked
        self.config.save()

    def _on_auto_paste_changed(self, checked: bool):
        """Handle auto-paste toggle."""
        self.config.auto_paste = checked
        self.config.save()

    def _on_always_top_changed(self, checked: bool):
        """Handle always-on-top toggle."""
        self.config.always_on_top = checked
        self.config.save()

        if checked:
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
            )
        else:
            self.setWindowFlags(
                self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint
            )
        self.show()

    def _on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def closeEvent(self, event):
        """Handle window close."""
        if self.config.minimize_to_tray:
            event.ignore()
            self.hide()
        else:
            self._quit_app()

    def _quit_app(self):
        """Quit the application."""
        # Cleanup
        self.hotkey_manager.unregister()
        self.tray_icon.hide()
        self.config.save()
        QApplication.quit()


def run():
    """Run the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("WhisperTyping")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
