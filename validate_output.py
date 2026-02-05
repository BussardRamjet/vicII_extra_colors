"""
VIC-II Output Validator
Validates that converted images follow the correct constraints.
"""

import sys
from typing import List, Tuple, Set, Dict
from pathlib import Path
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Standard C64 VIC-II 16-color palette (approximate RGB values)
C64_PALETTE = [
    (0, 0, 0),        # 0: Black
    (255, 255, 255),  # 1: White
    (136, 57, 50),    # 2: Red
    (103, 182, 189),  # 3: Cyan
    (139, 63, 150),   # 4: Purple
    (85, 160, 73),    # 5: Green
    (64, 49, 141),    # 6: Blue
    (191, 206, 114),  # 7: Yellow
    (139, 84, 41),    # 8: Orange
    (87, 66, 0),      # 9: Brown
    (184, 105, 98),   # 10: Light Red
    (80, 80, 80),     # 11: Dark Grey
    (120, 120, 120),  # 12: Medium Grey
    (148, 224, 137),  # 13: Light Green
    (120, 105, 196),  # 14: Light Blue
    (159, 159, 159),  # 15: Light Grey
]


class ValidationResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.errors = []
        self.warnings = []
        self.info = []

    def error(self, msg: str):
        self.passed = False
        self.errors.append(msg)

    def warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def print_report(self):
        status = "PASS" if self.passed else "FAIL"
        print(f"\n{'='*60}")
        print(f"{self.name}: {status}")
        print('='*60)

        for msg in self.info:
            print(f"  INFO: {msg}")

        for msg in self.warnings:
            print(f"  WARNING: {msg}")

        for msg in self.errors:
            print(f"  ERROR: {msg}")

        if self.passed and not self.warnings:
            print("  All checks passed.")


def color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Simple RGB distance"""
    return ((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2) ** 0.5


def is_c64_color(rgb: Tuple[int, int, int], tolerance: int = 5) -> bool:
    """Check if a color matches any C64 palette color within tolerance"""
    for c64_color in C64_PALETTE:
        if color_distance(rgb, c64_color) <= tolerance:
            return True
    return False


def find_nearest_c64_color(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Find the nearest C64 color"""
    best = C64_PALETTE[0]
    best_dist = float('inf')
    for c64_color in C64_PALETTE:
        dist = color_distance(rgb, c64_color)
        if dist < best_dist:
            best_dist = dist
            best = c64_color
    return best


def check_wide_pixels(img: Image.Image) -> Tuple[bool, float]:
    """
    Check if image has double-wide pixels.
    Returns (is_wide_pixel, percentage of paired pixels)
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    pixels = img.load()

    paired_count = 0
    total_pairs = 0

    for y in range(height):
        for x in range(0, width - 1, 2):
            total_pairs += 1
            p1 = pixels[x, y]
            p2 = pixels[x + 1, y]
            if p1 == p2:
                paired_count += 1

    percentage = (paired_count / total_pairs * 100) if total_pairs > 0 else 0
    # Consider it wide-pixel if >95% of pairs match
    is_wide = percentage > 95

    return is_wide, percentage


def get_unique_colors(img: Image.Image) -> Set[Tuple[int, int, int]]:
    """Get all unique colors in an image"""
    if img.mode != 'RGB':
        img = img.convert('RGB')

    colors = set()
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            colors.add(pixels[x, y])

    return colors


def get_scanline_colors(img: Image.Image, y: int) -> List[Tuple[int, int, int]]:
    """Get all colors used in a scanline"""
    pixels = img.load()
    width = img.size[0]
    return [pixels[x, y] for x in range(width)]


def validate_original(img: Image.Image, expected_width: int = None,
                      expected_height: int = None) -> ValidationResult:
    """
    Validate the original image:
    - Should NOT have wide pixels
    - Should use full color palette (more than 16 colors)
    - Should match expected resolution
    """
    result = ValidationResult("Original Image")

    if img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    result.add_info(f"Resolution: {width}x{height}")

    # Check resolution
    if expected_width and width != expected_width:
        result.error(f"Width mismatch: expected {expected_width}, got {width}")
    if expected_height and height != expected_height:
        result.error(f"Height mismatch: expected {expected_height}, got {height}")

    # Check for wide pixels (should NOT have them)
    is_wide, pair_percentage = check_wide_pixels(img)
    result.add_info(f"Pixel pairing: {pair_percentage:.1f}%")

    if is_wide:
        result.error(f"Original has wide pixels ({pair_percentage:.1f}% paired) - should have full resolution")

    # Check color count
    unique_colors = get_unique_colors(img)
    result.add_info(f"Unique colors: {len(unique_colors)}")

    if len(unique_colors) <= 16:
        result.warning(f"Only {len(unique_colors)} unique colors - expected more for full palette")

    return result


def validate_c64_multicolor(img: Image.Image, cell_width: int = 4) -> ValidationResult:
    """
    Validate C64 multicolor image:
    - Must have wide pixels (double-wide)
    - Must use only C64 16-color palette
    - Per scanline: 1 background color
    - Per 4-pixel cell: max 3 additional colors (4 total including background)
    """
    result = ValidationResult("C64 Multicolor")

    if img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    pixels = img.load()
    result.add_info(f"Resolution: {width}x{height}")

    # Check for wide pixels
    is_wide, pair_percentage = check_wide_pixels(img)
    result.add_info(f"Pixel pairing: {pair_percentage:.1f}%")

    if not is_wide:
        result.error(f"Not wide pixels ({pair_percentage:.1f}% paired) - should be >95%")

    # Check all colors are C64 palette
    unique_colors = get_unique_colors(img)
    result.add_info(f"Unique colors: {len(unique_colors)}")

    non_c64_colors = []
    for color in unique_colors:
        if not is_c64_color(color):
            non_c64_colors.append(color)

    if non_c64_colors:
        result.error(f"Found {len(non_c64_colors)} non-C64 colors")
        for color in non_c64_colors[:5]:
            nearest = find_nearest_c64_color(color)
            result.add_info(f"  Non-C64 color: RGB{color} (nearest C64: RGB{nearest})")
        if len(non_c64_colors) > 5:
            result.add_info(f"  ... and {len(non_c64_colors) - 5} more")

    # Check multicolor constraints per scanline
    scanline_violations = 0
    cell_violations = 0

    for y in range(height):
        scanline_colors = set()

        # Process each cell (4 double-wide pixels = 8 actual pixels)
        for cell_start in range(0, width, cell_width * 2):
            cell_end = min(cell_start + cell_width * 2, width)

            cell_colors = set()
            for x in range(cell_start, cell_end, 2):  # Step by 2 for double-wide
                cell_colors.add(pixels[x, y])

            scanline_colors.update(cell_colors)

            if len(cell_colors) > 4:
                cell_violations += 1

        # Check if we can identify a background (most common color)
        # For now, just check total colors per scanline isn't too high
        if len(scanline_colors) > 16:  # Reasonable upper bound
            scanline_violations += 1

    if cell_violations > 0:
        result.error(f"{cell_violations} cells have more than 4 colors")

    if scanline_violations > 0:
        result.warning(f"{scanline_violations} scanlines have unusually many colors")

    return result


def validate_extended_multicolor(img: Image.Image, cell_width: int = 4) -> ValidationResult:
    """
    Validate Extended palette multicolor image:
    - Must have wide pixels (double-wide)
    - Can use any colors (256-color palette)
    - Per scanline: 1 background color (can change per scanline)
    - Per 4-pixel cell: max 3 additional colors (4 total including background)
    """
    result = ValidationResult("Extended Multicolor")

    if img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    pixels = img.load()
    result.add_info(f"Resolution: {width}x{height}")

    # Check for wide pixels
    is_wide, pair_percentage = check_wide_pixels(img)
    result.add_info(f"Pixel pairing: {pair_percentage:.1f}%")

    if not is_wide:
        result.error(f"Not wide pixels ({pair_percentage:.1f}% paired) - should be >95%")

    # Check color count (should use more than C64's 16)
    unique_colors = get_unique_colors(img)
    result.add_info(f"Unique colors: {len(unique_colors)}")

    if len(unique_colors) <= 16:
        result.warning(f"Only {len(unique_colors)} colors - extended palette should typically use more")

    # Check multicolor constraints per scanline
    cell_violations = 0
    cells_checked = 0

    for y in range(height):
        # Find the most common color in scanline (likely background)
        color_counts = defaultdict(int)
        for x in range(0, width, 2):
            color_counts[pixels[x, y]] += 1

        bg_color = max(color_counts.items(), key=lambda x: x[1])[0]

        # Process each cell
        for cell_start in range(0, width, cell_width * 2):
            cell_end = min(cell_start + cell_width * 2, width)
            cells_checked += 1

            cell_colors = set()
            for x in range(cell_start, cell_end, 2):
                cell_colors.add(pixels[x, y])

            # Cell should have at most 4 colors (1 bg + 3 cell colors)
            if len(cell_colors) > 4:
                cell_violations += 1

    result.add_info(f"Cells checked: {cells_checked}")

    if cell_violations > 0:
        result.error(f"{cell_violations} cells have more than 4 colors (violates multicolor constraint)")

    return result


def validate_all(original_path: str, c64_path: str, extended_path: str):
    """Validate all three images"""
    print("VIC-II Output Validator")
    print("="*60)

    # Load images
    print(f"\nLoading images...")

    try:
        original = Image.open(original_path)
        print(f"  Original: {original_path}")
    except Exception as e:
        print(f"  ERROR loading original: {e}")
        return

    try:
        c64 = Image.open(c64_path)
        print(f"  C64: {c64_path}")
    except Exception as e:
        print(f"  ERROR loading C64: {e}")
        return

    try:
        extended = Image.open(extended_path)
        print(f"  Extended: {extended_path}")
    except Exception as e:
        print(f"  ERROR loading extended: {e}")
        return

    # Validate each
    orig_result = validate_original(original)
    c64_result = validate_c64_multicolor(c64)
    ext_result = validate_extended_multicolor(extended)

    # Print reports
    orig_result.print_report()
    c64_result.print_report()
    ext_result.print_report()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    all_passed = orig_result.passed and c64_result.passed and ext_result.passed
    print(f"  Original:  {'PASS' if orig_result.passed else 'FAIL'}")
    print(f"  C64:       {'PASS' if c64_result.passed else 'FAIL'}")
    print(f"  Extended:  {'PASS' if ext_result.passed else 'FAIL'}")
    print(f"\n  Overall:   {'ALL PASS' if all_passed else 'SOME FAILED'}")

    return all_passed


def main():
    if len(sys.argv) < 4:
        print("Usage: python validate_output.py <original> <c64_mc> <extended_mc>")
        print("\nValidates that output images follow VIC-II constraints:")
        print("  - Original: full resolution, full palette, no wide pixels")
        print("  - C64: wide pixels, C64 16-color palette, multicolor limits")
        print("  - Extended: wide pixels, 256-color palette, multicolor limits")
        print("\nExample:")
        print("  python validate_output.py Unreal.png Unreal_C64_mc.png Unreal_Extended_mc.png")
        sys.exit(1)

    original_path = sys.argv[1]
    c64_path = sys.argv[2]
    extended_path = sys.argv[3]

    success = validate_all(original_path, c64_path, extended_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
