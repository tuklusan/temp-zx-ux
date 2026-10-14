# ZX-UX 0x6000 compact TZX: real-speed Fuse acceptance

**Status: PASS — verified 2026-10-14 in GitHub Actions.**

- Run: https://github.com/tuklusan/temp-zx-ux/actions/runs/38586716509
- Run conclusion: `success`
- Fuse: **1.6.0** (Ubuntu pinned package `fuse-emulator-sdl=1.6.0+dfsg1-2build3`)
- ROM: authentic Sinclair 48K, from the SHA-256 pinned `spectrum-roms_20081224-5_all.deb`
- Execution: 48K machine, real tape timing; `--no-traps --no-fastload --no-accelerate-loader`; attached TZX played with F8.
- The debugger installs only the `PC=0x6000` breakpoint and a final time watchdog. No ROM, tape-event, or turbo memory-write breakpoints interrupt loading.

## Hard execution proof

The raw `output/fuse.log` from the passing run records:

```text
0x3939e70
0x6000
0x16e9
0xc3
0x40
0xb3
0xc3
0x76
0x64
0x21
0xb9
0xff
0x11
0xba
0xff
0x1
0x3a
0x0
0x36
```

The first line is the debugger's unique success marker (decimal `60006000`
printed as hex); the next is the actual Z80 PC. The 16 subsequent RAM bytes
exactly match the first 16 bytes of the canonical source payload.

The measured entry frame is `0x16E9` = 5,865 frames (~117.3 seconds at 50 fps).
The output `fuse-result.txt` is `ENTRY_6000`, and CI asserts both the marker
and the actual PC.

## Canonical source and output

- Source TAP: `experiments/zx-ux-loader-6000-fuse/ZX-UX.tap`
- Source TAP SHA-256: `4f18817a198c7e6ad3a44b12503c112c204968bae207214bc74c4384dedb6fb9`
- Reconstructed source payload SHA-256: `ab81f6b8fe419e92b674a603c752bfb5d704be1768d748ff9309680fca68daf2`
- Payload: 24,670 bytes, resident from `0x6000` to `0xC05D`
- Compact TZX SHA-256: `4c548d0c355fe4912dfb0da0a1fa85b450bddd9393883c885166e2246b02cb12`
- TZX size: **27,305 bytes**
- TZX layout: two 0x10 ROM bootstrap blocks; 24 pairs of 0x19 generalized-data header/payload blocks; 23 short 0x20 pauses
- Header: 17-byte ZQLoader-format header before each 24-way data segment
- Pilot: 450 T-states per pulse, 1,600 edges (~206 ms); sync 250/499, minisync 501
- Bits: **0 = 1,140 T-states; 1 = 2,280 T-states** (1.5x standard full-bit timing)
- Final post-copy dispatch: `0x6000`

The committed builder `build.py` deterministically rebuilds the TZX from the
committed TAP; the pinned workflow also checks the source SHA. The ZIP is a
container around that canonical TZX. Recompression may change the ZIP SHA due
to ZIP metadata; always compare the **TZX SHA** for canonical identity.

## Rebuild and verification

```sh
python3 experiments/zx-ux-loader-6000-fuse/build.py
sha256sum experiments/zx-ux-loader-6000-fuse/output/zx-ux-new-loader-test.tzx
```

The full passing debugger trace, screenshot, output hashes, and generated files
are committed alongside this record under `output/`. The workflow lives at
`.github/workflows/zxux-loader-6000-fuse.yml` and is serialized with the other
ZX-UX workflows on main (one active and at most one pending).
