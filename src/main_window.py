"""Main window for ГолосТекст application - Compact WhisperTyping style."""
import sys
import time
import threading
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox,
    QCheckBox, QGroupBox, QTabWidget,
    QSystemTrayIcon, QMenu, QMessageBox,
    QApplication, QDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPoint, QRectF
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QAction, QColor,
    QPainter, QLinearGradient, QBrush, QPen, QMouseEvent,
    QPainterPath
)

from .config import Config, WHISPER_MODELS, SHERPA_MODELS, PODLODKA_MODELS, LANGUAGES, BACKENDS
from .audio_recorder import AudioRecorder
from .transcriber import Transcriber, get_available_backends
from .hotkeys import HotkeyManager, type_text
from .history_manager import HistoryManager

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


# WhisperTyping-style gradient colors
GRADIENT_COLORS = {
    'left': '#f97316',      # Orange
    'middle': '#ec4899',    # Pink
    'right': '#8b5cf6',     # Purple
}

# UI Colors
COLORS = {
    'bg_dark': '#1a1a2e',
    'bg_medium': '#16213e',
    'bg_light': '#0f3460',
    'accent': '#ec4899',
    'accent_hover': '#f472b6',
    'text_primary': '#ffffff',
    'text_secondary': '#a0a0a0',
    'success': '#4ecca3',
    'warning': '#ffc107',
    'border': '#2d2d44',
}

# Compact bar dimensions - reduced width
COMPACT_HEIGHT = 52
COMPACT_WIDTH = 340  # Reduced from 520
ICON_SIZE = 18


# Settings dialog stylesheet
DIALOG_STYLESHEET = f"""
QDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}

QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
}}

QPushButton {{
    background-color: {COLORS['bg_light']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

QTextEdit {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
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
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 20px;
    border-left: 1px solid {COLORS['border']};
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

QScrollArea {{
    border: none;
    background-color: transparent;
}}
"""


class TranscriptionThread(QThread):
    """Thread for running transcription."""

    finished = pyqtSignal(str, float)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, transcriber, audio, sample_rate: int):
        super().__init__()
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate

    def run(self):
        try:
            text, duration = self.transcriber.transcribe(self.audio, self.sample_rate)
            self.finished.emit(text, duration)
        except Exception as e:
            self.error.emit(str(e))


class WaveformWidget(QWidget):
    """Widget showing audio waveform visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_level = 0.0
        self.wave_bars: List[float] = [0.1] * 9  # 9 bars for waveform
        self.setFixedSize(60, 30)

    def set_audio_level(self, level: float):
        """Update audio level and shift wave bars."""
        self.audio_level = min(1.0, level)
        # Shift bars left and add new level
        self.wave_bars = self.wave_bars[1:] + [max(0.1, min(1.0, level * 3))]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw waveform bars
        bar_width = 4
        spacing = 3
        total_width = len(self.wave_bars) * (bar_width + spacing) - spacing
        start_x = (self.width() - total_width) // 2
        center_y = self.height() // 2

        for i, level in enumerate(self.wave_bars):
            x = start_x + i * (bar_width + spacing)
            bar_height = max(4, int(level * 20))

            # Draw bar centered vertically
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 200))
            painter.drawRoundedRect(
                x, center_y - bar_height // 2,
                bar_width, bar_height,
                2, 2
            )


class GradientWidget(QWidget):
    """Widget with gradient background and hover detection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self._hovered = False

    def set_hovered(self, hovered: bool):
        self._hovered = hovered
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)


class IconButton(QPushButton):
    """Transparent icon button that appears on hover."""

    def __init__(self, icon_char: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.icon_char = icon_char
        self.setToolTip(tooltip)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._visible_mode = False
        self._update_style()
        self.setText(icon_char)

    def set_visible_mode(self, visible: bool):
        """Set whether button should be visible or semi-transparent."""
        self._visible_mode = visible
        self._update_style()

    def _update_style(self):
        if self._visible_mode:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.15);
                    border: none;
                    border-radius: 14px;
                    color: rgba(255, 255, 255, 0.9);
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.25);
                    color: white;
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.35);
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: rgba(255, 255, 255, 0.0);
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.15);
                    border-radius: 14px;
                    color: rgba(255, 255, 255, 0.9);
                }
            """)


class SettingsDialog(QDialog):
    """Settings and history dialog."""

    def __init__(self, parent=None, config=None, history_manager=None):
        super().__init__(parent)
        self.config = config
        self.history_manager = history_manager
        self.setWindowTitle("Настройки")
        self.setMinimumSize(450, 500)
        self.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._setup_ui()
        self._drag_position = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header with close button - VISIBLE
        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 16px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(233, 69, 96, 0.8);
                border-color: #e94560;
            }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_transcription_tab()
        self._create_settings_tab()
        self._create_history_tab()

    def _create_transcription_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Транскрибированный текст появится здесь...")
        self.text_edit.setMinimumHeight(200)
        layout.addWidget(self.text_edit)

        self.status_label = QLabel("Готово")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Копировать")
        self.copy_btn.clicked.connect(self._copy_text)
        btn_layout.addWidget(self.copy_btn)

        self.paste_btn = QPushButton("Вставить")
        btn_layout.addWidget(self.paste_btn)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(lambda: self.text_edit.clear())
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)
        self.tabs.addTab(tab, "Текст")

    def _create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Backend
        backend_group = QGroupBox("Движок распознавания")
        backend_layout = QVBoxLayout(backend_group)
        self.backend_combo = QComboBox()
        for backend_id, backend_name in BACKENDS.items():
            self.backend_combo.addItem(backend_name, backend_id)
        if self.config:
            idx = list(BACKENDS.keys()).index(self.config.backend)
            self.backend_combo.setCurrentIndex(idx)
        backend_layout.addWidget(self.backend_combo)
        scroll_layout.addWidget(backend_group)

        # Model
        model_group = QGroupBox("Модель")
        model_layout = QVBoxLayout(model_group)
        self.model_combo = QComboBox()
        self._update_model_options()
        model_layout.addWidget(self.model_combo)
        scroll_layout.addWidget(model_group)

        # Language
        lang_group = QGroupBox("Язык")
        lang_layout = QVBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        for lang_id, lang_name in LANGUAGES.items():
            self.lang_combo.addItem(lang_name, lang_id)
        if self.config:
            lang_keys = list(LANGUAGES.keys())
            if self.config.language in lang_keys:
                self.lang_combo.setCurrentIndex(lang_keys.index(self.config.language))
        lang_layout.addWidget(self.lang_combo)
        scroll_layout.addWidget(lang_group)

        # Behavior
        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_copy_cb = QCheckBox("Авто-копирование в буфер")
        if self.config:
            self.auto_copy_cb.setChecked(self.config.auto_copy)
        behavior_layout.addWidget(self.auto_copy_cb)

        self.auto_paste_cb = QCheckBox("Авто-вставка после транскрибации")
        if self.config:
            self.auto_paste_cb.setChecked(self.config.auto_paste)
        behavior_layout.addWidget(self.auto_paste_cb)

        self.always_top_cb = QCheckBox("Поверх всех окон")
        if self.config:
            self.always_top_cb.setChecked(self.config.always_on_top)
        behavior_layout.addWidget(self.always_top_cb)

        self.post_process_cb = QCheckBox("Пост-обработка текста")
        if self.config:
            self.post_process_cb.setChecked(self.config.enable_post_processing)
        behavior_layout.addWidget(self.post_process_cb)

        scroll_layout.addWidget(behavior_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Настройки")

    def _create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        stats_group = QGroupBox("Статистика")
        stats_layout = QVBoxLayout(stats_group)

        if self.config:
            self.stats_words = QLabel(f"Всего слов: {self.config.total_words:,}")
            stats_layout.addWidget(self.stats_words)
            self.stats_recordings = QLabel(f"Записей: {self.config.total_recordings:,}")
            stats_layout.addWidget(self.stats_recordings)
            saved_mins = self.config.total_seconds_saved / 60
            self.stats_saved = QLabel(f"Сохранено времени: {saved_mins:.1f} мин")
            stats_layout.addWidget(self.stats_saved)

        layout.addWidget(stats_group)

        history_group = QGroupBox("История (последние 50)")
        history_layout = QVBoxLayout(history_group)

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setMinimumHeight(200)
        history_layout.addWidget(self.history_text)

        clear_btn = QPushButton("Очистить историю")
        clear_btn.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_btn)

        layout.addWidget(history_group)
        self.tabs.addTab(tab, "История")
        self._update_history_display()

    def _update_model_options(self):
        self.model_combo.clear()
        if not self.config:
            return
        current_backend = self.backend_combo.currentData() if self.backend_combo.currentData() else self.config.backend
        if current_backend == "whisper":
            models = WHISPER_MODELS
        elif current_backend == "sherpa":
            models = SHERPA_MODELS
        elif current_backend == "podlodka-turbo":
            models = PODLODKA_MODELS
        else:
            models = {}
        for model_id, model_name in models.items():
            self.model_combo.addItem(model_name, model_id)
        model_keys = list(models.keys())
        if self.config.model_size in model_keys:
            self.model_combo.setCurrentIndex(model_keys.index(self.config.model_size))

    def _update_history_display(self):
        if not self.history_manager:
            return
        history = self.history_manager.get_history()
        if not history:
            self.history_text.setPlainText("История пуста")
            return
        lines = []
        for idx, entry in enumerate(history, 1):
            lines.append(f"[{idx}] {entry.timestamp}")
            lines.append(f"Модель: {entry.backend}/{entry.model}")
            lines.append(f"Длительность: {entry.duration:.1f}с | Слов: {entry.word_count}")
            lines.append(f"Текст:\n{entry.text}")
            lines.append("-" * 60)
            lines.append("")
        self.history_text.setPlainText("\n".join(lines))

    def _clear_history(self):
        if self.history_manager:
            reply = QMessageBox.question(
                self, "Подтверждение", "Очистить историю?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.history_manager.clear_history()
                self._update_history_display()

    def _copy_text(self):
        text = self.text_edit.toPlainText()
        if text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                self.status_label.setText("Скопировано!")
            except:
                pass

    def update_stats_display(self):
        if self.config:
            self.stats_words.setText(f"Всего слов: {self.config.total_words:,}")
            self.stats_recordings.setText(f"Записей: {self.config.total_recordings:,}")
            saved_mins = self.config.total_seconds_saved / 60
            self.stats_saved.setText(f"Сохранено времени: {saved_mins:.1f} мин")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)


class MainWindow(QMainWindow):
    """Compact main application window in WhisperTyping style."""

    status_update = pyqtSignal(str)
    audio_level_update = pyqtSignal(float)

    def __init__(self):
        super().__init__()

        self.config = Config.load()

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
        self.history_manager = HistoryManager(max_entries=50)

        self._transcription_thread: Optional[TranscriptionThread] = None
        self._recording_start_time: float = 0
        self._drag_position = None
        self._settings_dialog = None
        self._is_recording = False
        self._last_transcribed_text = ""

        # Recording timer
        self._recording_timer = QTimer()
        self._recording_timer.timeout.connect(self._update_recording_time)
        self._recording_seconds = 0

        self._setup_ui()
        self._setup_tray()
        self._connect_signals()
        self._register_hotkey()

        QTimer.singleShot(1000, self._load_model_async)

    def _setup_ui(self):
        """Setup the compact user interface."""
        self.setWindowTitle("ГолосТекст")
        self.setFixedSize(COMPACT_WIDTH, COMPACT_HEIGHT)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = GradientWidget()
        self.central_widget.setMouseTracking(True)
        self.setCentralWidget(self.central_widget)

        layout = QHBoxLayout(self.central_widget)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(6)

        # Left side: Status label OR Waveform when recording
        self.status_label = QLabel("Listening")
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.status_label)

        # Waveform visualization (shown during recording)
        self.waveform = WaveformWidget()
        self.waveform.hide()
        layout.addWidget(self.waveform)

        # Timer label (shown during recording)
        self.timer_label = QLabel("")
        self.timer_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        self.timer_label.hide()
        layout.addWidget(self.timer_label)

        layout.addStretch()

        # Right side buttons container
        self.buttons_container = QWidget()
        self.buttons_container.setStyleSheet("background: transparent;")
        buttons_layout = QHBoxLayout(self.buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)

        # Copy button
        self.copy_btn = IconButton("📋", "Копировать последний текст")
        self.copy_btn.clicked.connect(self._copy_last_text)
        buttons_layout.addWidget(self.copy_btn)

        # History button
        self.history_btn = IconButton("📜", "История транскрибаций")
        self.history_btn.clicked.connect(self._show_history)
        buttons_layout.addWidget(self.history_btn)

        # Settings button
        self.settings_btn = IconButton("⚙", "Настройки")
        self.settings_btn.clicked.connect(self._show_settings)
        buttons_layout.addWidget(self.settings_btn)

        # Record/Stop button (microphone or stop)
        self.record_btn = IconButton("🎤", "Начать/Остановить запись")
        self.record_btn.clicked.connect(self._toggle_recording)
        buttons_layout.addWidget(self.record_btn)

        # Close button - always somewhat visible
        self.close_btn = IconButton("✕", "Закрыть")
        self.close_btn.clicked.connect(self._quit_app)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.5);
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 14px;
                color: white;
            }
        """)
        buttons_layout.addWidget(self.close_btn)

        layout.addWidget(self.buttons_container)

        # Start with buttons semi-hidden
        self._set_buttons_visible(False)

    def _set_buttons_visible(self, visible: bool):
        """Set visibility mode for action buttons."""
        for btn in [self.copy_btn, self.history_btn, self.settings_btn, self.record_btn]:
            btn.set_visible_mode(visible)

    def enterEvent(self, event):
        """Show buttons when mouse enters window."""
        self._set_buttons_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide buttons when mouse leaves window."""
        self._set_buttons_visible(False)
        super().leaveEvent(event)

    def _setup_tray(self):
        """Setup system tray icon."""
        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 32, 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))

        tray_menu = QMenu()

        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self._show_settings)
        tray_menu.addAction(settings_action)

        record_action = QAction("Начать запись", self)
        record_action.triggered.connect(self._toggle_recording)
        tray_menu.addAction(record_action)
        self.tray_record_action = record_action

        tray_menu.addSeparator()

        quit_action = QAction("Выход", self)
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
        self.hotkey_manager.register(self.config.hotkey)

    def _load_model_async(self):
        """Load model in background."""
        def load():
            self.transcriber.load_model()
        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _on_audio_level(self, level: float):
        """Handle audio level update."""
        scaled = min(1.0, level * 10)
        self.audio_level_update.emit(scaled)

    def _on_transcriber_progress(self, message: str):
        """Handle transcriber progress update."""
        self.status_update.emit(message)

    def _on_hotkey(self):
        """Handle hotkey press."""
        self._toggle_recording()

    def _toggle_recording(self):
        """Toggle recording state."""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start audio recording."""
        if self.recorder.start():
            self._is_recording = True
            self._recording_start_time = time.time()
            self._recording_seconds = 0

            # Update UI for recording state
            self.status_label.setText("Listening")
            self.waveform.show()
            self.timer_label.show()
            self.timer_label.setText("0,0s")
            self.record_btn.setText("⏹")
            self.record_btn.setToolTip("Остановить запись")

            # Start timer
            self._recording_timer.start(100)  # Update every 100ms

            self.tray_record_action.setText("Остановить запись")

            # Update tray icon to green
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(COLORS['success']))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(2, 2, 28, 28)
            painter.end()
            self.tray_icon.setIcon(QIcon(pixmap))

    def _stop_recording(self):
        """Stop recording and transcribe."""
        self._is_recording = False
        self._recording_timer.stop()

        audio = self.recorder.stop()

        # Update UI for idle state
        self.status_label.setText("Готово")
        self.waveform.hide()
        self.timer_label.hide()
        self.record_btn.setText("🎤")
        self.record_btn.setToolTip("Начать запись")

        self.tray_record_action.setText("Начать запись")

        # Reset tray icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 32, 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

        if audio is None or len(audio) == 0:
            return

        duration = self.recorder.get_duration(audio)
        if duration < 0.5:
            return

        self.status_label.setText("Обработка...")

        self._transcription_thread = TranscriptionThread(
            self.transcriber, audio, self.config.sample_rate
        )
        self._transcription_thread.finished.connect(self._on_transcription_done)
        self._transcription_thread.error.connect(self._on_transcription_error)
        self._transcription_thread.start()

    def _update_recording_time(self):
        """Update the recording timer display."""
        elapsed = time.time() - self._recording_start_time
        self.timer_label.setText(f"{elapsed:.1f}s")

    def _on_transcription_done(self, text: str, process_time: float):
        """Handle transcription completion."""
        if not text:
            self.status_label.setText("Готово")
            return

        self._last_transcribed_text = text
        self.status_label.setText("Готово")

        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.text_edit.setPlainText(text)
            self._settings_dialog.status_label.setText(f"Готово ({process_time:.1f}с)")

        word_count = len(text.split())
        recording_duration = time.time() - self._recording_start_time
        self.config.update_stats(word_count, recording_duration)

        self.history_manager.add_entry(
            text=text,
            duration=process_time,
            backend=self.config.backend,
            model=self.config.model_size
        )

        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.update_stats_display()
            self._settings_dialog._update_history_display()

        if self.config.auto_copy and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
            except:
                pass

        if self.config.auto_paste:
            QTimer.singleShot(100, lambda: self._auto_type_text(text))

    def _on_transcription_error(self, error: str):
        """Handle transcription error."""
        self.status_label.setText("Ошибка")
        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.status_label.setText(f"Ошибка: {error}")

    def _auto_type_text(self, text: str):
        """Auto-type the transcribed text."""
        try:
            type_text(text)
        except Exception as e:
            print(f"Auto-type failed: {e}")

    def _update_status(self, message: str):
        """Update status."""
        if not self._is_recording:
            self.status_label.setText(message)
        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.status_label.setText(message)

    def _update_level(self, level: float):
        """Update audio level visualization."""
        if self._is_recording:
            self.waveform.set_audio_level(level)

    def _copy_last_text(self):
        """Copy last transcribed text to clipboard."""
        if self._last_transcribed_text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(self._last_transcribed_text)
                self.status_label.setText("Скопировано!")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Готово") if not self._is_recording else None)
            except:
                pass

    def _show_history(self):
        """Show history in settings dialog."""
        self._show_settings()
        if self._settings_dialog:
            self._settings_dialog.tabs.setCurrentIndex(2)  # History tab

    def _show_settings(self):
        """Show settings dialog."""
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(
                self, config=self.config, history_manager=self.history_manager
            )
            self._settings_dialog.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
            self._settings_dialog.model_combo.currentIndexChanged.connect(self._on_model_changed)
            self._settings_dialog.lang_combo.currentIndexChanged.connect(self._on_language_changed)
            self._settings_dialog.auto_copy_cb.toggled.connect(self._on_auto_copy_changed)
            self._settings_dialog.auto_paste_cb.toggled.connect(self._on_auto_paste_changed)
            self._settings_dialog.always_top_cb.toggled.connect(self._on_always_top_changed)
            self._settings_dialog.post_process_cb.toggled.connect(self._on_post_process_changed)
            self._settings_dialog.paste_btn.clicked.connect(self._paste_from_dialog)

        pos = self.pos()
        self._settings_dialog.move(pos.x(), pos.y() + self.height() + 10)
        self._settings_dialog.show()
        self._settings_dialog.raise_()

    def _paste_from_dialog(self):
        """Paste text from dialog."""
        if self._settings_dialog:
            text = self._settings_dialog.text_edit.toPlainText()
            if text:
                self._auto_type_text(text)

    def _on_backend_changed(self, index: int):
        if not self._settings_dialog:
            return
        backend_id = self._settings_dialog.backend_combo.currentData()
        if backend_id != self.config.backend:
            self.config.backend = backend_id
            self.config.save()
            self._settings_dialog._update_model_options()
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
            self.transcriber.switch_backend(backend_id, default_model)

    def _on_model_changed(self, index: int):
        if not self._settings_dialog:
            return
        model_id = self._settings_dialog.model_combo.currentData()
        if model_id and model_id != self.config.model_size:
            self.config.model_size = model_id
            self.config.save()
            current_backend = self._settings_dialog.backend_combo.currentData()
            self.transcriber.switch_backend(current_backend, model_id)

    def _on_language_changed(self, index: int):
        if not self._settings_dialog:
            return
        lang_id = self._settings_dialog.lang_combo.currentData()
        self.config.language = lang_id
        self.config.save()
        self.transcriber.language = lang_id if lang_id != "auto" else None

    def _on_auto_copy_changed(self, checked: bool):
        self.config.auto_copy = checked
        self.config.save()

    def _on_auto_paste_changed(self, checked: bool):
        self.config.auto_paste = checked
        self.config.save()

    def _on_always_top_changed(self, checked: bool):
        self.config.always_on_top = checked
        self.config.save()
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def _on_post_process_changed(self, checked: bool):
        self.config.enable_post_processing = checked
        self.config.save()
        self.transcriber.enable_post_processing = checked
        if hasattr(self.transcriber, 'text_processor'):
            self.transcriber.text_processor.enable_corrections = checked

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def _quit_app(self):
        self.hotkey_manager.unregister()
        self.tray_icon.hide()
        self.config.save()
        QApplication.quit()


def run():
    """Run the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("ГолосТекст")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
