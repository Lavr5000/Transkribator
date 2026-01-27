#!/usr/bin/env python3
"""Convert PNG to ICO with multiple sizes for Windows shortcut"""

from PIL import Image
import os

# Input and output paths
png_path = "Transcriber.png"
ico_path = "Transcriber.ico"

print(f"Converting {png_path} to {ico_path}...")

try:
    # Open the PNG
    img = Image.open(png_path)

    # Create ICO with multiple sizes for best quality
    # Windows uses different sizes in different contexts (desktop, taskbar, etc.)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

    # Save as ICO with all sizes
    img.save(ico_path, format='ICO', sizes=sizes)

    print(f"[OK] ICO created: {ico_path}")
    print(f"    Sizes: {sizes}")

    # Verify file was created
    if os.path.exists(ico_path):
        size_kb = os.path.getsize(ico_path) / 1024
        print(f"    File size: {size_kb:.1f} KB")
    else:
        print("[ERROR] ICO file was not created!")
        exit(1)

except FileNotFoundError:
    print(f"[ERROR] {png_path} not found!")
    print("Run create_icon.py first to generate the PNG.")
    exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    exit(1)
