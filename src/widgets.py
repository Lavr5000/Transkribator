"""Reusable widget classes for the main application UI."""
import math
import webbrowser

from PyQt6.QtWidgets import (
    QPushButton, QLabel, QDialog, QVBoxLayout, QHBoxLayout,
    QWidget, QLineEdit, QCheckBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QLinearGradient, QBrush, QPen,
    QPainterPath,
)


# Gradient colors - Algorithmic Presence theme
GRADIENT_COLORS = {
    'left': '#081420',
    'middle': '#0F2840',
    'right': '#1E5080',
}

COLORS = {
    'bg_darkest': (8, 12, 20),
    'bg_dark': (15, 25, 40),
    'bg_mid': (25, 40, 65),
    'accent_primary': (0, 120, 255),
    'accent_secondary': (0, 200, 255),
    'accent_glow': (100, 220, 255),
    'text_primary': (245, 248, 255),
    'text_secondary': (140, 160, 180),
    'success': (10, 185, 129),
    'border': (25, 40, 65),
}

COLORS_HEX = {
    'bg_darkest': '#080C14',
    'bg_dark': '#0F1928',
    'bg_mid': '#192841',
    'accent_primary': '#0078FF',
    'accent_secondary': '#00C8FF',
    'accent_glow': '#64DCFF',
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


class RecordButton(QPushButton):
    """Stylish central record button with custom painting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._audio_level = 0.0
        self._wave_phase = 0.0
        self._level_history = [0.0] * 30
        self.setFixedSize(180, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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
        self._level_history.append(self._audio_level)
        self._level_history = self._level_history[-30:]
        self.update()

    def _animate(self):
        self._wave_phase += 0.3
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._dragging = False
            parent = self.window()
            if parent and hasattr(parent, '_drag_pos'):
                parent._drag_pos = event.globalPosition().toPoint() - parent.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, '_press_global'):
            delta = event.globalPosition().toPoint() - self._press_global
            if abs(delta.x()) > 4 or abs(delta.y()) > 4:
                self._dragging = True
                parent = self.window()
                if parent and hasattr(parent, '_drag_pos') and parent._drag_pos is not None:
                    parent.move(event.globalPosition().toPoint() - parent._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, '_dragging', False):
            self._dragging = False
            parent = self.window()
            if parent and hasattr(parent, '_drag_pos'):
                parent._drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        if self._recording:
            w = self.width()
            h = self.height()
            bar_count = 30
            bar_w = 3.0
            gap = (w - bar_count * bar_w) / (bar_count + 1)

            painter.setPen(Qt.PenStyle.NoPen)
            for i, lvl in enumerate(self._level_history):
                phase_boost = (math.sin(self._wave_phase + i * 0.4) + 1) / 2 * 0.3
                bar_h = max(2.0, (lvl + phase_boost) * (h - 8))
                x = gap + i * (bar_w + gap)
                y = (h - bar_h) / 2

                brightness = int(160 + lvl * 95)
                alpha = int(140 + lvl * 115)
                painter.setBrush(QColor(0, brightness, 255, min(255, alpha)))
                painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)

            cx, cy = w / 2, h / 2
            painter.setBrush(QColor(*COLORS['accent_glow'], 240))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(cx - 5, cy - 5, 10, 10), 2, 2)
        else:
            if self.underMouse():
                painter.setBrush(QColor(*COLORS['accent_primary'], 40))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(center_x - 18, center_y - 18, 36, 36))

            painter.setPen(Qt.PenStyle.NoPen)
            for offset in range(4, 0, -1):
                glow_alpha = (5 - offset) * 7
                painter.setBrush(QColor(*COLORS['accent_glow'], glow_alpha))
                painter.drawRoundedRect(
                    QRectF(center_x - 4 - offset, center_y - 9 - offset,
                           8 + offset * 2, 12 + offset * 2),
                    3 + offset, 3 + offset
                )

            painter.setBrush(QColor(*COLORS['accent_secondary'], 225))
            painter.drawRoundedRect(QRectF(center_x - 4, center_y - 9, 8, 12), 3, 3)

            painter.setPen(QPen(QColor(*COLORS['accent_secondary'], 200), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(center_x - 6, center_y + 1)
            path.quadTo(center_x - 6, center_y + 8, center_x, center_y + 8)
            path.quadTo(center_x + 6, center_y + 8, center_x + 6, center_y + 1)
            painter.drawPath(path)

            painter.setPen(QPen(QColor(*COLORS['accent_secondary'], 175), 1.0))
            painter.drawLine(QPointF(center_x, center_y + 8), QPointF(center_x, center_y + 12))
            painter.drawLine(QPointF(center_x - 4, center_y + 12), QPointF(center_x + 4, center_y + 12))


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

        bg_alpha = int(100 * self._opacity)
        painter.setBrush(QColor(*COLORS['bg_mid'], bg_alpha))
        painter.setPen(QPen(QColor(255, 255, 255, int(255 * self._opacity)), 1))
        painter.drawRoundedRect(QRectF(0, 0, 18, 18), 4, 4)

        self._draw_icon(painter)

    def _draw_icon(self, painter):
        pass


class CopyButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0
        color = QColor(255, 255, 255, min(255, alpha + hover_boost))
        pen = QPen(color, 1.5)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(5, 2, 9, 11), 1.5, 1.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*COLORS['bg_mid']))
        painter.drawRoundedRect(QRectF(2, 5, 9, 11), 1.5, 1.5)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(2, 5, 9, 11), 1.5, 1.5)


class HistoryButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))

        painter.drawEllipse(QRectF(3, 3, 12, 12))
        painter.drawLine(QPoint(9, 5), QPoint(9, 9))
        painter.drawLine(QPoint(9, 9), QPoint(12, 9))


class SettingsButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0
        color = QColor(255, 255, 255, min(255, alpha + hover_boost))

        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx, cy = 9.0, 9.0
        n = 6
        r_body = 5.0
        r_tooth = 7.0
        tw = 0.22

        path = QPainterPath()
        first = True
        for i in range(n):
            base = i * 2 * math.pi / n - math.pi / 2
            pts = [
                (r_body, base - tw),
                (r_tooth, base - tw),
                (r_tooth, base + tw),
                (r_body, base + tw),
            ]
            for r, a in pts:
                x = cx + r * math.cos(a)
                y = cy + r * math.sin(a)
                if first:
                    path.moveTo(x, y); first = False
                else:
                    path.lineTo(x, y)
            next_start = (i + 1) * 2 * math.pi / n - math.pi / 2 - tw
            cur_end = base + tw
            for s in range(1, 5):
                a = cur_end + s * (next_start - cur_end) / 4
                path.lineTo(cx + r_body * math.cos(a), cy + r_body * math.sin(a))
        path.closeSubpath()
        painter.drawPath(path)

        painter.drawEllipse(QRectF(cx - 2.5, cy - 2.5, 5, 5))


class CloseButton(MiniButton):
    def _draw_icon(self, painter):
        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0
        color = QColor(255, 100, 100, min(255, alpha + hover_boost)) if self.underMouse() else QColor(255, 255, 255, alpha)

        painter.setPen(QPen(color, 1.5))

        painter.drawLine(QPoint(5, 5), QPoint(13, 13))
        painter.drawLine(QPoint(13, 5), QPoint(5, 13))


class CancelButton(MiniButton):
    """Cancel button - shown only during recording."""
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 80 if self.underMouse() else 0

        color = QColor(255, 200, 50, min(255, alpha + hover_boost))

        painter.setPen(QPen(color, 2.0))

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

        wrong_label = QLabel("Неправильное написание:")
        layout.addWidget(wrong_label)
        self.wrong_input = QLineEdit()
        self.wrong_input.setText(wrong)
        self.wrong_input.setPlaceholderText("Например: торопинка")
        layout.addWidget(self.wrong_input)

        correct_label = QLabel("Правильное написание:")
        layout.addWidget(correct_label)
        self.correct_input = QLineEdit()
        self.correct_input.setText(correct)
        self.correct_input.setPlaceholderText("Например: переписка")
        layout.addWidget(self.correct_input)

        self.case_sensitive_cb = QCheckBox("С учетом регистра")
        self.case_sensitive_cb.setChecked(case_sensitive)
        layout.addWidget(self.case_sensitive_cb)

        layout.addSpacing(20)

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
        return {
            "wrong": self.wrong_input.text().strip(),
            "correct": self.correct_input.text().strip(),
            "case_sensitive": self.case_sensitive_cb.isChecked()
        }

    def accept(self):
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
    """Floating transcription text panel - appears above for 5 seconds."""

    copy_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._setup_ui()

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

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        if self._text:
            painter.setPen(QPen(QColor(*COLORS['text_primary'], 230)))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)

            text_rect = self.rect().adjusted(12, 8, -40, -8)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, self._text)

        copy_btn_x = self.width() - 30
        copy_btn_y = (self.height() - 18) // 2

        painter.setPen(QPen(QColor(*COLORS['accent_secondary'], 200), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(copy_btn_x, copy_btn_y + 2, 8, 10), 1, 1)
        painter.drawRoundedRect(QRectF(copy_btn_x + 4, copy_btn_y, 8, 10), 1, 1)

    def set_text(self, text: str):
        self._text = text

        font_metrics = self.fontMetrics()
        text_width = COMPACT_WIDTH - 52
        lines = max(1, len(text) // 40 + 1)
        height = min(120, max(60, 30 + lines * 20))
        self.setFixedHeight(height)

        self.update()

    def get_text(self) -> str:
        return self._text

    def show_with_timeout(self, timeout_ms: int = 5000):
        self._hide_timer.stop()
        self.show()
        self._hide_timer.start(timeout_ms)

    def mousePressEvent(self, event):
        copy_btn_x = self.width() - 35
        if event.pos().x() >= copy_btn_x:
            self.copy_requested.emit()
        else:
            self._hide_timer.stop()
            self.hide()
