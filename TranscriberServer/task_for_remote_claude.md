# Task for Claude Code on Remote PC (192.168.31.9)

Execute this on the remote PC to install Sherpa and fix the server.

## Goal: Make transcriber_loaded=true on http://192.168.31.9:8000/health

## Steps:

1. **Verify src folder exists:**
   ```powershell
   Test-Path "C:\Users\Denis\TranscriberServer\src"
   ```
   Expected: True

2. **Install sherpa-onnx:**
   ```batch
   pip install sherpa-onnx
   ```

3. **Verify installation:**
   ```python
   python -c "import sherpa_onnx; print('OK')"
   ```

4. **Stop old server:**
   ```batch
   taskkill /F /IM python.exe
   ```

5. **Start server:**
   ```batch
   cd C:\Users\Denis\TranscriberServer
   python server.py
   ```

6. **Check health:**
   ```batch
   curl http://192.168.31.9:8000/health
   ```

   Expected:
   ```json
   {"status": "healthy", "transcriber_loaded": true}
   ```

## If transcriber_loaded=false:

Problem: Sherpa model not loading

Solution: Switch to Whisper backend

1. Edit `C:\Users\Denis\TranscriberServer\transcriber_wrapper.py`

2. Change backend to Whisper:
   ```python
   transcriber = Transcriber(
       backend="whisper",  # Changed from "sherpa"
       model_size="base",  # Changed from "giga-am-v2-ru"
       device="cpu",
       language="ru",
       enable_post_processing=True
   )
   ```

3. Restart server

4. Check health again - should be transcriber_loaded=true

## Final Test:

After transcriber_loaded=true, test from laptop:
- Press F9 → speak → F9
- Should see 🌐 (globe) indicator
- Transcription should be fast (3-10 seconds)
