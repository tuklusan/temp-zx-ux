# ZX-UX 24-line turbo TZX loader

Use Python 3 (standard library only) from this directory:

```sh
python3 build.py
python3 build.py path/to/new-tape.tap --text-lines text-lines.txt
python3 verify_tzx_display.py --tzx output/zx-ux-new-loader-test.tzx --source ZX-UX.tap --text-lines text-lines.txt
```

The first BASIC program header is exactly **ZX-UX UNIX** (10 bytes).
The border uses black and blue during turbo loading. The first generalized
data frame loads the direct-screen 24-line printer and configuration bytes
to free RAM at 0xC100. Its callback returns to ZQLoader 0x5CFA. The next 24
frames carry source payload and invoke one text row each. After row 24 the
printer jumps to entry 0x6000.

Each line in text-lines.txt must be exactly 32 printable ASCII characters
(including trailing spaces). The 24 progress rows are the exact corrected lines supplied with the new TAP.
The last row is drawn completely, followed by one ROM beeper tone for ~250 ms,
then a 500 ms silent hold before handoff to the kernel at 0x6000.

The display is rendered by direct writes to Spectrum bitmap and attributes,
so bottom rows 22 and 23 work. No ROM PRINT stream restriction applies.
All data frames use standard compact TZX 0x19, 450T pilot, 1140T/2280T
per data bit, and ZQLoader's 17-byte per-segment headers.

**The current user-supplied source TAP is unchanged** (SHA-256
9ff03bfbfcd33cc11e9a4f45b4197b67f0abb347052957bc36b74102eaf09004).
The ZX Spectrum ROM screen shown after payload execution must be checked
in Fuse, not assumed from an offline-only byte comparison.

Provenance: ZQLoader upstream pinned commit
ca5913fb563be1903f70aab9e88b0497606769f4,
https://github.com/tuklusan/zqloader, MIT copyright Daan Scherft.

New source CODE blocks: 21,702 bytes at 0x6000 and 3,100 bytes at 0xB4C6,
contiguous to 0xC0E1. This release must be verified against the normal-speed
reference boot/login screen after real-speed tape execution.
