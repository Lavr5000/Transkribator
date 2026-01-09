#!/bin/bash
# WhisperTyping Installation Script for Linux/macOS

set -e

echo "=================================="
echo "  WhisperTyping Installer"
echo "=================================="
echo ""

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.9 or later."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

# Check if version is >= 3.9
MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]); then
    echo "Error: Python 3.9 or later is required. Found $PYTHON_VERSION"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
$PYTHON_CMD -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Ask for GPU support
echo ""
echo "Do you have an NVIDIA GPU and want GPU acceleration? (y/n)"
read -r GPU_SUPPORT

if [ "$GPU_SUPPORT" = "y" ] || [ "$GPU_SUPPORT" = "Y" ]; then
    echo ""
    echo "Installing GPU version..."
    pip install -r requirements-gpu.txt
else
    echo ""
    echo "Installing CPU version..."
    pip install -r requirements.txt
fi

# Install package
echo ""
echo "Installing WhisperTyping..."
pip install -e .

# Create desktop entry (Linux only)
if [ "$(uname)" = "Linux" ]; then
    echo ""
    echo "Creating desktop shortcut..."

    DESKTOP_FILE="$HOME/.local/share/applications/whisper-typing.desktop"
    mkdir -p "$HOME/.local/share/applications"

    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=WhisperTyping
Comment=Local Voice Transcription
Exec=$PWD/venv/bin/python $PWD/main.py
Icon=audio-input-microphone
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
EOF

    echo "Desktop shortcut created: $DESKTOP_FILE"
fi

echo ""
echo "=================================="
echo "  Installation Complete!"
echo "=================================="
echo ""
echo "To run WhisperTyping:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or use the desktop shortcut (Linux)"
echo ""
