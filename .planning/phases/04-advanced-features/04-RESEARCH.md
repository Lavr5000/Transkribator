# Phase 04: Advanced Features - Research

**Date:** 2026-01-29
**Status:** Complete

---

## Existing Configuration System

### Config Structure (`src/config.py`)

**Already implemented settings relevant to Phase 4:**

| Setting | Type | Default | Location |
|---------|------|---------|----------|
| `backend` | str | "sherpa" | ✅ Exists |
| `model_size` | str | "giga-am-v2-ru" | ✅ Exists |
| `webrtc_enabled` | bool | True | ✅ Exists |
| `noise_suppression_level` | int | 2 (0-4) | ✅ Exists |
| `vad_enabled` | bool | True | ✅ Exists |
| `vad_threshold` | float | 0.5 | ✅ Exists |
| `min_silence_duration_ms` | int | 800 | ✅ Exists |
| `min_speech_duration_ms` | int | 500 | ✅ Exists |
| `enable_post_processing` | bool | True | ✅ Exists |

**New settings needed:**

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `quality_profile` | str | "balanced" | Preset: fast/balanced/quality |
| `user_dictionary` | list | [] | User-defined corrections [{wrong, correct, case_sensitive}] |

### Config Storage

**Location:** `~/.config/WhisperTyping/WhisperTyping/config.json`
**Methods:**
- `Config.load()` — Load from JSON with fallback to defaults
- `config.save()` — Save to JSON via `dataclasses.asdict()`
- Platform-agnostic via `platformdirs`

---

## Existing UI Components

### SettingsDialog (`src/main_window.py:591-806`)

**Current structure:**
```
SettingsDialog (QDialog, frameless)
├── QTabWidget
│   ├── "Настройки" tab (QScrollArea)
│   │   ├── QGroupBox "Движок" → backend_combo
│   │   ├── QGroupBox "Модель" → model_combo (dynamic by backend)
│   │   ├── QGroupBox "Язык" → lang_combo
│   │   ├── QGroupBox "Поведение" → checkboxes
│   │   └── QGroupBox "Кнопка мыши" → mouse settings
│   └── "История" tab
│       ├── QGroupBox "Статистика"
│       └── QGroupBox "История" → history_text
```

**Styling:** `DIALOG_STYLESHEET` constant with dark theme colors

**Signal connection pattern:**
```python
self._settings.backend_combo.currentIndexChanged.connect(self._backend_changed)
self._settings.auto_copy_cb.toggled.connect(lambda c: setattr(self.config, 'auto_copy', c) or self.config.save())
```

---

## Quality Profiles Design

### Profile Definitions

| Profile | Backend | Model | VAD | Post-processing | RTF target |
|---------|---------|-------|-----|-----------------|------------|
| **Fast** | sherpa | giga-am-v2-ru | Off | Min | <0.5 |
| **Balanced** | sherpa | giga-am-v2-ru | Medium (0.5) | Standard | ~1.0 |
| **Quality** | whisper | small | Aggressive (0.3) | Max | ~2.0 |

### Implementation Approach

**Option A:** Preset method in Config
```python
def apply_quality_profile(self, profile: str):
    profiles = {
        "fast": {"backend": "sherpa", "vad_enabled": False, ...},
        "balanced": {...},
        "quality": {...}
    }
    for key, value in profiles[profile].items():
        setattr(self, key, value)
```

**Option B:** Dynamic profile calculation
- Calculate optimal settings based on profile name
- Update UI controls to reflect profile values

**Decision:** Option A — clearer, maintainable

---

## User Dictionary Design

### Data Structure

```json
{
  "user_dictionary": [
    {"wrong": "торопинка", "correct": "переписка", "case_sensitive": false},
    {"wrong": "JTimon", "correct": "Дмитрий", "case_sensitive": false}
  ]
}
```

### Integration Points

1. **Config extension:** Add `user_dictionary: list[dict]` field
2. **TextProcessor integration:** Pass user dict to `EnhancedTextProcessor`
3. **UI components:**
   - QTableWidget for CRUD display
   - Add/Edit/Delete buttons
   - Import/Export (JSON/TXT)

### File Locations

- Main storage: `config.json` (embedded)
- Optional external file: `~/.config/WhisperTyping/WhisperTyping/user_dictionary.json`

---

## VAD/Noise Sliders Design

### Slider Mappings

| Control | Config Key | Range | Default |
|---------|------------|-------|---------|
| VAD Threshold | `vad_threshold` | 0.0-1.0 | 0.5 |
| Min Silence | `min_silence_duration_ms` | 100-3000ms | 800 |
| Noise Level | `noise_suppression_level` | 0-4 | 2 |

### UI Components

- **QSlider** with integer values
- **QLabel** for numeric display
- Position labels: "Sensitive" (0.3) / "Medium" (0.5) / "Silent" (0.7)

---

## Model Selection Enhancement

### Current State

`WHISPER_MODELS`, `SHERPA_MODELS`, `PODLODKA_MODELS` dictionaries in config.py:
```python
WHISPER_MODELS = {
    "tiny": "Tiny (~1GB VRAM, fastest)",
    "base": "Base (~1GB VRAM, fast)",
    ...
}
```

### Enhancement Needed

**Add metadata:**
```python
MODEL_METADATA = {
    "tiny": {"ram_mb": 1000, "rtf": 0.3, "description": "Максимальная скорость"},
    "base": {"ram_mb": 1000, "rtf": 0.5, "description": "Быстрый"},
    ...
}
```

**Display format:** "Model Name — RAM usage — Description"

---

## File Modifications Summary

| File | Changes | Lines |
|------|---------|-------|
| `src/config.py` | Add quality_profile, user_dictionary; MODEL_METADATA | ~50 |
| `src/main_window.py` | Add quality profile UI; dictionary tab; VAD sliders; model metadata | ~200 |
| `src/transcriber.py` | Pass user dictionary to text processor | ~10 |
| `src/text_processor_enhanced.py` | Apply user dictionary corrections | ~30 |

---

## Integration Points

### Backend Parameter Updates

**When quality profile changes:**
1. Update config values
2. Call `transcriber.switch_backend()` if backend changed
3. Update `transcriber.vad_enabled`, `transcriber.vad_threshold`
4. Update `transcriber.enable_post_processing`

### When VAD/Noise sliders change:
1. Update config value
2. Call `config.save()`
3. Update `transcriber` parameters in real-time

### When user dictionary changes:
1. Update config list
2. Rebuild text processor with new dictionary
3. `config.save()`

---

## Testing Considerations

1. **Config migration:** Old config files should get defaults for new fields
2. **Profile switching:** Verify all parameters update correctly
3. **Dictionary persistence:** Test add/edit/delete/save/load cycle
4. **Slider ranges:** Validate min/max values prevent invalid states

---

*Research complete: 2026-01-29*
