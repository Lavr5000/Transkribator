# WhisperTyping

**Local Voice-to-Text Transcription App**

A free, unlimited, local voice transcription application powered by OpenAI's Whisper. Works completely offline, no API keys required, runs entirely on your computer.

![WhisperTyping Screenshot](assets/screenshot.png)

## Features

- **100% Local Processing** - No internet required, your voice data never leaves your computer
- **Unlimited Usage** - No API costs, no quotas, no limits
- **Fast Transcription** - GPU acceleration with CUDA (50x realtime) or optimized CPU inference
- **Global Hotkey** - Press `Ctrl+Shift+Space` anywhere to start/stop recording
- **Auto-Type** - Automatically types transcribed text into any application
- **Multi-Language** - Supports 99+ languages with auto-detection
- **Modern UI** - Dark theme, system tray integration, always-on-top mode

## Installation

### Quick Install (Recommended)

#### Windows
```batch
# Download and extract the project
# Run the installer
scripts\install.bat
```

#### Linux/macOS
```bash
# Clone or download the project
cd whisper_typing

# Make scripts executable
chmod +x scripts/*.sh

# Run installer
./scripts/install.sh
```

### Manual Install

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For GPU acceleration (NVIDIA)
pip install -r requirements-gpu.txt

# Run
python main.py
```

## Usage

1. **Start the app**: Run `python main.py` or use the desktop shortcut
2. **Record**: Click the red button OR press `Ctrl+Shift+Space`
3. **Speak**: Say what you want to transcribe
4. **Stop**: Click the button again OR press `Ctrl+Shift+Space`
5. **Result**: Text is automatically copied to clipboard and typed

### Hotkey

The default hotkey is `Ctrl+Shift+Space`. You can:
- Press once to start recording
- Press again to stop and transcribe

### Settings

Access settings in the "Settings" tab:
- **Model Size**: Choose from tiny to large (larger = more accurate, slower)
- **Language**: Auto-detect or force a specific language
- **Auto-Copy**: Automatically copy transcription to clipboard
- **Auto-Paste**: Automatically type the text into active window
- **Always on Top**: Keep window above other applications

## System Requirements

### Minimum (CPU)
- Python 3.9+
- 4GB RAM
- 2GB disk space (for base model)

### Recommended (GPU)
- Python 3.9+
- NVIDIA GPU with 4GB+ VRAM
- CUDA 12.x
- 8GB RAM
- 10GB disk space (for large model)

## Model Sizes

| Model | VRAM | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~1GB | Fastest | Basic |
| base | ~1GB | Fast | Good |
| small | ~2GB | Medium | Better |
| medium | ~5GB | Slow | Great |
| large | ~10GB | Slowest | Best |
| large-v3 | ~10GB | Slowest | Latest |

## Troubleshooting

### "No audio recorded"
- Check your microphone is connected and working
- Check system audio permissions
- Try selecting a different input device

### "Model loading failed"
- Ensure you have enough RAM/VRAM
- Try a smaller model (tiny/base)
- Check internet connection for first download

### "Hotkey not working"
- On Linux, may need root access for global hotkeys
- Try running with elevated privileges
- Check for conflicts with other applications

### GPU not detected
- Install NVIDIA drivers
- Install CUDA toolkit
- Use `requirements-gpu.txt`

## Project Structure

```
whisper_typing/
├── main.py              # Entry point
├── requirements.txt     # CPU dependencies
├── requirements-gpu.txt # GPU dependencies
├── pyproject.toml       # Package config
├── README.md            # This file
├── src/
│   ├── __init__.py
│   ├── config.py        # Configuration management
│   ├── audio_recorder.py # Audio recording
│   ├── transcriber.py   # Whisper integration
│   ├── hotkeys.py       # Global hotkey handling
│   └── main_window.py   # PyQt6 GUI
├── scripts/
│   ├── install.sh       # Linux/macOS installer
│   ├── install.bat      # Windows installer
│   ├── run.sh           # Linux/macOS launcher
│   └── run.bat          # Windows launcher
└── assets/
    └── screenshot.png   # App screenshot
```

## License

MIT License - Free for personal and commercial use.

## Credits

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized inference
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Audio recording

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.
