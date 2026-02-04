# VIC-II Extended Colors

Extended 256-color palettes for the Commodore 64 VIC-II chip, designed to allow picking each of the 16 active colors from a larger palette while maintaining the 8-bit aesthetic.

## Overview

The original VIC-II has a fixed 16-color palette. This project explores what an extended 256-color palette could look like if the chip allowed selecting each color from 256 options, taking into account:

- **Backward compatibility** - Original 16 VIC-II colors preserved at indices 0-15
- **Human perception** - Colors chosen using perceptual color spaces (OKLab)
- **Practical usage** - Organized into artist-friendly ramps for easy shading

## Palette Versions

| Palette | Avg Score | Description |
|---------|-----------|-------------|
| **V8_Ultimate** | **90.7%** | Best overall - adds blue-gray ramps and near-black tints |
| V6_Refined | 89.7% | Organized ramps with specialty colors |
| V5_Artistic | 87.7% | Artist-friendly gradient ramps |
| V0_C64 | 57.1% | Original 16 colors (baseline) |

## V8 Ultimate Structure

```
Indices 0-15:    Original VIC-II colors (compatibility)
Indices 16-31:   16-level grayscale
Indices 32-63:   Skin tones (4 bases × 8 shades)
Indices 64-127:  Saturated color ramps (8 hues × 8 shades)
Indices 128-175: Desaturated ramps (6 hues × 8 shades)
Indices 176-207: Blue-gray/Cyan-gray ramps (4 × 8 shades)
Indices 208-239: Specialty (gold, silver, earth, forest)
Indices 240-255: Near-black variants with color tints
```

## Tools

### palette_generator.py
Generates all palette versions with visualizations and exports to ASM/JSON.

```bash
python palette_generator.py
```

### image_converter.py
Converts images to use any palette with perceptual (OKLab) color matching.

```bash
python image_converter.py <image.png> [output_dir]
```

### image_analyzer.py
Analyzes perceptual distance between original and converted images.

```bash
python image_analyzer.py <image1.png> [image2.png] ...
```

### palette_optimizer.py
Analyzes palette weaknesses and creates optimized versions.

```bash
python palette_optimizer.py <image1.png> [image2.png] ...
```

## Requirements

```bash
pip install Pillow
```

## Output Formats

- **PNG** - Visual palette reference (16×16 grid)
- **ASM** - 6502 assembly with separate R/G/B tables
- **JSON** - Machine-readable with hex values

## Quality Metrics

Quality scores are based on OKLab perceptual distance:
- **~0.02-0.04**: Just noticeable difference
- **~0.10**: Clearly different but similar
- **~0.30**: Very different colors

A quality score of 90% means the average pixel has an OKLab distance of ~0.02 from the original.

## License

MIT License - feel free to use these palettes in your projects.

## Credits

Palette optimization based on analysis of classic Amiga pixel art including works by Facet and scenes from Agony, Unreal, and Defender of the Crown.
