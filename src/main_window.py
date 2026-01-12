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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPoint, QRectF, QSize
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QAction, QColor,
    QPainter, QLinearGradient, QBrush, QPen, QMouseEvent,
    QPainterPath
)
from PyQt6 import sip

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


# Gradient colors
GRADIENT_COLORS = {
    'left': '#e85d04',
    'middle': '#d63384',
    'right': '#7c3aed',
}

COLORS = {
    'bg_dark': '#1a1a2e',
    'bg_medium': '#16213e',
    'bg_light': '#0f3460',
    'accent': '#ec4899',
    'text_primary': '#ffffff',
    'text_secondary': '#a0a0a0',
    'success': '#10b981',
    'border': '#2d2d44',
}

COMPACT_HEIGHT = 52
COMPACT_WIDTH = 340


DIALOG_STYLESHEET = f"""
QDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
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
}}
QPushButton:hover {{
    background-color: {COLORS['accent']};
}}
QTextEdit {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px;
}}
QComboBox {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent']};
}}
QCheckBox {{
    color: {COLORS['text_primary']};
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
}}
QGroupBox {{
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
}}
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    background-color: {COLORS['bg_dark']};
}}
QTabBar::tab {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_secondary']};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
}}
QTabBar::tab:selected {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
}}
"""


class TranscriptionThread(QThread):
    finished = pyqtSignal(str, float)
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


class RecordButton(QPushButton):
    """Stylish central record button with custom painting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._audio_level = 0.0
        self._wave_phase = 0.0
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Animation timer for wave effect
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)

    def set_recording(self, recording: bool):
        self._recording = recording
        if recording:
            self._anim_timer.start(50)
        else:
            self._anim_timer.stop()
            self._audio_level = 0.0
        self.update()

    def set_audio_level(self, level: float):
        self._audio_level = min(1.0, level * 2)
        self.update()

    def _animate(self):
        self._wave_phase += 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        if self._recording:
            # Recording state - draw animated sound waves
            base_alpha = 180

            # Draw pulsing circles based on audio level
            for i in range(3):
                import math
                phase_offset = i * 0.8
                pulse = (math.sin(self._wave_phase + phase_offset) + 1) / 2
                radius = 8 + i * 5 + self._audio_level * 6 * pulse
                alpha = int(base_alpha * (1 - i * 0.3) * (0.5 + self._audio_level * 0.5))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, alpha))
                painter.drawEllipse(
                    QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
                )

            # Draw center circle (stop button)
            painter.setBrush(QColor(255, 255, 255, 240))
            painter.drawRoundedRect(
                QRectF(center_x - 6, center_y - 6, 12, 12), 2, 2
            )
        else:
            # Idle state - draw microphone icon
            # Outer glow on hover
            if self.underMouse():
                painter.setBrush(QColor(255, 255, 255, 30))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(2, 2, 32, 32))

            # Mic body
            painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Mic head (rounded rect)
            mic_rect = QRectF(center_x - 5, center_y - 10, 10, 14)
            painter.drawRoundedRect(mic_rect, 5, 5)

            # Mic stand curve
            path = QPainterPath()
            path.moveTo(center_x - 8, center_y + 2)
            path.quadTo(center_x - 8, center_y + 8, center_x, center_y + 8)
            path.quadTo(center_x + 8, center_y + 8, center_x + 8, center_y + 2)
            painter.drawPath(path)

            # Mic stand
            painter.drawLine(
                QPoint(int(center_x), int(center_y + 8)),
                QPoint(int(center_x), int(center_y + 12))
            )
            painter.drawLine(
                QPoint(int(center_x - 5), int(center_y + 12)),
                QPoint(int(center_x + 5), int(center_y + 12))
            )


class MiniButton(QPushButton):
    """Tiny corner button that appears on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opacity = 0.0

    def set_opacity(self, opacity: float):
        self._opacity = opacity
        self.update()

    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        # Subclasses implement actual drawing
        pass


class CopyButton(MiniButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw two overlapping rectangles (copy icon)
        painter.drawRoundedRect(QRectF(3, 5, 8, 10), 1, 1)
        painter.drawRoundedRect(QRectF(7, 3, 8, 10), 1, 1)


class HistoryButton(MiniButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))

        # Draw clock icon
        painter.drawEllipse(QRectF(3, 3, 12, 12))
        painter.drawLine(QPoint(9, 5), QPoint(9, 9))
        painter.drawLine(QPoint(9, 9), QPoint(12, 9))


class SettingsButton(MiniButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw gear icon (simplified)
        painter.drawEllipse(QRectF(5, 5, 8, 8))

        # Gear teeth
        import math
        for i in range(6):
            angle = i * math.pi / 3
            x1 = 9 + 4 * math.cos(angle)
            y1 = 9 + 4 * math.sin(angle)
            x2 = 9 + 6 * math.cos(angle)
            y2 = 9 + 6 * math.sin(angle)
            painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))


class CloseButton(MiniButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0
        color = QColor(255, 100, 100, min(255, alpha + hover_boost)) if self.underMouse() else QColor(255, 255, 255, alpha)

        painter.setPen(QPen(color, 1.5))

        # Draw X
        painter.drawLine(QPoint(5, 5), QPoint(13, 13))
        painter.drawLine(QPoint(13, 5), QPoint(5, 13))


class CancelButton(MiniButton):
    """Кнопка отмены записи - показывается только во время записи."""
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 80 if self.underMouse() else 0

        # Желтовато-оранжевый цвет для отмены записи
        color = QColor(255, 200, 50, min(255, alpha + hover_boost))

        painter.setPen(QPen(color, 2.0))

        # Draw thicker X
        painter.drawLine(QPoint(4, 4), QPoint(14, 14))
        painter.drawLine(QPoint(14, 4), QPoint(4, 14))


class GradientWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

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


class TextPopup(QWidget):
    """Всплывающая панель с текстом транскрибации - появляется сверху на 5 секунд."""

    copy_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._setup_ui()

        # Таймер автоскрытия
        self._hide_timer = QTimer()
        self._hide_timer.timeout.connect(self.hide)
        self._hide_timer.setSingleShot(True)

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(COMPACT_WIDTH)
        self.setMinimumHeight(60)
        self.setMaximumHeight(120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Градиентный фон как у главного окна
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        # Текст
        if self._text:
            painter.setPen(QPen(QColor(255, 255, 255, 230)))
            font = painter.font()
            font.setPointSize(10)  # Уменьшен с 11 до 10
            painter.setFont(font)

            # Отступы
            text_rect = self.rect().adjusted(12, 8, -40, -8)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, self._text)

        # Кнопка копирования (справа)
        copy_btn_x = self.width() - 30
        copy_btn_y = (self.height() - 18) // 2

        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(copy_btn_x, copy_btn_y + 2, 8, 10), 1, 1)
        painter.drawRoundedRect(QRectF(copy_btn_x + 4, copy_btn_y, 8, 10), 1, 1)

    def set_text(self, text: str):
        """Установить текст и показать панель."""
        self._text = text

        # Рассчитываем высоту на основе текста
        font_metrics = self.fontMetrics()
        text_width = COMPACT_WIDTH - 52  # отступы
        lines = max(1, len(text) // 40 + 1)  # примерная оценка строк
        height = min(120, max(60, 30 + lines * 20))
        self.setFixedHeight(height)

        self.update()

    def get_text(self) -> str:
        return self._text

    def show_with_timeout(self, timeout_ms: int = 5000):
        """Показать панель с автоскрытием через указанное время."""
        self._hide_timer.stop()
        self.show()
        self._hide_timer.start(timeout_ms)

    def mousePressEvent(self, event):
        # Проверяем клик на кнопке копирования
        copy_btn_x = self.width() - 35
        if event.pos().x() >= copy_btn_x:
            self.copy_requested.emit()
        else:
            # Закрываем при клике в любом другом месте
            self._hide_timer.stop()
            self.hide()


class SettingsDialog(QDialog):
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

        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 14px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e94560;
            }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_settings_tab()
        self._create_history_tab()

    def _create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        scroll_layout = QVBoxLayout(content)

        backend_group = QGroupBox("Движок")
        backend_layout = QVBoxLayout(backend_group)
        self.backend_combo = QComboBox()
        for bid, bname in BACKENDS.items():
            self.backend_combo.addItem(bname, bid)
        if self.config:
            self.backend_combo.setCurrentIndex(list(BACKENDS.keys()).index(self.config.backend))
        backend_layout.addWidget(self.backend_combo)
        scroll_layout.addWidget(backend_group)

        model_group = QGroupBox("Модель")
        model_layout = QVBoxLayout(model_group)
        self.model_combo = QComboBox()
        self._update_model_options()
        model_layout.addWidget(self.model_combo)
        scroll_layout.addWidget(model_group)

        lang_group = QGroupBox("Язык")
        lang_layout = QVBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        for lid, lname in LANGUAGES.items():
            self.lang_combo.addItem(lname, lid)
        if self.config and self.config.language in LANGUAGES:
            self.lang_combo.setCurrentIndex(list(LANGUAGES.keys()).index(self.config.language))
        lang_layout.addWidget(self.lang_combo)
        scroll_layout.addWidget(lang_group)

        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_copy_cb = QCheckBox("Авто-копирование")
        self.auto_paste_cb = QCheckBox("Авто-вставка")
        self.always_top_cb = QCheckBox("Поверх окон")
        self.post_process_cb = QCheckBox("Пост-обработка")

        if self.config:
            self.auto_copy_cb.setChecked(self.config.auto_copy)
            self.auto_paste_cb.setChecked(self.config.auto_paste)
            self.always_top_cb.setChecked(self.config.always_on_top)
            self.post_process_cb.setChecked(self.config.enable_post_processing)

        behavior_layout.addWidget(self.auto_copy_cb)
        behavior_layout.addWidget(self.auto_paste_cb)
        behavior_layout.addWidget(self.always_top_cb)
        behavior_layout.addWidget(self.post_process_cb)
        scroll_layout.addWidget(behavior_group)
        scroll_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Настройки")

    def _create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        if self.config:
            stats = QGroupBox("Статистика")
            stats_layout = QVBoxLayout(stats)
            self.stats_words = QLabel(f"Слов: {self.config.total_words:,}")
            self.stats_recordings = QLabel(f"Записей: {self.config.total_recordings:,}")
            self.stats_saved = QLabel(f"Время: {self.config.total_seconds_saved/60:.1f} мин")
            stats_layout.addWidget(self.stats_words)
            stats_layout.addWidget(self.stats_recordings)
            stats_layout.addWidget(self.stats_saved)
            layout.addWidget(stats)

        history_group = QGroupBox("История")
        history_layout = QVBoxLayout(history_group)
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        history_layout.addWidget(self.history_text)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_btn)
        layout.addWidget(history_group)

        self.tabs.addTab(tab, "История")
        self._update_history_display()

    def _update_model_options(self):
        self.model_combo.clear()
        if not self.config:
            return
        backend = self.backend_combo.currentData() or self.config.backend
        models = {"whisper": WHISPER_MODELS, "sherpa": SHERPA_MODELS, "podlodka-turbo": PODLODKA_MODELS}.get(backend, {})
        for mid, mname in models.items():
            self.model_combo.addItem(mname, mid)
        if self.config.model_size in models:
            self.model_combo.setCurrentIndex(list(models.keys()).index(self.config.model_size))

    def _update_history_display(self):
        if not self.history_manager:
            return
        history = self.history_manager.get_history()
        if not history:
            self.history_text.setPlainText("Пусто")
            return
        lines = []
        for i, e in enumerate(history, 1):
            lines.append(f"[{i}] {e.timestamp}\n{e.text}\n")
        self.history_text.setPlainText("\n".join(lines))

    def _clear_history(self):
        if self.history_manager:
            self.history_manager.clear_history()
            self._update_history_display()

    def update_stats_display(self):
        if self.config:
            self.stats_words.setText(f"Слов: {self.config.total_words:,}")
            self.stats_recordings.setText(f"Записей: {self.config.total_recordings:,}")
            self.stats_saved.setText(f"Время: {self.config.total_seconds_saved/60:.1f} мин")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)


class MainWindow(QMainWindow):
    status_update = pyqtSignal(str)
    audio_level_update = pyqtSignal(float)

    def __init__(self):
        super().__init__()

        self.config = Config.load()
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            on_level_update=self._on_audio_level,
            device=self.config.audio_device if self.config.audio_device != -1 else None,
            mic_boost=self.config.mic_boost
        )
        self.transcriber = Transcriber(
            backend=self.config.backend,
            model_size=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            language=self.config.language,
            on_progress=self._on_progress,
            enable_post_processing=self.config.enable_post_processing
        )
        self.hotkey_manager = HotkeyManager(on_hotkey=self._on_hotkey)
        self.history_manager = HistoryManager(max_entries=50)

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

        self._setup_ui()
        self._setup_tray()
        self._setup_text_popup()
        self._connect_signals()
        self.hotkey_manager.register(self.config.hotkey)
        # Preload model immediately (in background thread) to eliminate cold start
        QTimer.singleShot(100, self._load_model)

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

        # Status label (left) - фиксированная ширина для всех статусов
        self.status_label = QLabel("Готово", self.central)
        self.status_label.setStyleSheet("color: white; font-size: 13px; font-weight: 500;")
        self.status_label.setFixedWidth(85)  # Для "Готово", "Слушаю", "Обработка..."
        self.status_label.move(12, 17)

        # Timer label - позиционируется слева, чтобы не перекрывать кнопку записи
        self.timer_label = QLabel("", self.central)
        self.timer_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 10px;")
        self.timer_label.setFixedWidth(55)  # Компактный "9.9→9.9с"
        self.timer_label.move(95, 18)  # Слева от кнопки записи (95-150)
        self.timer_label.hide()

        # Center record button
        self.record_btn = RecordButton(self.central)
        self.record_btn.move((COMPACT_WIDTH - 36) // 2, (COMPACT_HEIGHT - 36) // 2)
        self.record_btn.clicked.connect(self._toggle_recording)

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
        self._set_corner_opacity(0.0)

        # Recording timer
        self._rec_timer = QTimer()
        self._rec_timer.timeout.connect(self._update_timer)

    def _set_corner_opacity(self, opacity: float):
        for btn in self._corner_btns:
            btn.set_opacity(opacity)

    def enterEvent(self, event):
        self._hover = True
        self._set_corner_opacity(0.7)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._set_corner_opacity(0.0)
        super().leaveEvent(event)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)

        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 32, 0)
        g.setColorAt(0, QColor(GRADIENT_COLORS['left']))
        g.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        g.setColorAt(1, QColor(GRADIENT_COLORS['right']))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 28, 28)
        p.end()
        self.tray.setIcon(QIcon(pix))

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
        self._text_popup.hide()

    def _copy_from_popup(self):
        """Копировать текст из всплывающей панели."""
        text = self._text_popup.get_text()
        if text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                self.status_label.setText("Скопировано!")
                QTimer.singleShot(1500, lambda: self.status_label.setText("Готово") if not self._recording else None)
            except:
                pass

    def _show_text_popup(self, text: str):
        """Показать всплывающую панель с текстом сверху окна."""
        if not text:
            return

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

    def _connect_signals(self):
        self.status_update.connect(self._set_status)
        self.audio_level_update.connect(self._set_level)

    def _load_model(self):
        threading.Thread(target=self.transcriber.load_model, daemon=True).start()

    def _on_audio_level(self, level):
        try:
            # Проверяем что окно ещё существует
            if not sip.isdeleted(self):
                self.audio_level_update.emit(min(1.0, level * 10))
        except:
            pass

    def _on_progress(self, msg):
        self.status_update.emit(msg)

    def _on_hotkey(self):
        self._toggle_recording()

    def _toggle_recording(self):
        # Защита от повторных вызовов во время обработки транскрибации
        if self._processing:
            with open("debug.log", "a") as f:
                f.write("[DEBUG] _toggle_recording BLOCKED by _processing flag\n")
            return

        # Debounce: блокируем только ПОВТОРНЫЙ запуск, не остановку!
        if not self._recording:
            current_time = time.time()
            if current_time - self._last_toggle_time < 0.3:
                with open("debug.log", "a") as f:
                    f.write(f"[DEBUG] _toggle_recording START BLOCKED by debounce ({current_time - self._last_toggle_time:.3f}s)\n")
                return
            self._last_toggle_time = current_time

        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _toggle_recording: _recording={self._recording}, _processing={self._processing}\n")

        if self._recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _start() called, _recording={self._recording}, _processing={self._processing}\n")

        if self.recorder.start():
            self._recording = True
            self._rec_start = time.time()
            self.status_label.setText("Слушаю")
            self.timer_label.setText("0.0с")
            self.timer_label.show()
            self.record_btn.set_recording(True)
            self._rec_timer.start(100)
            self.tray_rec.setText("Стоп")

            # Показываем кнопку отмены, скрываем кнопку закрытия
            self.cancel_btn.set_opacity(1.0)
            self.cancel_btn.show()
            self.close_btn.hide()

            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] _start() SUCCESS: recording started\n")
        else:
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] _start() FAILED: recorder.start() returned False\n")

    def _stop(self):
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _stop() called, _recording={self._recording}, _processing={self._processing}\n")

        self._recording = False
        self._processing = True  # Блокируем повторные вызовы
        self._rec_timer.stop()

        # Сохраняем время записи
        self._rec_duration = time.time() - self._rec_start

        audio = self.recorder.stop()

        self.timer_label.hide()
        self.record_btn.set_recording(False)
        self.tray_rec.setText("Запись")

        # Скрываем кнопку отмены, показываем кнопку закрытия
        self.cancel_btn.hide()
        self.close_btn.show()

        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _stop(): audio is None={audio is None}, len={len(audio) if audio is not None else 0}\n")

        if audio is None or len(audio) == 0 or self.recorder.get_duration(audio) < 0.5:
            self.status_label.setText("Готово")
            self._processing = False  # Разблокируем
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] _stop(): audio too short, _processing set to False\n")
            return

        self.status_label.setText("Обработка...")
        self._transcription_start = time.time()  # Фиксируем начало транскрибации
        self._thread = TranscriptionThread(self.transcriber, audio, self.config.sample_rate)
        self._thread.finished.connect(self._done)
        self._thread.error.connect(self._error)
        self._thread.start()

        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _stop(): transcription thread started, _processing={self._processing}\n")

    def _cancel_recording(self):
        """Отменить запись без транскрибации."""
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _cancel_recording() called\n")

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

        # Скрываем кнопку отмены, показываем кнопку закрытия
        self.cancel_btn.hide()
        self.close_btn.show()

        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _cancel_recording(): recording cancelled\n")

    def _update_timer(self):
        self.timer_label.setText(f"{time.time() - self._rec_start:.1f}с")

    def _done(self, text, duration):
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _done() called, setting _processing=False, text_len={len(text)}\n")

        self._processing = False  # Разблокируем
        self._last_text = text

        # Вычисляем время транскрибации
        transcription_time = time.time() - self._transcription_start

        # Показываем время записи → время транскрибации на 2 секунды
        self.status_label.setText("Готово")
        self.timer_label.setText(f"{self._rec_duration:.1f}→{transcription_time:.1f}с")
        self.timer_label.show()
        QTimer.singleShot(2000, self._hide_timer_after_done)

        # Убеждаемся что кнопка закрытия видна (на всякий случай)
        self.cancel_btn.hide()
        self.close_btn.show()

        if self._settings and self._settings.isVisible():
            self._settings.update_stats_display()
            self._settings._update_history_display()

        self.config.update_stats(len(text.split()), self._rec_duration)
        self.history_manager.add_entry(text, duration, self.config.backend, self.config.model_size)

        # Авто-копирование в буфер обмена
        if self.config.auto_copy and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
            except:
                pass

        # Показываем всплывающую панель с текстом ВСЕГДА
        self._show_text_popup(text)

        # Авто-вставка текста если включено
        if self.config.auto_paste:
            QTimer.singleShot(100, lambda: self._type(text))

        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] _done() finished, _processing={self._processing}\n")

    def _hide_timer_after_done(self):
        """Скрыть таймер после показа результата."""
        if not self._recording:
            self.timer_label.hide()

    def _error(self, err):
        self._processing = False  # Разблокируем
        self.status_label.setText("Ошибка")

        # Возвращаем кнопку закрытия при ошибке
        self.cancel_btn.hide()
        self.close_btn.show()

    def _type(self, text):
        try:
            type_text(text)
        except Exception as e:
            pass

    def _set_status(self, msg):
        self.status_label.setText(msg)

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
                QTimer.singleShot(1500, lambda: self.status_label.setText("Готово") if not self._recording else None)
            except:
                pass

    def _show_history(self):
        self._show_settings()
        if self._settings:
            self._settings.tabs.setCurrentIndex(1)

    def _show_settings(self):
        if not self._settings:
            self._settings = SettingsDialog(self, self.config, self.history_manager)
            self._settings.backend_combo.currentIndexChanged.connect(self._backend_changed)
            self._settings.model_combo.currentIndexChanged.connect(self._model_changed)
            self._settings.lang_combo.currentIndexChanged.connect(self._lang_changed)
            self._settings.auto_copy_cb.toggled.connect(lambda c: setattr(self.config, 'auto_copy', c) or self.config.save())
            self._settings.auto_paste_cb.toggled.connect(lambda c: setattr(self.config, 'auto_paste', c) or self.config.save())
            self._settings.always_top_cb.toggled.connect(self._top_changed)
            self._settings.post_process_cb.toggled.connect(self._post_changed)

        self._settings.move(self.pos().x(), self.pos().y() + self.height() + 10)
        self._settings.show()
        self._settings.raise_()

    def _backend_changed(self):
        bid = self._settings.backend_combo.currentData()
        if bid != self.config.backend:
            self.config.backend = bid
            self._settings._update_model_options()
            default = {"whisper": "base", "sherpa": "giga-am-v2-ru", "podlodka-turbo": "podlodka-turbo"}.get(bid, "base")
            self.config.model_size = default
            self.config.save()
            self.transcriber.switch_backend(bid, default)

    def _model_changed(self):
        mid = self._settings.model_combo.currentData()
        if mid and mid != self.config.model_size:
            self.config.model_size = mid
            self.config.save()
            self.transcriber.switch_backend(self.config.backend, mid)

    def _lang_changed(self):
        lid = self._settings.lang_combo.currentData()
        self.config.language = lid
        self.config.save()
        self.transcriber.language = lid if lid != "auto" else None

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
        self.hotkey_manager.unregister()
        self.tray.hide()
        self.config.save()
        QApplication.quit()


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("ГолосТекст")
    app.setQuitOnLastWindowClosed(False)
    MainWindow().show()
    sys.exit(app.exec())
