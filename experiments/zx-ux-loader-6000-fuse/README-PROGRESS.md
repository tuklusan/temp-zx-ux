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
(including trailing spaces). The 24 provided rows are the legacy wording
*unchanged*, including its original E000/E003 values. Edit those labels in
the configuration file if you want them to match a new kernel build.

The display is rendered by direct writes to Spectrum bitmap and attributes,
so bottom rows 22 and 23 work. No ROM PRINT stream restriction applies.
All data frames use standard compact TZX 0x19, 450T pilot, 1140T/2280T
per data bit, and ZQLoader's 17-byte per-segment headers.

**The current user-supplied source TAP is unchanged** (SHA-256
4f18817a198c7e6ad3a44b12503c112c204968bae207214bc74c4384dedb6fb9).
The ZX Spectrum ROM screen shown after payload execution must be checked
in Fuse, not assumed from an offline-only byte comparison.

Provenance: ZQLoader upstream pinned commit
ca5913fb563be1903f70aab9e88b0497606769f4,
https://github.com/tuklusan/zqloader, MIT copyright Daan Scherft.
