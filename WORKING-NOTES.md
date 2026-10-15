# ZX-UX working notes

These notes describe the ZX-UX v1 source and its build process.
They describe the expected build and the tests recorded before this import.
They do not claim a fresh test run.

## Main limits

The 48K ZX Spectrum leaves little spare RAM.
Keep the resident kernel at or below 8,192 bytes.
The current kernel fills 8,161 bytes.
A further 177 bytes of kernel (strings, the keyboard token table, the
tape clock routine and its variables) are loaded by the BASIC loader at
`5D98h`, below the kernel stack: block `lowk`, which costs the arena
nothing.
The kernel stack keeps at least 180 bytes above it.
The machine has four process slots and one terminal.
All logins have the same user rights.

The system uses its own cassette and program formats.
Their names start with `SS`: `SSO1`, `SSA1`, `SSX1`, `SSB1`, and `SST1`.
Do not change a format without updating its readers and writers.

Code changes must preserve the system call entry at `6003h`.
A resident program's 8-byte header is `jr .+8`, stack reserve, bss size,
entry. The stack reserve (at most `STKRES`) sizes the SAVE block that
holds the program's stack while another program has the window.
Use the Spectrum ROM where it is helpful.
Keep the private checker outside the source and Git folders.

## Source folders

`src/` holds the resident code and built-in commands.
`sdk/` holds the C48 tools and runtime.
`tools/` builds tapes and runs development checks.
`tests/` holds regression sessions.
`docs/` contains the R1 designs and the later R2 descriptions.

The R1 files record earlier design ideas.
R2 describes the later code and overrides R1 when they differ.

## Build inputs

Use Python 3, `sjasmplus` 1.24.0, SkoolKit 10.1, and Pillow.
The current C48 program collection is checked into `programs/c48/`.
Building it does not need an external or retired C48 SDK.

The main build needs only Python and the Z80 assembler.
The test snapshot needs SkoolKit's `tap2sna.py`.
The C48 compiler also uses SkoolKit for ROM-based float constants.

## Build sequence

Run these commands in the source root:

```sh
python3 tools/build.py /path/to/sjasmplus
python3 sdk/lib/build.py
sh tools/t.sh
python3 tools/mktapes.py
python3 tools/mtsnap.py
python3 tests/suite.py
python3 sdk/tests/vm_checks.py --bytecode
python3 tests/ssxrun.py
python3 tools/gallery.py
```

The screenshot tasks need their `--png` settings.
The output paths and tools are listed in `README.md`.
An unavailable external tool is a stop, not a test pass.

Older test records listed 20 passing system sessions,
73 passing C48 VM sessions in each compiler mode,
and 73 cassette program runs.
Those figures describe the older test run only.
Repeat the tests after changes to the source.

## Memory layout

| Address | Use |
|---|---|
| `4000h`–`5AFFh` | Spectrum display |
| `5B00h`–`5FFFh` | System data and low-memory work space; the low kernel at `5D98h` |
| `6000h`–`7FFFh` | Resident kernel, up to 8 KB |
| `8000h` onward | Resident commands and text; end varies by build |
| After resident text | Startup area (boot code and messages, at least 256 bytes: later the zxpack model), i-node table, and RAM file area |
| `F000h` onward | Execution window and process data |

The build prints exact addresses.
Do not rely on this table after changing program sizes.

## How programs share the screen

A C48 program can claim the full screen.
When the user types at the shell, the shell shows a small text strip.
The running program uses the area above that strip.
Two compatible programs can each draw in half of the screen.

The demo uses `hanoi` and `queens8`.
It runs both from one cassette image.
Their reduced stack sizes let them share the available RAM.

## Kernel size work

The existing development helpers live in `tools/dev/`.
Use `ksz.py` to inspect routine sizes.
Use `jr.py` to look for shorter relative jumps.
Use `dead.py` to find unused labels.
Use `sizes.py` for C48 code size comparisons.

Do not treat a smaller output as correct until its tests pass.

## Releases

The release tool copies finished files from `build/` into `release/`.
It does not make ZIP files.
Tapes, snapshots, screenshots, and logs keep their normal formats.
Only copy files that have passed the private checker.

Do not add the private checker or its rule list to Git.
Do not publish unfinished test logs as passed tests.

## Known limits

There are only four process slots.
Some background programs leave too little free RAM for another command.
A program that borrows the execution window may pause shell output.
The kernel has almost no room for another resident feature.
