# Timing extracted from user-provided Brian_Bloodaxe.tzx

Source attachment SHA-256:
`f90eaa3f5e8686217de1862ced82f16789f562932cf0a3ac010253b1fab85a5a`

It is a TZX v1.10 tape (`ZXTape!`) of 49,281 bytes, containing:

- one 0x32 archive-info block,
- five normal-speed 0x10 blocks (BLOODAXE BASIC header/data, BRIAN BASIC
  header/data, trailing data),
- two standard compact 0x11 turbo-data blocks, **not** 0x19 generalized blocks.

The two 0x11 blocks have these *half*-pulse parameters:

| Parameter | block 1 | block 2 (used for ZX-UX) |
|---|---:|---:|
| pilot pulse (T states) | 2162 | **2042** |
| pilot count (edges) | 247 | **247** |
| sync 1 (T states) | 525 | **875** |
| sync 2 (T states) | 788 | **613** |
| zero half-bit (T states) | 543 | **513** |
| one half-bit (T states) | 1084 | **1025** |
| data length (bytes) | 6913 | 39281 |

The game's own 290-byte BASIC data block relocates ~256 bytes to `0xFF00`.
Its pulse detection calls the Sinclair ROM routines `0x05E3`/`0x05E7`, with
leader/sync detection and a per-byte XOR checksum. This project implements a
small dedicated relocated version of that read loop at `0xD000` and adds its
own fixed 24-block destination lengths plus a printable progress callback.
It does not include or load the game's own machine-code payload.

ROM disassembly documentation: https://skoolkid.github.io/rom/asm/05E3.html
