# Aural Flux — Implementation Guide

## Design Philosophy Summary

**Aural Flux** transforms sound into visible light. This is a visual philosophy where audio waves become flowing gradients, where voice becomes color, where silence becomes deep space ready to be filled with meaning.

### Core Principles

1. **Movement in Stillness** — Even static elements suggest motion through curved forms and directional gradients
2. **Depth Through Layers** — Transparency, glow, and soft blur create spatial hierarchy
3. **Light as Structure** — Bright elements guide attention; everything else prepares the stage
4. **Meticulous Craftsmanship** — Every gradient, curve, and spacing is precisely calibrated

---

## Color Palette for Code

Replace the current gradient colors in `src/main_window.py`:

```python
# Current (WhisperTyping style — TO REPLACE):
GRADIENT_COLORS = {
    'left': '#e85d04',      # Orange
    'middle': '#d63384',    # Magenta
    'right': '#7c3aed',     # Violet
}

# NEW — Aural Flux palette:
GRADIENT_COLORS = {
    'left': '#1e3a5f',      # Deep Navy Blue
    'middle': '#0ea5e9',    # Electric Blue
    'right': '#22d3ee',     # Bright Cyan
}
```

### Complete Color System

```python
COLORS = {
    'bg_dark': '#0f1437',      # Deepest navy (almost black)
    'bg_medium': '#1e3a5f',    # Mid navy
    'bg_light': '#235a8c',     # Light navy teal
    'accent': '#0ea5e9',       # Electric blue (primary)
    'accent_bright': '#22d3ee',# Cyan (highlights)
    'accent_glow': '#78e6ff',  # Glowing cyan (active states)
    'text_primary': '#f0f9ff', # Nearly white
    'text_secondary': '#94a3b8',# Muted blue-gray
    'success': '#10b981',      # Emerald green (unchanged)
    'border': '#1e3a5f',       # Subtle navy
}
```

---

## Visual Elements

### Button Styling (RecordButton)

- **Idle state**: Deep navy circle (#235a8c) with bright cyan outline (#78e6ff)
- **Recording**: Pulsing cyan glow, expanding rings like sound waves
- **Hover**: Subtle glow effect (alpha 30-40)

### Mini Buttons (Copy, Settings, Close)

- **Default opacity**: 0.0 (hidden)
- **Hover opacity**: 0.7
- **Color**: White/cyan with glow on hover
- **Stroke width**: 1.5px

### Telegram Icon (New)

```python
class TelegramButton(MiniButton):
    def paintEvent(self, event):
        if self._opacity < 0.05:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(255 * self._opacity)
        hover_boost = 60 if self.underMouse() else 0

        painter.setPen(QPen(QColor(120, 230, 255, min(255, alpha + hover_boost)), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Paper plane icon
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        center_x, center_y = 9, 9
        # Plane body
        path.moveTo(center_x - 6, center_y + 4)
        path.lineTo(center_x + 6, center_y - 2)
        path.lineTo(center_x, center_y + 5)
        path.closeSubpath()
        painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            import webbrowser
            webbrowser.open('https://t.me/ai_vibes_coding_ru')
```

### Gradient Background (GradientWidget)

The gradient should flow horizontally: deep navy → electric blue → cyan

```python
gradient = QLinearGradient(0, 0, self.width(), 0)
gradient.setColorAt(0.0, QColor(GRADIENT_COLORS['left']))   # Deep navy
gradient.setColorAt(0.5, QColor(GRADIENT_COLORS['middle'])) # Electric blue
gradient.setColorAt(1.0, QColor(GRADIENT_COLORS['right']))  # Cyan
```

---

## Implementation Checklist

- [ ] Replace `GRADIENT_COLORS` in main_window.py (lines 36-40)
- [ ] Update `COLORS` dict (lines 42-51)
- [ ] Update `RecordButton` paint event for cyan glow
- [ ] Create `TelegramButton` class
- [ ] Add Telegram button to layout (around line 767)
- [ ] Update `TextPopup` gradient (lines 420-428)
- [ ] Update tray icon gradient (lines 794-797)
- [ ] Test all buttons with new colors
- [ ] Verify Telegram link opens correctly
- [ ] Check contrast and readability

---

## Design Files Created

- `design_variants/aural_flux_philosophy.md` — Full design philosophy
- `design_variants/aural_flux_masterpiece.png` — Visual reference (1600x1000)
- `design_variants/aural_flux_design.pdf` — PDF version

---

## Why This Works

1. **Unique Identity**: The navy→electric blue→cyan gradient is distinct from WhisperTyping's orange→magenta→violet
2. **Modern & Cool**: Cyan glow and deep navy create a futuristic, tech-forward aesthetic
3. **Sound-Metaphor**: Blue tones echo audio recording software while remaining fresh
4. **High Contrast**: Deep backgrounds with bright accents ensure readability
5. **Professional**: The palette is sophisticated, not cartoonish or garish

**Aural Flux** turns voice into light, silence into depth, and transcription into transformation.
