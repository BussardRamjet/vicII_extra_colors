"""Create a test image with gradients and color samples for palette testing"""
from PIL import Image, ImageDraw
import colorsys

width, height = 256, 192

img = Image.new('RGB', (width, height), (128, 128, 128))
draw = ImageDraw.Draw(img)

# Top section: RGB gradients
for x in range(width):
    # Red gradient
    draw.line([(x, 0), (x, 15)], fill=(x, 0, 0))
    # Green gradient
    draw.line([(x, 16), (x, 31)], fill=(0, x, 0))
    # Blue gradient
    draw.line([(x, 32), (x, 47)], fill=(0, 0, x))
    # Grayscale gradient
    draw.line([(x, 48), (x, 63)], fill=(x, x, x))

# Middle section: Hue wheel
for x in range(width):
    for y in range(64, 128):
        hue = x / width
        sat = 1.0 - (y - 64) / 64 * 0.7  # Saturation decreases downward
        lum = 0.5
        r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
        img.putpixel((x, y), (int(r * 255), int(g * 255), int(b * 255)))

# Bottom section: Skin tones and nature colors
# Skin tones
skin_colors = [
    (255, 224, 196), (255, 205, 170), (234, 192, 160), (210, 160, 130),
    (180, 128, 100), (150, 100, 75), (120, 80, 55), (90, 60, 40)
]
for i, color in enumerate(skin_colors):
    x0 = i * 32
    draw.rectangle([x0, 128, x0 + 31, 143], fill=color)

# Nature colors
nature_colors = [
    (34, 139, 34),   # Forest green
    (85, 107, 47),   # Dark olive
    (107, 142, 35),  # Olive drab
    (154, 205, 50),  # Yellow green
    (139, 69, 19),   # Saddle brown
    (160, 82, 45),   # Sienna
    (210, 180, 140), # Tan
    (70, 130, 180),  # Steel blue
]
for i, color in enumerate(nature_colors):
    x0 = i * 32
    draw.rectangle([x0, 144, x0 + 31, 159], fill=color)

# Vibrant colors
vibrant_colors = [
    (255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
    (0, 255, 255), (0, 0, 255), (127, 0, 255), (255, 0, 127)
]
for i, color in enumerate(vibrant_colors):
    x0 = i * 32
    draw.rectangle([x0, 160, x0 + 31, 175], fill=color)

# Pastels
pastel_colors = [
    (255, 182, 193), (255, 218, 185), (255, 255, 186), (186, 255, 201),
    (186, 225, 255), (186, 186, 255), (221, 186, 255), (255, 186, 243)
]
for i, color in enumerate(pastel_colors):
    x0 = i * 32
    draw.rectangle([x0, 176, x0 + 31, 191], fill=color)

img.save('test_image.png')
print("Created test_image.png")
