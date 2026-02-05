# VIC-II Extended 256-Color Palette Implementation Plan

## Overview

This document outlines a plan to add an extended 256-color palette feature to the C64's VIC-II chip, initially implemented in an emulator. The design prioritizes **backward compatibility** - existing C64 software must continue to work unchanged.

### The Core Idea

```
Standard VIC-II:
  Color slot 0-15 → Fixed 16 VIC-II colors

Extended VIC-II:
  Color slot 0-15 → 16-byte mapping table → 256-color Ultimate palette
```

- VIC-II still uses 16 color slots (0-15)
- Screen RAM, Color RAM, background registers - all unchanged
- Only the **final color lookup** is redirected through a mapping table
- Each slot maps to any of 256 pre-defined colors
- **No changes to existing software required** - just set up the mapping table

## Research Summary

### VIC-II Register Space

| Address Range | Purpose | Status |
|---------------|---------|--------|
| $D000-$D02E | Standard VIC-II registers | In use |
| $D02F-$D030 | C128 keyboard/special | Rarely used on C64 |
| $D031-$D03F | Unused | **Available for extensions** |

### Key Facts
- Registers $D02F-$D03F read as $FF on original hardware, writes ignored
- VIC-II registers mirror every 64 bytes ($D000 = $D040 = $D080...)
- Color registers ($D020-$D02E) have unused upper 4 bits (always read as 1)
- No existing software should write specific sequences to unused registers

### Prior Art: VIC-II Kawari
The [VIC-II Kawari](https://github.com/randyrossi/vicii-kawari) FPGA replacement uses:
- **Unlock sequence**: Write "VIC2" (bytes 86, 73, 67, 50) to $D03F
- **Extended registers** at $D02F-$D03F for math, DMA, video RAM access
- **Hardware jumpers** for security lockdown

---

## Implementation Plan

### Phase 1: Activation Mechanism

#### Magic Unlock Sequence
Write a specific 4-byte sequence to $D03F to unlock extended mode:

```
Write to $D03F: $56 ('V')
Write to $D03F: $49 ('I')
Write to $D03F: $43 ('C')
Write to $D03F: $58 ('X')  ; 'X' for extended
```

**Unlock Code:**
```asm
; Enable extended palette mode
LDA #$56        ; 'V'
STA $D03F
LDA #$49        ; 'I'
STA $D03F
LDA #$43        ; 'C'
STA $D03F
LDA #$58        ; 'X'
STA $D03F
; Extended mode now active
```

**Deactivation:**
```asm
; Disable extended mode (return to standard VIC-II)
LDA #$00
STA $D02F       ; Clear EXT_CTRL
```

**Why This Approach:**
- No existing software writes "VICX" to $D03F
- Easy to detect in emulator (state machine)
- Easy to implement in hardware (FPGA)
- Different from Kawari's "VIC2" to avoid conflicts
- Proven approach used by VIC-II Kawari

---

### Phase 2: Extended Register Map

Once unlocked, the following registers become active:

| Address | Name | R/W | Description |
|---------|------|-----|-------------|
| $D02F | EXT_CTRL | R/W | Extension control register |
| $D030 | EXT_STATUS | R | Extension status/version |
| $D031 | PAL_PTR_LO | R/W | Palette table pointer (low byte) - optional |
| $D032 | PAL_PTR_HI | R/W | Palette table pointer (high byte) - optional |
| $D033 | Reserved | - | Future expansion |
| $D034 | COLOR_MODE | R/W | Color mode selection |
| $D035 | PAL_INDEX | R/W | Screen palette slot select (0-15) |
| $D036 | PAL_DATA | R/W | Screen mapping (0-255 = Ultimate palette index) |
| $D037-$D03E | Reserved | - | Future expansion |
| $D03F | EXT_LOCK | W | Lock/unlock register |

#### How Screen Palette Mapping Works
```
; Example: Map VIC-II color slot 2 (normally red) to Ultimate palette color #47
LDA #$02        ; Select slot 2
STA $D035
LDA #$2F        ; Ultimate palette index 47
STA $D036

; Now any pixel using color 2 displays Ultimate palette color #47
```

#### How Sprite Colors Work in Extended Mode
Sprites only use 3 colors max (plus transparent), so no mapping table needed!

**Existing sprite color registers:**
| Address | Standard Mode | Extended Mode |
|---------|---------------|---------------|
| $D025 | Sprite Multicolor 0 (bits 3-0 = color 0-15) | Full 8-bit Ultimate index |
| $D026 | Sprite Multicolor 1 (bits 3-0 = color 0-15) | Full 8-bit Ultimate index |
| $D027-$D02E | Sprite 0-7 color (bits 3-0 = color 0-15) | Full 8-bit Ultimate index |

The upper 4 bits of $D025-$D02E are unused on real hardware (read as 1). In extended mode, all 8 bits become active.

```
; Set sprite 0 color to Ultimate palette index #200
LDA #$C8
STA $D027

; Set shared multicolor 0 to Ultimate palette index #47
LDA #$2F
STA $D025
```

**No new registers needed!** Just write the Ultimate index directly to existing registers.

#### EXT_CTRL ($D02F) Bit Layout
```
Bit 7: Extended mode enable (1=enabled, 0=disabled)
Bit 6: Palette auto-increment (for fast palette writes)
Bit 5: Per-scanline palette swap enable
Bit 4: Reserved
Bit 3-0: Active color mode
```

#### COLOR_MODE ($D034) Values
```
$00: Standard VIC-II (fixed 16 colors, mapping disabled)
$01: Extended palette mapping enabled (16 slots → 256 colors)
$02: Extended + per-scanline palette auto-switch
```

Note: The multicolor cell rules (4×1 vs 4×8, per-scanline vs global bg) are software conventions, not hardware modes. The VIC-II hardware constraints remain the same.

---

### Phase 3: Palette Mapping

#### Concept
The VIC-II still uses 16 color slots (0-15), but each slot maps to one of the 256 colors in our pre-defined **Ultimate Palette** (V8). The Ultimate Palette is fixed in the emulator/hardware - software just picks which 16 colors to use.

#### Palette Mapping Table Format
16 entries × 1 byte = **16 bytes total**

```
Offset $00: Color slot 0 → Ultimate palette index (0-255)
Offset $01: Color slot 1 → Ultimate palette index (0-255)
...
Offset $0F: Color slot 15 → Ultimate palette index (0-255)
```

#### Default Mapping (Compatibility)
On reset or when extended mode disabled:
```
Slot 0  → Index 0   (Black)
Slot 1  → Index 1   (White)
Slot 2  → Index 2   (Red)
...
Slot 15 → Index 15  (Light Grey)
```
The first 16 entries of the Ultimate Palette match standard VIC-II colors.

#### Palette Location Options

**Option 1: Direct Register Access (Recommended)**
- Use PAL_INDEX ($D035) to select slot (0-15)
- Use PAL_DATA ($D036) to read/write the mapping (0-255)
- Simple, no RAM needed, fast for per-scanline changes

**Option 2: Pointer-Based**
- PAL_PTR_LO/HI points to 16-byte table in VIC memory
- Good for bulk palette loading

#### Recommended: Option 1 (Direct Register Access)
- Only 16 bytes to manage
- Register access is fast enough
- No RAM overhead

---

### Phase 4: Color Indexing

#### Key Insight: VIC-II Still Uses 4-Bit Indices
The VIC-II hardware always works with 16 color slots (0-15). What changes is **what color each slot displays**.

```
Standard Mode:  Slot 0-15 → Fixed VIC-II colors
Extended Mode:  Slot 0-15 → Mapped to any of 256 Ultimate palette colors
```

#### No Memory Layout Changes Required!
- Screen RAM: still 4-bit indices (0-15)
- Color RAM: still 4-bit indices (0-15)
- Background registers: still 4-bit indices (0-15)

The only difference is the **palette mapping table** that translates slot → Ultimate color.

#### Example
```
; Standard: Slot 6 always displays VIC-II blue (#40318D)
; Extended: Slot 6 can display ANY of 256 colors

LDA #$06        ; Select slot 6
STA $D035
LDA #$C0        ; Map to Ultimate palette index 192 (maybe a nice teal)
STA $D036

; Now everywhere color 6 is used, it shows color #192 instead of blue
```

---

### Phase 5: Multicolor Mode Adaptation

#### Multicolor Works Exactly The Same!
The VIC-II multicolor logic is unchanged:
```
%00 = Background ($D021)     → Slot 0-15 → Mapped Ultimate color
%01 = Upper nibble screen RAM → Slot 0-15 → Mapped Ultimate color
%10 = Lower nibble screen RAM → Slot 0-15 → Mapped Ultimate color
%11 = Color RAM              → Slot 0-15 → Mapped Ultimate color
```

The only change is the **final color lookup** - instead of fixed VIC-II colors, each slot goes through the 16-byte mapping table to get an Ultimate palette color.

#### Existing Code Compatibility
Since the 4-bit indices are unchanged, existing multicolor code works perfectly. The only new code needed is to set up the palette mapping at startup.

```
; Example: Set up a custom 16-color palette for a game
LDX #$00
setup_loop:
    STX $D035           ; Select slot X
    LDA my_palette,X    ; Get Ultimate palette index
    STA $D036           ; Store mapping
    INX
    CPX #$10
    BNE setup_loop
    RTS

my_palette:
    .byte $00, $01, $2F, $3A, $45, $52, $6B, $78  ; Slots 0-7
    .byte $8C, $99, $A5, $B2, $C0, $D8, $E4, $FF  ; Slots 8-15
```

---

### Phase 6: Per-Scanline Palette (Raster Effects)

When EXT_CTRL bit 5 = 1:
- VIC reads palette mapping from pointer at start of each scanline
- Allows different 16-color mappings per scanline
- Each mapping is 16 bytes, pointer table is 200 × 2 bytes = 400 bytes

**Scanline Palette Table Format**:
```
$0000: Scanline 0 mapping pointer (low)
$0001: Scanline 0 mapping pointer (high)
$0002: Scanline 1 mapping pointer (low)
$0003: Scanline 1 mapping pointer (high)
...
```

**Memory Usage**:
- Pointer table: 400 bytes
- If every scanline uses unique mapping: 200 × 16 = 3200 bytes
- If scanlines share mappings: much less (e.g., 20 unique = 320 bytes)

**Alternative: Raster Interrupt Approach**
Instead of automatic per-scanline switching, software can use raster interrupts to update the 16-byte mapping at specific scanlines. This uses less memory but more CPU.

---

## Implementation Phases (Emulator)

### Phase 1: Basic Infrastructure
1. Add extended register storage ($D02F-$D03F)
2. Implement unlock sequence detection ("VICX" to $D03F)
3. Add EXT_CTRL register handling
4. Display extension status in emulator UI

### Phase 2: Ultimate Palette
1. Embed 256-color Ultimate palette (V8) as RGB lookup table
2. This is fixed/read-only - the master color reference

### Phase 3: Palette Mapping
1. Add 16-byte mapping table (slot → Ultimate index)
2. Initialize mapping to 0-15 (standard VIC-II colors)
3. Implement PAL_INDEX ($D035) and PAL_DATA ($D036) registers
4. Hook mapping into VIC-II color output stage

### Phase 4: Video Output Integration
1. Modify screen color lookup: slot → screen_mapping[slot] → ultimate_palette[index]
2. Modify sprite color lookup: $D025-$D02E value → ultimate_palette[value] (direct, no mapping)
3. All existing VIC-II modes work unchanged (bitmap, multicolor, sprites)
4. Test with standard software

### Phase 5: Per-Scanline Switching (Optional)
1. Implement palette pointer registers
2. Add scanline-triggered mapping reload
3. Test raster effects

### Phase 6: Validation
1. Run existing C64 software - must work unchanged
2. Test palette switching
3. Use converter tool images as reference
4. Performance optimization

---

## Compatibility Checklist

- [ ] Unlock sequence cannot be triggered by existing software
- [ ] Unlocked state does not affect standard VIC-II behavior until color mode changed
- [ ] COLOR_MODE $00 is 100% identical to standard VIC-II
- [ ] Reading unused registers returns expected values ($FF)
- [ ] Standard C64 boot sequence works
- [ ] GEOS, productivity software works
- [ ] Games work (test suite needed)
- [ ] Demos work (especially those using VIC tricks)

---

## Test Software Requirements

1. **Palette loader**: Load 256-color palette from file
2. **Mode switcher**: Toggle between standard and extended modes
3. **Image viewer**: Display converted images
4. **Validation tool**: Compare emulator output with converter output

---

## Memory Footprint Summary

### In Emulator/Hardware
| Component | Size | Description |
|-----------|------|-------------|
| Ultimate Palette | 768 bytes | 256 × RGB (fixed, read-only) |
| Screen Mapping | 16 bytes | 16 slots → Ultimate index |
| Sprite Colors | 0 bytes | Uses existing $D025-$D02E (direct index) |
| Extended Registers | 17 bytes | $D02F-$D03F |
| **Total** | **~801 bytes** | |

### In C64 RAM (Optional)
| Component | Size | Description |
|-----------|------|-------------|
| Per-scanline pointers | 400 bytes | 200 scanlines × 2 bytes (if used) |
| Palette tables | varies | 16 bytes per unique palette |

---

## References

- [VIC-II Kawari Registers](https://github.com/randyrossi/vicii-kawari/blob/main/doc/REGISTERS.md)
- [VIC-II Register Reference](https://www.oxyron.de/html/registers_vic2.html)
- [C64 Memory Map](https://www.c64-wiki.com/wiki/Memory_Map)
- [Christian Bauer's VIC-II Documentation](https://www.zimmers.net/cbmpics/cbm/c64/vic-ii.txt)

---

## Next Steps

1. Choose target emulator (VICE, custom, etc.)
2. Implement Phase 1 (unlock mechanism)
3. Create simple test program to verify unlock works
4. Proceed with palette system implementation
5. Integrate with existing converter tool for testing
