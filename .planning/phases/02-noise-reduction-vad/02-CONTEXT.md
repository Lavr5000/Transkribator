# Phase 2: Noise Reduction + VAD - Context

**Gathered:** 2026-01-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Аудио на входе очищено от шума, тишина удалена до транскрибации, что даёт 5-15% улучшение WER. WebRTC для шумоподавления, Silero VAD для детекции речи. Пользователь видит только результат (лучшее качество) и VAD индикатор в UI.

</domain>

<decisions>
## Implementation Decisions

### Noise Reduction
- **Intensity:** Moderate — баланс между подавлением шума и качеством голоса
- **Timing:** Real-time — обработка во время записи (на лету)
- **Quality mode:** High quality — приоритет качеству над задержкой
- **Toggle:** Должна быть настройка в UI для включения/выключения

### VAD Behavior
- **Sensitivity:** Moderate — обычная речь детектится надёжно
- **Min speech duration:** Long (500ms+) — только полноценные фразы
- **Min silence duration:** Medium (800-1000ms) — даём время подумать перед завершением
- **Adaptation:** Fixed parameters — без адаптации к фоновому шуму

### VAD Visualization
- **Type:** Level bar — полоса/штрих с интенсивностью речи
- **Colors:** Gray (тишина) → Blue (речь)
- **Data:** Volume level — уровень громкости речи
- **Update rate:** Responsive (20-30ms) — быстрая реакция

### Gain Control
- **Target level:** Standard normalization (-16 dBFS)
- **Adaptation speed:** Slow — постепенное усиление (плавно)
- **Max gain limit:** No limit — WebRTC сам решает
- **Active:** Always on — автоматическая регулировка всегда активна

### Claude's Discretion
- Точные параметры WebRTC (noise_suppression_level, gain_control_mode)
- Позиция level bar в UI
- Размер и стиль визуальных элементов

</decisions>

<specifics>
## Specific Ideas

- WebRTC High Quality mode для лучшего подавления шума
- VAD level bar обновляется каждые 20-30ms для отзывчивости
- Цветовая схема: серый (нет речи) → синий (речь)
- Медленная адаптация AGC для естественности звука

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-noise-reduction-vad*
*Context gathered: 2026-01-27*
