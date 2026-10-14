# ZX-UX — Complete offline compact TZX builder

**A Python-only, no-network build kit** for making a ZX Spectrum 48K TZX from an updated `ZX-UX.tap` source.

The Python builder contains a **bit-for-bit copy of the known Fuse-verified ZQLoader bootstrap**, including the timing patches. You do not need to install an assembler, download ZQLoader, or install Fuse just to **build** the TZX. The included inspector checks the resulting format and payload independently. Only a new **runtime proof** requires a ZX Spectrum / compatible emulator.

## 1. Build a new tape (Linux, macOS, Windows)

Requires **Python 3.9 or later**. No `pip install` needed.

Put your updated `.tap` anywhere accessible to this computer and run, from this kit's root:

```sh
python3 build_tzx.py /path/to/your-new-ZX-UX.tap --out output/zx-ux-new-loader-test.tzx
python3 inspect_tzx.py output/zx-ux-new-loader-test.tzx --source /path/to/your-new-ZX-UX.tap
```

On Windows, replace `python3` with `py -3` and provide a Windows path:

```bat
py -3 build_tzx.py C:\ZX\ZX-UX.tap --out output\zx-ux-new-loader-test.tzx
py -3 inspect_tzx.py output\zx-ux-new-loader-test.tzx --source C:\ZX\ZX-UX.tap
```

The builder produces **three files**:

| File | Use |
| --- | --- |
| `output/zx-ux-new-loader-test.tzx` | Normal, compact TZX tape image |
| `output/zx-ux-new-loader-test.tzx.zip` | Portable ZIP containing the TZX |
| `output/zx-ux-new-loader-test.tzx.manifest.json` | Input hashes, payload, settings, and all 24 segment addresses |

The builder **replaces only the payload**, not the verified loader. Do not manually patch the included bootstrap.

## 2. What a replacement source TAP must contain

- A valid ZX Spectrum **TAP**, containing at least one standard **CODE header and matching CODE data block**. Two code blocks like the original are supported; more CODE blocks are supported too.
- CODE blocks must be **contiguous in RAM**, in their tape order, beginning at **`0x6000`** by default.
- The complete payload must end **before `0xFF47`**, where the turbo-loader lives after it relocates. This allows up to **40,775 bytes** from `0x6000` through `0xFF46`.
- Source CODE payload may change in **size, bytes, CODE block split, and filenames**. There is **no hardcoded 24,670-byte requirement** or fixed expected source TAP SHA in this offline builder.
- Old BASIC or other non-CODE header/data pairs are validated but intentionally **not copied**. The TZX always starts with the verified loader's own BASIC bootstrap.
- Bad Spectrum XOR checksums, missing/mismatched header/data pairs, a gap between CODE addresses, or overwrite of the resident loader cause a clear build failure.

The default 24 segments require at least 24 bytes of payload. The optional `--segments N` and `--entry 0x...` overrides are supported but **not runtime-certified** for configurations other than 24 segments and entry `0x6000`.

**Important:** Replacing the payload does not make arbitrary code safe or runnable. The new payload must itself be valid Z80 code with a useful entry point at `0x6000`. The builder only guarantees tape construction and placement; each new payload should be tested in Fuse or on a real machine.

## 3. Preserved, previously proven loader settings

| Setting | Value |
| --- | --- |
| Machine | ZX Spectrum 48K |
| Execution entry | `0x6000` |
| Bit 0 time | 1,140 T-states (one edge) |
| Bit 1 time | 2,280 T-states (one edge) |
| Data rate | 1.5× standard complete-bit time |
| Segments | 24 by default |
| Leader/pilot | 450 T-states per edge, 1,600 edges (~206 ms) |
| Header sync | 250 + 499 T-states |
| Payload minisync | 501 T-states |
| Pause between segments | 20 ms |
| Header | 17 bytes, with ZQLoader checksum and after-block dispatch |
| TZX format | Standard v1.20, block `0x10` + compact `0x19` generalized data + `0x20` pause |

**No pulse-expanded `0x13` TZX blocks** are produced.

## 4. Validate the kit offline

```sh
python3 -m unittest discover -s tests -v
python3 build_tzx.py examples/reconstructed-reference.tap --out output/rebuilt-reference.tzx
python3 inspect_tzx.py output/rebuilt-reference.tzx --source examples/reconstructed-reference.tap
```

The rebuilt reference must have this exact SHA-256:

```
4c548d0c355fe4912dfb0da0a1fa85b450bddd9393883c885166e2246b02cb12
```

This matches `reference/verified-zx-ux.tzx` **byte-for-byte**. Check with:

```sh
python3 -c "import pathlib; assert pathlib.Path('output/rebuilt-reference.tzx').read_bytes() == pathlib.Path('reference/verified-zx-ux.tzx').read_bytes(); print('EXACT MATCH')"
```

`examples/reconstructed-reference.tap` is an **example reconstructed from the verified TZX**, split into two CODE blocks. It contains the exact **verified payload bytes**, but it **is not the original source TAP** (its TAP file metadata and SHA differ). The exact original source TAP lives in the private repository under `experiments/zx-ux-loader-6000-fuse/ZX-UX.tap`.

## 5. Know what is (and isn't) verified

The included `reference/verified-zx-ux.tzx` was **actually executed in Fuse 1.6.0** with real tape speed and acceleration disabled. The passing run reached hard debugger PC=`0x6000` and read the correct first 16 payload bytes. The full evidence and CI workflow are preserved in the repository.

- Verified GitHub Actions run: https://github.com/tuklusan/temp-zx-ux/actions/runs/38586716509
- Original source TAP SHA-256: `4f18817a198c7e6ad3a44b12503c112c204968bae207214bc74c4384dedb6fb9`
- Verified TZX SHA-256: `4c548d0c355fe4912dfb0da0a1fa85b450bddd9393883c885166e2246b02cb12`
- Verified payload SHA-256: `ab81f6b8fe419e92b674a603c752bfb5d704be1768d748ff9309680fca68daf2`
- Verified loader reached `0x6000` at frame 5,865 (~117.3 seconds at 50 Hz).

**An offline inspection pass is not a substitute for testing the newly generated tape in Fuse.** A replacement may change what the payload itself does at startup.

## 6. Bundle files

| Path | Purpose |
| --- | --- |
| `build_tzx.py` | Offline builder; embedded pinned loader bootstrap, strict source validation, deterministic ZIP |
| `inspect_tzx.py` | Independent compact TZX header/pulse/data/checksum/dispatch validator |
| `tests/test_offline.py` | Automated offline regression suite |
| `examples/reconstructed-reference.tap` | Test-input TAP using exact historical payload, reconstructed TAP metadata |
| `reference/verified-zx-ux.tzx` | Known-good, Fuse-tested TZX |
| `reference/verified-bootstrap.tap` | Exact timing-patched BASIC/Z80 ZQLoader bootstrap (also embedded in builder) |
| `reference/payload.bin` | Extracted original payload bytes for independent comparison |
| `reference/VERIFIED-ACCEPTANCE.md` | Runtime evidence and SHA records |
| `reference/UPSTREAM-PROVENANCE.md` | Exact ZQLoader commit and runtime toolchain sources |
| `licenses/zqloader-MIT.txt` | Upstream loader license notice |
| `PINNED-SHA256SUMS.txt` | Hashes for immutable reference files |
| `output/` | Deterministically generated files, including a tested demo build |

## 7. Reproduce a real-speed Fuse runtime test (optional)

The offline builder is self-contained. For emulator testing, use the repo workflow
`.github/workflows/zxux-loader-6000-fuse.yml`, which pins Fuse/ROM packages and
checks execution at PC=`0x6000`. It deliberately uses `--no-traps`,
`--no-fastload`, and `--no-accelerate-loader`, sends real Spectrum `LOAD ""`
keystrokes, and starts tape playback with F8. **Do not add ROM, tape-event, or
RAM-write breakpoints during tape playback**: earlier attempts showed they
could disturb loading. The accepted test uses only the final PC breakpoint and
a timeout breakpoint.

The emulator and Sinclair ROM are **not included** in this ZIP. They are not
required for offline generation, and each may have distribution conditions.

---

This kit is for ZX-UX code placed at `0x6000`. No cloud runner, GitHub access,
network, external compiler, or online license activation is required to build
or statically verify the TZX.