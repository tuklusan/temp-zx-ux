# ZX-UX 48K simple Brian Bloodaxe–timed TZX loader

This is **not ZQLoader**. It uses a small, resident Z80 tape decoder based on the
ROM edge-reading approach present in the *user-provided* `Brian_Bloodaxe.tzx`
bootstrap, plus the original Sinclair 48K ROM's `LD-EDGE-1/2` routines.

## Requirements

- Python 3.9 or later. **No assembler, pip packages, or internet required**
  for the offline builder and verifier.
- A ZX Spectrum 48K or compatible emulator that supports TZX `0x11` blocks.
- To validate a new payload at real tape speed: Fuse 1.6.0 with the original
  Sinclair 48K ROM (see `.github/workflows/zxux-brian-loader-fuse.yml`).

## Use

Place your replacement normal-speed tape in this directory as `ZX-UX.tap`,
then adjust `text-lines.txt` if desired (exactly 24 ASCII lines of 32 columns).
Run:

```shell
python3 build.py
python3 verify.py
python3 -m unittest -v test_build.py
```

Output: `output/zx-ux-brian-turbo.tzx` and
`output/zx-ux-brian-turbo.tzx.zip`.

This is a *new loader*, not a renamed Brian game tape. The tape data,
CODE layout, and progress lines are taken solely from your ZX-UX source.

## Timing and tape structure

- BASIC program header: `ZX-UX UNIX` (10 characters), autorun from line 10.
- Four standard-speed TZX `0x10` blocks: BASIC header/data and CODE header/data.
- Resident CODE loader is 1125 bytes at `0xD000`, no ZQLoader dependency.
- 24 compact TZX turbo blocks `0x11` (one per displayed line), with 247-pulse
  short pilot, 2042T pilot pulse, 875/613T sync and 513/1025T zero/one
  *half*-pulses (two half-pulses per bit). Each block includes the exact source
  bytes plus a one-byte XOR parity check; **no large pulse-stream blocks**.
- One 400ms pause between blocks gives time for text printing.
- The helper draws direct to the 24-row Spectrum display bitmap; the ROM's
  special bottom two rows are handled correctly, including the final line.
- Exactly one 250ms ROM beep, followed by 25 video-frame dwell cycles, then
  `JP 0x6000` (assuming a 50Hz Spectrum 48K clock).
- The source CODE blocks must be contiguous from `0x6000` and fit below the
  reserved stack at 0xCEFF. The original source's BASIC program is not copied;
  it is replaced by this loader program.

## Loading border

The ROM edge reader toggles complementary border colours on each tape edge.
To avoid the old yellow/blue pair without adding a larger pulse reader,
ZX-UX uses red/cyan during the short pilot and black/white during data.
The most visible data-loading border is black/white; red is visible during
inter-block synchronization. The underlying Brian timing is unchanged.

## Verification status

Static verifier and unit tests verify exact payload reconstruction, bit timing,
checksums, text, program name, and memory bounds. Runtime acceptance is more
strict: Fuse must reach `PC=0x6000`, and the first payload bytes in RAM must
match the TAP. The after-boot kernel screen and final row need screenshot
inspection. Do not claim success before those checks pass.

## Source/provenance

The Brian game tape was supplied by the user for reference; only technical
framing and its loader's ROM-edge decoding method were adapted. The game
payload is **not** redistributed as part of the generated ZX-UX TZX.
See `reference/BRIAN-FRAMING.md` for the actual source-block timing values.
