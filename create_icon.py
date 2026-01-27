#!/usr/bin/env python3
"""Create Telegram-style icon for Transkribator"""

from PIL import Image, ImageDraw, ImageFont
import os

# Telegram colors
telegram_blue = (40, 103, 178)
telegram_light = (68, 137, 201)

# Create 256x256 image
size = 256
img = Image.new('RGB', (size, size), telegram_blue)
draw = ImageDraw.Draw(img)

# Draw outer circle
draw.ellipse([20, 20, size-20, size-20], fill=telegram_light)

# Draw T letter
try:
    font = ImageFont.truetype('arial.ttf', 140)
except:
    font = ImageFont.load_default()

# Center text
text = 'T'
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]

x = (size - text_width) // 2
y = (size - text_height) // 2 - 10

draw.text((x, y), text, fill='white', font=font)

# Save as PNG (Windows 10/11 supports PNG icons)
img.save('Transcriber.png')
print('[OK] Icon created: Transcriber.png')
