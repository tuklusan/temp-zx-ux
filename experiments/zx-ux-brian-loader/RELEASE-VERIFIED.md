> Historical: the hashes and Fuse proof below are for the ORIGINAL 400ms-gap version, not the current gapless tape. Gapless runtime proof: https://github.com/tuklusan/temp-zx-ux/actions/runs/38641939636 .

# ZX-UX simple Brian-timed loader: VERIFIED RELEASE

**Real-speed Fuse 1.6.0 proof: PASS, 2026-10-14.**

Release build commit: `36bb787ee8c12e4a631faea342ac6e490eeb917e` on `main`.
Two independent real-time Fuse jobs passed:

1. Initial Brian-timed decoding proof: https://github.com/tuklusan/temp-zx-ux/actions/runs/38638743247
2. Final red-pilot / white-data border: https://github.com/tuklusan/temp-zx-ux/actions/runs/38639410838

Both runs used the original Spectrum 48K ROM and disabled Fuse fastload,
ROM traps and loader acceleration. Physical tape bits were decoded in Z80.

## Mandatory proof from the final run's raw `output/fuse.log`

```
0xC85E31            ; custom loader entry marker
0xD000              ; PC = 0xD000
0x18152AD           ; ROM BEEPER call site marker, exactly once
0xD064              ; PC = beep instruction
0xFA                ; DE = 250
0x197               ; HL = 407
0x190BC62           ; after-beep jump marker, exactly once
0xD06D              ; PC = final JP 0x6000
0x3939E70           ; kernel entry marker
0x6000              ; PC = 0x6000
0x190A              ; Spectrum frame count at handoff
0xC3 0xA8 0xB3 0xC3 0x76 0x64 0x21 0xB9
0xFF 0x11 0xBA 0xFF 0x01 0x3A 0x00 0x36
```

These 16 RAM bytes exactly match the supplied normal-speed ZX-UX source TAP.
CI captured (a) progress mid-load, (b) all 24 lines including the last line
at the beep, and (c) the ZX-UX `login:` screen after the jump. Source screenshots
and the full debugger log are checked in under
`experiments/zx-ux-brian-loader/output/`.

## Canonical hashes and format

- Normal-speed user source TAP SHA-256:
  `9ff03bfbfcd33cc11e9a4f45b4197b67f0abb347052957bc36b74102eaf09004`
- Corrected 24x32 line file SHA-256:
  `c487dbb686e03e4297cf15ba8ff31a32292932be102c95e81a61d7e2801ef269`
- **Final TZX SHA-256**:
  `d9dff423d4b378e3318c9ccea71f909168fc6d0512ec10844f37108301d944fe`
- Final TZX size: **26,520 bytes** (4 standard `0x10` bootstrap records,
  24 standard compact `0x11` turbo records).
- Target: 24,802 exact payload bytes at `0x6000-0xC0E1`, `JP 0x6000`.
- Program name: `ZX-UX UNIX` (exactly 10 bytes).
- Resident standalone machine-code loader at `0xD000`, 1,125 bytes.
- Brian second turbo block timing: 247 pilot edges at 2042T, sync 875/613T,
  zero bit 2x513T, one bit 2x1025T (approx 1.67x normal data speed).
- Short between-block recovery pause: 400 ms.
- Border uses RED/CYAN during the short pilot and WHITE/BLACK during data;
  no yellow/blue loader border.
- Beep: exactly one Sinclair ROM call at 0x03B5, DE=250 and HL=407;
  followed by 500 ms final line dwell.

## Offline build

```sh
python3 build.py --source ZX-UX.tap --text text-lines.txt \
    --output output/zx-ux-new-loader-test.tzx
python3 verify.py --tzx output/zx-ux-new-loader-test.tzx \
    --tap ZX-UX.tap --text text-lines.txt
python3 -m unittest -v test_build.py
```

This builder does **not** require ZQLoader, pip packages, a network connection,
external Z80 assemblers, or the original Brian Bloodaxe game tape. The
user-supplied game tape was used for its timing and edge-reader method only.

The release ZIP is an archive wrapping this TZX. A changed ZIP filename or
compression metadata does not change the canonical TZX SHA-256 above.
