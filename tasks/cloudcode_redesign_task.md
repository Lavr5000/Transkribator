# Задача: Редизайн приложения Transkribator

## Контекст
Приложение **ГолосТекст (Transkribator)** — это инструмент для голосовой транскрибации с использованием Whisper. Текущий дизайн использует градиент Orange → Magenta → Violet, который ассоциируется с WhisperTyping. Нужно создать уникальный фирменный стиль.

## Цели

### 1. Уйти от WhisperTyping айдентики
- Исключить оранжево-розово-фиолетовый градиент
- Создать уникальную цветовую палитру
- Избегать визуального сходства с конкурентами

### 2. Единственная брендовая тема
- Использовать **одну** цветовую схему для всех элементов:
  - Главного окна
  - Кнопок записи
  - Всплывающих панелей (TextPopup)
  - Настроек и диалогов
- Соответствие современным трендам дизайна

### 3. Современный крутой дизайн
- Рассмотреть варианты:
  - Glass morphism (стекломорфизм)
  - Neomorphism (неоморфизм)
  - Dark mode с неоновыми акцентами
  - Gradient borders (градиентные рамки)
  - Subtle glow effects (мягкое свечение)
- Микровзаимодействия (hover, click, animation)
- Плавные анимации переходов

### 4. Добавить иконку Telegram
- **Бумажный самолётик**, направленный диагонально вверх-вправо
- Размер: ~16-20px
- Позиция: в правой части окна
- Действие: открыть `https://t.me/ai_vibes_coding_ru`
- Стиль: соответствует общей теме

## Файлы для изменения

### Основной файл: `src/main_window.py`

**Ключевые классы для редактирования:**

```python
# Цветовые константы (строки ~36-51)
GRADIENT_COLORS = {
    'left': '#e85d04',      # ИЗМЕНИТЬ
    'middle': '#d63384',    # ИЗМЕНИТЬ
    'right': '#7c3aed',     # ИЗМЕНИТЬ
}

COLORS = {
    'bg_dark': '#1a1a2e',   # Можно адаптировать
    'bg_medium': '#16213e',
    'bg_light': '#0f3460',
    'accent': '#ec4899',    # ИЗМЕНИТЬ
    # ...
}

# Размеры окна (строки ~53-54)
COMPACT_HEIGHT = 52  # Можно изменить
COMPACT_WIDTH = 340  # Можно изменить
```

**Классы компонентов:**

| Класс | Строки | Назначение |
|-------|--------|------------|
| `RecordButton` | ~157-251 | Центральная кнопка записи |
| `MiniButton` | ~253+ | Маленькие угловые кнопки |
| `CloseButton` | ~375+ | Кнопка закрытия |
| `GradientWidget` | ~406+ | Фон главного окна |
| `TextPopup` | ~425+ | Всплывающая панель |
| `MainWindow._setup_ui` | ~830+ | Расстановка элементов |

### Структура layout (строки ~840-877):

```
┌────────────────────────────────────────┐
│ [95:18]      [CENTER]      [CORNER]    │
│ Timer       RecordBtn    Close/Copy/Set│
└────────────────────────────────────────┘
```

Нужно добавить:
- Telegram иконку в правую часть (рядом с close/copy/settings)

## Требования к реализации

1. **Не ломать функционал** — только визуальные изменения
2. **Сохранить размеры** или изменить обоснованно
3. **Добавить Telegram иконку** как отдельный класс или встроить в существующий
4. **Тестировать** — приложение должно запускаться без ошибок

## Идеи для вдохновения

### Варианты цветовых схем:

1. **Ocean Depths** (глубокий океан)
   - Teal (#0D9488) → Aqua (#06B6D4) → Sky Blue (#0EA5E9)

2. **Cyberpunk Purple**
   - Deep Purple (#581C87) → Electric Purple (#A855F7) → Pink (#EC4899)

3. **Forest Aurora**
   - Emerald (#047857) → Teal (#14B8A6) → Cyan (#22D3EE)

4. **Sunset Shift** (но уникальный)
   - Coral (#F43F5E) → Orange (#FB923C) → Amber (#FBBF24)

5. **Nordic Night**
   - Slate Blue (#1E3A5F) → Steel Blue (#475569) → Cool Gray (#94A3B8)

### Стили кнопок:

- **Glassy**: полупрозрачные с blur эффектом
- **Neon**: яркий контур с glow
- **Flat**: плоские с hover подчёркиванием
- **3D**: объёмные с тенями

## Telegram иконка

**SVG Path для бумажного самолётика:**

```svg
<svg viewBox="0 0 24 24" fill="currentColor">
  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
</svg>
```

**Поворот:** -15 градусов (diag up-right)

**Реализация в PyQt:**
```python
class TelegramButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Paper plane path
        # ... drawing code ...

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
```

## Финальная проверка

После изменений:
1. Запустить `python main.py`
2. Проверить все кнопки работают
3. Проверить Telegram ссылку открывается
4. Убедиться дизайн современный и уникальный

---

**Готовый результат:** Запушить изменения в git с комментарием вида `feat: redesign with [theme name] theme`
