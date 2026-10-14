# ZX-UX compact loader transport: prior-release reference comparison

These are technical comparison notes, not a copy of the earlier REV17 release.
The user-supplied reference sources are for studying how the earlier 8K
fastloader worked, *not* for altering the 24,670-byte 0x6000 payload, requested
1.5x tape bit speed or 0x6000 entry point.

## Shared format
- Bootstrap: two standard-speed TZX 0x10 tape blocks.
- Turbo: 24 segments, each with a 17-byte ZQLoader header and data; 48
  TZX 0x19 generalized-data blocks altogether.
- Header check: start E=1; add each byte to E (modulo 256) and rotate E
  left by one bit.
- Intermediate after-block word 0x0100 means load next segment.
- Final after-block dispatch in the supplied reference ultimately reaches
  0xE003 after its display finalizer. Current test must reach **0x6000**.
- Older reference interleaves 24 status-row callbacks; current experiment
  does not include those callbacks. They are not needed to decode turbo data.

## Differences needing real-speed proof
- Reference build.py preserves an immutable known-good TZX seed's exact
  pilot/sync symbols and patches its payload and header checks. The user's
  seed file input/known-good-white-on-black-e003.tzx.b64 and
  src/print_hook.asm were not among the uploaded files. Bytewise timing
  comparison against that seed is not possible without the seed itself.
- This experiment generates 0x19 generalized data using 400-T-state leader
  pulses, now 800 edges (~91 ms), and bit pulses zero=1140, one=2280.
- Pinned upstream zqloader/turboblock.h uses leader patterns 500/500 T-states
  with 200 ms default leader, plus sync 250/499 and minisync 501. The
  different current leader is a hypothesis to test, not a proven match.
- Upstream tzxwriter.cpp encodes one-edge-per-bit compact data with
  npd=1, asd=2 only when extra end-of-byte delay is zero. An alternative
  256-symbol-per-byte encoding implements extra delay at greater size.
- Upstream may insert short pauses between sections for processing time.
  Current builder uses 20 ms between segments.

## Proof gate
Source TAP SHA-256:
4f18817a198c7e6ad3a44b12503c112c204968bae207214bc74c4384dedb6fb9

24,670 exact bytes into 0x6000–0xC05D. The TZX must remain compact and must
be run in Fuse 1.6.0 at real tape speed with disabled acceleration, finishing
with a hard debugger PC=0x6000 proof and preferably RAM byte comparison.
Unsuccessful diagnostics must never be called a functional release.
