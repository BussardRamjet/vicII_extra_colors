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
; EXT_CTRL automatically set to $80 (registers accessible, palette off)
```

**Disable palette mapping (keep registers accessible):**
```asm
LDA #$80
STA $D02F       ; Palette mapping off, registers still accessible
```

**Re-lock (return to original hardware behavior):**
```asm
LDA #$00
STA $D02F       ; Bit 7 = 0 → re-locks registers, back to standard VIC-II
```

#### State Machine Behavior
- The unlock sequence is tracked by an internal 2-bit counter
- Each correct byte advances the counter: V(0) → I(1) → C(2) → X(3=unlock)
- **Any incorrect write to $D03F resets the counter to 0**
- Writes to other VIC registers do NOT affect the counter
- On successful unlock, EXT_CTRL is automatically set to $80 (registers on, palette off)

#### Re-lock Behavior
- Writing any value with bit 7 = 0 to EXT_CTRL re-locks the extension
- All registers return to reading $FF (identical to original hardware)
- The unlock sequence must be performed again to regain access
- No special sequence needed — just clear bit 7

#### Reset Behavior
On hardware/software reset:
- Unlock state clears (registers locked)
- EXT_CTRL resets to $00
- PAL_PTR resets to $0000
- EXT_STATUS reflects disabled state
- VIC-II operates in standard mode, identical to original hardware

**Why This Approach:**
- No existing software writes "VICX" to $D03F
- Easy to detect in emulator (state machine)
- Easy to implement in hardware (FPGA)
- Different from Kawari's "VIC2" to avoid conflicts
- Proven approach used by VIC-II Kawari
- Incorrect writes reset the counter, preventing accidental unlock
- Re-lock is simple (just clear bit 7) — no reverse sequence needed

---

### Phase 2: Extended Register Map

Once unlocked, only **4 new registers** are needed:

| Address | Name | R/W | Description |
|---------|------|-----|-------------|
| $D02F | EXT_CTRL | R/W | Extension control register |
| $D030 | EXT_STATUS | R | Extension status/version |
| $D031 | PAL_PTR_LO | R/W | Palette pointer low byte (VIC bank-relative) |
| $D032 | PAL_PTR_HI | R/W | Palette pointer high byte (bits 5-0 used, 14-bit) |
| $D033-$D03E | Reserved | - | Future expansion |
| $D03F | EXT_LOCK | W | Lock/unlock register (state machine) |

**Palette data lives in C64 RAM within the current VIC bank** - just modify memory directly!

#### Register Read Behavior

| State | $D02F | $D030 | $D031-$D032 | $D033-$D03E | $D03F |
|-------|-------|-------|-------------|-------------|-------|
| Locked (default) | $FF | $FF | $FF | $FF | $FF |
| Unlocked | R/W | Status | R/W | $FF | W only |

- **Before unlock**: all extended registers read as $FF (identical to original hardware)
- **After unlock**: EXT_CTRL, EXT_STATUS, and PAL_PTR all become readable
- **PAL_PTR reads return the last written value** when unlocked (useful for software to verify configuration)
- **After re-lock (write bit 7=0 to EXT_CTRL)**: all registers return to reading $FF

#### EXT_STATUS ($D030) Format
```
Bit 7: Palette mapping active (1=mapping enabled, mirrors EXT_CTRL bit 6)
Bit 6: Extension unlocked (1=registers accessible, mirrors EXT_CTRL bit 7)
Bits 5-0: Version number (currently %000000 = version 0)
```
- Returns $FF when locked (indistinguishable from original hardware)
- When unlocked: reflects current state and version
- Software can read this to detect extension presence after unlock

#### VIC Bank-Relative Addressing

Pointers use the same 14-bit addressing as other VIC data (screen RAM, charset, bitmap):

```
Actual address = VIC_BANK_BASE + (PAL_PTR_HI[5:0] << 8) + PAL_PTR_LO

VIC Bank selection via CIA2 ($DD00 bits 1-0):
  %11 → Bank 0: $0000-$3FFF
  %10 → Bank 1: $4000-$7FFF
  %01 → Bank 2: $8000-$BFFF
  %00 → Bank 3: $C000-$FFFF
```

**Why VIC bank-relative:**
- Consistent with how VIC accesses all other data (screen, charset, sprites)
- Palette naturally co-located with graphics data
- Simpler hardware implementation (reuses existing 14-bit address bus)
- Matches mental model of existing VIC programming

#### Character ROM Shadow Warning
In VIC banks 0 and 2, offsets $1000-$1FFF are shadowed by character ROM — the VIC reads character ROM instead of RAM at these addresses. This is a standard VIC-II behavior that applies to **all** VIC data fetches, including the palette mapping table.

**Do NOT place the palette table at these offsets:**
- Bank 0: $1000-$1FFF (absolute $1000-$1FFF)
- Bank 2: $1000-$1FFF (absolute $9000-$9FFF)

Banks 1 and 3 are unaffected and have no character ROM shadow.

#### VIC Bank Switching
If the program switches the VIC bank (via CIA2 $DD00), the PAL_PTR offset now refers to a different physical address. Software must either:
- Keep a copy of the palette data at the same offset in every VIC bank used, or
- Update PAL_PTR after switching banks

This is the same consideration that applies to screen RAM and character data placement.

#### Register Mirroring
Standard VIC-II registers mirror every 64 bytes throughout the $D000-$D3FF range ($D000 = $D040 = $D080...). Extended registers follow the same mirroring behavior:
- $D03F = $D07F = $D0BF = $D0FF = ... (unlock/lock register)
- $D02F = $D06F = $D0AF = ... (EXT_CTRL)
- etc.

This maintains consistency with existing VIC-II behavior. The unlock sequence works at any mirrored address.

#### EXT_CTRL ($D02F) Bit Layout
```
Bit 7: Extension enable (1=registers unlocked, write 0 to re-lock)
Bit 6: Palette mapping active (1=use mapping table, 0=standard VIC-II colors)
Bits 5-0: Reserved (0)
```

| Value | State | Description |
|-------|-------|-------------|
| `$C0` | Fully active | Registers accessible, palette mapping enabled |
| `$80` | Setup mode | Registers accessible, standard VIC-II colors |
| `$00` | Locked | Registers return $FF, standard VIC-II (write 0 to bit 7 to re-lock) |

**Typical workflow:**
1. VICX unlock → EXT_CTRL automatically set to `$80`
2. Configure PAL_PTR and palette data in RAM
3. Write `$C0` to enable palette mapping
4. Write `$80` to temporarily disable mapping (e.g., reconfigure palette)
5. Write `$00` to fully re-lock (must VICX unlock again to access registers)

#### How Screen Palette Mapping Works
```asm
; Assume VIC bank 0 ($0000-$3FFF), palette at $3000
; Set up palette pointer (VIC bank-relative offset = $3000)
LDA #$00
STA $D031       ; Low byte
LDA #$30
STA $D032       ; High byte (bits 5-0 = $30)

; Enable palette mapping
LDA #$C0
STA $D02F

; Modify palette directly in RAM
LDA #$2F        ; Ultimate palette index 47
STA $3002       ; Slot 2 now maps to color 47

; Palette data at $3000 (within VIC bank 0)
my_palette = $3000
; .byte $00,$01,$02,$03,$04,$05,$06,$07  ; Slots 0-7 (defaults)
; .byte $08,$09,$0A,$0B,$0C,$0D,$0E,$0F  ; Slots 8-15 (defaults)
```

**VIC Bank Example:**
```asm
; Using VIC bank 2 ($8000-$BFFF)
LDA #%00000001  ; Select bank 2
STA $DD00

; Palette at $8800 → VIC offset = $0800
LDA #$00
STA $D031
LDA #$08
STA $D032
```

#### Color Register Behavior in Extended Mode

There are two categories of color registers, each handled differently:

**Mapped registers (4-bit slot → palette mapping table):**
These registers use their lower 4 bits as a slot index into the 16-byte palette mapping table, just like screen RAM and color RAM.

| Address | Purpose | Extended behavior |
|---------|---------|-------------------|
| $D020 | Border color | Bits 3-0 → palette mapping → Ultimate color |
| $D021 | Background color 0 | Bits 3-0 → palette mapping → Ultimate color |
| $D022 | Background color 1 (multicolor/ECM) | Bits 3-0 → palette mapping → Ultimate color |
| $D023 | Background color 2 (ECM) | Bits 3-0 → palette mapping → Ultimate color |
| $D024 | Background color 3 (ECM) | Bits 3-0 → palette mapping → Ultimate color |

**Direct registers (full 8-bit Ultimate palette index):**
Sprite color registers bypass the mapping table entirely. The full 8-bit value is used as a direct index into the 256-color Ultimate palette.

| Address | Purpose | Extended behavior |
|---------|---------|-------------------|
| $D025 | Sprite multicolor 0 (shared) | Full 8-bit → Ultimate palette direct |
| $D026 | Sprite multicolor 1 (shared) | Full 8-bit → Ultimate palette direct |
| $D027-$D02E | Sprite 0-7 individual colors | Full 8-bit → Ultimate palette direct |

The upper 4 bits of $D025-$D02E are unused on real hardware (read as 1). In extended mode, all 8 bits become active for sprite registers only.

**Why the asymmetry?**
- Border and background registers are interleaved with screen/color RAM lookups in the VIC-II pipeline — they share the same 4-bit slot system, so they naturally go through the mapping table
- Sprites are rendered independently and only use 3 colors each (plus transparent), so direct 8-bit indexing gives them access to the full palette without needing a separate mapping table
- This means sprites can use colors outside the current 16-slot mapping — useful for UI overlays, cursors, etc.

```asm
; Sprite 0: direct Ultimate palette index #200
LDA #$C8
STA $D027

; Sprite multicolor 0: direct Ultimate palette index #47
LDA #$2F
STA $D025

; Border: uses slot 0 from mapping table (whatever slot 0 maps to)
LDA #$00
STA $D020

; Background: uses slot 6 from mapping table
LDA #$06
STA $D021
```

Note: The multicolor cell rules (4x1 vs 4x8, per-scanline vs global bg) are software conventions, not hardware modes. The VIC-II hardware constraints remain the same.

---

### Phase 3: Palette Mapping

#### Concept
The VIC-II still uses 16 color slots (0-15), but each slot maps to one of the 256 colors in our pre-defined **Ultimate Palette** (V8). The Ultimate Palette is fixed in the emulator/hardware - software just picks which 16 colors to use.

#### Palette Mapping Table Format
16 entries × 1 byte = **16 bytes total** in C64 RAM

```
PAL_PTR + $00: Color slot 0 → Ultimate palette index (0-255)
PAL_PTR + $01: Color slot 1 → Ultimate palette index (0-255)
...
PAL_PTR + $0F: Color slot 15 → Ultimate palette index (0-255)
```

#### Default Mapping (Compatibility)
On reset or when extended mode disabled, VIC uses standard colors.
Typical initialization:
```
Slot 0  → Index 0   (Black)
Slot 1  → Index 1   (White)
Slot 2  → Index 2   (Red)
...
Slot 15 → Index 15  (Light Grey)
```
The first 16 entries of the Ultimate Palette match standard VIC-II colors.

#### Why Pointer-Based (No Registers)
- CPU can modify palette directly in RAM - faster than register access
- Bulk changes are trivial (just copy 16 bytes)
- Software can use raster interrupts to swap palettes per-scanline if desired
- Only 4 new VIC registers needed total

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
```asm
; Standard: Slot 6 always displays VIC-II blue (#40318D)
; Extended: Slot 6 can display ANY of 256 colors

; Assuming PAL_PTR points to my_palette
LDA #$C0        ; Ultimate palette index 192 (maybe a nice teal)
STA my_palette+6  ; Modify slot 6 directly in RAM

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
Since the 4-bit indices are unchanged, existing multicolor code works perfectly. The only new code needed is to set up the palette pointer at startup.

```asm
; Example: Set up a custom 16-color palette for a game
LDA #<my_palette
STA $D031
LDA #>my_palette
STA $D032
LDA #$C0          ; Enable palette mapping
STA $D02F
RTS

my_palette:
    .byte $00, $01, $2F, $3A, $45, $52, $6B, $78  ; Slots 0-7
    .byte $8C, $99, $A5, $B2, $C0, $D8, $E4, $FF  ; Slots 8-15
```

---

### Phase 6: All VIC-II Modes

The palette mapping applies identically across **all** VIC-II display modes. The mapping is always the final step — it replaces the standard color lookup without changing any mode-specific logic.

#### Standard Character Mode (High-Resolution)
```
Foreground: upper nibble screen RAM → Slot 0-15 → Mapped Ultimate color
Background: $D021                   → Slot 0-15 → Mapped Ultimate color
```

#### Multicolor Character Mode
```
%00 = Background ($D021)       → Slot 0-15 → Mapped Ultimate color
%01 = Upper nibble screen RAM  → Slot 0-15 → Mapped Ultimate color
%10 = Lower nibble screen RAM  → Slot 0-15 → Mapped Ultimate color
%11 = Color RAM                → Slot 0-15 → Mapped Ultimate color
```

#### Standard Bitmap Mode (High-Resolution)
```
Foreground: upper nibble screen RAM → Slot 0-15 → Mapped Ultimate color
Background: lower nibble screen RAM → Slot 0-15 → Mapped Ultimate color
```

#### Multicolor Bitmap Mode
```
%00 = Background ($D021)       → Slot 0-15 → Mapped Ultimate color
%01 = Upper nibble screen RAM  → Slot 0-15 → Mapped Ultimate color
%10 = Lower nibble screen RAM  → Slot 0-15 → Mapped Ultimate color
%11 = Color RAM                → Slot 0-15 → Mapped Ultimate color
```

#### Extended Color Mode (ECM)
```
Character color: upper nibble screen RAM → Slot 0-15 → Mapped Ultimate color
Background: selected by upper 2 bits of character code:
  %00 → $D021 → Slot 0-15 → Mapped Ultimate color
  %01 → $D022 → Slot 0-15 → Mapped Ultimate color
  %10 → $D023 → Slot 0-15 → Mapped Ultimate color
  %11 → $D024 → Slot 0-15 → Mapped Ultimate color
```

#### Sprites
```
Sprite individual color ($D027-$D02E) → Direct 8-bit Ultimate index
Sprite multicolor 0 ($D025)          → Direct 8-bit Ultimate index
Sprite multicolor 1 ($D026)          → Direct 8-bit Ultimate index
Sprite-background priority/collision: unchanged
```

#### Border
```
Border color ($D020) → Slot 0-15 → Mapped Ultimate color
```

**Key principle:** All 4-bit color sources go through the mapping table. Only sprite color registers use direct 8-bit indexing.

---

## Implementation Phases (Emulator)

### Phase 1: Basic Infrastructure
1. Add 4 extended registers ($D02F-$D032, $D03F)
2. Implement unlock state machine ("VICX" to $D03F, reset on incorrect byte)
3. Implement re-lock via EXT_CTRL bit 7 (write 0 to re-lock)
4. Auto-set EXT_CTRL to $80 on successful unlock
5. Add EXT_CTRL and EXT_STATUS register handling
6. Implement register read behavior (locked=$FF, unlocked=values)
7. Handle register mirroring (every 64 bytes)
8. Handle reset (all state cleared, return to standard mode)

### Phase 2: Ultimate Palette
1. Embed 256-color Ultimate palette (V8) as RGB lookup table
2. This is fixed/read-only - the master color reference

### Phase 3: Palette Mapping
1. Implement PAL_PTR ($D031/$D032) - points to 16-byte table in C64 RAM
2. Read palette from C64 RAM at PAL_PTR location (respecting VIC bank + char ROM shadow)
3. Hook into VIC-II color output: slot → RAM[PAL_PTR+slot] → ultimate_palette

### Phase 4: Video Output Integration
1. Modify mapped color lookup (border, background, screen/color RAM): slot → mapping → Ultimate
2. Modify sprite color lookup: $D025-$D02E value → ultimate_palette[value] (direct 8-bit)
3. Verify all VIC-II modes: standard, multicolor, bitmap, multicolor bitmap, ECM
4. Test with standard software (must be identical when extended mode disabled)

### Phase 5: Validation
1. Run existing C64 software - must work unchanged
2. Test palette switching across all display modes
3. Test sprite colors (direct 8-bit) alongside mapped screen colors
4. Test VIC bank switching with palette data
5. Test unlock (VICX), re-lock (clear bit 7), and state transitions ($80 ↔ $C0)
6. Use converter tool images as reference
7. Performance optimization

---

## Compatibility Checklist

- [ ] Unlock sequence cannot be triggered by existing software
- [ ] Incorrect writes to $D03F reset the unlock state machine
- [ ] Unlocked state does not affect standard VIC-II behavior until EXT_CTRL bit 7 set
- [ ] EXT_CTRL = $00 is 100% identical to standard VIC-II
- [ ] All extended registers read as $FF when locked
- [ ] Register mirroring works correctly (every 64 bytes)
- [ ] Hardware/software reset clears all extended state
- [ ] PAL_PTR in character ROM shadow range ($1000-$1FFF in banks 0/2) handled correctly
- [ ] VIC bank switching updates palette source address correctly
- [ ] Standard C64 boot sequence works
- [ ] GEOS, productivity software works
- [ ] Games work (test suite needed)
- [ ] Demos work (especially those using VIC tricks)
- [ ] All display modes work: standard, multicolor, bitmap, MCM bitmap, ECM
- [ ] Sprite direct 8-bit colors work independently of mapping table

---

## Test Software Requirements

1. **Register test**: Verify VICX unlock, re-lock (bit 7=0), state transitions ($80/$C0), register read behavior ($FF when locked, values when unlocked), EXT_STATUS format
2. **Palette test**: Load palette, verify mapping across all display modes (standard, multicolor, bitmap, ECM)
3. **Sprite test**: Verify direct 8-bit sprite colors work independently of mapping table
4. **Bank switching test**: Verify palette follows VIC bank, char ROM shadow avoidance
5. **Compatibility test**: Run standard C64 software with extension inactive
6. **Image viewer**: Display converted images using extended palette
7. **Validation tool**: Compare emulator output with converter output

---

## Memory Footprint Summary

### In Emulator/Hardware
| Component | Size | Description |
|-----------|------|-------------|
| Ultimate Palette | 768 bytes | 256 × RGB (fixed, read-only) |
| Extended Registers | 5 bytes | $D02F-$D032, $D03F |
| Unlock state machine | 1 byte | 2-bit counter + locked/unlocked flag |
| **Total** | **~774 bytes** | |

### In C64 RAM
| Component | Size | Description |
|-----------|------|-------------|
| Palette mapping table | 16 bytes | 16 slots × 1 byte Ultimate index |

---

## Ultimate Palette V8 - Complete 256-Color Reference

The Ultimate Palette is fixed in the emulator/hardware (768 bytes = 256 × RGB). Software selects colors by index (0-255). The first 16 entries match standard VIC-II colors for backward compatibility.

The palette is organized into 8-color ramps (dark → light) by hue, plus special groups.

### Standard C64 Colors (0-15)

| Idx | Color | R | G | B | Hex |
|-----|-------|---|---|---|-----|
| 0 | Black | 0 | 0 | 0 | #000000 |
| 1 | White | 255 | 255 | 255 | #ffffff |
| 2 | Red | 136 | 57 | 50 | #883932 |
| 3 | Cyan | 103 | 182 | 189 | #67b6bd |
| 4 | Purple | 139 | 63 | 150 | #8b3f96 |
| 5 | Green | 85 | 160 | 73 | #55a049 |
| 6 | Blue | 64 | 49 | 141 | #40318d |
| 7 | Yellow | 191 | 206 | 114 | #bfce72 |
| 8 | Orange | 139 | 84 | 41 | #8b5429 |
| 9 | Brown | 87 | 66 | 0 | #574200 |
| 10 | Light Red | 184 | 105 | 98 | #b86962 |
| 11 | Dark Grey | 80 | 80 | 80 | #505050 |
| 12 | Medium Grey | 120 | 120 | 120 | #787878 |
| 13 | Light Green | 148 | 224 | 137 | #94e089 |
| 14 | Light Blue | 120 | 105 | 196 | #7869c4 |
| 15 | Light Grey | 159 | 159 | 159 | #9f9f9f |

### Grayscale Ramp (16-31)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 16 | 0 | 0 | 0 | #000000 |
| 17 | 17 | 17 | 17 | #111111 |
| 18 | 34 | 34 | 34 | #222222 |
| 19 | 51 | 51 | 51 | #333333 |
| 20 | 68 | 68 | 68 | #444444 |
| 21 | 85 | 85 | 85 | #555555 |
| 22 | 102 | 102 | 102 | #666666 |
| 23 | 119 | 119 | 119 | #777777 |
| 24 | 136 | 136 | 136 | #888888 |
| 25 | 153 | 153 | 153 | #999999 |
| 26 | 170 | 170 | 170 | #aaaaaa |
| 27 | 187 | 187 | 187 | #bbbbbb |
| 28 | 204 | 204 | 204 | #cccccc |
| 29 | 221 | 221 | 221 | #dddddd |
| 30 | 238 | 238 | 238 | #eeeeee |
| 31 | 255 | 255 | 255 | #ffffff |

### Warm Browns (32-39)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 32 | 59 | 37 | 17 | #3b2511 |
| 33 | 96 | 62 | 30 | #603e1e |
| 34 | 132 | 87 | 45 | #84572d |
| 35 | 167 | 112 | 62 | #a7703e |
| 36 | 188 | 138 | 91 | #bc8a5b |
| 37 | 200 | 164 | 130 | #c8a482 |
| 38 | 214 | 190 | 168 | #d6bea8 |
| 39 | 229 | 216 | 204 | #e5d8cc |

### Cool Browns (40-47)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 40 | 57 | 35 | 19 | #392313 |
| 41 | 88 | 55 | 31 | #58371f |
| 42 | 118 | 76 | 45 | #764c2d |
| 43 | 146 | 96 | 60 | #92603c |
| 44 | 174 | 117 | 77 | #ae754d |
| 45 | 185 | 141 | 109 | #b98d6d |
| 46 | 197 | 164 | 141 | #c5a48d |
| 47 | 210 | 188 | 172 | #d2bcac |

### Rust (48-55)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 48 | 61 | 29 | 15 | #3d1d0f |
| 49 | 82 | 40 | 22 | #522816 |
| 50 | 103 | 53 | 31 | #67351f |
| 51 | 122 | 65 | 41 | #7a4129 |
| 52 | 141 | 78 | 51 | #8d4e33 |
| 53 | 158 | 92 | 63 | #9e5c3f |
| 54 | 175 | 105 | 76 | #af694c |
| 55 | 181 | 123 | 98 | #b57b62 |

### Dark Sienna (56-63)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 56 | 63 | 25 | 13 | #3f190d |
| 57 | 76 | 32 | 18 | #4c2012 |
| 58 | 88 | 39 | 23 | #582717 |
| 59 | 100 | 47 | 30 | #642f1e |
| 60 | 112 | 55 | 37 | #703725 |
| 61 | 122 | 63 | 44 | #7a3f2c |
| 62 | 132 | 72 | 53 | #844835 |
| 63 | 141 | 81 | 62 | #8d513e |

### Pure Red (64-71)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 64 | 61 | 0 | 0 | #3d0000 |
| 65 | 115 | 1 | 1 | #730101 |
| 66 | 168 | 3 | 3 | #a80303 |
| 67 | 220 | 7 | 7 | #dc0707 |
| 68 | 245 | 37 | 37 | #f52525 |
| 69 | 245 | 92 | 92 | #f55c5c |
| 70 | 247 | 145 | 145 | #f79191 |
| 71 | 250 | 198 | 198 | #fac6c6 |

### Orange (72-79)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 72 | 61 | 29 | 0 | #3d1d00 |
| 73 | 115 | 56 | 1 | #733801 |
| 74 | 168 | 82 | 3 | #a85203 |
| 75 | 220 | 109 | 7 | #dc6d07 |
| 76 | 245 | 137 | 37 | #f58925 |
| 77 | 245 | 165 | 92 | #f5a55c |
| 78 | 247 | 194 | 145 | #f7c291 |
| 79 | 250 | 223 | 198 | #fadfc6 |

### Yellow (80-87)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 80 | 61 | 55 | 0 | #3d3700 |
| 81 | 115 | 103 | 1 | #736701 |
| 82 | 168 | 151 | 3 | #a89703 |
| 83 | 220 | 198 | 7 | #dcc607 |
| 84 | 245 | 224 | 37 | #f5e025 |
| 85 | 245 | 230 | 92 | #f5e65c |
| 86 | 247 | 237 | 145 | #f7ed91 |
| 87 | 250 | 245 | 198 | #faf5c6 |

### Pure Green (88-95)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 88 | 1 | 61 | 0 | #013d00 |
| 89 | 3 | 115 | 1 | #037301 |
| 90 | 6 | 168 | 3 | #06a803 |
| 91 | 11 | 220 | 7 | #0bdc07 |
| 92 | 41 | 245 | 37 | #29f525 |
| 93 | 95 | 245 | 92 | #5ff55c |
| 94 | 147 | 247 | 145 | #93f791 |
| 95 | 199 | 250 | 198 | #c7fac6 |

### Cyan (96-103)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 96 | 0 | 61 | 61 | #003d3d |
| 97 | 1 | 115 | 115 | #017373 |
| 98 | 3 | 168 | 168 | #03a8a8 |
| 99 | 7 | 220 | 220 | #07dcdc |
| 100 | 37 | 245 | 245 | #25f5f5 |
| 101 | 92 | 245 | 245 | #5cf5f5 |
| 102 | 145 | 247 | 247 | #91f7f7 |
| 103 | 198 | 250 | 250 | #c6fafa |

### Blue (104-111)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 104 | 0 | 24 | 61 | #00183d |
| 105 | 1 | 46 | 115 | #012e73 |
| 106 | 3 | 69 | 168 | #0345a8 |
| 107 | 7 | 92 | 220 | #075cdc |
| 108 | 37 | 120 | 245 | #2578f5 |
| 109 | 92 | 153 | 245 | #5c99f5 |
| 110 | 145 | 186 | 247 | #91baf7 |
| 111 | 198 | 219 | 250 | #c6dbfa |

### Violet (112-119)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 112 | 30 | 0 | 61 | #1e003d |
| 113 | 58 | 1 | 115 | #3a0173 |
| 114 | 85 | 3 | 168 | #5503a8 |
| 115 | 113 | 7 | 220 | #7107dc |
| 116 | 141 | 37 | 245 | #8d25f5 |
| 117 | 169 | 92 | 245 | #a95cf5 |
| 118 | 196 | 145 | 247 | #c491f7 |
| 119 | 224 | 198 | 250 | #e0c6fa |

### Magenta (120-127)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 120 | 61 | 0 | 36 | #3d0024 |
| 121 | 115 | 1 | 69 | #730145 |
| 122 | 168 | 3 | 102 | #a80366 |
| 123 | 220 | 7 | 134 | #dc0786 |
| 124 | 245 | 37 | 162 | #f525a2 |
| 125 | 245 | 92 | 184 | #f55cb8 |
| 126 | 247 | 145 | 206 | #f791ce |
| 127 | 250 | 198 | 229 | #fac6e5 |

### Muted Red (128-135)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 128 | 68 | 33 | 33 | #442121 |
| 129 | 98 | 47 | 47 | #622f2f |
| 130 | 127 | 61 | 61 | #7f3d3d |
| 131 | 157 | 75 | 75 | #9d4b4b |
| 132 | 179 | 97 | 97 | #b36161 |
| 133 | 193 | 127 | 127 | #c17f7f |
| 134 | 207 | 156 | 156 | #cf9c9c |
| 135 | 221 | 186 | 186 | #ddbaba |

### Muted Orange (136-143)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 136 | 68 | 50 | 33 | #443221 |
| 137 | 98 | 71 | 47 | #62472f |
| 138 | 127 | 93 | 61 | #7f5d3d |
| 139 | 157 | 114 | 75 | #9d724b |
| 140 | 179 | 136 | 97 | #b38861 |
| 141 | 193 | 158 | 127 | #c19e7f |
| 142 | 207 | 181 | 156 | #cfb59c |
| 143 | 221 | 203 | 186 | #ddcbba |

### Muted Yellow (144-151)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 144 | 68 | 65 | 33 | #444121 |
| 145 | 98 | 93 | 47 | #625d2f |
| 146 | 127 | 121 | 61 | #7f793d |
| 147 | 157 | 149 | 75 | #9d954b |
| 148 | 179 | 171 | 97 | #b3ab61 |
| 149 | 193 | 186 | 127 | #c1ba7f |
| 150 | 207 | 202 | 156 | #cfca9c |
| 151 | 221 | 218 | 186 | #dddaba |

### Muted Green (152-159)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 152 | 33 | 68 | 33 | #214421 |
| 153 | 48 | 98 | 47 | #30622f |
| 154 | 62 | 127 | 61 | #3e7f3d |
| 155 | 77 | 157 | 75 | #4d9d4b |
| 156 | 99 | 179 | 97 | #63b361 |
| 157 | 128 | 193 | 127 | #80c17f |
| 158 | 157 | 207 | 156 | #9dcf9c |
| 159 | 186 | 221 | 186 | #baddba |

### Muted Blue (160-167)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 160 | 33 | 47 | 68 | #212f44 |
| 161 | 47 | 67 | 98 | #2f4362 |
| 162 | 61 | 88 | 127 | #3d587f |
| 163 | 75 | 108 | 157 | #4b6c9d |
| 164 | 97 | 130 | 179 | #6182b3 |
| 165 | 127 | 153 | 193 | #7f99c1 |
| 166 | 156 | 177 | 207 | #9cb1cf |
| 167 | 186 | 200 | 221 | #bac8dd |

### Muted Purple (168-175)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 168 | 50 | 33 | 68 | #322144 |
| 169 | 72 | 47 | 98 | #482f62 |
| 170 | 94 | 61 | 127 | #5e3d7f |
| 171 | 116 | 75 | 157 | #744b9d |
| 172 | 138 | 97 | 179 | #8a61b3 |
| 173 | 160 | 127 | 193 | #a07fc1 |
| 174 | 182 | 156 | 207 | #b69ccf |
| 175 | 203 | 186 | 221 | #cbbadd |

### Blue-Grey (176-183)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 176 | 30 | 38 | 45 | #1e262d |
| 177 | 51 | 64 | 76 | #33404c |
| 178 | 71 | 89 | 107 | #47596b |
| 179 | 91 | 115 | 137 | #5b7389 |
| 180 | 117 | 141 | 163 | #758da3 |
| 181 | 147 | 166 | 183 | #93a6b7 |
| 182 | 178 | 191 | 203 | #b2bfcb |
| 183 | 209 | 217 | 224 | #d1d9e0 |

### Steel Blue (184-191)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 184 | 24 | 38 | 51 | #182633 |
| 185 | 41 | 64 | 86 | #294056 |
| 186 | 58 | 90 | 120 | #3a5a78 |
| 187 | 74 | 116 | 154 | #4a749a |
| 188 | 100 | 141 | 180 | #648db4 |
| 189 | 134 | 166 | 196 | #86a6c4 |
| 190 | 168 | 192 | 213 | #a8c0d5 |
| 191 | 203 | 217 | 230 | #cbd9e6 |

### Teal-Grey (192-199)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 192 | 30 | 45 | 45 | #1e2d2d |
| 193 | 51 | 76 | 76 | #334c4c |
| 194 | 71 | 107 | 107 | #476b6b |
| 195 | 91 | 137 | 137 | #5b8989 |
| 196 | 117 | 163 | 163 | #75a3a3 |
| 197 | 147 | 183 | 183 | #93b7b7 |
| 198 | 178 | 203 | 203 | #b2cbcb |
| 199 | 209 | 224 | 224 | #d1e0e0 |

### Deep Teal (200-207)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 200 | 24 | 51 | 51 | #183333 |
| 201 | 41 | 86 | 86 | #295656 |
| 202 | 58 | 120 | 120 | #3a7878 |
| 203 | 74 | 154 | 154 | #4a9a9a |
| 204 | 100 | 180 | 180 | #64b4b4 |
| 205 | 134 | 196 | 196 | #86c4c4 |
| 206 | 168 | 213 | 213 | #a8d5d5 |
| 207 | 203 | 230 | 230 | #cbe6e6 |

### Gold / Amber (208-215)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 208 | 68 | 51 | 5 | #443305 |
| 209 | 114 | 84 | 10 | #72540a |
| 210 | 159 | 117 | 17 | #9f7511 |
| 211 | 204 | 148 | 26 | #cc941a |
| 212 | 230 | 171 | 47 | #e6ab2f |
| 213 | 241 | 188 | 79 | #f1bc4f |
| 214 | 254 | 206 | 109 | #fece6d |
| 215 | 255 | 225 | 138 | #ffe18a |

### Cool Grey (216-223)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 216 | 40 | 40 | 50 | #282832 |
| 217 | 68 | 68 | 78 | #44444e |
| 218 | 97 | 97 | 107 | #61616b |
| 219 | 125 | 125 | 135 | #7d7d87 |
| 220 | 154 | 154 | 164 | #9a9aa4 |
| 221 | 182 | 182 | 192 | #b6b6c0 |
| 222 | 211 | 211 | 221 | #d3d3dd |
| 223 | 240 | 240 | 250 | #f0f0fa |

### Earth Brown (224-231)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 224 | 38 | 23 | 12 | #26170c |
| 225 | 68 | 41 | 22 | #442916 |
| 226 | 98 | 60 | 32 | #623c20 |
| 227 | 128 | 78 | 42 | #804e2a |
| 228 | 158 | 97 | 52 | #9e6134 |
| 229 | 188 | 115 | 62 | #bc733e |
| 230 | 200 | 136 | 91 | #c8885b |
| 231 | 210 | 158 | 121 | #d29e79 |

### Natural Green (232-239)

| Idx | R | G | B | Hex |
|-----|---|---|---|-----|
| 232 | 21 | 36 | 14 | #15240e |
| 233 | 36 | 63 | 24 | #243f18 |
| 234 | 51 | 89 | 34 | #335922 |
| 235 | 67 | 116 | 44 | #43742c |
| 236 | 82 | 142 | 54 | #528e36 |
| 237 | 97 | 169 | 64 | #61a940 |
| 238 | 115 | 188 | 80 | #73bc50 |
| 239 | 136 | 198 | 107 | #88c66b |

### Near-Black Shades (240-255)

| Idx | Group | R | G | B | Hex |
|-----|-------|---|---|---|-----|
| 240 | Dark Red | 16 | 0 | 0 | #100000 |
| 241 | Dark Red | 24 | 4 | 4 | #180404 |
| 242 | Dark Red | 32 | 8 | 8 | #200808 |
| 243 | Dark Red | 40 | 12 | 12 | #280c0c |
| 244 | Dark Blue | 0 | 0 | 16 | #000010 |
| 245 | Dark Blue | 4 | 4 | 24 | #040418 |
| 246 | Dark Blue | 8 | 8 | 32 | #080820 |
| 247 | Dark Blue | 12 | 12 | 40 | #0c0c28 |
| 248 | Dark Yellow | 8 | 8 | 0 | #080800 |
| 249 | Dark Yellow | 16 | 16 | 4 | #101004 |
| 250 | Dark Yellow | 24 | 20 | 8 | #181408 |
| 251 | Dark Yellow | 32 | 28 | 12 | #201c0c |
| 252 | Dark Teal | 4 | 8 | 10 | #04080a |
| 253 | Dark Teal | 8 | 16 | 20 | #081014 |
| 254 | Dark Teal | 12 | 24 | 28 | #0c181c |
| 255 | Dark Teal | 16 | 32 | 36 | #102024 |

### Palette Organization Summary

| Index Range | Group | Description |
|-------------|-------|-------------|
| 0-15 | C64 Standard | Original VIC-II colors (backward compatible) |
| 16-31 | Grayscale | 16-step pure grey ramp |
| 32-63 | Browns | 4 ramps: warm, cool, rust, sienna |
| 64-127 | Pure Hues | 8 ramps: red, orange, yellow, green, cyan, blue, violet, magenta |
| 128-175 | Muted Hues | 6 ramps: red, orange, yellow, green, blue, purple (desaturated) |
| 176-207 | Cool Tones | 4 ramps: blue-grey, steel blue, teal-grey, deep teal |
| 208-239 | Specialty | Gold/amber, cool grey, earth brown, natural green |
| 240-255 | Near-Black | 4 groups of 4: dark red, dark blue, dark yellow, dark teal |

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
