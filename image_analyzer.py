"""
Analyze perceptual distance between original and palette-converted images.
Uses OKLab color space for perceptually meaningful measurements.
"""

import sys
import math
from pathlib import Path
from typing import List, Tuple, Dict

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

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

# Try to import V7 if available
try:
    from palette_optimizer import create_v7_hybrid_optimized
    HAS_V7 = True
except ImportError:
    HAS_V7 = False

from image_converter import rgb_to_oklab, oklab_distance, PaletteMatcher, convert_image


def calculate_image_distance(original: Image.Image, converted: Image.Image) -> Dict[str, float]:
    """
    Calculate perceptual distance metrics between original and converted images.
    Returns dict with various metrics.
    """
    if original.mode != 'RGB':
        original = original.convert('RGB')
    if converted.mode != 'RGB':
        converted = converted.convert('RGB')

    width, height = original.size
    orig_pixels = original.load()
    conv_pixels = converted.load()

    total_distance = 0.0
    max_distance = 0.0
    distances = []

    for y in range(height):
        for x in range(width):
            r1, g1, b1 = orig_pixels[x, y]
            r2, g2, b2 = conv_pixels[x, y]

            lab1 = rgb_to_oklab(r1, g1, b1)
            lab2 = rgb_to_oklab(r2, g2, b2)

            dist = oklab_distance(lab1, lab2)
            distances.append(dist)
            total_distance += dist
            max_distance = max(max_distance, dist)

    num_pixels = width * height
    avg_distance = total_distance / num_pixels

    # Calculate standard deviation
    variance = sum((d - avg_distance) ** 2 for d in distances) / num_pixels
    std_dev = math.sqrt(variance)

    # Calculate percentiles
    distances.sort()
    p50 = distances[int(num_pixels * 0.50)]
    p90 = distances[int(num_pixels * 0.90)]
    p99 = distances[int(num_pixels * 0.99)]

    # Calculate a "quality score" (0-100, higher is better)
    # Based on average distance, where 0 distance = 100 score
    # OKLab distances typically range from 0 to ~1.4 for very different colors
    # A "just noticeable difference" in OKLab is roughly 0.02-0.04
    quality_score = max(0, 100 - (avg_distance * 500))

    return {
        'avg_distance': avg_distance,
        'max_distance': max_distance,
        'std_dev': std_dev,
        'p50': p50,
        'p90': p90,
        'p99': p99,
        'quality_score': quality_score,
        'num_pixels': num_pixels,
    }


def analyze_image(source_path: str, scale_height: int = None):
    """Analyze an image against all palettes and print metrics."""

    # Load source image
    print(f"Loading: {source_path}")
    source = Image.open(source_path)

    # Scale if requested
    if scale_height and source.size[1] != scale_height:
        ratio = scale_height / source.size[1]
        new_width = int(source.size[0] * ratio)
        source = source.resize((new_width, scale_height), Image.Resampling.LANCZOS)
        print(f"Scaled to: {source.size[0]}x{source.size[1]}")
    else:
        print(f"Size: {source.size[0]}x{source.size[1]}")

    if source.mode != 'RGB':
        source = source.convert('RGB')

    # Define palettes
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

    results = []

    print("\nAnalyzing palettes...")
    print("-" * 80)

    for name, palette in palettes:
        matcher = PaletteMatcher(palette)
        converted = convert_image(source, matcher)
        metrics = calculate_image_distance(source, converted)
        metrics['name'] = name
        results.append(metrics)

    # Sort by quality score (descending)
    results.sort(key=lambda x: x['quality_score'], reverse=True)

    # Print results table
    print(f"\n{'Palette':<12} {'Quality':>8} {'Avg Dist':>10} {'Median':>10} {'P90':>10} {'P99':>10} {'Max':>10}")
    print("=" * 80)

    for r in results:
        print(f"{r['name']:<12} {r['quality_score']:>7.1f}% {r['avg_distance']:>10.4f} "
              f"{r['p50']:>10.4f} {r['p90']:>10.4f} {r['p99']:>10.4f} {r['max_distance']:>10.4f}")

    print("\n" + "=" * 80)
    print("Metrics explanation:")
    print("  Quality:   Score 0-100 (higher = closer to original)")
    print("  Avg Dist:  Average OKLab distance per pixel (lower = better)")
    print("  Median:    50th percentile distance")
    print("  P90/P99:   90th/99th percentile (shows worst-case pixels)")
    print("  Max:       Maximum distance for any single pixel")
    print("\nOKLab distance reference:")
    print("  ~0.02-0.04: Just noticeable difference")
    print("  ~0.10:      Clearly different but similar")
    print("  ~0.30:      Very different colors")

    return results


def analyze_multiple(image_paths: List[str], scale_height: int = None):
    """Analyze multiple images and show aggregate results."""

    all_results = {}

    for path in image_paths:
        print(f"\n{'#' * 80}")
        results = analyze_image(path, scale_height)

        for r in results:
            name = r['name']
            if name not in all_results:
                all_results[name] = []
            all_results[name].append(r['quality_score'])

    # Print aggregate summary
    print(f"\n{'#' * 80}")
    print("AGGREGATE RESULTS (Average quality score across all images)")
    print("=" * 50)

    aggregates = []
    for name, scores in all_results.items():
        avg_score = sum(scores) / len(scores)
        aggregates.append((name, avg_score, min(scores), max(scores)))

    aggregates.sort(key=lambda x: x[1], reverse=True)

    print(f"{'Palette':<12} {'Avg Score':>10} {'Min':>10} {'Max':>10}")
    print("-" * 50)
    for name, avg, min_s, max_s in aggregates:
        print(f"{name:<12} {avg:>9.1f}% {min_s:>9.1f}% {max_s:>9.1f}%")


def main():
    if len(sys.argv) < 2:
        print("Usage: python image_analyzer.py <image1> [image2] ... [--scale HEIGHT]")
        print("\nAnalyzes perceptual distance between original and palette-converted images.")
        print("\nOptions:")
        print("  --scale HEIGHT   Scale images to specified height before analysis")
        sys.exit(1)

    # Parse arguments
    images = []
    scale_height = None

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--scale' and i + 1 < len(sys.argv):
            scale_height = int(sys.argv[i + 1])
            i += 2
        else:
            images.append(sys.argv[i])
            i += 1

    if len(images) == 1:
        analyze_image(images[0], scale_height)
    else:
        analyze_multiple(images, scale_height)


if __name__ == "__main__":
    main()
