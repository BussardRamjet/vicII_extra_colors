"""
VIC-II Extended Palette Image Converter
Converts images to use different palettes with perceptual color matching (OKLab).
"""

import sys
import math
from typing import List, Tuple, Dict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Import palette generators
from palette_generator import (
    Color,
    create_palette_v0_c64_original,
    create_palette_v1_rgb332,
    create_palette_v2_hybrid_666,
    create_palette_v3_hsl,
    create_palette_v4_perceptual,
    create_palette_v5_artistic,
    create_palette_v6_refined_artistic,
    create_palette_v8_ultimate,
)


# =============================================================================
# OKLab Color Space (Perceptually Uniform)
# =============================================================================

def srgb_to_linear(c: float) -> float:
    """Convert sRGB component to linear RGB"""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """Convert linear RGB component to sRGB"""
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1/2.4)) - 0.055


def rgb_to_oklab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert 8-bit RGB to OKLab color space"""
    # Normalize to 0-1 and convert to linear
    r_lin = srgb_to_linear(r / 255.0)
    g_lin = srgb_to_linear(g / 255.0)
    b_lin = srgb_to_linear(b / 255.0)

    # RGB to LMS
    l = 0.4122214708 * r_lin + 0.5363325363 * g_lin + 0.0514459929 * b_lin
    m = 0.2119034982 * r_lin + 0.6806995451 * g_lin + 0.1073969566 * b_lin
    s = 0.0883024619 * r_lin + 0.2817188376 * g_lin + 0.6299787005 * b_lin

    # Cube root (handle negative values)
    l = l ** (1/3) if l >= 0 else -((-l) ** (1/3))
    m = m ** (1/3) if m >= 0 else -((-m) ** (1/3))
    s = s ** (1/3) if s >= 0 else -((-s) ** (1/3))

    # LMS to OKLab
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b_out = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s

    return (L, a, b_out)


def oklab_distance(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """Calculate perceptual distance between two OKLab colors"""
    dL = lab1[0] - lab2[0]
    da = lab1[1] - lab2[1]
    db = lab1[2] - lab2[2]
    return math.sqrt(dL * dL + da * da + db * db)


# =============================================================================
# Palette Matching
# =============================================================================

class PaletteMatcher:
    """Efficiently matches colors to a palette using OKLab distance"""

    def __init__(self, palette: List[Color]):
        self.palette = palette
        # Pre-compute OKLab values for all palette colors
        self.palette_oklab = [rgb_to_oklab(c.r, c.g, c.b) for c in palette]
        # Cache for already-matched colors
        self.cache: Dict[Tuple[int, int, int], int] = {}

    def find_nearest(self, r: int, g: int, b: int) -> int:
        """Find the index of the nearest palette color using OKLab distance"""
        key = (r, g, b)
        if key in self.cache:
            return self.cache[key]

        source_lab = rgb_to_oklab(r, g, b)

        best_idx = 0
        best_dist = float('inf')

        for idx, pal_lab in enumerate(self.palette_oklab):
            dist = oklab_distance(source_lab, pal_lab)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
                # Early exit if exact match
                if dist == 0:
                    break

        self.cache[key] = best_idx
        return best_idx

    def get_color(self, idx: int) -> Tuple[int, int, int]:
        """Get RGB tuple for palette index"""
        c = self.palette[idx]
        return (c.r, c.g, c.b)


def convert_image(source: Image.Image, matcher: PaletteMatcher) -> Image.Image:
    """Convert an image to use the palette"""
    # Convert to RGB if necessary
    if source.mode != 'RGB':
        source = source.convert('RGB')

    width, height = source.size
    result = Image.new('RGB', (width, height))

    source_pixels = source.load()
    result_pixels = result.load()

    for y in range(height):
        for x in range(width):
            r, g, b = source_pixels[x, y]
            idx = matcher.find_nearest(r, g, b)
            result_pixels[x, y] = matcher.get_color(idx)

    return result


def create_comparison_image(source: Image.Image, converted_images: List[Tuple[str, Image.Image]],
                            max_width: int = 1920) -> Image.Image:
    """Create a side-by-side comparison image"""
    n = len(converted_images) + 1  # +1 for original

    # Calculate layout
    # Try to fit images in a reasonable grid
    src_w, src_h = source.size

    # Scale down if images are too large
    scale = 1.0
    if src_w * n > max_width:
        # Use 2 rows
        cols = (n + 1) // 2
        if src_w * cols > max_width:
            scale = max_width / (src_w * cols)
    else:
        cols = n

    rows = (n + cols - 1) // cols

    # Scaled dimensions
    img_w = int(src_w * scale)
    img_h = int(src_h * scale)

    # Add space for labels
    label_height = 25

    # Create output image
    out_w = cols * img_w
    out_h = rows * (img_h + label_height)

    output = Image.new('RGB', (out_w, out_h), (30, 30, 30))

    # Try to load a font
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(output)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()

    # Place images
    all_images = [("Original", source)] + list(converted_images)

    for i, (name, img) in enumerate(all_images):
        row = i // cols
        col = i % cols

        x = col * img_w
        y = row * (img_h + label_height)

        # Resize if needed
        if scale != 1.0:
            img = img.resize((img_w, img_h), Image.Resampling.NEAREST)

        # Paste image
        output.paste(img, (x, y + label_height))

        # Draw label
        draw.text((x + 5, y + 5), name, fill=(255, 255, 255), font=font)

    return output


def convert_with_all_palettes(source_path: str, output_dir: str = None):
    """Convert an image using all available palettes"""

    # Load source image
    print(f"Loading: {source_path}")
    source = Image.open(source_path)
    print(f"  Size: {source.size[0]}x{source.size[1]}")
    print(f"  Mode: {source.mode}")

    # Determine output directory
    source_path = Path(source_path)
    if output_dir is None:
        output_dir = source_path.parent
    output_dir = Path(output_dir)

    # Define palettes to use
    palettes = [
        ("V0_C64", create_palette_v0_c64_original()),
        ("V1_RGB332", create_palette_v1_rgb332()),
        ("V2_Hybrid", create_palette_v2_hybrid_666()),
        ("V3_HSL", create_palette_v3_hsl()),
        ("V4_OKLab", create_palette_v4_perceptual()),
        ("V5_Artistic", create_palette_v5_artistic()),
        ("V6_Refined", create_palette_v6_refined_artistic()),
        ("V8_Ultimate", create_palette_v8_ultimate()),
    ]

    converted_images = []

    for name, palette in palettes:
        print(f"Converting with {name}...")
        matcher = PaletteMatcher(palette)
        converted = convert_image(source, matcher)
        converted_images.append((name, converted))

        # Save individual converted image
        out_path = output_dir / f"{source_path.stem}_{name}.png"
        converted.save(out_path)
        print(f"  Saved: {out_path}")

    # Create comparison image
    print("Creating comparison image...")
    comparison = create_comparison_image(source, converted_images)
    comparison_path = output_dir / f"{source_path.stem}_comparison.png"
    comparison.save(comparison_path)
    print(f"Saved comparison: {comparison_path}")

    print("\nDone!")
    return comparison_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python image_converter.py <source_image> [output_dir]")
        print("\nConverts an image to all VIC-II extended palettes using")
        print("perceptual color matching (OKLab color space).")
        print("\nOutputs:")
        print("  - Individual converted images for each palette")
        print("  - A comparison image showing all versions side by side")
        sys.exit(1)

    source_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    convert_with_all_palettes(source_path, output_dir)


if __name__ == "__main__":
    main()
