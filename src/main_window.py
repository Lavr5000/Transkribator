"""Main window for ГолосТекст application - Compact WhisperTyping style."""
import sys
import time
import json
import threading
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox,
    QCheckBox, QGroupBox, QTabWidget, QButtonGroup,
    QSystemTrayIcon, QMenu, QMessageBox,
    QApplication, QDialog, QScrollArea, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QLineEdit, QAbstractItemView,
    QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPoint, QRectF, QSize
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QAction, QColor,
    QPainter, QLinearGradient, QBrush, QPen, QMouseEvent,
    QPainterPath
)
from PyQt6 import sip

from config import Config, WHISPER_MODELS, SHERPA_MODELS, PODLODKA_MODELS, LANGUAGES, BACKENDS, MOUSE_BUTTONS, PASTE_METHODS, QUALITY_PROFILES, MODEL_METADATA
from audio_recorder import AudioRecorder
from transcriber import Transcriber, get_available_backends
from hotkeys import HotkeyManager, type_text, safe_paste_text, paste_from_clipboard
from history_manager import HistoryManager
from mouse_handler import MouseButtonHandler
from remote_client import RemoteTranscriptionClient

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


# Gradient colors - Algorithmic Presence theme
GRADIENT_COLORS = {
    'left': '#081420',      # Deepest navy
    'middle': '#0F2840',    # Electric blue-dark
    'right': '#1E5080',     # Lighter navy-blue
}

COLORS = {
    'bg_darkest': (8, 12, 20),       # #080C14 - Near black
    'bg_dark': (15, 25, 40),         # #0F1928 - Deep navy
    'bg_mid': (25, 40, 65),          # #192841 - Mid navy
    'accent_primary': (0, 120, 255),   # #0078FF - Electric blue
    'accent_secondary': (0, 200, 255), # #00C8FF - Cyan
    'accent_glow': (100, 220, 255),    # #64DCFF - Light cyan
    'text_primary': (245, 248, 255),   # #F5F8FF - Nearly white
    'text_secondary': (140, 160, 180), # #8CA0B4 - Muted blue-gray
    'success': (10, 185, 129),        # #0AB981 - Emerald green
    'border': (25, 40, 65),           # #192841 - Subtle border
}

# Hex versions for CSS stylesheets
COLORS_HEX = {
    'bg_darkest': '#080C14',
    'bg_dark': '#0F1928',
    'bg_mid': '#192841',
    'accent_primary': '#0078FF',      # Electric blue
    'accent_secondary': '#00C8FF',    # Cyan
    'accent_glow': '#64DCFF',         # Light cyan
    'text_primary': '#F5F8FF',
    'text_secondary': '#8CA0B4',
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
    background-color: {COLORS['bg_mid']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 16px;
}}
QPushButton:hover {{
    background-color: {COLORS['accent_primary']};
}}
QTextEdit {{
    background-color: {COLORS['bg_mid']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px;
}}
QComboBox {{
    background-color: {COLORS['bg_mid']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_mid']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent_primary']};
}}
QCheckBox {{
    color: {COLORS['text_primary']};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLORS['border']};
    background-color: {COLORS['bg_mid']};
}}
QCheckBox::indicator:checked {{
    background-color: {COLORS['accent_primary']};
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
    background-color: {COLORS['bg_mid']};
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

    # Timeout for local transcription before trying remote
    LOCAL_TIMEOUT_SECONDS = 20.0

    def __init__(self, remote_client, transcriber, audio, sample_rate: int, enable_remote: bool = False):
        super().__init__()
        self.remote_client = remote_client
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate
        self._is_cancelled = False
        self._enable_remote = enable_remote  # Allow disabling remote fallback

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
                        text, duration = future.result(timeout=self.LOCAL_TIMEOUT_SECONDS)

                        if not self._is_cancelled and text:
                            # Local transcription successful!
                            self.transcription_done.emit(text, duration, False)  # is_remote=False
                            return

                    except concurrent.futures.TimeoutError:
                        # Local transcription took too long - cancel and try remote
                        future.cancel()
                        with open("debug.log", "a", encoding="utf-8") as f:
                            f.write(f"[DEBUG] Local transcription timeout ({self.LOCAL_TIMEOUT_SECONDS}s)\n")
                        raise Exception("Local transcription timeout")

            except Exception as local_error:
                # Local transcription failed - try remote fallback
                if not self._is_cancelled:
                    with open("debug.log", "a", encoding="utf-8") as f:
                        f.write(f"[DEBUG] Local transcription failed: {local_error}\n")
                        f.write(f"[DEBUG] Trying remote fallback...\n")

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
                        with open("debug.log", "a", encoding="utf-8") as f:
                            f.write(f"[DEBUG] Remote transcription also failed: {remote_error}\n")
                        self.transcription_error.emit(f"Local and remote failed: {remote_error}")

            # === Remote fallback disabled or not available ===
            elif not self._is_cancelled:
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[DEBUG] Local transcription failed, remote fallback disabled\n")
                self.transcription_error.emit("Local transcription failed. Enable remote fallback in settings if needed.")

        except Exception as e:
            if not self._is_cancelled:
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[DEBUG] HybridTranscriptionThread error: {e}\n")
                self.transcription_error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True


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
            # Recording state - Algorithmic Presence cyan glow
            base_alpha = 180

            # Pulsing circles with cyan glow - 4 layers for richer effect
            for i in range(4):
                import math
                phase_offset = i * 0.8
                pulse = (math.sin(self._wave_phase + phase_offset) + 1) / 2
                radius = 8 + i * 6 + self._audio_level * 8 * pulse
                alpha = int(base_alpha * (1 - i * 0.25) * (0.5 + self._audio_level * 0.5))

                painter.setPen(Qt.PenStyle.NoPen)
                # Algorithmic Presence cyan
                painter.setBrush(QColor(*COLORS['accent_secondary'], alpha))
                painter.drawEllipse(
                    QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
                )

            # Center circle (stop button) - light cyan
            painter.setBrush(QColor(*COLORS['accent_glow'], 240))
            painter.drawRoundedRect(
                QRectF(center_x - 6, center_y - 6, 12, 12), 2, 2
            )
        else:
            # Idle state - geometric mic icon with electric blue
            # Outer glow on hover
            if self.underMouse():
                painter.setBrush(QColor(*COLORS['accent_primary'], 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(2, 2, 32, 32))

            # Mic body - electric blue color
            painter.setPen(QPen(QColor(*COLORS['accent_secondary'], 220), 2))
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

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Geometric rounded square background
        bg_alpha = int(100 * self._opacity)
        painter.setBrush(QColor(*COLORS['bg_mid'], bg_alpha))
        painter.setPen(QPen(QColor(255, 255, 255, int(255 * self._opacity)), 1))
        painter.drawRoundedRect(QRectF(0, 0, 18, 18), 4, 4)

        # Subclasses implement icon drawing on top of background
        self._draw_icon(painter)

    def _draw_icon(self, painter):
        # Override in subclasses
        pass


class CopyButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw two overlapping rectangles (copy icon)
        painter.drawRoundedRect(QRectF(3, 5, 8, 10), 1, 1)
        painter.drawRoundedRect(QRectF(7, 3, 8, 10), 1, 1)


class HistoryButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))

        # Draw clock icon
        painter.drawEllipse(QRectF(3, 3, 12, 12))
        painter.drawLine(QPoint(9, 5), QPoint(9, 9))
        painter.drawLine(QPoint(9, 9), QPoint(12, 9))


class SettingsButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Geometric gear - 8 spokes for better look
        import math
        center_x, center_y = 9, 9
        for i in range(8):
            angle = i * math.pi / 4
            r_inner, r_outer = 5, 8
            x1, y1 = center_x + r_inner * math.cos(angle), center_y + r_inner * math.sin(angle)
            x2, y2 = center_x + r_outer * math.cos(angle), center_y + r_outer * math.sin(angle)
            painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))

        # Center circle
        painter.drawEllipse(QRectF(center_x - 3, center_y - 3, 6, 6))


class CloseButton(MiniButton):
    def _draw_icon(self, painter):
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

        # Yellow-orange color for cancel
        color = QColor(255, 200, 50, min(255, alpha + hover_boost))

        painter.setPen(QPen(color, 2.0))

        # Draw thicker X
        painter.drawLine(QPoint(4, 4), QPoint(14, 14))
        painter.drawLine(QPoint(14, 4), QPoint(4, 14))


class ClickableLabel(QLabel):
    """Label that opens URL on click."""

    def __init__(self, text, url, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            import webbrowser
            webbrowser.open(self.url)

    def enterEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("opacity: 0.7", "opacity: 1.0"))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("opacity: 1.0", "opacity: 0.7"))
        super().leaveEvent(event)


class DictionaryEntryDialog(QDialog):
    """Dialog for adding/editing dictionary entries."""

    def __init__(self, parent=None, wrong: str = "", correct: str = "", case_sensitive: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Запись словаря")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLESHEET)
        self._setup_ui(wrong, correct, case_sensitive)

    def _setup_ui(self, wrong: str, correct: str, case_sensitive: bool):
        layout = QVBoxLayout(self)

        # Wrong spelling field
        wrong_label = QLabel("Неправильное написание:")
        layout.addWidget(wrong_label)
        self.wrong_input = QLineEdit()
        self.wrong_input.setText(wrong)
        self.wrong_input.setPlaceholderText("Например: торопинка")
        layout.addWidget(self.wrong_input)

        # Correct spelling field
        correct_label = QLabel("Правильное написание:")
        layout.addWidget(correct_label)
        self.correct_input = QLineEdit()
        self.correct_input.setText(correct)
        self.correct_input.setPlaceholderText("Например: переписка")
        layout.addWidget(self.correct_input)

        # Case sensitive checkbox
        self.case_sensitive_cb = QCheckBox("С учетом регистра")
        self.case_sensitive_cb.setChecked(case_sensitive)
        layout.addWidget(self.case_sensitive_cb)

        layout.addSpacing(20)

        # Buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def get_entry(self) -> dict:
        """Get the dictionary entry from dialog inputs."""
        return {
            "wrong": self.wrong_input.text().strip(),
            "correct": self.correct_input.text().strip(),
            "case_sensitive": self.case_sensitive_cb.isChecked()
        }

    def accept(self):
        """Validate and accept the dialog."""
        wrong = self.wrong_input.text().strip()
        correct = self.correct_input.text().strip()

        if not wrong or not correct:
            QMessageBox.warning(self, "Ошибка", "Заполните оба поля")
            return

        if wrong == correct:
            QMessageBox.warning(self, "Ошибка", "Значения не должны быть одинаковыми")
            return

        super().accept()


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

        # Algorithmic Presence gradient background
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        # Текст с Algorithmic Presence цветом
        if self._text:
            painter.setPen(QPen(QColor(*COLORS['text_primary'], 230)))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)

            # Отступы
            text_rect = self.rect().adjusted(12, 8, -40, -8)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, self._text)

        # Кнопка копирования (справа) - electric blue accent
        copy_btn_x = self.width() - 30
        copy_btn_y = (self.height() - 18) // 2

        painter.setPen(QPen(QColor(*COLORS['accent_secondary'], 200), 1.5))
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
        self._create_dictionary_tab()
        self._create_history_tab()

    def _create_settings_tab(self):
        """Create settings tab - minimal version."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Use scroll area for proper layout
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        scroll_layout = QVBoxLayout(content)

        # === Quality Profile Selection (Phase 4) ===
        quality_group = QGroupBox("Профиль качества")
        quality_layout = QVBoxLayout(quality_group)

        # Create button group for radio-like behavior
        self.quality_profile_group = QButtonGroup()
        self.quality_profile_buttons = {}

        for profile_id in ["fast", "balanced", "quality"]:
            profile_info = QUALITY_PROFILES[profile_id]
            btn = QPushButton(profile_info["description"])
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['bg_mid']};
                    color: {COLORS['text_primary']};
                    border: 2px solid {COLORS['border']};
                    border-radius: 8px;
                    padding: 12px 8px;
                    text-align: center;
                    font-size: 12px;
                }}
                QPushButton:checked {{
                    background-color: {COLORS['accent_primary']};
                    border-color: {COLORS['accent_secondary']};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent_primary']};
                }}
            """)
            self.quality_profile_buttons[profile_id] = btn
            self.quality_profile_group.addButton(btn, int(profile_id == "fast") + int(profile_id == "balanced") * 2 + int(profile_id == "quality") * 3)
            quality_layout.addWidget(btn)

        # Set current profile
        current_profile = self.config.quality_profile if self.config else "quality"
        if current_profile in self.quality_profile_buttons:
            self.quality_profile_buttons[current_profile].setChecked(True)

        scroll_layout.addWidget(quality_group)

        # Info label
        scroll_layout.addWidget(QLabel(f"Бэкенд: {self.config.backend if self.config else 'N/A'}"))
        scroll_layout.addWidget(QLabel(f"Модель: {self.config.model_size if self.config else 'N/A'}"))

        # Backend combo
        backend_group = QGroupBox("Движок")
        backend_layout = QVBoxLayout(backend_group)
        self.backend_combo = QComboBox()
        for bid, bname in BACKENDS.items():
            self.backend_combo.addItem(bname, bid)
        if self.config:
            self.backend_combo.setCurrentIndex(list(BACKENDS.keys()).index(self.config.backend))
        backend_layout.addWidget(self.backend_combo)
        scroll_layout.addWidget(backend_group)

        # Model combo
        model_group = QGroupBox("Модель")
        model_layout = QVBoxLayout(model_group)
        self.model_combo = QComboBox()
        # Fill models based on current backend
        self._update_model_options()
        model_layout.addWidget(self.model_combo)

        # Model info label
        self.model_info_label = QLabel()
        self.model_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        model_layout.addWidget(self.model_info_label)

        scroll_layout.addWidget(model_group)

        # Language combo
        lang_group = QGroupBox("Язык")
        lang_layout = QVBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        for lid, lname in LANGUAGES.items():
            self.lang_combo.addItem(lname, lid)
        if self.config and self.config.language in LANGUAGES:
            self.lang_combo.setCurrentIndex(list(LANGUAGES.keys()).index(self.config.language))
        lang_layout.addWidget(self.lang_combo)
        scroll_layout.addWidget(lang_group)

        # Behavior group
        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_copy_cb = QCheckBox("Авто-копирование")
        self.auto_paste_cb = QCheckBox("Авто-вставка")

        # Paste method selection
        paste_method_label = QLabel("Метод вставки:")
        paste_method_label.setStyleSheet("margin-top: 5px;")
        self.paste_method_combo = QComboBox()
        for mid, mname in PASTE_METHODS.items():
            self.paste_method_combo.addItem(mname, mid)
        if self.config and self.config.paste_method in PASTE_METHODS:
            self.paste_method_combo.setCurrentIndex(
                list(PASTE_METHODS.keys()).index(self.config.paste_method)
            )

        self.always_top_cb = QCheckBox("Поверх окон")
        self.post_process_cb = QCheckBox("Пост-обработка")

        if self.config:
            self.auto_copy_cb.setChecked(self.config.auto_copy)
            self.auto_paste_cb.setChecked(self.config.auto_paste)
            self.always_top_cb.setChecked(self.config.always_on_top)
            self.post_process_cb.setChecked(self.config.enable_post_processing)

        behavior_layout.addWidget(self.auto_copy_cb)
        behavior_layout.addWidget(self.auto_paste_cb)
        behavior_layout.addWidget(paste_method_label)
        behavior_layout.addWidget(self.paste_method_combo)
        behavior_layout.addWidget(self.always_top_cb)
        behavior_layout.addWidget(self.post_process_cb)
        scroll_layout.addWidget(behavior_group)

        # Mouse button group
        mouse_group = QGroupBox("Кнопка мыши")
        mouse_layout = QVBoxLayout(mouse_group)

        # Enable checkbox
        self.enable_mouse_button_cb = QCheckBox("Использовать кнопку мыши для записи")
        if self.config:
            self.enable_mouse_button_cb.setChecked(self.config.enable_mouse_button)
        mouse_layout.addWidget(self.enable_mouse_button_cb)

        # Button selection
        self.mouse_button_combo = QComboBox()
        for bid, bname in MOUSE_BUTTONS.items():
            self.mouse_button_combo.addItem(bname, bid)
        if self.config and self.config.mouse_button in MOUSE_BUTTONS:
            self.mouse_button_combo.setCurrentIndex(
                list(MOUSE_BUTTONS.keys()).index(self.config.mouse_button)
            )
        mouse_layout.addWidget(self.mouse_button_combo)

        scroll_layout.addWidget(mouse_group)

        # VAD Settings group
        vad_group = QGroupBox("Голосовая активность (VAD)")
        vad_layout = QVBoxLayout(vad_group)

        # VAD Threshold slider
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Порог:")
        threshold_label.setFixedWidth(80)
        threshold_layout.addWidget(threshold_label)

        self.vad_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_threshold_slider.setRange(0, 100)  # 0.0-1.0
        vad_layout.addWidget(QLabel("Чувствительность детекции речи"))
        vad_layout.addWidget(self.vad_threshold_slider)

        self.vad_threshold_value = QLabel("0.50")
        self.vad_threshold_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vad_threshold_value.setFixedWidth(50)
        vad_layout.addWidget(self.vad_threshold_value)

        threshold_positions = QHBoxLayout()
        threshold_positions.addWidget(QLabel("Тихий"))
        threshold_positions.addStretch()
        threshold_positions.addWidget(QLabel("Чувствительный"))
        vad_layout.addLayout(threshold_positions)

        # Min Silence Duration slider
        vad_layout.addSpacing(10)
        vad_layout.addWidget(QLabel("Мин. тишина перед остановкой:"))

        silence_layout = QHBoxLayout()
        self.min_silence_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_silence_slider.setRange(100, 3000)  # 100-3000ms
        vad_layout.addWidget(self.min_silence_slider)

        self.min_silence_value = QLabel("800мс")
        self.min_silence_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_silence_value.setFixedWidth(60)
        vad_layout.addWidget(self.min_silence_value)

        silence_positions = QHBoxLayout()
        silence_positions.addWidget(QLabel("Коротко"))
        silence_positions.addStretch()
        silence_positions.addWidget(QLabel("Долго"))
        vad_layout.addLayout(silence_positions)

        # Reset button
        vad_layout.addSpacing(10)
        vad_reset_btn = QPushButton("Сбросить настройки VAD")
        vad_reset_btn.clicked.connect(self._reset_vad_defaults)
        vad_layout.addWidget(vad_reset_btn)

        scroll_layout.addWidget(vad_group)

        # Noise Reduction group
        noise_group = QGroupBox("Шумоподавление")
        noise_layout = QVBoxLayout(noise_group)

        # WebRTC Enable checkbox
        self.webrtc_enabled_cb = QCheckBox("Включить обработку WebRTC")
        self.webrtc_enabled_cb.setToolTip("Шумоподавление и автоматическая регулировка усиления")
        noise_layout.addWidget(self.webrtc_enabled_cb)

        # Noise Suppression Level slider
        noise_layout.addSpacing(5)
        noise_layout.addWidget(QLabel("Уровень подавления шума:"))

        self.noise_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.noise_level_slider.setRange(0, 4)
        noise_layout.addWidget(self.noise_level_slider)

        self.noise_level_value = QLabel("Умеренно")
        self.noise_level_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        noise_layout.addWidget(self.noise_level_value)

        noise_positions = QHBoxLayout()
        noise_positions.addWidget(QLabel("Выкл"))
        noise_positions.addWidget(QLabel("Слабо"))
        noise_positions.addWidget(QLabel("Умеренно"))
        noise_positions.addWidget(QLabel("Сильно"))
        noise_positions.addWidget(QLabel("Очень"))
        noise_layout.addLayout(noise_positions)

        # Noise status indicator
        self.noise_status_label = QLabel("(Активно)")
        self.noise_status_label.setStyleSheet(f"color: {COLORS['accent_secondary']}; font-size: 11px;")
        noise_layout.addWidget(self.noise_status_label)

        # Reset button
        noise_layout.addSpacing(10)
        noise_reset_btn = QPushButton("Сбросить настройки шума")
        noise_reset_btn.clicked.connect(self._reset_noise_defaults)
        noise_layout.addWidget(noise_reset_btn)

        scroll_layout.addWidget(noise_group)

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

    def _create_dictionary_tab(self):
        """Create the user dictionary tab for custom corrections."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.dictionary_search = QLineEdit()
        self.dictionary_search.setPlaceholderText("Введите текст для поиска...")
        self.dictionary_search.textChanged.connect(self._filter_dictionary)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.dictionary_search)
        layout.addLayout(search_layout)

        # Dictionary table
        self.dictionary_table = QTableWidget()
        self.dictionary_table.setColumnCount(3)
        self.dictionary_table.setHorizontalHeaderLabels(["Неправильно", "Правильно", "С учетом регистра"])
        self.dictionary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dictionary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.dictionary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dictionary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dictionary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.dictionary_table)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.dict_add_btn = QPushButton("Добавить")
        self.dict_add_btn.clicked.connect(self._add_dictionary_entry)
        buttons_layout.addWidget(self.dict_add_btn)

        self.dict_edit_btn = QPushButton("Изменить")
        self.dict_edit_btn.clicked.connect(self._edit_dictionary_entry)
        buttons_layout.addWidget(self.dict_edit_btn)

        self.dict_delete_btn = QPushButton("Удалить")
        self.dict_delete_btn.clicked.connect(self._delete_dictionary_entry)
        buttons_layout.addWidget(self.dict_delete_btn)

        layout.addLayout(buttons_layout)

        # Import/Export buttons
        io_layout = QHBoxLayout()

        self.dict_import_btn = QPushButton("Импорт")
        self.dict_import_btn.clicked.connect(self._import_dictionary)
        io_layout.addWidget(self.dict_import_btn)

        self.dict_export_btn = QPushButton("Экспорт")
        self.dict_export_btn.clicked.connect(self._export_dictionary)
        io_layout.addWidget(self.dict_export_btn)

        layout.addLayout(io_layout)

        self.tabs.addTab(tab, "Словарь")
        self._update_dictionary_display()

    def _update_dictionary_display(self):
        """Update the dictionary table with current entries."""
        if not hasattr(self, 'dictionary_table'):
            return

        self.dictionary_table.setRowCount(0)

        if not self.config:
            return

        for entry in self.config.user_dictionary:
            row = self.dictionary_table.rowCount()
            self.dictionary_table.insertRow(row)
            self.dictionary_table.setItem(row, 0, QTableWidgetItem(entry.get("wrong", "")))
            self.dictionary_table.setItem(row, 1, QTableWidgetItem(entry.get("correct", "")))

            case_sensitive = entry.get("case_sensitive", False)
            case_item = QTableWidgetItem("Да" if case_sensitive else "Нет")
            case_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dictionary_table.setItem(row, 2, case_item)

    def _filter_dictionary(self, text: str):
        """Filter dictionary table by search text."""
        search_text = text.lower()
        for row in range(self.dictionary_table.rowCount()):
            show = False
            for col in range(2):  # Only check wrong/correct columns
                item = self.dictionary_table.item(row, col)
                if item and search_text in item.text().lower():
                    show = True
                    break
            self.dictionary_table.setRowHidden(row, not show)

    def _add_dictionary_entry(self):
        """Add a new dictionary entry."""
        dialog = DictionaryEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry = dialog.get_entry()
            self.config.user_dictionary.append(entry)
            self.config.save()
            self._update_dictionary_display()
            # Update transcriber
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _edit_dictionary_entry(self):
        """Edit selected dictionary entry."""
        selected = self.dictionary_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Выберите запись для изменения")
            return

        row = self.dictionary_table.currentRow()
        wrong = self.dictionary_table.item(row, 0).text()
        correct = self.dictionary_table.item(row, 1).text()
        case_sensitive = self.dictionary_table.item(row, 2).text() == "Да"

        dialog = DictionaryEntryDialog(self, wrong, correct, case_sensitive)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry = dialog.get_entry()
            # Update the entry at this row
            self.config.user_dictionary[row] = entry
            self.config.save()
            self._update_dictionary_display()
            # Update transcriber
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _delete_dictionary_entry(self):
        """Delete selected dictionary entry."""
        selected = self.dictionary_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Выберите запись для удаления")
            return

        row = self.dictionary_table.currentRow()
        wrong = self.config.user_dictionary[row].get("wrong", "")

        reply = QMessageBox.question(
            self, "Подтверждение",
            f'Удалить запись "{wrong}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.config.user_dictionary[row]
            self.config.save()
            self._update_dictionary_display()
            # Update transcriber
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _import_dictionary(self):
        """Import dictionary from JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Импорт словаря", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported = json.load(f)

                # Merge with existing (no duplicates by "wrong" field)
                existing_wrongs = {e.get("wrong") for e in self.config.user_dictionary}
                for entry in imported:
                    wrong = entry.get("wrong")
                    if wrong and wrong not in existing_wrongs:
                        self.config.user_dictionary.append(entry)
                        existing_wrongs.add(wrong)

                self.config.save()
                self._update_dictionary_display()
                # Update transcriber
                if hasattr(self, 'transcriber'):
                    self.transcriber.set_user_dictionary(self.config.user_dictionary)

                QMessageBox.information(self, "Успех", f"Импортировано записей: {len(imported)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать: {e}")

    def _export_dictionary(self):
        """Export dictionary to JSON file."""
        if not self.config.user_dictionary:
            QMessageBox.information(self, "Информация", "Словарь пуст")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт словаря", "dictionary.json", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config.user_dictionary, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Успех", f"Экспортировано записей: {len(self.config.user_dictionary)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {e}")

    def _update_model_options(self):
        self.model_combo.clear()
        if not self.config:
            return
        backend = self.backend_combo.currentData() or self.config.backend
        models = {"whisper": WHISPER_MODELS, "sherpa": SHERPA_MODELS, "podlodka-turbo": PODLODKA_MODELS}.get(backend, {})

        # Sort models by RTF (fastest first)
        sorted_models = sorted(models.items(), key=lambda x: MODEL_METADATA.get(x[0], {}).get("rtf", 1.0))

        for mid, mname in sorted_models:
            # Format with metadata
            meta = MODEL_METADATA.get(mid, {})
            ram = meta.get("ram_mb", "?")
            desc = meta.get("description", "")
            display_text = f"{mid} — {ram}MB — {desc}"
            self.model_combo.addItem(display_text, mid)

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

    def _reset_vad_defaults(self):
        """Reset VAD settings to defaults."""
        self.vad_threshold_slider.setValue(50)
        self.min_silence_slider.setValue(800)

    def _noise_level_changed(self, value: int):
        """Handle noise level slider change."""
        labels = ["Выкл", "Слабо", "Умеренно", "Сильно", "Очень сильно"]
        self.noise_level_value.setText(labels[value] if 0 <= value < len(labels) else "Умеренно")

    def _reset_noise_defaults(self):
        """Reset noise reduction settings to defaults."""
        self.webrtc_enabled_cb.setChecked(True)
        self.noise_level_slider.setValue(2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)


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

        # Preload model to avoid first transcription delay
        self._on_progress("Preloading transcription model...")
        try:
            self.transcriber.load_model()
            self._on_progress("Model loaded successfully!")
        except Exception as e:
            self._on_progress(f"Model preload failed: {e}")

        self.hotkey_manager = HotkeyManager(on_hotkey=self._on_hotkey)
        self.history_manager = HistoryManager(max_entries=50)

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
        self.brand_label = ClickableLabel("NoCodeiFounder", "https://t.me/ai_vibes_coding_ru", self.central)
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
        self.record_btn.move((COMPACT_WIDTH - 36) // 2, (COMPACT_HEIGHT - 36) // 2)
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
        # Показываем статус "Готово" при наведении
        if self.status_label.text() == "Готово":
            self.status_label.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._set_corner_opacity(0.0)
        # Скрываем статус "Готово" когда мышка ушла
        if self.status_label.text() == "Готово":
            self.status_label.hide()
        super().leaveEvent(event)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)

        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Aural Flux gradient for tray icon
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
                self.status_label.show()  # Показываем статус копирования
                QTimer.singleShot(1500, self._restore_status_after_copy)
            except:
                pass

    def _restore_status_after_copy(self):
        """Восстановить статус после копирования."""
        if not self._recording:
            self.status_label.setText("Готово")
            # Скрываем "Готово" если нет hover
            if not self._hover:
                self.status_label.hide()

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
        # Connect toggle signal for thread-safe hotkey/mouse callbacks
        # This ensures _toggle_recording runs in the main Qt thread
        self._request_toggle.connect(self._toggle_recording, Qt.ConnectionType.QueuedConnection)

    def _load_model(self):
        threading.Thread(target=self.transcriber.load_model, daemon=True).start()

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
            # DEBUG: Print to console to verify callback is working
            # print(f"[MAIN WINDOW] VAD level update: {level:.6f}")

            # Проверяем что окно ещё существует и не закрывается
            if not self._shutting_down and not sip.isdeleted(self):
                # Convert level to percentage with higher gain for better sensitivity
                # Audio levels are typically very small (0.001-0.1), so we amplify
                percentage = min(100, int(level * 10000))

                # Update the level bar (if exists)
                if self.vad_level_bar:
                    self.vad_level_bar.setValue(percentage)

                # VAD level bar removed - no color changes needed
        except (RuntimeError, AttributeError) as e:
            print(f"[VAD UI ERROR] {e}")  # DEBUG

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
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write("[DEBUG] _toggle_recording BLOCKED by _processing flag\n")
            return

        # Debounce: блокируем только ПОВТОРНЫЙ запуск, не остановку!
        if not self._recording:
            current_time = time.time()
            if current_time - self._last_toggle_time < 0.3:
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[DEBUG] _toggle_recording START BLOCKED by debounce ({current_time - self._last_toggle_time:.3f}s)\n")
                return
            self._last_toggle_time = current_time

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _toggle_recording: _recording={self._recording}, _processing={self._processing}\n")

        if self._recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _start() called, _recording={self._recording}, _processing={self._processing}\n")

        # Reset VAD level bar to silence state (if exists)
        if self.vad_level_bar:
            self.vad_level_bar.setValue(0)

        if self.recorder.start():
            self._recording = True
            self._rec_start = time.time()
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

            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DEBUG] _start() SUCCESS: recording started\n")
        else:
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DEBUG] _start() FAILED: recorder.start() returned False\n")

    def _stop(self):
        with open("debug.log", "a", encoding="utf-8") as f:
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

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _stop(): audio is None={audio is None}, len={len(audio) if audio is not None else 0}\n")

        if audio is None or len(audio) == 0 or self.recorder.get_duration(audio) < 0.5:
            self.status_label.setText("Готово")
            # Скрываем "Готово" если нет hover
            if not self._hover:
                self.status_label.hide()
            self._processing = False  # Разблокируем
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DEBUG] _stop(): audio too short, _processing set to False\n")
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

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _stop(): transcription thread started, _processing={self._processing}\n")

    def _cancel_recording(self):
        """Отменить запись без транскрибации."""
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _cancel_recording() called\n")

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

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _cancel_recording(): recording cancelled\n")

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
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _done() called, setting _processing=False, text_len={len(text)}, is_remote={is_remote}\n")

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
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] Transcription time: {transcription_time:.1f}s, is_remote={is_remote}\n")

        try:
            if is_remote:  # Remote transcription successful
                self.mode_label.setText("🌐")
                self.mode_label.setToolTip("Удаленная транскрибация")
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[DEBUG] Mode: REMOTE (is_remote=True)\n")
            else:  # Local transcription (fallback)
                self.mode_label.setText("🏠")
                self.mode_label.setToolTip("Локальная транскрибация")
                with open("debug.log", "a", encoding="utf-8") as f:
                    f.write(f"[DEBUG] Mode: LOCAL (is_remote=False, fallback)\n")
            self.mode_label.show()

            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"[DEBUG] Mode label shown: {self.mode_label.text()}\n")
        except Exception as e:
            with open("debug.log", "a", encoding="utf-8") as f:
                f.write(f"[ERROR] Failed to show mode_label: {e}\n")

        QTimer.singleShot(5000, self._hide_timer_after_done)  # Changed to 5 seconds

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

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _done() finished, _processing={self._processing}\n")

    def _hide_timer_after_done(self):
        """Скрыть таймер после показа результата."""
        if not self._recording:
            self.timer_label.hide()
            self.mode_label.hide()

    def _error(self, err):
        # Check if we're shutting down
        if self._shutting_down:
            return

        self._processing = False  # Разблокируем
        self.status_label.setText("Ошибка")
        self.status_label.show()  # Показываем статус ошибки

        # Возвращаем кнопку закрытия при ошибке
        self.cancel_btn.hide()
        self.close_btn.show()

        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] _error() called: {err}\n")

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
            print(f"Paste/type error: {e}")

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
            except:
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

            self._settings.move(self.pos().x(), self.pos().y() + self.height() + 10)
            self._settings.show()
            self._settings.raise_()
        except Exception as e:
            print(f"[ERROR] _show_settings failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple dialog
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Ошибка", f"Не удалось открыть настройки:\n{e}")

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

            self.config.model_size = mid
            self.config.save()
            self.transcriber.switch_backend(self.config.backend, mid)
            self._update_model_info_label()

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

                print(f"[INFO] Quality profile changed to: {profile}")
        except Exception as e:
            print(f"[ERROR] _quality_profile_changed failed: {e}")
            import traceback
            traceback.print_exc()

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

        self.hotkey_manager.unregister()
        self.mouse_handler.stop()
        self.tray.hide()
        self.config.save()
        QApplication.quit()


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("ГолосТекст")
    app.setQuitOnLastWindowClosed(False)
    MainWindow().show()
    sys.exit(app.exec())
