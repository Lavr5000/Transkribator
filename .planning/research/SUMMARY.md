# Research Summary - Transkribator Milestone v1.1

## Overview

Проведена диагностика проблемы медленной транскрибации на удалённом сервере. Найдены **критические проблемы** в конфигурации и архитектуре.

## Key Findings

### 1. CRITICAL: Server uses OLD parameters

**File:** `TranscriberServer/transcriber_wrapper.py`

**Current (PROBLEMATIC):**
```python
self.transcriber = Transcriber(
    backend="whisper",      # Slow
    model_size="base",      # Not optimized
    language="auto",        # Extra computations + worse accuracy
)
```

**Optimal (from Phase 1-4):**
```python
self.transcriber = Transcriber(
    backend="sherpa",              # 10x faster
    model_size="giga-am-v2-ru",    # Russian optimized
    language="ru",                 # Force Russian
    vad_enabled=True,              # Remove silence
)
```

### 2. CRITICAL: WAV format without compression

**File:** `src/remote_client.py:158`

Impact: 30 sec recording = ~960 KB, 5 min = ~9.6 MB
Upload time at 1 Mbps: 30 sec = ~8 sec, 5 min = ~80 sec

**Solution:** Opus encoding (~10x compression)

### 3. IMPORTANT: Slow polling

**File:** `src/remote_client.py:204`
```python
check_interval = 2.0  # Add 1-2 sec delay
```

## Bottlenecks (by time)

| Stage | Time | % of total |
|-------|------|------------|
| Upload (WAV) | 5-30 sec | **40-70%** |
| Transcription | 2-10 sec | 15-30% |
| Polling delay | 1-2 sec | 5-10% |
| Other | 1-2 sec | 5-10% |

**Upload is the main bottleneck!**

---
*Research completed: 2026-01-30*
