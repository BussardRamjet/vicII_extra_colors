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


def select_best_colors_for_scanline(source: Image.Image, y: int,
                                     palette: List[Color], max_colors: int) -> List[int]:
    """
    Select the best N palette colors for a single scanline.
    Uses weighted color frequency and error minimization.
    """
    width = source.size[0]
    pixels = source.load()

    # Collect all unique colors in this scanline with their counts
    color_counts = {}
    for x in range(width):
        rgb = pixels[x, y]
        color_counts[rgb] = color_counts.get(rgb, 0) + 1

    # For each unique source color, find best palette match and track error
    palette_usage = {}  # palette_idx -> (total_weighted_error, count)
    color_to_palette = {}  # source_rgb -> palette_idx

    for rgb, count in color_counts.items():
        r, g, b = rgb
        source_lab = rgb_to_oklab(r, g, b)

        # Find best palette color
        best_idx = 0
        best_dist = float('inf')

        for idx, pal_color in enumerate(palette):
            pal_lab = rgb_to_oklab(pal_color.r, pal_color.g, pal_color.b)
            dist = oklab_distance(source_lab, pal_lab)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        color_to_palette[rgb] = best_idx

        if best_idx not in palette_usage:
            palette_usage[best_idx] = {'count': 0, 'weighted_importance': 0}
        palette_usage[best_idx]['count'] += count
        # Weight by count and inverse of error (colors with low error and high count are important)
        palette_usage[best_idx]['weighted_importance'] += count * (1.0 / (best_dist + 0.001))

    # If we already have <= max_colors, we're done
    if len(palette_usage) <= max_colors:
        return list(palette_usage.keys())

    # Otherwise, select the most important colors
    sorted_colors = sorted(
        palette_usage.items(),
        key=lambda x: x[1]['weighted_importance'],
        reverse=True
    )

    return [idx for idx, _ in sorted_colors[:max_colors]]


def convert_image_scanline_limited(source: Image.Image, palette: List[Color],
                                    colors_per_scanline: int = 16) -> Image.Image:
    """
    Convert an image with a limit on colors per scanline (VIC-II style).

    For each scanline:
    1. Analyze which palette colors best represent that line
    2. Select the best N colors for that scanline
    3. Map each pixel to only those N colors
    """
    if source.mode != 'RGB':
        source = source.convert('RGB')

    width, height = source.size
    result = Image.new('RGB', (width, height))

    source_pixels = source.load()
    result_pixels = result.load()

    # Pre-compute OKLab values for palette
    palette_oklab = [rgb_to_oklab(c.r, c.g, c.b) for c in palette]

    for y in range(height):
        # Select best colors for this scanline
        scanline_palette_indices = select_best_colors_for_scanline(
            source, y, palette, colors_per_scanline
        )

        # Build a mini-matcher for just these colors
        scanline_palette = [palette[i] for i in scanline_palette_indices]
        scanline_oklab = [palette_oklab[i] for i in scanline_palette_indices]

        # Convert each pixel in this scanline
        for x in range(width):
            r, g, b = source_pixels[x, y]
            source_lab = rgb_to_oklab(r, g, b)

            # Find nearest from scanline palette
            best_local_idx = 0
            best_dist = float('inf')

            for local_idx, pal_lab in enumerate(scanline_oklab):
                dist = oklab_distance(source_lab, pal_lab)
                if dist < best_dist:
                    best_dist = dist
                    best_local_idx = local_idx

            # Get the color
            pal_color = scanline_palette[best_local_idx]
            result_pixels[x, y] = (pal_color.r, pal_color.g, pal_color.b)

    return result


def select_background_for_scanline(source: Image.Image, y: int,
                                    palette: List[Color],
                                    palette_oklab: List[Tuple[float, float, float]]) -> int:
    """
    Select the best background color for a scanline.
    The background should be a color that's useful across many 4-pixel cells.
    """
    width = source.size[0]
    pixels = source.load()

    # Count how often each palette color is the best match across the scanline
    palette_votes = {}

    for x in range(width):
        r, g, b = pixels[x, y]
        source_lab = rgb_to_oklab(r, g, b)

        # Find best palette match
        best_idx = 0
        best_dist = float('inf')
        for idx, pal_lab in enumerate(palette_oklab):
            dist = oklab_distance(source_lab, pal_lab)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        # Vote for this color, weighted by how good the match is
        if best_idx not in palette_votes:
            palette_votes[best_idx] = 0
        palette_votes[best_idx] += 1.0 / (best_dist + 0.001)

    # Return the color with most weighted votes
    if not palette_votes:
        return 0
    return max(palette_votes.items(), key=lambda x: x[1])[0]


def select_cell_colors(pixels_rgb: List[Tuple[int, int, int]],
                       background_idx: int,
                       palette: List[Color],
                       palette_oklab: List[Tuple[float, float, float]],
                       num_colors: int = 3) -> List[int]:
    """
    Select the best N additional colors for a cell, given a fixed background.
    Returns palette indices for the cell colors (not including background).
    """
    if not pixels_rgb:
        return []

    # Find which palette colors (other than background) best serve these pixels
    color_importance = {}  # palette_idx -> importance score

    bg_lab = palette_oklab[background_idx]

    for r, g, b in pixels_rgb:
        source_lab = rgb_to_oklab(r, g, b)

        # How well does background cover this pixel?
        bg_dist = oklab_distance(source_lab, bg_lab)

        # Find the best non-background color
        best_idx = None
        best_dist = float('inf')

        for idx, pal_lab in enumerate(palette_oklab):
            if idx == background_idx:
                continue
            dist = oklab_distance(source_lab, pal_lab)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        # Only vote for this color if it's better than background
        if best_idx is not None and best_dist < bg_dist:
            if best_idx not in color_importance:
                color_importance[best_idx] = 0
            # Weight by improvement over background
            improvement = bg_dist - best_dist
            color_importance[best_idx] += improvement

    # Return top N colors by importance
    sorted_colors = sorted(color_importance.items(), key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in sorted_colors[:num_colors]]


def convert_image_multicolor(source: Image.Image, palette: List[Color],
                              cell_width: int = 4,
                              double_pixels: bool = True) -> Image.Image:
    """
    Convert an image using VIC-II multicolor mode constraints.

    Constraints:
    - Double-wide pixels (160x200 effective for 320x200 input)
    - Per scanline: 1 background color (changeable via raster interrupt)
    - Per cell (4 pixels wide): 3 additional colors
    - Each pixel uses one of 4 colors (background + 3 cell colors)

    Args:
        source: Source image
        palette: 256-color palette
        cell_width: Width of each cell in source pixels (4 = standard multicolor)
        double_pixels: If True, output same size as input with doubled pixels (default)
                       If False, output at half horizontal resolution

    Returns:
        Converted image (same size as input if double_pixels=True)
    """
    if source.mode != 'RGB':
        source = source.convert('RGB')

    src_width, height = source.size
    # Output width depends on double_pixels setting
    out_width = src_width if double_pixels else src_width // 2

    result = Image.new('RGB', (out_width, height))

    source_pixels = source.load()
    result_pixels = result.load()

    # Pre-compute OKLab values for palette
    palette_oklab = [rgb_to_oklab(c.r, c.g, c.b) for c in palette]

    # Process each scanline
    for y in range(height):
        # Select background color for this scanline
        bg_idx = select_background_for_scanline(source, y, palette, palette_oklab)
        bg_lab = palette_oklab[bg_idx]
        bg_color = palette[bg_idx]

        # Process each cell (4 source pixels = 2 multicolor pixels per cell)
        for cell_start in range(0, src_width, cell_width):
            cell_end = min(cell_start + cell_width, src_width)

            # Collect source pixels for this cell (sample every 2 pixels for double-wide)
            cell_pixels = []
            for x in range(cell_start, cell_end, 2):
                cell_pixels.append(source_pixels[x, y])

            # Select 3 additional colors for this cell
            cell_color_indices = select_cell_colors(
                cell_pixels, bg_idx, palette, palette_oklab, num_colors=3
            )

            # Build the 4-color palette for this cell
            cell_palette_indices = [bg_idx] + cell_color_indices
            cell_palette_oklab = [palette_oklab[i] for i in cell_palette_indices]

            # Convert each double-wide pixel in this cell
            for i, x in enumerate(range(cell_start, cell_end, 2)):
                r, g, b = source_pixels[x, y]
                source_lab = rgb_to_oklab(r, g, b)

                # Find nearest from cell's 4-color palette
                best_local_idx = 0
                best_dist = float('inf')

                for local_idx, pal_lab in enumerate(cell_palette_oklab):
                    dist = oklab_distance(source_lab, pal_lab)
                    if dist < best_dist:
                        best_dist = dist
                        best_local_idx = local_idx

                # Get the color
                pal_idx = cell_palette_indices[best_local_idx]
                pal_color = palette[pal_idx]
                color_rgb = (pal_color.r, pal_color.g, pal_color.b)

                if double_pixels:
                    # Write two pixels (double-wide)
                    result_pixels[x, y] = color_rgb
                    if x + 1 < out_width:
                        result_pixels[x + 1, y] = color_rgb
                else:
                    # Write single pixel at half resolution
                    result_pixels[x // 2, y] = color_rgb

    return result


def create_comparison_image(source: Image.Image, converted_images: List[Tuple[str, Image.Image]],
                            max_width: int = 1920, multicolor: bool = False) -> Image.Image:
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
    all_images = [("Original", source, True)] + [(name, img, False) for name, img in converted_images]

    for i, (name, img, is_original) in enumerate(all_images):
        row = i // cols
        col = i % cols

        x = col * img_w
        y = row * (img_h + label_height)

        # Resize if needed
        if scale != 1.0:
            if multicolor and is_original:
                # Original gets smooth scaling to show full detail
                img = img.resize((img_w, img_h), Image.Resampling.LANCZOS)
            else:
                # Converted images (or non-multicolor) use NEAREST to preserve pixels
                img = img.resize((img_w, img_h), Image.Resampling.NEAREST)

        # Paste image
        output.paste(img, (x, y + label_height))

        # Draw label
        draw.text((x + 5, y + 5), name, fill=(255, 255, 255), font=font)

    return output


def convert_with_all_palettes(source_path: str, output_dir: str = None,
                               scanline_limit: int = None,
                               multicolor: bool = False):
    """
    Convert an image using all available palettes.

    Args:
        source_path: Path to source image
        output_dir: Output directory (default: same as source)
        scanline_limit: Max colors per scanline (VIC-II mode), None for unlimited
        multicolor: Use VIC-II multicolor mode (double-wide pixels, 4 colors per cell)
    """

    # Load source image
    print(f"Loading: {source_path}")
    source = Image.open(source_path)
    print(f"  Size: {source.size[0]}x{source.size[1]}")
    print(f"  Mode: {source.mode}")
    if multicolor:
        print(f"  Multicolor mode: 1 bg/scanline + 3 colors per 4-pixel cell, double-wide pixels")
    elif scanline_limit:
        print(f"  Scanline limit: {scanline_limit} colors per line")

    # Determine output directory
    source_path = Path(source_path)
    if output_dir is None:
        output_dir = source_path.parent
    output_dir = Path(output_dir)

    # Define palettes to use
    if multicolor:
        # Multicolor mode: just C64 original vs extended palette
        palettes = [
            ("C64", create_palette_v0_c64_original()),
            ("Extended", create_palette_v8_ultimate()),
        ]
    else:
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

        if multicolor:
            converted = convert_image_multicolor(source, palette)
            suffix = f"_{name}_mc"
        elif scanline_limit:
            converted = convert_image_scanline_limited(source, palette, scanline_limit)
            suffix = f"_{name}_sl{scanline_limit}"
        else:
            matcher = PaletteMatcher(palette)
            converted = convert_image(source, matcher)
            suffix = f"_{name}"

        converted_images.append((name, converted))

        # Save individual converted image
        out_path = output_dir / f"{source_path.stem}{suffix}.png"
        converted.save(out_path)
        print(f"  Saved: {out_path}")

    # Create comparison image
    print("Creating comparison image...")

    if multicolor:
        mode_suffix = "_mc"
    elif scanline_limit:
        mode_suffix = f"_sl{scanline_limit}"
    else:
        mode_suffix = ""

    comparison = create_comparison_image(source, converted_images, multicolor=multicolor)
    comparison_path = output_dir / f"{source_path.stem}_comparison{mode_suffix}.png"
    comparison.save(comparison_path)
    print(f"Saved comparison: {comparison_path}")

    print("\nDone!")
    return comparison_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python image_converter.py <source_image> [output_dir] [options]")
        print("\nConverts an image to all VIC-II extended palettes using")
        print("perceptual color matching (OKLab color space).")
        print("\nOptions:")
        print("  --scanline N    Limit to N colors per scanline (VIC-II hardware limit)")
        print("                  Use --scanline 16 for authentic VIC-II constraints")
        print("  --multicolor    VIC-II multicolor bitmap mode:")
        print("                  - Double-wide pixels (half horizontal resolution)")
        print("                  - 1 background color per scanline (raster interrupt)")
        print("                  - 3 additional colors per 4-pixel cell")
        print("                  - Each pixel uses one of 4 colors (bg + 3 cell)")
        print("\nOutputs:")
        print("  - Individual converted images for each palette")
        print("  - A comparison image showing all versions side by side")
        sys.exit(1)

    # Parse arguments
    source_path = sys.argv[1]
    output_dir = None
    scanline_limit = None
    multicolor = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--scanline' and i + 1 < len(sys.argv):
            scanline_limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--multicolor':
            multicolor = True
            i += 1
        else:
            output_dir = sys.argv[i]
            i += 1

    convert_with_all_palettes(source_path, output_dir, scanline_limit, multicolor)


if __name__ == "__main__":
    main()
