# Model Parameter Optimization for Speech-to-Text Accuracy

**Date:** 2025-01-27
**Project:** Transkribator
**Goal:** Maximize Russian speech recognition accuracy while balancing speed and quality

---

## Table of Contents

1. [Faster-Whisper Optimization](#faster-whisper-optimization)
2. [Sherpa-ONNX GigaAM v2 Optimization](#sherpa-onnx-gigaam-v2-optimization)
3. [Language Detection vs Forced Language](#language-detection-vs-forced-language)
4. [Model Size Recommendations](#model-size-recommendations)
5. [Whisper Variants Comparison](#whisper-variants-comparison)
6. [Implementation Recommendations](#implementation-recommendations)

---

## Faster-Whisper Optimization

### Core Decoding Parameters

#### beam_size (Integer, default: 1)

**Purpose:** Number of parallel paths to explore during beam search (when temperature=0)

**Recommendation for Russian:**
- **High accuracy:** `beam_size=5` (10-20% accuracy improvement over beam_size=1)
- **Balanced:** `beam_size=2` (minimal quality loss, 2x faster than beam_size=5)
- **Fast:** `beam_size=1` (greedy search, fastest but ~5-10% accuracy loss)

**Current Transkribator setting:** `beam_size=1` (FAST mode)
**Recommended:** Upgrade to `beam_size=2` for better Russian accuracy

**Sources:**
- [OpenAI Whisper Discussion #679](https://github.com/openai/whisper/discussions/679) - recommends beam_size=5
- [Academic Paper 2025](https://www.mdpi.com/2076-3417/15/8/4324) - uses beam_size=5 for research
- [Chinese Optimization Guide 2025](https://blog.csdn.net/gitblog_00401/article/details/151339849)

---

#### best_of (Integer, default: 5)

**Purpose:** Number of candidate samples when temperature > 0 (sampling mode)

**Recommendation for Russian:**
- **With temperature > 0:** `best_of=5` (recommended by OpenAI)
- **With temperature=0:** Irrelevant (use beam_size instead)

**Usage pattern:**
```python
# Option 1: Beam search (recommended for Russian)
model.transcribe(audio, temperature=0, beam_size=5)

# Option 2: Sampling (experimental)
model.transcribe(audio, temperature=[0.0, 0.2, 0.4], best_of=5)
```

**Sources:**
- [GitHub Whisper Discussion](https://github.com/openai/whisper/discussions/679)
- [Faster-Whisper WebUI](https://huggingface.co/spaces/avans06/whisper-webui-translate)

---

#### temperature (Float or list, default: 0.0)

**Purpose:** Controls randomness in sampling. Lower = more deterministic.

**Recommendation for Russian:**
- **Best accuracy:** `temperature=0.0` (deterministic, no hallucinations)
- **Experimental:** Try multiple temperatures `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]` for difficult audio

**Why temperature=0 is best:**
- Eliminates random hallucinations
- Consistent results across runs
- Faster inference (no sampling overhead)
- 20% accuracy improvement in Chinese study

**Sources:**
- [Compression Ratio Guide (Chinese)](https://blog.csdn.net/gitblog_01052/article/details/151035265)
- [Whisper API Docs](https://whisper-api.com/docs/transcription-options/)

---

#### repetition_penalty (Float, default: 1.0)

**Purpose:** Penalty for repeating tokens. Higher values reduce loops.

**Recommendation for Russian:**
- **Current:** Not used (default 1.0)
- **For repetitive audio:** `repetition_penalty=1.2` (prevents "я я я я..." loops)
- **Normal speech:** `repetition_penalty=1.0` (no penalty)

**When to use:**
- Radio/podcast audio with repeated phrases
- Music/background noise causing loops
- Low-quality recordings

**Sources:**
- [10x Improvement Guide (Chinese)](https://blog.csdn.net/gitblog_00649/article/details/151365930)
- [Whisper API Docs](https://whisper-api.com/docs/transcription-options/)

---

#### no_speech_threshold (Float, default: 0.6)

**Purpose:** Probability threshold for detecting silence/no-speech segments.

**Recommendation for Russian:**
- **Strict:** `no_speech_threshold=0.6` (default, recommended)
- **Lenient:** `no_speech_threshold=0.8` (more sensitive to quiet speech)
- **Aggressive:** `no_speech_threshold=0.4` (skip more silence, faster)

**Known Issue:**
When threshold is triggered, faster-whisper may output hallucinations instead of silence (GitHub Issue #621).

**Workaround:**
```python
# Use VAD filter instead for better silence detection
vad_filter=True,
vad_parameters={"min_silence_duration_ms": 200}
```

**Sources:**
- [GitHub Issue #621](https://github.com/SYSTRAN/faster-whisper/issues/621)
- [Core Speech Recognition Docs](https://tessl.io/registry/tessl/pypi-faster-whisper/1.2.0/files/docs/core-speech-recognition.md)

---

#### compression_ratio_threshold (Float, default: 2.4)

**Purpose:** Detects hallucinations by checking if output is too compressed (repetitive).

**Recommendation for Russian:**
- **Default:** `compression_ratio_threshold=2.4` (good balance)
- **Strict:** `compression_ratio_threshold=2.0` (more aggressive filtering)
- **Disabled:** `compression_ratio_threshold=None` (no filtering)

**What it does:**
- Calculates ratio of unique tokens to total tokens
- If ratio < threshold, segment is flagged as potential hallucination
- Helps prevent text like "да да да да да" (yes yes yes yes)

**Sources:**
- [Compression Ratio Optimization Guide](https://blog.csdn.net/gitblog_01052/article/details/151035265)

---

### VAD (Voice Activity Detection) Parameters

#### vad_filter (Boolean, default: False)

**Recommendation for Russian:**
- **ENABLED:** `vad_filter=True` (critical for accuracy)
- **Current Transkribator:** Already enabled ✓

**Benefits:**
- Removes silence automatically
- Prevents hallucinations in quiet sections
- Reduces processing time by skipping silence
- Improves punctuation placement

**Sources:**
- Current implementation in `whisper_backend.py` line 166
- [Whisper API Configuration](https://whisper-api.com/docs/transcription-options/)

---

#### vad_parameters.min_silence_duration_ms (Integer, default: varies)

**Recommendation for Russian:**
- **Current Transkribator:** `200ms` (GOOD)
- **Faster splitting:** `100ms` (more granular, but slower)
- **Longer pauses:** `500ms` (faster, but may merge sentences)

**Trade-off:**
- **Lower value:** Better sentence segmentation, slower processing
- **Higher value:** Faster processing, may merge distinct sentences

**Recommended:** Keep `200ms` for balanced performance

**Sources:**
- Current implementation in `whisper_backend.py` line 167
- Sherpa-ONNX VAD documentation

---

### Recommended Faster-Whisper Configuration for Russian

```python
# HIGH QUALITY (Recommended for Russian)
segments, info = model.transcribe(
    audio,
    language="ru",  # Force Russian (see section below)
    beam_size=5,    # Better accuracy than 1
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 200},
    temperature=0.0,  # Deterministic
    repetition_penalty=1.0,  # Default
    no_speech_threshold=0.6,
    compression_ratio_threshold=2.4,
)

# BALANCED (Fast + Good quality)
segments, info = model.transcribe(
    audio,
    language="ru",
    beam_size=2,  # Sweet spot
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 200},
    temperature=0.0,
)

# FAST (Current Transkribator default)
segments, info = model.transcribe(
    audio,
    language=None,  # Auto-detect
    beam_size=1,  # Greedy
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 200},
)
```

---

## Sherpa-ONNX GigaAM v2 Optimization

### Model Architecture

GigaAM v2 uses **Transducer** architecture (not CTC), which requires different parameters.

**Available GigaAM v2 models:**
1. `sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19` (Latest, 231MB)
2. `sherpa-onnx-nemo-transducer-giga-am-russian-2024-10-24` (Older, 548MB)

**Current Transkribator:** Uses CTC mode (incorrect for v2 models)
**Required fix:** Switch to Transducer mode

---

### Decoding Parameters

#### decoding_method (String, default: "greedy_search")

**Available options:**
- `"greedy_search"` - Fast, good accuracy (RECOMMENDED)
- `"modified_beam_search"` - Slower, marginal improvement
- `"fast_greedy_search"` - Not available for Transducer

**Recommendation for GigaAM v2:**
```python
decoder_config = sherpa_onnx.OfflineTransducerModelConfig(
    encoder_filename="encoder.int8.onnx",
    decoder_filename="decoder.onnx",
    joiner_filename="joiner.onnx",
)

recognizer = sherpa_onnx.OfflineRecognizer(
    model_config=decoder_config,
    tokens="tokens.txt",
    decoding_method="greedy_search",  # ✓ Recommended
    max_active_paths=4,  # See below
)
```

**Sources:**
- [Sherpa-ONNX NeMo Transducer Docs](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html)

---

#### max_active_paths (Integer, default: 4)

**Purpose:** Number of active paths in beam search for Transducer models.

**Recommendation for GigaAM v2:**
- **Default:** `max_active_paths=4` (good balance)
- **High accuracy:** `max_active_paths=8` (minimal gain, 2x slower)
- **Fast:** `max_active_paths=2` (slightly faster, minimal quality loss)

**Performance impact:**
- `max_active_paths=4`: RTF 0.382 (Real-time Factor)
- `max_active_paths=8`: RTF ~0.5 (estimated, 30% slower)

**Sources:**
- [Sherpa-ONNX Offline Decoder Example](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-decode-files.py)
- [Sherpa-ONNX Russian Model Docs](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19-russian)

---

### Threading Parameters

#### num_threads (Integer, default: cpu_count)

**Current Transkribator:**
```python
cpu_count = os.cpu_count() or 4
self.num_threads = max(1, min(cpu_count, 8))  # Max 8 threads
```

**Recommendation for GigaAM v2:**
- **CPU with 4+ cores:** `num_threads=4` (sweet spot)
- **CPU with 8+ cores:** `num_threads=6` (diminishing returns beyond 6)
- **Low-end CPU:** `num_threads=2` (avoid overloading)

**Benchmark from Sherpa-ONNX docs (Cortex A76):**
| Threads | RTF | Speed |
|---------|-----|------|
| 1 | 0.220 | 4.5x real-time |
| 2 | 0.142 | 7x real-time |
| 3 | 0.118 | 8.5x real-time |
| 4 | 0.088 | 11x real-time |

**Sources:**
- [Sherpa-ONNX Parakeet Model Benchmarks](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#rtf-on-rk3588-with-cortex-a76-cpu)

---

### VAD for Sherpa-ONNX

**Current Transkribator:** No VAD used
**Recommendation:** Optional (GigaAM v2 has built-in silence handling)

**If enabling VAD:**
```bash
# Download Silero VAD model
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx

# Use VAD-enabled recognizer
./sherpa-onnx-vad-microphone-offline-asr \
  --silero-vad-model=./silero_vad.onnx \
  --encoder=./encoder.int8.onnx \
  --decoder=./decoder.onnx \
  --joiner=./joiner.onnx \
  --tokens=./tokens.txt \
  --model-type=nemo_transducer
```

**Sources:**
- [Sherpa-ONNX NeMo Transducer with VAD](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#speech-recognition-from-a-microphone-with-vad)

---

### Recommended Sherpa-ONNX Configuration for Russian

```python
# GigaAM v2 (Transducer) - Recommended
recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
    encoder="encoder.int8.onnx",
    decoder="decoder.onnx",
    joiner="joiner.onnx",
    tokens="tokens.txt",
    num_threads=4,  # Adjust based on CPU cores
    decoding_method="greedy_search",  # ✓ Best for Transducer
    max_active_paths=4,  # Default, good balance
)

# Alternative: Use config object directly
from sherpa_onnx import OfflineRecognizerConfig, OfflineTransducerModelConfig

config = OfflineRecognizerConfig(
    feat_config=sherpa_onnx.FeatureExtractorConfig(
        sampling_rate=16000,
        feature_dim=80,
    ),
    model_config=OfflineTransducerModelConfig(
        encoder_filename="encoder.int8.onnx",
        decoder_filename="decoder.onnx",
        joiner_filename="joiner.onnx",
    ),
    decoding_method="greedy_search",
    max_active_paths=4,
    num_threads=4,
)

recognizer = sherpa_onnx.OfflineRecognizer(config)
```

---

### Bug Fix Required in Transkribator

**Current code (sherpa_backend.py:162-170):**
```python
# INCORRECT: Uses CTC mode for Transducer model
self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
    model=str(model_file),
    tokens=str(tokens_file),
    num_threads=self.num_threads,
    sample_rate=16000,
    feature_dim=80,
    decoding_method="greedy_search",
    debug=False,
)
```

**Fixed code:**
```python
# CORRECT: Use Transducer mode for GigaAM v2
self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
    encoder=str(model_dir / "encoder.int8.onnx"),
    decoder=str(model_dir / "decoder.onnx"),
    joiner=str(model_dir / "joiner.onnx"),
    tokens=str(tokens_file),
    num_threads=self.num_threads,
    decoding_method="greedy_search",
)
```

---

## Language Detection vs Forced Language

### Faster-Whisper

**Recommendation:** **Always force Russian language** (`language="ru"`)

**Why:**
1. **Known detection issues** ([GitHub Issue #918](https://github.com/SYSTRAN/faster-whisper/issues/918))
2. **Eliminates overhead** - no time spent on detection
3. **Prevents misclassification** - won't confuse Russian with Ukrainian/Belarusian
4. **Consistent behavior** - same results across runs

**When to use auto-detection:**
- Multilingual audio (Russian + English mixed)
- Unknown language (rare in Transkribator use case)

**Performance impact:**
- Forced language: ~2-5% faster
- Auto-detection: +50-200ms initial processing time

**Sources:**
- [Faster-Whisper GitHub](https://github.com/SYSTRAN/faster-whisper) - mentions detection issues
- [HuggingFace Large V3 Russian](https://huggingface.co/antony66/whisper-large-v3-russian) - fine-tuned model
- [Language Detection Discussion](https://github.com/openai/whisper/discussions/529)

---

### Sherpa-ONNX GigaAM

**Recommendation:** **Language is hardcoded in model** (no need to specify)

**Why:**
- GigaAM v2 is Russian-only model
- No language parameter in API
- Model architecture is monolingual

**Implementation:**
```python
# No language parameter needed
recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
    encoder="encoder.int8.onnx",
    decoder="decoder.onnx",
    joiner="joiner.onnx",
    tokens="tokens.txt",
    # language="ru"  # ← Not needed, model is Russian-only
)
```

**Sources:**
- [GigaAM v2 Model Docs](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19-russian)

---

## Model Size Recommendations

### Faster-Whisper Model Sizes

| Model | Parameters | VRAM | Speed (RTF) | Russian WER | Use Case |
|-------|-----------|------|-------------|-------------|----------|
| **tiny** | 39M | 1GB | 0.1x | ~25% | Real-time, low accuracy |
| **base** | 74M | 1GB | 0.15x | ~18% | Balanced (current default) |
| **small** | 244M | 2GB | 0.3x | ~12% | Good accuracy |
| **medium** | 769M | 5GB | 0.6x | ~9% | High accuracy |
| **large-v2** | 1550M | 10GB | 1.0x | ~7% | Best accuracy |
| **large-v3** | 1550M | 10GB | 1.2x | ~5.5% | State of the art |
| **large-v3-turbo** | 809M | 6GB | 0.4x | ~6% | Best balance |

**WER (Word Error Rate) for Russian:** Lower is better

---

### Recommended Models for Russian

#### Production (Recommended)
**Model:** `large-v3-turbo`
- **Accuracy:** 6% WER (near large-v3 quality)
- **Speed:** 0.4x RTF (2.5x real-time)
- **Size:** 809M parameters
- **VRAM:** 6GB (or 3GB with int8 quantization)

**Why:**
- 10-20% better than large-v2
- 3x faster than full large-v3
- Best accuracy/speed tradeoff

**Download:**
```bash
# faster-whisper
model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
```

**Sources:**
- [Faster-Whisper Issue #1030](https://github.com/SYSTRAN/faster-whisper/issues/1030) - benchmarks
- [Large V3 Turbo Article](https://medium.com/axinc-ai/whisper-large-v3-turbo-high-accuracy-and-fast-speech-recognition-model-be2f6af77bdc)

---

#### High Accuracy (Offline processing)
**Model:** `large-v3`
- **Accuracy:** 5.5% WER (best available)
- **Speed:** 1.2x RTF (slower than real-time)
- **Size:** 1550M parameters
- **VRAM:** 10GB

**When to use:**
- Batch processing (no real-time requirement)
- Maximum accuracy needed
- GPU with 10GB+ VRAM

**Russian fine-tuned version:**
- `antony66/whisper-large-v3-russian` - 6.39% WER on Russian test set (vs 9.84% base)
- [HuggingFace Model](https://huggingface.co/antony66/whisper-large-v3-russian)

---

#### Fast (Real-time)
**Model:** `small`
- **Accuracy:** 12% WER (acceptable for many use cases)
- **Speed:** 0.3x RTF (3x real-time)
- **Size:** 244M parameters
- **VRAM:** 2GB

**When to use:**
- Real-time transcription required
- CPU inference
- Low memory constraints

**Current Transkribator default:** `base` (similar speed, slightly worse accuracy)

---

### CPU vs GPU Recommendations

| Device | Recommended Model | Compute Type |
|--------|------------------|--------------|
| **CPU (fast)** | base | int8 |
| **CPU (accurate)** | small | int8 |
| **GPU (4GB)** | medium | float16 |
| **GPU (6GB)** | large-v3-turbo | float16 |
| **GPU (10GB+)** | large-v3 | float16 |

**Current Transkribator logic (whisper_backend.py:57-61):**
```python
if compute_type == "auto":
    if device == "cuda":
        compute_type = "float16"  # ✓ Correct
    else:
        compute_type = "int8"     # ✓ Correct
```

---

### Sherpa-ONNX Model Recommendations

| Model | Size | RTF | Accuracy | Notes |
|-------|------|-----|----------|-------|
| **GigaAM v2** | 231MB | 0.38 | Best | Latest, recommended |
| **GigaAM v1** | 548MB | 0.16 | Good | Older, faster |

**Recommendation:** Use GigaAM v2 for best Russian accuracy

**Performance:** RTF 0.38 means 2.6x faster than real-time

**Sources:**
- [GigaAM v2 Documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19-russian)
- [GigaAM v1 Documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-transducer-giga-am-russian-2024-10-24-russian)

---

## Whisper Variants Comparison

### Accuracy Comparison (Russian WER)

| Model | WER | Improvement | Notes |
|-------|-----|-------------|-------|
| Whisper tiny | ~25% | baseline | Fastest, worst accuracy |
| Whisper base | ~18% | +28% vs tiny | Current Transkribator default |
| Whisper small | ~12% | +33% vs base | Good balance |
| Whisper medium | ~9% | +25% vs small | High accuracy |
| Whisper large-v2 | ~7% | +22% vs medium | Previous SOTA |
| **Whisper large-v3** | ~5.5% | +21% vs v2 | **Current SOTA** |
| Large v3-turbo | ~6% | -9% vs v3 | Best speed/accuracy |
| Large v3-russian | ~6.4% | -16% vs v3 | Fine-tuned for Russian |

**SOTA = State of the Art**

**Sources:**
- [OpenAI Whisper Paper](https://cdn.openai.com/papers/whisper.pdf)
- [HuggingFace Large V3](https://huggingface.co/openai/whisper-large-v3)
- [Russian Fine-tuned Model](https://huggingface.co/antony66/whisper-large-v3-russian)
- [10 Speech-to-Text Models Tested](https://www.telusdigital.com/insights/data-and-ai/article/10-speech-to-text-models-tested)

---

### Speed Comparison (RTF - Real-Time Factor)

RTF < 1.0 = faster than real-time
RTF > 1.0 = slower than real-time

| Model | CPU RTF | GPU RTF | Notes |
|-------|---------|---------|-------|
| tiny | 0.3 | 0.05 | Very fast |
| base | 0.5 | 0.08 | Current default |
| small | 1.0 | 0.15 | Real-time on GPU |
| medium | 2.5 | 0.3 | Good GPU speed |
| large-v2 | 5.0 | 0.5 | Slow on CPU |
| **large-v3-turbo** | 3.0 | **0.2** | **Recommended** |
| large-v3 | 6.0 | 0.6 | Best accuracy |

**Recommendation:**
- **CPU:** Use `base` or `small`
- **GPU:** Use `large-v3-turbo` (best balance)

---

### Faster-Whisper vs OpenAI Whisper

| Feature | Faster-Whisper | OpenAI Whisper |
|---------|---------------|----------------|
| Speed | 2-4x faster | Baseline |
| Memory | 50-70% less | Higher usage |
| Accuracy | Identical | Identical |
| Quantization | int8, float16, int4 | Only float16/float32 |
| GPU support | CUDA, CPU | CUDA, CPU, MPS |
| Language detection | ✓ | ✓ |
| VAD filter | ✓ Built-in | ✗ (needs separate) |

**Recommendation:** Use faster-whisper (already implemented in Transkribator)

**Sources:**
- [Faster-Whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [Comparison LinkedIn Post](https://www.linkedin.com/posts/dima-lavrentiev_whisper-vs-faster-whisper-which-speech-to-text-activity-7389420785032941568-WbKk)

---

## Implementation Recommendations

### Priority 1: Critical Fixes

1. **Fix Sherpa-ONNX backend (sherpa_backend.py:162)**
   - Change from `from_nemo_ctc()` to `from_nemo_transducer()`
   - Update to use encoder/decoder/joiner files separately
   - **Impact:** Fixes incorrect model architecture, major accuracy improvement

2. **Force Russian language in Whisper (whisper_backend.py:159)**
   - Change `language=None` to `language="ru"`
   - **Impact:** Eliminates detection overhead, prevents misclassification

3. **Increase Whisper beam_size (whisper_backend.py:165)**
   - Change from `beam_size=1` to `beam_size=2` or `beam_size=5`
   - **Impact:** 10-20% accuracy improvement for Russian

---

### Priority 2: Model Upgrades

1. **Upgrade to Whisper large-v3-turbo (optional)**
   - Change default model from `base` to `large-v3-turbo`
   - Requires GPU with 6GB+ VRAM
   - **Impact:** 12% → 6% WER (2x accuracy improvement)

2. **Add Russian fine-tuned model option (optional)**
   - Add `antony66/whisper-large-v3-russian` as model option
   - **Impact:** 9.84% → 6.39% WER on Russian test set

---

### Priority 3: Parameter Tuning

1. **Add repetition_penalty for noisy audio (optional)**
   ```python
   # In transcribe() method
   repetition_penalty=1.2 if is_noisy_audio else 1.0
   ```

2. **Tune VAD parameters for speech pacing (optional)**
   - Allow user to adjust `min_silence_duration_ms`
   - Range: 100-500ms
   - **Impact:** Better sentence segmentation

---

### Recommended Configuration Files

#### config_whisper_russian.yaml
```yaml
# High accuracy configuration for Russian speech
model: "large-v3-turbo"
language: "ru"
device: "cuda"
compute_type: "float16"

# Decoding parameters
beam_size: 5
temperature: 0.0
best_of: 5

# VAD parameters
vad_filter: true
vad_parameters:
  min_silence_duration_ms: 200
  speech_pad_ms: 30

# Quality control
no_speech_threshold: 0.6
compression_ratio_threshold: 2.4
repetition_penalty: 1.0
```

#### config_sherpa_russian.yaml
```yaml
# GigaAM v2 configuration for Russian
model: "giga-am-v2-ru"
language: "ru"  # Hardcoded in model
num_threads: 4

# Decoding (Transducer-specific)
decoding_method: "greedy_search"
max_active_paths: 4

# Feature extraction
sample_rate: 16000
feature_dim: 80
```

---

### Code Changes Required

#### whisper_backend.py - Line 159-169
```python
# BEFORE (current)
language = self.language if self.language != "auto" else None

if WHISPER_BACKEND == "faster-whisper":
    segments, info = self._model.transcribe(
        audio,
        language=language,
        beam_size=1,  # Too small
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=200)
    )

# AFTER (recommended)
language = "ru"  # Force Russian (better than auto-detect)

if WHISPER_BACKEND == "faster-whisper":
    segments, info = self._model.transcribe(
        audio,
        language=language,
        beam_size=5,  # Better accuracy
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=200),
        temperature=0.0,  # Deterministic
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.4,
    )
```

#### sherpa_backend.py - Line 162-170
```python
# BEFORE (current - INCORRECT)
self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
    model=str(model_file),
    tokens=str(tokens_file),
    num_threads=self.num_threads,
    sample_rate=16000,
    feature_dim=80,
    decoding_method="greedy_search",
    debug=False,
)

# AFTER (recommended - CORRECT)
model_dir = self._get_model_dir()
self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
    encoder=str(model_dir / "encoder.int8.onnx"),
    decoder=str(model_dir / "decoder.onnx"),
    joiner=str(model_dir / "joiner.onnx"),
    tokens=str(tokens_file),
    num_threads=self.num_threads,
    decoding_method="greedy_search",
    max_active_paths=4,
)
```

---

## Summary of Key Recommendations

### For Faster-Whisper (Russian)
1. **Force language:** `language="ru"` (not auto-detect)
2. **Increase beam_size:** `5` for quality, `2` for balance
3. **Keep VAD enabled:** `vad_filter=True` with `min_silence_duration_ms=200`
4. **Use temperature=0:** Deterministic decoding
5. **Model upgrade:** Consider `large-v3-turbo` for GPU users

### For Sherpa-ONNX GigaAM v2
1. **Fix architecture:** Use Transducer mode (not CTC)
2. **Keep greedy_search:** Best for Transducer models
3. **max_active_paths=4:** Good balance
4. **num_threads=4-6:** Optimal for most CPUs
5. **Use latest model:** `giga-am-v2-russian-2025-04-19`

### General
1. **Always force Russian language** when audio is known to be Russian
2. **Enable VAD** for both backends
3. **Use int8 quantization** for CPU, float16 for GPU
4. **Monitor WER** to validate improvements

---

## Sources

### Faster-Whisper Optimization
1. [Optimization Guide (Chinese) - beam_size & temperature](https://blog.csdn.net/gitblog_00401/article/details/151339849)
2. [10x Improvement Guide (Chinese)](https://blog.csdn.net/gitblog_00649/article/details/151365930)
3. [Compression Ratio Guide (Chinese)](https://blog.csdn.net/gitblog_01052/article/details/151035265)
4. [Ultra-detailed API Manual (Chinese)](https://blog.csdn.net/gitblog_00941/article/details/151335763)
5. [OpenAI Whisper Discussion #679 - Hallucinations](https://github.com/openai/whisper/discussions/679)
6. [Faster-Whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
7. [Core Speech Recognition Docs](https://tessl.io/registry/tessl/pypi-faster-whisper/1.2.0/files/docs/core-speech-recognition.md)
8. [Whisper API Configuration Options](https://whisper-api.com/docs/transcription-options/)

### Sherpa-ONNX & GigaAM
1. [Sherpa-ONNX NeMo Transducer Models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html)
2. [Sherpa-ONNX GitHub](https://github.com/k2-fsa/sherpa-onnx)
3. [Offline Decoder Example](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-decode-files.py)
4. [GigaAM v2 Russian Model Docs](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19-russian)
5. [GigaAM ONNX Optimization Issue](https://github.com/salute-developers/GigaAM/issues/34)

### Whisper Model Comparison
1. [OpenAI Whisper Paper](https://cdn.openai.com/papers/whisper.pdf)
2. [HuggingFace Whisper Large V3](https://huggingface.co/openai/whisper-large-v3)
3. [Whisper Large V3 Turbo Article](https://medium.com/axinc-ai/whisper-large-v3-turbo-high-accuracy-and-fast-speech-recognition-model-be2f6af77bdc)
4. [Russian Fine-tuned Model](https://huggingface.co/antony66/whisper-large-v3-russian)
5. [Faster-Whisper Issue #1030 - Benchmarks](https://github.com/SYSTRAN/faster-whisper/issues/1030)
6. [10 Speech-to-Text Models Tested](https://www.telusdigital.com/insights/data-and-ai/article/10-speech-to-text-models-tested)
7. [Model Selection Guide 2025 (Chinese)](https://blog.csdn.net/gitblog_02885/article/details/149626003)
8. [Model Matrix Guide (Chinese)](https://blog.csdn.net/gitblog_00996/article/details/151335891)

### Language Detection & Russian Optimization
1. [Faster-Whisper Issue #918 - Language Detection](https://github.com/SYSTRAN/faster-whisper/issues/918)
2. [Wrong Language Detection Discussion](https://github.com/openai/whisper/discussions/529)
3. [HuggingFace Large V3 Russian](https://huggingface.co/antony66/whisper-large-v3-russian)
4. [Russian Optimized Turbo Model](https://huggingface.co/dvislobokov/faster-whisper-large-v3-turbo-russian)

### Academic Papers
1. [End-to-End Multi-Modal Speaker Change (MDPI 2025)](https://www.mdpi.com/2076-3417/15/8/4324) - Uses beam_size=5, temperature=0
2. [Scaling Speech Technology to 1000+ Languages (JMLR 2024)](https://jmlr.org/papers/volume25/23-1318/23-1318.pdf)
3. [arXiv:2406.18301v1 - Multilingual ASR vs Whisper](https://arxiv.org/pdf/2406.18301)

### Benchmarks & Performance
1. [URO-Bench: Comprehensive Evaluation (ACL 2025)](https://aclanthology.org/2025.findings-emnlp.933.pdf)
2. [Assessing Whisper ASR (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/pii/S2772766125000187)
3. [Speech Recognition Models Comparison (MDPI 2024)](https://www.mdpi.com/2078-2489/16/10/879)
4. [Real-world Russian ASR Study (ResearchGate)](https://www.researchgate.net/figure/The-CER-WER-results-average-boost-AB-over-the-monolingual-baseline-and_tbl5_367552794)

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-27 | Initial research document |

---

**Next Steps:**
1. Review and validate recommendations
2. Test configuration changes with real Russian audio
3. Measure WER improvements
4. Update Transkribator code with Priority 1 fixes
5. Add user-configurable profiles (Fast/Balanced/Quality)
