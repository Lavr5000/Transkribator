# Phase 4: Advanced Features - Context

**Gathered:** 2026-01-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Добавление UI настроек для управления качеством транскрибации. Пользователь может настраивать quality profiles, VAD, noise reduction и model selection через интерфейс приложения.

</domain>

<decisions>
## Implementation Decisions

### Placement Strategy
- **Settings dialog** — отдельное модальное окно, вызываемое из Tray menu или главного окна
- Тray icon правый клик → "Settings..." открывает диалог настроек
- Главное окно: кнопка "⚙️ Settings" в toolbar или menu bar
- Settings dialog: табированный интерфейс (General, Quality, Advanced, Dictionary)

### Quality Profiles UI
- **Radio card selection** — визуальные карточки с описанием, не просто dropdown
- Три карточки в ряд:
  - **Fast** — "Максимальная скорость, базовое качество" (tiny/base, VAD off, post-processing min)
  - **Balanced** — "Баланс скорости и точности" (small, VAD medium, post-processing standard) ← default
  - **Quality** — "Максимальная точность, медленнее" (medium/large, VAD aggressive, post-processing max)
- Selected card highlighted with accent color + checkmark
- Each card shows: model name, estimated RTF, features enabled/disabled

### User Dictionary UI
- **CRUD table interface** — таблица со столбцами: "Replacement" | "Target" | "Case Sensitive?" | Actions
- "Add word" button → открывает маленький modal dialog с полями:
  - "Wrong spelling" (что исправляем)
  - "Correct spelling" (на что заменяем)
  - Checkbox: "Case sensitive"
- Edit/Delete кнопки в каждой строке таблицы
- "Import from file..." кнопка для bulk import (JSON/TXT)
- "Export" кнопка для бэкапа словаря
- Live search filter сверху таблицы

### VAD and Noise Sliders
- **Hybrid sliders** — слайдер с подписями-позициями + числовое значение рядом
- VAD Threshold: "Silent" ←→ → "Sensitive" (0.0 - 1.0, default 0.5, show numeric)
- Min Silence Duration: "Short" ←→ → "Long" (500ms - 3000ms, default 1000ms)
- Noise Reduction: Toggle (On/Off) + Intensity slider: "Light" ←→ → "Aggressive"
- Показывать числовые значения справа от слайдера для точности
- "Reset to defaults" кнопка для каждого слайдера

### Model Selection
- **Dropdown with model info** — не просто список моделей, а с метаданными
- Format: "Model Name — Size — RAM usage"
- Пример: "GigaAM v2 (small) — 140MB — ~500MB RAM"
- Сгруппировать по бэкенду:
  - Whisper: tiny, base, small, medium, large-v3-turbo
  - Sherpa-ONNX: GigaAM v2 (tiny/small/base)
- Показывать текущую модель с индикатором загрузки (loading spinner при смене)
- Предупреждение если модель > 2GB RAM

### Settings Dialog Structure
```
┌─────────────────────────────────────────┐
│ Settings                       [X]      │
├─────────────────────────────────────────┤
│ [General] [Quality] [Advanced] [Dict]  │
│                                         │
│ ┌─ Quality Profiles ─────────────────┐ │
│ │ ┌─────────┐ ┌──────────┐ ┌──────┐ │ │
│ │ │  Fast   │ │Balanced  │ │Quality│ │ │
│ │ │ ⚡      │ │  ✓       │ │ 🎯   │ │ │
│ │ └─────────┘ └──────────┘ └──────┘ │ │
│ └────────────────────────────────────┘ │
│                                         │
│ ┌─ Voice Detection ─────────────────┐ │
│ │ VAD Threshold    [━━━●━━] 0.50    │ │
│ │ Min Silence       [━━━●━━] 1000ms │ │
│ └────────────────────────────────────┘ │
│                                         │
│ [Reset All] [Cancel] [Apply] [OK]      │
└─────────────────────────────────────────┘
```

</decisions>

<specifics>
## Specific Ideas

- **Modern dark mode aesthetic** — как VS Code или Obsidian settings
- **Instant apply** — настройки применяются сразу (кроме смены модели — требует перезагрузки бэкенда)
- **Persistence** — все настройки сохраняются в `config.json` в директории приложения
- **Validation** — показывать предупреждение если пользователь выбирает модель > доступной RAM
- **Keyboard shortcuts** — Ctrl+, для открытия настроек (стандарт для многих приложений)

</specifics>

<deferred>
## Deferred Ideas

- Hot-swap моделей без перезагрузки бэкенда — сложная инфраструктура, будущая фаза
- Cloud-based модели — отдельная фаза с сетевой интеграцией
- Профили для разных микрофонов — может быть добавлено позже как "Mic Profiles"
- A/B тестирование внутри UI — требует инфраструктуры сбора метрик

</deferred>

---

*Phase: 04-advanced-features*
*Context gathered: 2026-01-29*
