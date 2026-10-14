# ZX-UX Final loader: release lock

Restored on 2026-10-14 to the exact known-good build source and runtime
verification workflow from GitHub Actions commit:
`e41853137ce058041450988d725c0d349a905b00`

## Verified result

- **Passing real-speed Fuse run**: https://github.com/tuklusan/temp-zx-ux/actions/runs/38611069862
- **TZX SHA-256**: `e0880bc45b7fb575c887c50b95efd540e8f584448d9205d687de54bcb3414af5`
- **TZX length**: 28,288 bytes
- **Source TAP SHA-256**:
  `4f18817a198c7e6ad3a44b12503c112c204968bae207214bc74c4384dedb6fb9`
- **Payload**: 24,670 bytes loaded contiguously to 0x6000–0xC05D
- **Turbo segments**: 1 resident display installer, then 24 source segments,
  all compact TZX 0x19; 17-byte headers
- **Pilot**: 450 T-states × 1,600 edges
- **Bit durations**: 1,140 / 2,280 T-states
- **Pause**: 350 ms between turbo transfers
- **BASIC program name**: `ZX-UX UNIX` (exactly 10 characters)
- **Loading border**: black and blue
- **Progress**: 24 configurable, 32-column screen rows from `text-lines.txt`;
  draws on bottom two rows without ROM PRINT channel problems
- **Required PC proof**: `0x6000` plus the first 16 RAM bytes
- **Queue**: all project workflows share the same 1-running/1-pending concurrency
  group on `main`

## Source consistency

Do **not** use the later experimental 2,400-edge/1,000-ms configuration.
That revision failed CI and differs from the passing TZX. The version of
`build.py` in this commit is reverted to the passing `e41853137` source.
The workflow is likewise based on the passing configuration and now checks
the canonical TZX SHA-256 before it starts Fuse.

For portable builds outside GitHub, the delivered
`ZX-UX-final-portable-build-package.zip` contains an independent, self-contained
Python 3.9+ builder split into `build.py`, `build_base.py`, and
`display_hook.py` plus an independent inspector, checksums, example tape,
and offline tests. Its output was rebuilt in a clean extraction and matched
the above SHA byte-for-byte.

## Screen verification scope

The passing run proves that loader progress is visible and that control
reaches the requested entry. The captured final screenshot still showed the
24-line loader status display; the separate ZX-UX `login:` screen was
**not** captured or proven by the passing test. Do not infer kernel
application-level success from the debugger entry proof alone.
