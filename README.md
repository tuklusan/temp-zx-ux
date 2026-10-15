# ZX-UX for the Sinclair ZX Spectrum 48K

ZX-UX brings a small UNIX v1-style system to the 48K ZX Spectrum.
It uses new Z80 code and the Spectrum ROM.
It runs on a real 48K machine or a compatible emulator.

The system boots from a cassette image. It shows the ZX-UX UNIX v1
banner, the copyright mark, the measured kernel and free-memory values,
and then the `login:` prompt. The boot uses the 64-column text screen.
Enter any name with up to eight characters. There is no password.
All sessions have the same user rights.

ZX-UX has a shell, a file system in RAM, a 64-column text screen,
and a preemptive scheduler. Four processes can exist at once.
The clock interrupts the CPU at 50 Hz.
The kernel fits in an 8 KB block at address `6000h`.

## Start the system

Open `build/ZX-UX.tzx` or `build/ZX-UX.tap` in your emulator.
Load it through the Spectrum's tape loader.
Log in when the prompt appears.
You can then use commands such as `ls`, `cat`, `ps`, `top`, `vi`, and `tar`.

ZX-UX keeps files and program images in one memory area.
This area grows and shrinks as programs run and files change.
The `zxpack` command can pack files to save RAM.
Files that are idle may also be packed when space runs low.

The shell runs `cd` (or `chdir`), `kill PID`, `exec CMD`, `sh FILE` and
`login` itself, without a separate process, so they work even when all
four process slots are taken. `exit` or `logout` ends the shell and
returns to `login:`. Inside a command file run with `sh FILE`, `exit`
ends that file. Background jobs keep running after you log out; stop
them with `kill`.

The system supports one terminal and one user.
It can switch among four processes without help from the shell.
A C48 program may draw on the screen while a shell command runs below it.
Two C48 programs may also share the screen.

## Main build

You need Python 3 and `sjasmplus`.
Run these commands from the root of the source folder:

```sh
python3 tools/build.py
```

If the assembler is not on your search path, give its path:

```sh
python3 tools/build.py /path/to/sjasmplus
```

The main build writes five files:

| File | What it contains |
|---|---|
| `build/ZX-UX.tzx` | Boot tape in TZX form |
| `build/ZX-UX.tap` | Boot tape in TAP form |
| `build/unix.bin` | Z80 system image |
| `build/fs.img` | Starting RAM file system image |
| `build/kernel.json` | The kernel's SHA-256 and the addresses `sdk/rvm` reads |

The assembler also writes `src/unix.sym` and `src/unix.bin`.
The build generates `src/ptab.inc` from the program list. It also
writes `build/bootinfo.inc` with the measured kernel size, free space,
and process count. The assembler repeats until those figures agree
with the finished image. They are not guessed banner values.
These files are build inputs and working files, not tape releases.

## C48 programs

ZX-UX includes tools for a small C language called C48.
The compiler, linker, assembler, cassette writer, and VM live in `sdk/`.
The checked-in `programs/c48/` source collection supplies the example programs.

```sh
python3 sdk/lib/build.py
sdk/bin/rcc game.c -o game.ssx
sdk/bin/rtap -o game.tzx game.ssx
```

The first command builds `sdk/lib/libc48.ssa`.
The other commands compile a C48 program and make a cassette record.
The SDK needs only Python 3.11 or later; `sdk/bin/rvm game.ssx` runs the
program on an emulated Spectrum that boots this ZX-UX (see `sdk/README.md`).

On ZX-UX, type `/dev/cassette/game` and play the program tape.
`/dev/cassette/*` runs the first program on the tape, whatever its name.
You can add program arguments after the name.
Start some programs with `&` to keep the shell running.

To build the included C48 program collection, run:

```sh
python3 tools/mktapes.py
```

Every run is a full rebuild: all programs are compiled afresh and a
file in `build/c48` that no program makes is removed (`build/c48` is
the tool's output: keep your own programs elsewhere).
`python3 tools/mktapes.py --check` changes nothing and fails if any
C48 program or tape in `build/` is not what a rebuild makes; CI and
`tools/mkrelease.py` run it, so stale programs are never committed or
released.

This writes the `c48/` program files and the following tapes:

- `build/c48-apps.tzx`, `build/c48-games.tzx`
- `build/c48-demos.tzx`, `build/c48-examples.tzx`
- `build/c48-multitask.tzx`: `hanoi` and `queens8`, then `mobius` and
  `torus`, built to run two at a time in the background
- `build/ZX-UX-c48.tzx`, which starts with the system boot tape

The test collection has 56 programs and 17 further test cases.
See `sdk/README.md` for details.

## Tests and snapshots

SkoolKit 10.1 and Pillow are needed for the host-side emulator tests.
The normal sequence is:

```sh
sh tools/t.sh
python3 tests/suite.py
python3 tools/mktapes.py
python3 tools/mtsnap.py
python3 tests/ssxrun.py
python3 sdk/tests/vm_checks.py --native
python3 sdk/tests/vm_checks.py --bytecode
python3 sdk/tests/test_rvm.py
python3 sdk/tests/test_rtap.py
python3 tests/rvm_corpus.py --native
python3 tests/rvm_corpus.py --bytecode
python3 tests/rvm_machine.py
xvfb-run -a python3 tests/rvm_gui.py        # needs Tk; any display will do
python3 tools/gallery.py
```

The C48 sources are included in `programs/c48/`.
Tests that make pictures may need their `--png` option.
See `WORKING-NOTES.md` for the full sequence and required paths.

The tests can write these files:

| Path | Purpose |
|---|---|
| `build/test.z80` | Snapshot after loading the boot tape |
| `build/ZX-UX-multitask.z80` | Two C48 programs running together |
| `build/ZX-UX-multitask.png` | Image of the shared screen |
| `build/c48/` | Compiled programs and individual tapes |
| `build/ssx/` | Programs used by the tests |
| `build/shots/`, `build/shots-vm/` | Test screenshots |
| `build/gallery.html` | Screenshot comparison page |
| `build/sizes.json` | Program size data |

## Release files

Use the release script from a clean committed checkout, with the
private checker and tools stored outside this source folder:

```sh
python3 tools/release_v1.py \
  --checker /private/checker.py \
  --sjasm /tools/sjasmplus \
  --tap2sna /tools/tap2sna.py \
  --fuse-test-command 'python3 -B tests/fuse_boot.py --fuse /tools/fuse-sdl --rom /tools/48.rom --tape build/ZX-UX.tzx --assets /tools/fuse-assets --libdir /tools/fuse-libs --screen build/proofs/fuse-login.png --expect-zxux-login'
```

The script checks the tools and source, builds the tapes and C48
programs, runs the emulator and SDK tests, checks real screenshots,
and copies approved files into `release/`. It then writes a manifest
with the source commit, byte sizes, SHA-256 hashes, and test results.
It stops before creating a release if a required check fails.

The copying helper `tools/mkrelease.py` does not run tests by itself.
Do not use it as proof that the system was tested.
Release files keep their native `.tzx`, `.tap`, `.z80`, `.ssx`, and
`.png` formats. The private checker and its list stay outside Git
and outside the release.

## Memory and system calls

The screen uses `4000h`–`5AFFh`.
System data occupies the space below the resident kernel.
The kernel starts at `6000h` and ends below `8000h`.
The program and file area shares the upper RAM with an execution window.

The system call entry is at `6003h`.
Put the call number in `A` and arguments in `HL`, `DE`, and `BC`.
A failed call sets carry and returns an error number in `A`.

For exact memory addresses and file layouts, read:

- `docs/SPEC-ELASTIC-R2.md` — current memory and executable formats
- `docs/SPEC-SDK-R2.md` — compiler, library, and C48 execution
- `docs/SPEC-ELASTIC-R1.md` — earlier memory design
- `docs/SPEC-SDK-R1.md` — earlier compiler design

The R2 files take precedence when an earlier plan differs from the code.
The source code is the final guide to what the current build does.

## Source tree

| Folder | Contents |
|---|---|
| `src/` | Z80 kernel, commands, font, and file system code |
| `sdk/` | C48 tools, runtime, and test settings |
| `tools/` | Build, tape, test, and inspection programs |
| `tests/` | System tests and test C programs |
| `docs/` | Memory and compiler design notes |

`src/font4x8.bin` uses the font-specific terms retained in the root `LICENSE`.
The 48K ROM at `rom/48.rom` has separate redistribution terms in that same file.

## Reproducing a checked release

The complete offline release command and required private tooling are
documented in `docs/REPRODUCIBLE-V1-RELEASE.md`. GitHub Actions is not
needed. `tools/release_v1.py` runs the mandatory independent FUSE proof
and uses only the current v1 C48 source tree. Historical visual
comparisons are optional and never gate the independent release workflow.
