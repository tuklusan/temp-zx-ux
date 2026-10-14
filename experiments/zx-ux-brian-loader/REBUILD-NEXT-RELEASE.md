# Rebuild future ZX-UX releases

Unzip the offline toolset or use this directory in the repository.

Requirements: Python 3.9+; no assembler, pip packages, game tape or internet.

Run:

```sh
python3 release.py /path/to/new-kernel-and-filesystem.tap --name ZX-UX-v1.1
```

A standard-speed Spectrum TZX (.tzx containing only 0x10 blocks) also works.

This creates `output/ZX-UX-v1.1.tzx`, a single-file `.tzx.zip`, a JSON
manifest containing the source/builder/text SHA256 digests, and a
`.SHA256SUMS.txt`. The result is deterministic for the same input bytes,
text, and builder. The resulting TZX has 24 0x11 turbo data blocks with
**zero inter-block pause**, 247 short Brian-style pilot pulses per block,
and the original four ROM-safe bootstrap pauses.

Source CODE segments must start at 0x6000, be contiguous, and fit below
the loader's protected stack. The 24 progress lines (32 ASCII columns
each) are kept separately in `text-lines.txt`.

The command statically verifies the exact reconstructed kernel and
filesystem payload, checksums, ZIP contents, and the generator's unit
tests. It does **not** replace a Fuse no-fastload boot proof. The GitHub
workflow `.github/workflows/zxux-brian-loader-fuse.yml` automates that
proof, including checks at the beep and entry PC=0x6000. The first
successful gapless runtime test is
https://github.com/tuklusan/temp-zx-ux/actions/runs/38641939636 .

Historical hashes in PINNED-VERSIONS.json and RELEASE-VERIFIED.md refer
to the earlier 400ms-gap tape; each new release gets new generated hashes.
