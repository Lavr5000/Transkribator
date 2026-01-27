#!/usr/bin/env python3
"""Create Transkribator desktop shortcut with custom icon"""

import os
import sys
from pathlib import Path
import subprocess

def create_shortcut():
    # Paths
    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / "Transkribator.lnk"
    target = Path(r"C:\Users\user\.claude\0 ProEKTi\Transkribator\main.py")
    icon_path = Path(r"C:\Users\user\.claude\0 ProEKTi\Transkribator\Transcriber.ico")

    print("Creating Transkribator desktop shortcut...")
    print(f"  Target: {target}")
    print(f"  Shortcut: {shortcut_path}")
    print(f"  Icon: {icon_path}")

    # Create icon from Telegram logo
    if not icon_path.exists():
        print(f"  Icon not found, creating from Telegram logo...")
        create_transcriber_icon(icon_path)

    # Create shortcut using PowerShell
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "python"
$Shortcut.Arguments = '"{target}"'
$Shortcut.WorkingDirectory = "{target.parent}"
$Shortcut.Description = "Transkribator - AI Speech to Text"
$Shortcut.IconLocation = "{icon_path}"
$Shortcut.Save()
'''

    ps_file = desktop / "create_shortcut.ps1"
    ps_file.write_text(ps_script, encoding='utf-8')

    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)],
                   capture_output=True)
    ps_file.unlink()

    if shortcut_path.exists():
        print(f"\n✅ Shortcut created: {shortcut_path}")
        return True
    else:
        print(f"\n❌ Failed to create shortcut")
        return False

def create_transcriber_icon(icon_path):
    """Create Transkribator icon from Telegram logo style"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Telegram logo colors
        telegram_blue = (40, 103, 178)  # #2867B2
        telegram_light = (68, 137, 201)  # #4489C9

        # Create 256x256 icon
        size = 256
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))

        # Draw circle (Telegram style)
        margin = 20
        draw = ImageDraw.Draw(img)

        # Outer circle
        draw.ellipse([margin, margin, size-margin, size-margin],
                     fill=telegram_blue)

        # Inner circle (gradient effect)
        inner_margin = 35
        draw.ellipse([inner_margin, inner_margin, size-inner_margin, size-inner_margin],
                     fill=telegram_light)

        # Draw "T" letter (Transkribator)
        # Try to use default font
        try:
            font = ImageFont.truetype("arial.ttf", 120)
        except:
            font = ImageFont.load_default()

        # Draw "T" for Transkribator
        text = "T"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2 - 10

        draw.text((text_x, text_y), text, fill="white", font=font)

        # Save as ICO
        img.save(icon_path, format='ICO', sizes=[256, 128, 64, 32, 16])
        print(f"  Icon created: {icon_path}")

    except ImportError:
        print("  PIL not available, creating simple icon...")
        # Simple approach: download Telegram logo and use it
        import urllib.request

        # Download Telegram icon
        telegram_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/256px-Telegram_logo.svg.png"
        temp_png = icon_path.parent / "telegram_temp.png"

        try:
            urllib.request.urlretrieve(telegram_url, temp_png)

            # Convert to ICO
            from PIL import Image
            img = Image.open(temp_png)
            img.save(icon_path, format='ICO', sizes=[256, 128, 64, 32, 16])
            temp_png.unlink()
            print(f"  Icon created from Telegram logo: {icon_path}")

        except Exception as e:
            print(f"  Could not download icon: {e}")
            # Create placeholder
            create_placeholder_icon(icon_path)

def create_placeholder_icon(icon_path):
    """Create a simple placeholder icon"""
    try:
        from PIL import Image, ImageDraw

        size = 256
        img = Image.new('RGBA', (size, size), (40, 103, 178, 255))
        draw = ImageDraw.Draw(img)

        # Draw circle
        draw.ellipse([20, 20, size-20, size-20], fill=(68, 137, 201, 255))

        # Draw T
        try:
            font = ImageFont.truetype("arial.ttf", 140)
        except:
            font = ImageFont.load_default()

        draw.text((70, 50), "T", fill="white", font=font)

        img.save(icon_path, format='ICO', sizes=[256, 128, 64, 32, 16])

    except Exception as e:
        print(f"  Could not create icon: {e}")

if __name__ == "__main__":
    create_shortcut()
