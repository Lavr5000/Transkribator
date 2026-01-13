# Algorithmic Presence — Implementation Guide

## Brand Integration: Letter "A"

**Источник:** Логотип Telegram-канала [@ai_vibes_coding_ru](https://t.me/ai_vibes_coding_ru)

**Описание логотипа:**
- Буква "А" в геометрическом минималистичном стиле
- Цвет: белый на тёмном фоне
- Стиль: технологичный, современный, без кода

**Интеграция в интерфейс:**
- Буква "А" используется как архитектурный элемент, а не просто логотип
- Позиция: левая часть главного окна (branding anchor)
- Размер: 60-70px
- Может также появляться как водяной знак или в кнопке записи

---

## Цветовая палитра Algorithmic Presence

### Заменить текущие цвета в `src/main_window.py`:

```python
# Algorithmic Presence color system
COLORS = {
    'bg_darkest': (8, 12, 20),      # #080C14 - Near black (background)
    'bg_dark': (15, 25, 40),        # #0F1928 - Deep navy (window)
    'bg_mid': (25, 40, 65),         # #192841 - Mid navy (elements)
    'accent_primary': (0, 120, 255),   # #0078FF - Electric blue (main)
    'accent_secondary': (0, 200, 255), # #00C8FF - Cyan (highlight)
    'accent_glow': (100, 220, 255),    # #64DCFF - Light cyan (glow)
    'text_primary': (245, 248, 255),   # #F5F8FF - Nearly white
    'text_secondary': (140, 160, 180), # #8CA0B4 - Muted blue-gray
    'success': (10, 185, 129),        # #0AB981 - Emerald green (unchanged)
    'border': (25, 40, 65),           # #192841 - Subtle border
}
```

### Градиент для фона:

```python
GRADIENT_COLORS = {
    'left': '#081420',      # Deepest navy
    'middle': '#0F2840',    # Electric blue-dark
    'right': '#1E5080',     # Lighter navy-blue
}
```

---

## Улучшенные кнопки (Geometric Design)

### RecordButton (Центральная кнопка записи)

**Текущая проблема:** Кнопка выглядит слишком простой, "страшно"

**Решение:** Геометрический дизайн с glow-эффектами

```python
class RecordButton(QPushButton):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        if self._recording:
            # Recording state - cyan glow waves
            base_alpha = 180

            # Pulsing circles
            for i in range(4):
                import math
                phase_offset = i * 0.8
                pulse = (math.sin(self._wave_phase + phase_offset) + 1) / 2
                radius = 8 + i * 6 + self._audio_level * 8 * pulse
                alpha = int(base_alpha * (1 - i * 0.25) * (0.5 + self._audio_level * 0.5))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 200, 255, alpha))  # Cyan
                painter.drawEllipse(
                    QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
                )

            # Center circle (stop button)
            painter.setBrush(QColor(100, 220, 255, 240))  # Light cyan
            painter.drawRoundedRect(
                QRectF(center_x - 6, center_y - 6, 12, 12), 2, 2
            )
        else:
            # Idle state - geometric mic icon
            # Outer glow on hover
            if self.underMouse():
                painter.setBrush(QColor(0, 120, 255, 40))  # Electric blue glow
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(2, 2, 32, 32))

            # Mic body - geometric
            painter.setPen(QPen(QColor(0, 200, 255, 220), 2))  # Cyan
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Mic head (rounded rect)
            mic_rect = QRectF(center_x - 5, center_y - 10, 10, 14)
            painter.drawRoundedRect(mic_rect, 5, 5)

            # Mic stand
            path = QPainterPath()
            path.moveTo(center_x - 8, center_y + 2)
            path.quadTo(center_x - 8, center_y + 8, center_x, center_y + 8)
            path.quadTo(center_x + 8, center_y + 8, center_x + 8, center_y + 2)
            painter.drawPath(path)

            painter.drawLine(
                QPoint(int(center_x), int(center_y + 8)),
                QPoint(int(center_x), int(center_y + 12))
            )
            painter.drawLine(
                QPoint(int(center_x - 5), int(center_y + 12)),
                QPoint(int(center_x + 5), int(center_y + 12))
            )
```

### MiniButton (Мини-кнопки: Settings, Close, Copy, Telegram)

**Проблема:** Слишком простые, выглядят недоделанными

**Решение:** Геометрические скруглённые квадраты с улучшенными иконками

```python
class MiniButton(QPushButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        # Geometric rounded square background
        bg_alpha = int(100 * self._opacity)
        painter.setBrush(QColor(25, 40, 65, bg_alpha))  # bg_mid with opacity
        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1))
        painter.drawRoundedRect(QRectF(0, 0, 18, 18), 4, 4)

        # Subclasses implement icon drawing
```

### SettingsButton с улучшенной шестерёнкой:

```python
class SettingsButton(MiniButton):
    def paintEvent(self, event):
        super().paintEvent(event)  # Draw background

        if self._opacity < 0.05:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(255, 255, 255, min(255, alpha + hover_boost)), 1.5))

        # Geometric gear - 8 spokes
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
```

---

## Брендовый элемент Letter "A"

### Вариант 1: Логотип в главном окне

**Позиция:** Слева от статус-текста

**Реализация через QLabel:**

```python
# В MainWindow.__init__ после status_label:
self.brand_label = QLabel("A", self.central)
self.brand_label.setStyleSheet("""
    QLabel {
        color: #0078FF;
        font-size: 32px;
        font-weight: bold;
        font-family: Arial;
    }
""")
self.brand_label.setFixedWidth(40)
self.brand_label.move(app_x + 40, app_y + 25)  # Adjust position
```

### Вариант 2: Watermark на фоне

**Полупрозрачная буква "А" на фоне GradientWidget:**

```python
class GradientWidget(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gradient background
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))
        gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle']))
        gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        # Watermark "A" (subtle)
        painter.setPen(QColor(0, 120, 255, 30))  # Very transparent
        try:
            font = QFont('Arial', 48, QFont.Weight.Bold)
            painter.setFont(font)
        except:
            pass
        painter.drawText(self.rect().adjusted(20, 10, -20, -20),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "A")
```

---

## Шрифты (Typography)

**Algorithmic Presence использует моноширинные шрифты:**

```python
# Для таймера и технических элементов
TIMER_FONT_STYLE = """
    QLabel {
        color: #00C8FF;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 11px;
        font-weight: 500;
    }
"""

# Для статуса и UI текст
UI_FONT_STYLE = """
    QLabel {
        color: #F5F8FF;
        font-family: 'Segoe UI', 'Roboto', 'Helvetica', sans-serif;
        font-size: 13px;
        font-weight: 500;
        letter-spacing: 0.3px;
    }
"""
```

---

## Grid System (8px база)

**Все отступы кратны 8 пикселям:**

```python
SPACING = {
    'xs': 8,    # Минимальный отступ
    'sm': 16,   # 2 * 8
    'md': 24,   # 3 * 8
    'lg': 32,   # 4 * 8
    'xl': 48,   # 6 * 8
}

BUTTON_SIZE = 36  # Кратен 8 (не совсем, но близко)
ICON_SIZE = 18    # Кратен 8
```

---

## Анимации и переходы

**Быстрые, eased, функциональные:**

```python
# В RecordButton._animate()
self._wave_phase += 0.4  # Быстрее для большей отзывчивости

# Hover эффекты - 150ms ease-out
QPropertyAnimation(
    self,
    b"windowOpacity".encode(),
    150,
    QEasingCurve.Type.OutQuad
)
```

---

## Готовые значения для копирования

### Цвета (hex):

```python
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
```

### Размеры:

```python
WINDOW_SIZE = (340, 52)  # COMPACT_WIDTH, COMPACT_HEIGHT
BUTTON_SIZE = 18         # MiniButton
RECORD_BUTTON_SIZE = 36  # RecordButton
PADDING = 8              # Базовый отступ
```

---

## Checklist внедрения

- [ ] Обновить COLORS dict с новой палитрой
- [ ] Обновить GRADIENT_COLORS
- [ ] Перерисовать RecordButton с glow-эффектами
- [ ] Улучшить все MiniButton (Settings, Close, Copy, Telegram)
- [ ] Добавить букву "А" как брендовый элемент
- [ ] Обновить TextPopup с новыми цветами
- [ ] Обновить tray icon
- [ ] Применить моноширинный шрифт к таймеру
- [ ] Проверить все отступы по 8px grid
- [ ] Тестировать все кнопки в hover/active states
- [ ] Проверить контраст и читаемость

---

## Результат

**До (текущий Aural Flux):**
- Cyan gradient: #1E3A5F → #0EA5E9 → #22D3EE
- Простые кнопки без деталей
- Нет бренда
- Стандартный шрифт

**После (Algorithmic Presence):**
- Deep navy с electric blue акцентами
- Геометрические кнопки с glow
- Буква "А" как архитектурный элемент
- Моноширинные шрифты для технического вида
- Grid-based precision
- Профессиональный технологичный aesthetic

**Algorithmic Presence превращает приложение в инструмент для работы, а не просто в утилиту.**
