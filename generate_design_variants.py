"""
Generate 4 UI design variants for the transcription app.
Each variant shows a different gradient direction.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Design variants
VARIANTS = {
    "Neon Cyberpunk": {
        "colors": ["#FF006E", "#FB5607", "#8338EC"],
        "description": "Electric pink → Hot coral → Purple",
        "border": "#FF006E"
    },
    "Ocean Depths": {
        "colors": ["#0D9488", "#06B6D4", "#0EA5E9"],
        "description": "Deep teal → Aqua → Sky blue",
        "border": "#06B6D4"
    },
    "Solar Flare": {
        "colors": ["#F59E0B", "#EA580C", "#F43F5E"],
        "description": "Amber → Orange → Rose",
        "border": "#F59E0B"
    },
    "Matrix Code": {
        "colors": ["#22C55E", "#84CC16", "#10B981"],
        "description": "Bright green → Lime → Emerald",
        "border": "#22C55E"
    }
}

def hex_to_rgb(hex_color):
    """Convert hex to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_gradient(width, height, colors):
    """Create horizontal gradient from list of hex colors."""
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    n_stops = len(colors)
    segment_width = width / (n_stops - 1)

    for x in range(width):
        # Find which segment we're in
        segment = min(int(x // segment_width), n_stops - 2)

        # Position within segment (0-1)
        t = (x - segment * segment_width) / segment_width

        # Interpolate between two colors
        c1 = hex_to_rgb(colors[segment])
        c2 = hex_to_rgb(colors[segment + 1])

        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)

        for y in range(height):
            pixels[x, y] = (r, g, b)

    return img

def create_bar_preview(width, height, colors, border_color, bg_color="#0a0a0f"):
    """Create a preview of the app bar with gradient."""
    # Background
    bg = Image.new('RGB', (width + 40, height + 60), hex_to_rgb(bg_color))
    draw = ImageDraw.Draw(bg)

    # Draw shadow/glow
    shadow_offset = 2
    for i in range(3):
        y_off = shadow_offset + i
        draw.rounded_rectangle(
            [(20 - i, 20 + y_off - i), (20 + width + i, 20 + height + y_off + i)],
            radius=12,
            fill=tuple(hex_to_rgb(border_color) + (30,))
        )

    # Gradient bar
    gradient = create_gradient(width, height, colors)
    bg.paste(gradient, (20, 20))

    # Border
    draw.rounded_rectangle(
        [(20, 20), (20 + width, 20 + height)],
        radius=12,
        outline=hex_to_rgb(border_color),
        width=1
    )

    # Record button (red circle)
    button_x = 20 + width // 2
    button_y = 20 + height // 2
    button_radius = 12
    draw.ellipse(
        [(button_x - button_radius, button_y - button_radius),
         (button_x + button_radius, button_y + button_radius)],
        fill=(239, 68, 68)
    )

    # Telegram icon (small paper plane)
    tg_x = 20 + width - 30
    tg_y = 20 + height - 15
    # Simple plane shape
    plane_points = [
        (tg_x, tg_y + 5),
        (tg_x + 12, tg_y + 2),
        (tg_x, tg_y - 1),
        (tg_x + 3, tg_y + 2)
    ]
    draw.polygon(plane_points, fill=(0, 136, 204))

    return bg

def create_comparison_image():
    """Create image showing all 4 variants."""
    # Variant preview size
    bar_width = 300
    bar_height = 52
    padding = 40

    # Total image size (2x2 grid)
    total_width = (bar_width + 40) * 2 + padding * 3
    total_height = (bar_height + 100) * 2 + padding * 3

    # Dark background
    bg = Image.new('RGB', (total_width, total_height), (15, 15, 20))
    draw = ImageDraw.Draw(bg)

    # Try to load font
    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        label_font = ImageFont.truetype("arial.ttf", 18)
        hex_font = ImageFont.truetype("consola.ttf", 14)
    except:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        hex_font = ImageFont.load_default()

    # Title
    draw.text((total_width // 2, 20), "Voice Transcriber - Design Variants",
              fill=(255, 255, 255), font=title_font, anchor="mt")

    positions = [
        (padding, 80),
        (total_width // 2 + padding // 2, 80),
        (padding, 80 + (bar_height + 100)),
        (total_width // 2 + padding // 2, 80 + (bar_height + 100))
    ]

    for idx, (name, variant) in enumerate(VARIANTS.items()):
        x, y = positions[idx]

        # Create bar preview
        bar = create_bar_preview(bar_width, bar_height, variant['colors'], variant['border'])
        bg.paste(bar, (x, y))

        # Variant name
        text_y = y + bar_height + 55
        draw.text((x + bar_width // 2, text_y), name,
                  fill=hex_to_rgb(variant['colors'][1]),
                  font=label_font, anchor="mt")

        # Color hex codes
        hex_text = " | ".join(variant['colors'])
        draw.text((x + bar_width // 2, text_y + 25), hex_text,
                  fill=(150, 150, 160),
                  font=hex_font, anchor="mt")

    return bg

def create_individual_previews():
    """Create individual preview images for each variant."""
    previews = {}
    bar_width = 340
    bar_height = 52

    for name, variant in VARIANTS.items():
        preview = create_bar_preview(bar_width, bar_height, variant['colors'], variant['border'])
        previews[name] = preview

    return previews

if __name__ == "__main__":
    os.makedirs("design_variants", exist_ok=True)

    # Create comparison image
    print("Creating comparison image...")
    comparison = create_comparison_image()
    comparison.save("design_variants/comparison.png")
    print("Saved: design_variants/comparison.png")

    # Create individual previews
    print("\nCreating individual previews...")
    previews = create_individual_previews()
    for name, img in previews.items():
        filename = name.lower().replace(" ", "_") + ".png"
        path = os.path.join("design_variants", filename)
        img.save(path)
        print(f"Saved: {path}")

    # Generate Python code snippets for each variant
    print("\nGenerating code snippets...")
    with open("design_variants/color_codes.py", "w", encoding="utf-8") as f:
        f.write("# Color schemes for Voice Transcriber\n\n")
        f.write("# Copy the desired variant into main_window.py\n\n")

        for name, variant in VARIANTS.items():
            var_name = name.lower().replace(" ", "_")
            f.write(f"# {name}: {variant['description']}\n")
            f.write(f"{var_name.upper()}_GRADIENT = {variant['colors']}\n")
            f.write(f"{var_name.upper()}_ACCENT = '{variant['border']}'\n\n")

    print("Saved: design_variants/color_codes.py")
    print("\nDone! Check design_variants folder.")
