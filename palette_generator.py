"""
VIC-II Extended Palette Generator
Generates various 256-color palette options for an extended VIC-II chip.
"""

import colorsys
import math
from dataclasses import dataclass
from typing import List, Tuple

# PIL is optional - for visualization
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@dataclass
class Color:
    r: int
    g: int
    b: int

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def luminance(self) -> float:
        """Perceptual luminance using Rec. 709 coefficients"""
        return 0.2126 * self.r + 0.7152 * self.g + 0.0722 * self.b


# Original VIC-II palette (from various references, using common values)
VIC_II_COLORS = [
    Color(0x00, 0x00, 0x00),  # 0  Black
    Color(0xff, 0xff, 0xff),  # 1  White
    Color(0x88, 0x39, 0x32),  # 2  Red
    Color(0x67, 0xb6, 0xbd),  # 3  Cyan
    Color(0x8b, 0x3f, 0x96),  # 4  Purple
    Color(0x55, 0xa0, 0x49),  # 5  Green
    Color(0x40, 0x31, 0x8d),  # 6  Blue
    Color(0xbf, 0xce, 0x72),  # 7  Yellow
    Color(0x8b, 0x54, 0x29),  # 8  Orange
    Color(0x57, 0x42, 0x00),  # 9  Brown
    Color(0xb8, 0x69, 0x62),  # 10 Light Red
    Color(0x50, 0x50, 0x50),  # 11 Dark Grey
    Color(0x78, 0x78, 0x78),  # 12 Medium Grey
    Color(0x94, 0xe0, 0x89),  # 13 Light Green
    Color(0x78, 0x69, 0xc4),  # 14 Light Blue
    Color(0x9f, 0x9f, 0x9f),  # 15 Light Grey
]


def generate_grayscale(count: int) -> List[Color]:
    """Generate evenly spaced grayscale values"""
    colors = []
    for i in range(count):
        v = int(255 * i / (count - 1))
        colors.append(Color(v, v, v))
    return colors


def generate_rgb_332() -> List[Color]:
    """
    Generate RGB 3-3-2 palette (256 colors)
    3 bits red (8 levels), 3 bits green (8 levels), 2 bits blue (4 levels)
    """
    colors = []
    for r in range(8):
        for g in range(8):
            for b in range(4):
                # Scale to 0-255
                rv = int(r * 255 / 7)
                gv = int(g * 255 / 7)
                bv = int(b * 255 / 3)
                colors.append(Color(rv, gv, bv))
    return colors


def generate_rgb_cube(levels: int) -> List[Color]:
    """Generate an RGB cube with specified levels per channel"""
    colors = []
    for r in range(levels):
        for g in range(levels):
            for b in range(levels):
                rv = int(r * 255 / (levels - 1)) if levels > 1 else 0
                gv = int(g * 255 / (levels - 1)) if levels > 1 else 0
                bv = int(b * 255 / (levels - 1)) if levels > 1 else 0
                colors.append(Color(rv, gv, bv))
    return colors


def generate_hsl_palette(hues: int, sats: int, lums: int) -> List[Color]:
    """Generate colors based on HSL color space"""
    colors = []
    for h in range(hues):
        for s in range(sats):
            for l in range(lums):
                hue = h / hues
                sat = (s + 1) / sats  # Avoid 0 saturation (that's grayscale)
                lum = 0.15 + 0.7 * (l / (lums - 1)) if lums > 1 else 0.5  # Avoid pure black/white

                r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
                colors.append(Color(int(r * 255), int(g * 255), int(b * 255)))
    return colors


def generate_perceptual_hsl(hues: int, variations: int) -> List[Color]:
    """
    Generate perceptually-weighted HSL palette.
    More luminosity variations, fewer saturation variations.
    """
    colors = []
    saturations = [0.4, 0.7, 1.0]  # 3 saturation levels
    luminosities = [0.25, 0.40, 0.55, 0.70, 0.85]  # 5 luminosity levels

    for h in range(hues):
        hue = h / hues
        for sat in saturations:
            for lum in luminosities:
                r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
                colors.append(Color(int(r * 255), int(g * 255), int(b * 255)))
    return colors[:variations]  # Trim to requested size


def rgb_to_oklab(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Convert linear RGB to OKLab (perceptually uniform color space)"""
    # Convert to linear RGB
    def srgb_to_linear(c):
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r, g, b = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)

    # RGB to LMS
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    # Cube root
    l, m, s = l ** (1/3) if l >= 0 else -((-l) ** (1/3)), \
              m ** (1/3) if m >= 0 else -((-m) ** (1/3)), \
              s ** (1/3) if s >= 0 else -((-s) ** (1/3))

    # LMS to OKLab
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b_out = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s

    return (L, a, b_out)


def oklab_to_rgb(L: float, a: float, b: float) -> Tuple[int, int, int]:
    """Convert OKLab to sRGB"""
    # OKLab to LMS
    l = L + 0.3963377774 * a + 0.2158037573 * b
    m = L - 0.1055613458 * a - 0.0638541728 * b
    s = L - 0.0894841775 * a - 1.2914855480 * b

    # Cube
    l, m, s = l ** 3, m ** 3, s ** 3

    # LMS to RGB
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_out = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    # Linear to sRGB
    def linear_to_srgb(c):
        if c <= 0.0031308:
            return 12.92 * c
        return 1.055 * (c ** (1/2.4)) - 0.055

    r, g, b_out = linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(b_out)

    # Clamp and convert to 8-bit
    r = max(0, min(255, int(r * 255)))
    g = max(0, min(255, int(g * 255)))
    b_out = max(0, min(255, int(b_out * 255)))

    return (r, g, b_out)


def generate_oklab_palette(hues: int, chromas: int, lightnesses: int) -> List[Color]:
    """
    Generate palette using OKLab color space for perceptual uniformity.
    OKLab provides much better perceptual uniformity than HSL.
    """
    colors = []

    for l_idx in range(lightnesses):
        L = 0.25 + 0.6 * (l_idx / (lightnesses - 1)) if lightnesses > 1 else 0.5

        for c_idx in range(chromas):
            chroma = 0.05 + 0.12 * (c_idx / (chromas - 1)) if chromas > 1 else 0.1

            for h_idx in range(hues):
                hue_angle = 2 * math.pi * h_idx / hues
                a = chroma * math.cos(hue_angle)
                b = chroma * math.sin(hue_angle)

                r, g, b_out = oklab_to_rgb(L, a, b)
                colors.append(Color(r, g, b_out))

    return colors


# =============================================================================
# PALETTE DEFINITIONS
# =============================================================================

def create_palette_v0_c64_original() -> List[Color]:
    """
    Palette V0: Original C64 16 colors only (repeated to fill 256 slots)
    This is the baseline - what the VIC-II can do today.
    """
    # Just repeat the 16 colors to fill 256 slots
    palette = []
    for i in range(256):
        palette.append(VIC_II_COLORS[i % 16])
    return palette


def create_palette_v1_rgb332() -> List[Color]:
    """
    Palette V1: Pure RGB 3-3-2
    Simple, hardware-friendly, but VIC-II colors not preserved exactly.
    """
    return generate_rgb_332()


def create_palette_v2_hybrid_666() -> List[Color]:
    """
    Palette V2: VIC-II + Grayscale + 6×6×6 RGB cube
    - 0-15:   Original VIC-II colors
    - 16-31:  16-level grayscale
    - 32-247: 6×6×6 RGB cube (216 colors)
    - 248-255: Extra useful colors (skin tones, etc.)
    """
    palette = VIC_II_COLORS.copy()
    palette.extend(generate_grayscale(16))
    palette.extend(generate_rgb_cube(6))

    # Fill remaining with useful extra colors (skin tones, nature colors)
    extras = [
        Color(0xff, 0xcc, 0xaa),  # Light skin
        Color(0xe0, 0xa0, 0x70),  # Medium skin
        Color(0xc0, 0x80, 0x50),  # Tan skin
        Color(0x80, 0x50, 0x30),  # Dark skin
        Color(0x00, 0x80, 0x40),  # Forest green
        Color(0x40, 0x60, 0x80),  # Steel blue
        Color(0xff, 0x80, 0x00),  # Pure orange
        Color(0x80, 0x00, 0x40),  # Burgundy
    ]
    palette.extend(extras)

    return palette[:256]


def create_palette_v3_hsl() -> List[Color]:
    """
    Palette V3: VIC-II + Grayscale + HSL-based chromatic colors
    - 0-15:   Original VIC-II colors
    - 16-31:  16-level grayscale
    - 32-255: HSL-based (24 hues × 3 saturations × 3 luminosities = 216, trimmed)
    """
    palette = VIC_II_COLORS.copy()
    palette.extend(generate_grayscale(16))

    # 24 hues, 3 sat levels, 3 lum levels = 216 colors, we need 224
    hsl_colors = generate_hsl_palette(24, 3, 3)
    palette.extend(hsl_colors)

    # Pad if needed
    while len(palette) < 256:
        palette.append(Color(128, 128, 128))

    return palette[:256]


def create_palette_v4_perceptual() -> List[Color]:
    """
    Palette V4: VIC-II + Extended Grayscale + Perceptually uniform (OKLab)
    - 0-15:   Original VIC-II colors
    - 16-31:  16-level grayscale
    - 32-255: OKLab-based colors (perceptually uniform spacing)
    """
    palette = VIC_II_COLORS.copy()
    palette.extend(generate_grayscale(16))

    # Generate OKLab palette: 16 hues × 3 chromas × 4 lightnesses = 192 colors
    # Plus extra variations
    oklab_colors = generate_oklab_palette(16, 3, 5)  # 16 * 3 * 5 = 240, more than enough
    palette.extend(oklab_colors)

    return palette[:256]


def create_palette_v5_artistic() -> List[Color]:
    """
    Palette V5: Artist-friendly palette with hand-picked color ramps
    - 0-15:   Original VIC-II colors
    - 16-31:  Warm grayscale (slight sepia tint)
    - 32-255: Color ramps for pixel art (8 colors × 28 ramps)
    """
    palette = VIC_II_COLORS.copy()

    # Warm grayscale (sepia-tinted)
    for i in range(16):
        v = int(255 * i / 15)
        r = min(255, v + 8)
        g = v
        b = max(0, v - 8)
        palette.append(Color(r, g, b))

    # Define base hues for color ramps (28 hues to fill 224 slots with 8 shades each)
    # This gives artists smooth gradients for shading
    base_hues = [
        0.0,    # Red
        0.03,   # Red-orange
        0.07,   # Orange
        0.11,   # Orange-yellow
        0.15,   # Yellow
        0.22,   # Yellow-green
        0.30,   # Green
        0.38,   # Green-cyan
        0.47,   # Cyan
        0.53,   # Cyan-blue
        0.60,   # Blue
        0.67,   # Blue-purple
        0.75,   # Purple
        0.83,   # Purple-magenta
        0.90,   # Magenta
        0.95,   # Magenta-red
        # Desaturated versions
        0.0,    # Desaturated red
        0.07,   # Desaturated orange
        0.15,   # Desaturated yellow
        0.30,   # Desaturated green
        0.47,   # Desaturated cyan
        0.60,   # Desaturated blue
        0.75,   # Desaturated purple
        0.90,   # Desaturated magenta
        # Skin tones (special handling)
        0.06,   # Skin base 1
        0.05,   # Skin base 2
        0.04,   # Skin base 3
        0.08,   # Skin base 4
    ]

    for idx, hue in enumerate(base_hues):
        is_desaturated = idx >= 16 and idx < 24
        is_skin = idx >= 24

        for shade in range(8):
            if is_skin:
                # Skin tones: specific saturation and luminosity ranges
                sat = 0.3 + 0.2 * (idx - 24) / 4
                lum = 0.3 + 0.5 * shade / 7
            elif is_desaturated:
                sat = 0.35
                lum = 0.2 + 0.65 * shade / 7
            else:
                sat = 0.7 + 0.3 * (1 - shade / 7)  # Higher sat for darker shades
                lum = 0.15 + 0.7 * shade / 7

            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    return palette[:256]


def create_palette_v8_ultimate() -> List[Color]:
    """
    Palette V8: Ultimate palette based on empirical optimization.

    Structure:
    - 0-15:    Original VIC-II colors (compatibility)
    - 16-31:   16-level grayscale
    - 32-63:   Skin tones (4 bases × 8 shades)
    - 64-127:  Saturated color ramps (8 hues × 8 shades)
    - 128-175: Desaturated ramps (6 hues × 8 shades)
    - 176-207: Blue-gray/Cyan-gray ramps (4 ramps × 8 shades) - addresses V6 weakness
    - 208-239: Specialty ramps (metals, earth, etc.)
    - 240-255: Near-black variants with color tints - addresses V6 weakness
    """
    palette = VIC_II_COLORS.copy()

    # 16-31: Pure grayscale (16 levels)
    palette.extend(generate_grayscale(16))

    # 32-63: Skin tones - 4 different base tones, each with 8 shades
    skin_bases = [
        (0.08, 0.55, 0.85),  # Light/pale skin
        (0.07, 0.50, 0.75),  # Medium/tan skin
        (0.05, 0.60, 0.55),  # Olive/brown skin
        (0.04, 0.65, 0.40),  # Dark skin
    ]
    for hue, sat, max_lum in skin_bases:
        for shade in range(8):
            lum = 0.15 + (max_lum - 0.15) * shade / 7
            s = sat * (0.6 + 0.4 * (1 - shade / 7))
            r, g, b = colorsys.hls_to_rgb(hue, lum, s)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 64-127: Saturated color ramps - 8 well-spaced hues
    saturated_hues = [
        0.0,    # Red
        0.08,   # Orange
        0.15,   # Yellow
        0.33,   # Green
        0.50,   # Cyan
        0.60,   # Blue
        0.75,   # Purple
        0.90,   # Magenta
    ]
    for hue in saturated_hues:
        for shade in range(8):
            lum = 0.12 + 0.76 * shade / 7
            sat = 0.85 + 0.15 * (1 - shade / 7)
            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 128-175: Desaturated/muted ramps - 6 hues × 8 shades
    desaturated_hues = [
        0.0,    # Muted red
        0.08,   # Muted orange/brown
        0.15,   # Muted yellow/tan
        0.33,   # Muted green
        0.60,   # Muted blue
        0.75,   # Muted purple
    ]
    for hue in desaturated_hues:
        for shade in range(8):
            lum = 0.20 + 0.60 * shade / 7
            sat = 0.35
            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 176-207: Blue-gray and Cyan-gray ramps (4 ramps × 8 shades)
    # These are the colors V6 was missing - desaturated cool tones
    blue_gray_variants = [
        (0.58, 0.20),  # Blue-gray (low sat)
        (0.58, 0.35),  # Blue-gray (medium sat)
        (0.50, 0.20),  # Cyan-gray (low sat)
        (0.50, 0.35),  # Cyan-gray (medium sat)
    ]
    for hue, sat in blue_gray_variants:
        for shade in range(8):
            lum = 0.15 + 0.70 * shade / 7
            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 208-239: Specialty ramps (4 ramps × 8 shades)
    specialty_ramps = []

    # Gold metallic
    for shade in range(8):
        lum = 0.15 + 0.7 * shade / 7
        sat = 0.8 - 0.3 * shade / 7
        r, g, b = colorsys.hls_to_rgb(0.12, lum, sat)
        r = min(255, int(r * 255 * (1.0 + 0.15 * shade / 7)))
        g = int(g * 255)
        b = int(b * 255 * 0.7)
        specialty_ramps.append(Color(min(255, r), g, b))

    # Silver/steel metallic
    for shade in range(8):
        base = int(40 + 200 * shade / 7)
        r, g, b = base, base, min(255, base + 10)
        specialty_ramps.append(Color(r, g, b))

    # Earth/brown tones
    for shade in range(8):
        lum = 0.10 + 0.55 * shade / 7
        sat = 0.50
        r, g, b = colorsys.hls_to_rgb(0.07, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # Forest/moss green
    for shade in range(8):
        lum = 0.10 + 0.50 * shade / 7
        sat = 0.45
        r, g, b = colorsys.hls_to_rgb(0.28, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    palette.extend(specialty_ramps)

    # 240-255: Near-black variants with color tints (16 colors)
    # These handle very dark colors that have subtle color undertones
    near_blacks = [
        # Very dark with red tint (4 shades)
        Color(0x10, 0x00, 0x00),
        Color(0x18, 0x04, 0x04),
        Color(0x20, 0x08, 0x08),
        Color(0x28, 0x0c, 0x0c),
        # Very dark with blue tint (4 shades)
        Color(0x00, 0x00, 0x10),
        Color(0x04, 0x04, 0x18),
        Color(0x08, 0x08, 0x20),
        Color(0x0c, 0x0c, 0x28),
        # Very dark with green/brown tint (4 shades)
        Color(0x08, 0x08, 0x00),
        Color(0x10, 0x10, 0x04),
        Color(0x18, 0x14, 0x08),
        Color(0x20, 0x1c, 0x0c),
        # Very dark with cyan/gray tint (4 shades)
        Color(0x04, 0x08, 0x0a),
        Color(0x08, 0x10, 0x14),
        Color(0x0c, 0x18, 0x1c),
        Color(0x10, 0x20, 0x24),
    ]
    palette.extend(near_blacks)

    return palette[:256]


def create_palette_v6_refined_artistic() -> List[Color]:
    """
    Palette V6: Refined artist palette with better organization
    - 0-15:   Original VIC-II colors
    - 16-31:  Pure grayscale (16 levels)
    - 32-63:  Skin tones (4 base tones × 8 shades)
    - 64-127: Saturated color ramps (8 hues × 8 shades)
    - 128-191: Muted/desaturated ramps (8 hues × 8 shades)
    - 192-255: Specialty ramps (metals, earth, neon, etc.)
    """
    palette = VIC_II_COLORS.copy()

    # Pure grayscale (16 levels)
    palette.extend(generate_grayscale(16))

    # Skin tones - 4 different base tones, each with 8 shades
    skin_bases = [
        (0.08, 0.55, 0.85),  # Light/pale skin (hue, sat, max_lum)
        (0.07, 0.50, 0.75),  # Medium/tan skin
        (0.05, 0.60, 0.55),  # Olive/brown skin
        (0.04, 0.65, 0.40),  # Dark skin
    ]
    for hue, sat, max_lum in skin_bases:
        for shade in range(8):
            lum = 0.15 + (max_lum - 0.15) * shade / 7
            # Reduce saturation for lighter shades
            s = sat * (0.6 + 0.4 * (1 - shade / 7))
            r, g, b = colorsys.hls_to_rgb(hue, lum, s)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # Saturated color ramps - 8 well-spaced hues
    saturated_hues = [
        0.0,    # Red
        0.08,   # Orange
        0.15,   # Yellow
        0.33,   # Green
        0.50,   # Cyan
        0.60,   # Blue
        0.75,   # Purple
        0.90,   # Magenta
    ]
    for hue in saturated_hues:
        for shade in range(8):
            lum = 0.12 + 0.76 * shade / 7
            sat = 0.85 + 0.15 * (1 - shade / 7)  # Slightly more saturated in darks
            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # Muted/pastel color ramps - same hues, lower saturation
    for hue in saturated_hues:
        for shade in range(8):
            lum = 0.20 + 0.65 * shade / 7
            sat = 0.35
            r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
            palette.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # Specialty ramps (64 colors = 8 ramps × 8 shades)
    specialty_ramps = []

    # 1. Gold/brass metallic
    for shade in range(8):
        lum = 0.15 + 0.7 * shade / 7
        sat = 0.8 - 0.3 * shade / 7  # Desaturate toward highlights
        r, g, b = colorsys.hls_to_rgb(0.12, lum, sat)
        # Add slight variation for metallic feel
        r = min(255, int(r * 255 * (1.0 + 0.15 * shade / 7)))
        g = int(g * 255)
        b = int(b * 255 * 0.7)
        specialty_ramps.append(Color(min(255, r), g, b))

    # 2. Silver/steel metallic
    for shade in range(8):
        base = int(40 + 200 * shade / 7)
        # Slight blue tint
        r = base
        g = base
        b = min(255, base + 10)
        specialty_ramps.append(Color(r, g, b))

    # 3. Copper/bronze
    for shade in range(8):
        lum = 0.12 + 0.65 * shade / 7
        sat = 0.7
        r, g, b = colorsys.hls_to_rgb(0.05, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 4. Earth/dirt brown
    for shade in range(8):
        lum = 0.10 + 0.55 * shade / 7
        sat = 0.50
        r, g, b = colorsys.hls_to_rgb(0.07, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 5. Forest/moss green
    for shade in range(8):
        lum = 0.10 + 0.50 * shade / 7
        sat = 0.45
        r, g, b = colorsys.hls_to_rgb(0.28, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 6. Ocean/water blue
    for shade in range(8):
        lum = 0.15 + 0.65 * shade / 7
        sat = 0.55
        # Shift hue from deep blue to cyan as it gets lighter
        hue = 0.55 + 0.08 * shade / 7
        r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 7. Neon/electric (high saturation, limited lum range)
    neon_hues = [0.0, 0.33, 0.50, 0.60, 0.75, 0.85, 0.95, 0.15]  # Various neons
    for i, hue in enumerate(neon_hues):
        lum = 0.50 + 0.10 * (i % 4) / 3
        sat = 1.0
        r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    # 8. Blood/wine dark reds
    for shade in range(8):
        lum = 0.08 + 0.40 * shade / 7
        sat = 0.75
        # Shift from deep crimson to brighter red
        hue = 0.97 + 0.03 * shade / 7
        if hue >= 1.0:
            hue -= 1.0
        r, g, b = colorsys.hls_to_rgb(hue, lum, sat)
        specialty_ramps.append(Color(int(r * 255), int(g * 255), int(b * 255)))

    palette.extend(specialty_ramps)

    return palette[:256]


# =============================================================================
# VISUALIZATION
# =============================================================================

def visualize_palette(palette: List[Color], name: str, filename: str):
    """Create a visual representation of the palette"""
    if not HAS_PIL:
        print(f"  [Skipping image - PIL not installed]")
        return

    cell_size = 24
    cols = 16
    rows = 16
    margin = 40

    width = cols * cell_size + margin * 2
    height = rows * cell_size + margin * 2 + 30

    img = Image.new('RGB', (width, height), (40, 40, 40))
    draw = ImageDraw.Draw(img)

    # Title
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()

    draw.text((margin, 10), name, fill=(255, 255, 255), font=font)

    # Draw color cells
    for i, color in enumerate(palette):
        row = i // cols
        col = i % cols
        x = margin + col * cell_size
        y = margin + 20 + row * cell_size

        draw.rectangle([x, y, x + cell_size - 1, y + cell_size - 1],
                       fill=color.to_tuple())

        # Draw index for first 32 colors
        if i < 32:
            # Choose text color based on luminance
            text_color = (0, 0, 0) if color.luminance() > 128 else (255, 255, 255)
            try:
                small_font = ImageFont.truetype("arial.ttf", 8)
            except:
                small_font = font
            draw.text((x + 2, y + 2), str(i), fill=text_color, font=small_font)

    img.save(filename)
    print(f"  Saved: {filename}")


def print_palette_info(palette: List[Color], name: str):
    """Print palette statistics"""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"Total colors: {len(palette)}")

    # Count unique colors
    unique = len(set(c.to_hex() for c in palette))
    print(f"Unique colors: {unique}")

    # Luminance distribution
    lums = [c.luminance() for c in palette]
    print(f"Luminance range: {min(lums):.1f} - {max(lums):.1f}")

    # Show first 16 (VIC-II) colors
    print("\nFirst 16 colors (VIC-II compatible):")
    for i in range(16):
        c = palette[i]
        print(f"  {i:2d}: {c.to_hex()} (L={c.luminance():5.1f})")


def export_palette_asm(palette: List[Color], name: str, filename: str):
    """Export palette as assembly data"""
    with open(filename, 'w') as f:
        f.write(f"; {name}\n")
        f.write(f"; 256 colors, RGB format\n\n")

        f.write(f"{name.lower().replace(' ', '_')}_r:\n")
        for i in range(0, 256, 16):
            values = ', '.join(f'${palette[i+j].r:02x}' for j in range(16))
            f.write(f"    .byte {values}\n")

        f.write(f"\n{name.lower().replace(' ', '_')}_g:\n")
        for i in range(0, 256, 16):
            values = ', '.join(f'${palette[i+j].g:02x}' for j in range(16))
            f.write(f"    .byte {values}\n")

        f.write(f"\n{name.lower().replace(' ', '_')}_b:\n")
        for i in range(0, 256, 16):
            values = ', '.join(f'${palette[i+j].b:02x}' for j in range(16))
            f.write(f"    .byte {values}\n")

    print(f"  Saved: {filename}")


def export_palette_json(palette: List[Color], name: str, filename: str):
    """Export palette as JSON"""
    import json

    data = {
        "name": name,
        "colors": [{"r": c.r, "g": c.g, "b": c.b, "hex": c.to_hex()} for c in palette]
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  Saved: {filename}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("VIC-II Extended Palette Generator")
    print("==================================\n")

    palettes = [
        ("V1 - RGB 3-3-2", create_palette_v1_rgb332()),
        ("V2 - Hybrid 6x6x6", create_palette_v2_hybrid_666()),
        ("V3 - HSL Based", create_palette_v3_hsl()),
        ("V4 - Perceptual OKLab", create_palette_v4_perceptual()),
        ("V5 - Artistic Ramps", create_palette_v5_artistic()),
        ("V6 - Refined Artistic", create_palette_v6_refined_artistic()),
        ("V8 - Ultimate", create_palette_v8_ultimate()),
    ]

    for name, palette in palettes:
        print_palette_info(palette, name)

        # Generate safe filename
        safe_name = name.lower().replace(' ', '_').replace('-', '').replace('/', '')

        # Export visualizations and data
        print("\nExporting:")
        visualize_palette(palette, name, f"palette_{safe_name}.png")
        export_palette_asm(palette, name, f"palette_{safe_name}.asm")
        export_palette_json(palette, name, f"palette_{safe_name}.json")

    print("\n" + "="*60)
    print("Generation complete!")
    print("\nPalette summary:")
    print("  V1 - RGB 3-3-2:       Classic 8-bit, simple hardware")
    print("  V2 - Hybrid 6x6x6:    VIC-II compat + web-safe-like cube")
    print("  V3 - HSL Based:       Intuitive hue organization")
    print("  V4 - Perceptual:      OKLab-based, uniform perception")
    print("  V5 - Artistic:        Gradient ramps for pixel art")
    print("  V6 - Refined:         Organized ramps + specialty colors")
    print("  V8 - Ultimate:        Optimized with blue-grays + near-blacks")


if __name__ == "__main__":
    main()
