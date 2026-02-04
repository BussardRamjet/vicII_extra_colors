"""
Palette Optimizer
Analyzes which colors are poorly represented in a palette and suggests improvements.
"""

import sys
import math
from collections import defaultdict
from typing import List, Tuple, Dict, Set
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required.")
    sys.exit(1)

from palette_generator import (
    Color,
    VIC_II_COLORS,
    create_palette_v6_refined_artistic,
    generate_grayscale,
)
from image_converter import rgb_to_oklab, oklab_distance, PaletteMatcher


def analyze_color_errors(image_paths: List[str], palette: List[Color],
                         error_threshold: float = 0.03) -> Dict:
    """
    Analyze which source colors have high error when mapped to the palette.
    Returns information about poorly-represented colors.
    """
    matcher = PaletteMatcher(palette)

    # Track colors with high error
    high_error_colors = defaultdict(lambda: {'count': 0, 'total_error': 0, 'sources': []})

    # Track all color usage
    color_histogram = defaultdict(int)

    total_pixels = 0
    total_error = 0

    for path in image_paths:
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        pixels = img.load()

        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                total_pixels += 1
                color_histogram[(r, g, b)] += 1

                # Find nearest palette color and calculate error
                source_lab = rgb_to_oklab(r, g, b)
                best_idx = matcher.find_nearest(r, g, b)
                pal_color = palette[best_idx]
                pal_lab = rgb_to_oklab(pal_color.r, pal_color.g, pal_color.b)

                error = oklab_distance(source_lab, pal_lab)
                total_error += error

                if error > error_threshold:
                    key = (r, g, b)
                    high_error_colors[key]['count'] += 1
                    high_error_colors[key]['total_error'] += error
                    high_error_colors[key]['mapped_to'] = (pal_color.r, pal_color.g, pal_color.b)
                    high_error_colors[key]['error'] = error

    # Sort by weighted importance (count * error)
    sorted_errors = sorted(
        high_error_colors.items(),
        key=lambda x: x[1]['count'] * x[1]['error'],
        reverse=True
    )

    return {
        'total_pixels': total_pixels,
        'avg_error': total_error / total_pixels,
        'high_error_colors': sorted_errors[:100],  # Top 100
        'unique_colors': len(color_histogram),
        'color_histogram': color_histogram,
    }


def cluster_colors_oklab(colors: List[Tuple[int, int, int]], n_clusters: int) -> List[Tuple[int, int, int]]:
    """
    Simple k-means clustering in OKLab space to find representative colors.
    """
    import random

    if len(colors) <= n_clusters:
        return colors

    # Convert to OKLab
    lab_colors = [(rgb_to_oklab(r, g, b), (r, g, b)) for r, g, b in colors]

    # Initialize centroids randomly
    centroids = [lab_colors[i][0] for i in random.sample(range(len(lab_colors)), n_clusters)]

    for iteration in range(20):  # Max iterations
        # Assign colors to nearest centroid
        clusters = [[] for _ in range(n_clusters)]
        for lab, rgb in lab_colors:
            best_idx = min(range(n_clusters), key=lambda i: oklab_distance(lab, centroids[i]))
            clusters[best_idx].append((lab, rgb))

        # Update centroids
        new_centroids = []
        for cluster in clusters:
            if cluster:
                avg_L = sum(c[0][0] for c in cluster) / len(cluster)
                avg_a = sum(c[0][1] for c in cluster) / len(cluster)
                avg_b = sum(c[0][2] for c in cluster) / len(cluster)
                new_centroids.append((avg_L, avg_a, avg_b))
            else:
                new_centroids.append(centroids[len(new_centroids)])

        centroids = new_centroids

    # Find the RGB color closest to each centroid
    result = []
    for centroid in centroids:
        best_rgb = min(lab_colors, key=lambda x: oklab_distance(x[0], centroid))[1]
        result.append(best_rgb)

    return result


def extract_image_colors(image_paths: List[str], min_count: int = 10) -> List[Tuple[Tuple[int, int, int], int]]:
    """
    Extract all unique colors from images with their frequency.
    """
    color_counts = defaultdict(int)

    for path in image_paths:
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        pixels = img.load()
        width, height = img.size

        for y in range(height):
            for x in range(width):
                color_counts[pixels[x, y]] += 1

    # Filter by minimum count and sort by frequency
    filtered = [(color, count) for color, count in color_counts.items() if count >= min_count]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return filtered


def create_optimized_palette(image_paths: List[str]) -> List[Color]:
    """
    Create an optimized palette based on actual image content.

    Strategy:
    - 0-15: Original VIC-II colors (compatibility)
    - 16-31: 16-level grayscale
    - 32-255: Colors optimized from image analysis
    """
    print("Analyzing images for optimal palette...")

    # Start with VIC-II and grayscale
    palette = VIC_II_COLORS.copy()
    palette.extend(generate_grayscale(16))

    # Extract colors from images
    print("Extracting colors from images...")
    all_colors = extract_image_colors(image_paths, min_count=5)
    print(f"Found {len(all_colors)} unique colors (min count 5)")

    # Get just the RGB values
    color_list = [c[0] for c in all_colors]

    # Remove colors that are already well-represented by VIC-II + grayscale
    existing_matcher = PaletteMatcher(palette)
    poorly_covered = []

    for rgb in color_list:
        r, g, b = rgb
        source_lab = rgb_to_oklab(r, g, b)
        best_idx = existing_matcher.find_nearest(r, g, b)
        pal_color = palette[best_idx]
        pal_lab = rgb_to_oklab(pal_color.r, pal_color.g, pal_color.b)
        error = oklab_distance(source_lab, pal_lab)

        if error > 0.02:  # Not well covered
            poorly_covered.append(rgb)

    print(f"Found {len(poorly_covered)} colors poorly covered by VIC-II + grayscale")

    # Cluster the poorly covered colors to get 224 representative colors
    if len(poorly_covered) > 224:
        print("Clustering to find 224 representative colors...")
        representative = cluster_colors_oklab(poorly_covered, 224)
    else:
        representative = poorly_covered
        # Pad with additional colors if needed
        while len(representative) < 224:
            representative.append((128, 128, 128))

    # Add to palette
    for r, g, b in representative[:224]:
        palette.append(Color(r, g, b))

    return palette[:256]


def create_v7_hybrid_optimized(image_paths: List[str]) -> List[Color]:
    """
    V7: Hybrid approach combining V6 structure with optimization.

    Keep V6's structure but replace the weakest colors with
    colors that are frequently needed but poorly represented.
    """
    from palette_generator import create_palette_v6_refined_artistic

    print("\nCreating V7 Hybrid Optimized palette...")

    # Start with V6 as base
    base_palette = create_palette_v6_refined_artistic()

    # Analyze errors with V6
    print("Analyzing V6 errors...")
    analysis = analyze_color_errors(image_paths, base_palette, error_threshold=0.025)

    print(f"Average error: {analysis['avg_error']:.4f}")
    print(f"High-error colors found: {len(analysis['high_error_colors'])}")

    # Get the most problematic source colors
    problem_colors = []
    for (r, g, b), info in analysis['high_error_colors'][:50]:
        # Weight by frequency and error
        importance = info['count'] * info['error']
        problem_colors.append(((r, g, b), importance))

    print(f"\nTop 10 problematic colors:")
    for (r, g, b), importance in problem_colors[:10]:
        info = analysis['high_error_colors'][problem_colors.index(((r, g, b), importance))][1]
        print(f"  #{r:02x}{g:02x}{b:02x} -> #{info['mapped_to'][0]:02x}{info['mapped_to'][1]:02x}{info['mapped_to'][2]:02x} "
              f"(error: {info['error']:.3f}, count: {info['count']})")

    # Create new palette: keep structure but add problem colors
    # Replace some of the less-used specialty colors
    palette = base_palette.copy()

    # Replace colors 240-255 (end of specialty ramps) with problem colors
    # These are the "neon" and "blood" specialty colors that may be less useful
    replacement_start = 240

    # Cluster problem colors to get good representatives
    if len(problem_colors) > 16:
        problem_rgbs = [c[0] for c in problem_colors]
        representatives = cluster_colors_oklab(problem_rgbs, 16)
    else:
        representatives = [c[0] for c in problem_colors]

    for i, (r, g, b) in enumerate(representatives[:16]):
        if replacement_start + i < 256:
            palette[replacement_start + i] = Color(r, g, b)

    return palette


def main():
    if len(sys.argv) < 2:
        print("Usage: python palette_optimizer.py <image1> [image2] ...")
        print("\nAnalyzes images to create an optimized 256-color palette.")
        sys.exit(1)

    image_paths = sys.argv[1:]

    # Analyze current V6 errors
    from palette_generator import create_palette_v6_refined_artistic
    v6 = create_palette_v6_refined_artistic()

    print("=" * 60)
    print("Analyzing V6 palette errors across all images")
    print("=" * 60)

    analysis = analyze_color_errors(image_paths, v6)

    print(f"\nTotal pixels analyzed: {analysis['total_pixels']:,}")
    print(f"Unique colors in images: {analysis['unique_colors']:,}")
    print(f"Average OKLab error: {analysis['avg_error']:.4f}")
    print(f"Colors with error > 0.03: {len(analysis['high_error_colors'])}")

    print("\nTop 20 worst-represented colors:")
    print("-" * 70)
    print(f"{'Source':<10} {'Mapped To':<10} {'Error':>8} {'Count':>10} {'Impact':>10}")
    print("-" * 70)

    for (r, g, b), info in analysis['high_error_colors'][:20]:
        mapped = info['mapped_to']
        impact = info['count'] * info['error']
        print(f"#{r:02x}{g:02x}{b:02x}    #{mapped[0]:02x}{mapped[1]:02x}{mapped[2]:02x}    "
              f"{info['error']:>7.3f} {info['count']:>10,} {impact:>10.1f}")

    # Create optimized palette
    print("\n" + "=" * 60)
    print("Creating optimized palette V7")
    print("=" * 60)

    v7 = create_v7_hybrid_optimized(image_paths)

    # Save the new palette
    from palette_generator import export_palette_asm, export_palette_json, visualize_palette

    print("\nExporting V7 palette...")
    visualize_palette(v7, "V7 - Optimized", "palette_v7_optimized.png")
    export_palette_asm(v7, "V7 Optimized", "palette_v7_optimized.asm")
    export_palette_json(v7, "V7 Optimized", "palette_v7_optimized.json")

    # Test V7
    print("\n" + "=" * 60)
    print("Testing V7 against V6")
    print("=" * 60)

    v7_analysis = analyze_color_errors(image_paths, v7)

    print(f"\nV6 average error: {analysis['avg_error']:.4f}")
    print(f"V7 average error: {v7_analysis['avg_error']:.4f}")
    improvement = (analysis['avg_error'] - v7_analysis['avg_error']) / analysis['avg_error'] * 100
    print(f"Improvement: {improvement:.1f}%")


if __name__ == "__main__":
    main()
