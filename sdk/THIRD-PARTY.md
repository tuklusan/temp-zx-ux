# Third-party components in the SDK

The SDK tools (`rcc`, `ras`, `rld`, `rtap`, `rvm`) need only Python 3.11 or
later.  Two parts of the SDK are not ZX-UX code and are not covered by the
ZX-UX licence.

## z80-python 0.4.0 (`z80_python/`)

- What: a pure-Python Z80 instruction core.  `zxcore.py` runs the 48K ROM
  on it for `rcc`'s float constants and for `rvm`.
- Source: PyPI `z80-python` 0.4.0, https://github.com/alewman/z80-python
  (sdist `z80_python-0.4.0.tar.gz`, SHA-256
  `8bdb3052d8f1a409a07f5f92022a5af65f0d5a59b4e30b10f4f83431a43bd59e`).
- Licence: MIT, `Copyright (c) 2026 alewman`; the full text is
  `z80_python/LICENSE` and must stay with the files.
- Changes: none.  `z80_python/` is the package directory `src/z80_python/`
  of that sdist, byte for byte.  The SDK's speed-ups are in its own file
  `z80fast.py` (handlers generated per opcode, checked equal to the core's
  by `tests/test_z80fast.py`), not in the vendored code.
- File checksums (SHA-256):

```
5ed6b21b2cca09a29a3b3434f83c6f34731a6e95e2d7ae1afc90f4f598228db5  __init__.py
17ec8fd42374b0838f4b5055303d443adc400dc74b09a066073bc1d76d6011b6  __main__.py
32afb0f6d543ae875cbac18499f9948368ae9f9f08cca102cdae6997cf5e689f  _alu.py
1911050ec97c77ab4a270d4afee516629d3daf75d00e7c6f7d6b514a67b5a5b2  _blocks.py
43cc5f1f5a1ce672b9703c9aa5627b8cc1779a998bf624876323c5226f5c8f3b  _control.py
76babb10515e925b971bb0387645857327f4fb67ca8cc9c04ffd0a74ec890692  _core.py
ff29d0aec7b5aded030a627aaca882f70f2d2f130697d45d3ba49d4cdf7edf48  _dispatch.py
25381bb37800aedb8e544e06e3982e8ae3ec7ab8de6e49303f1bf406ed37c785  _flags.py
3de9ac26302ac6d07908c66d23d8833abacbc6b0e0a262bcfc98ff19bb749fdf  _index.py
d7bf9a2e71b5ec95a97bbacceab2cf989b8d52531c0e9db418bc81e9302d1b7b  _index_dispatch.py
5f116bf8d8503945e8d548b6624c2d24d7b0177851b22eb972294558812dca90  _io.py
7256aca97b1d28c029c0bddc12ad412455a05361b9fbcdf5a4cfa4062bdab6dd  _loads.py
b88cfbdbd0a4c68df8be11c94a59d5053ead01e18755ae148572d586c663a51c  _rotate.py
2e78c99800850e02293d41ae4dfbe8ce13f0da536716aa35786bed3ccb404a2e  conformance.py
94b82dc867c62e4fcd41b9c3765686d78e8925fe60b51b17b31c860a108fe3f3  console.py
dcd77967522f4df1c33a779f4be4a21510a95f6b7a7f1e152f263418bc3f6fe9  cpu.py
cd578d7ece7c645636a885b1f9dd9c9579890382b7000c20461a697eeae45f4e  debug.py
8e9e08a118aff8d5f68b453e929227a9dd0e5c4c91169f4eb0291a47d5626145  disasm.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  py.typed
f6c0efb62674d5453dda6d5aa75b44a515fb24ee96afb8232f5160f0cadf6ca3  state.py
8108a7a943adaa1194d847405acc3b1064caa264441b390e0beb91c5cb7e80a8  trace.py
```

## Sinclair ZX Spectrum 48K ROM (`rom/48.rom`)

- The original 16,384-byte ROM, SHA-256
  `d55daa439b673b0e3f5897f99ac37ecb45f974d1862b4dadb85dec34af99cb42`, the
  same bytes as the repository's `rom/48.rom`, unchanged.
- Copyright remains with its rights holder (historically Sinclair Research,
  then Amstrad plc).  Amstrad allows the ROM to be distributed with
  emulators provided its copyright messages are not altered; it must not be
  sold separately.  See the third-party notice in the repository `LICENSE`
  and https://github.com/z00m128/zxs-rom/blob/master/LICENSE.md

`rom/font4x8.bin` is the ZX-UX 4x8 font (a copy of `src/font4x8.bin`),
ZX-UX's own.
