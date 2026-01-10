# Sherpa-ONNX Integration Plan

## 🎯 Goal
Integrate Sherpa-ONNX with GigaAM v2 Russian model into "ГолосТекст" application for improved Russian speech recognition accuracy.

## 📋 Architecture

### Multi-Backend Design
```
User Interface
    ↓
MainWindow (Backend Selection)
    ↓
Transcriber (Abstract Interface)
    ↓
├─ WhisperBackend (current - faster-whisper)
│  ├─ base model
│  ├─ small/medium models
│  └─ whisper-podlodka-turbo model
│
└─ SherpaBackend (NEW - sherpa-onnx)
   ├─ GigaAM v2 Russian model
   └─ Future: other Sherpa models
```

## 🔄 Implementation Steps

### Phase 1: Dependencies & Setup ✅
- [x] Research completed
- [ ] Install sherpa-onnx package
- [ ] Download GigaAM v2 model
- [ ] Create models/ directory structure

### Phase 2: Core Implementation
- [ ] Create abstract `BaseBackend` class
- [ ] Implement `SherpaBackend` class
- [ ] Refactor existing `WhisperBackend` from transcriber.py
- [ ] Add backend selection to Config
- [ ] Integrate backends into Transcriber class

### Phase 3: UI Updates
- [ ] Add backend selector dropdown to Settings tab
- [ ] Add model download manager/progress indicator
- [ ] Update tooltips and help text
- [ ] Test backend switching

### Phase 4: Testing & Optimization
- [ ] Test SherpaBackend with user's singing sample
- [ ] Compare accuracy: Whisper vs Sherpa
- [ ] Benchmark performance (speed, memory)
- [ ] Fine-tune post-processing rules for Sherpa output

### Phase 5: Documentation
- [ ] Update README with backend comparison
- [ ] Add model installation instructions
- [ ] Document backend-specific features

## 📁 File Structure

```
Transkribator/
├── src/
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base class
│   │   ├── whisper_backend.py   # Current implementation
│   │   └── sherpa_backend.py    # NEW: Sherpa-ONNX
│   ├── transcriber.py           # Main orchestrator
│   ├── text_processor.py        # Post-processing (existing)
│   ├── config.py                # Add backend selection
│   └── main_window.py           # UI updates
│
├── models/
│   ├── whisper/
│   │   ├── base/
│   │   ├── small/
│   │   └── podlodka-turbo/
│   └── sherpa/
│       └── giga-am-v2-ru/       # GigaAM v2 Russian model
│
└── scripts/
    ├── download_models.py       # Model download helper
    └── test_backends.py         # Comparison testing script
```

## 🔧 Technical Details

### GigaAM v2 Model Information
- **Model:** sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19
- **Source:** https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19
- **Size:** ~50-100MB (estimated)
- **Language:** Russian
- **Type:** CTC offline model
- **Developer:** Salute-developers (GigaAM team)

### Sherpa-ONNX Installation
```bash
pip install sherpa-onnx
```

### Backend Interface
```python
class BaseBackend(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> Tuple[str, float]:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    def load_model(self):
        """Load model into memory."""
        pass

    @abstractmethod
    def unload_model(self):
        """Unload model from memory."""
        pass
```

## 📊 Expected Results

### Accuracy Improvement
- **Current (Whisper base):** ~50% accuracy on test song
- **Expected (Sherpa GigaAM):** ~70-80% accuracy (Russian-optimized)

### Performance
- **Whisper base:** ~1-2 seconds for short audio
- **Sherpa GigaAM:** ~0.5-1 second (CTC is faster than Transformer)

## 🐛 Known Issues & Solutions

### Issue 1: Model Download Size
**Problem:** GigaAM model may be large
**Solution:** Implement lazy loading with progress indicator

### Issue 2: Backend Switching
**Problem:** Models loaded in memory
**Solution:** Unload previous backend before loading new one

### Issue 3: Post-Processing
**Problem:** Sherpa output may have different error patterns
**Solution:** Add Sherpa-specific correction rules to text_processor.py

## 🚀 Rollout Plan

1. **Phase 1-2:** Core implementation (backend classes)
2. **Phase 3:** UI integration (backend selector)
3. **Phase 4:** Testing with user's audio sample
4. **Phase 5:** Documentation and final polish

## 📝 Notes

- Keep existing WhisperBackend as default initially
- Make SherpaBackend opt-in during testing phase
- Eventually make Sherpa default for Russian language
- Maintain backward compatibility
