# ZX-UX C48 tools

These tools build and run small C48 programs for the ZX Spectrum 48K.
The compiler runs on your host computer, not inside ZX-UX.
The output is an SSX1 program that can run in the VM or load from tape.

## Make a program

The C48 runtime `lib/libc48.ssa` is included built.  After changing
`lib/`, rebuild it with `python3 sdk/lib/build.py`.

Compile a C file and make a cassette record:

```sh
sdk/bin/rcc hello.c -o hello.ssx
sdk/bin/rtap -o hello.tzx hello.ssx
```

Load `build/ZX-UX.tzx` and log in.
Type `/dev/cassette/hello` in ZX-UX, then play `hello.tzx`.

You can also test the same program on your host:

```sh
sdk/bin/rvm hello.ssx --png hello.png --text
```

The tools need only Python 3.11 or later and its standard library.
The compiler runs the real 48K ROM for float constants, and `rvm` runs
programs, on the Z80 core bundled in `z80_python/` (z80-python 0.4.0, MIT,
unmodified) with the faster handlers of `z80fast.py`; the ROM and the
4x8 font are in `rom/`.  See `THIRD-PARTY.md`.  `lib/libc48.ssa` is
checked in built; `python3 sdk/lib/build.py` rebuilds it.

## Included tools

| Tool | Use |
|---|---|
| `rcc` | Compile C48 source into SSX1 code |
| `ras` | Assemble Z80 source into SSO1 files |
| `rld` | Link objects and SSA1 libraries |
| `rtap` | Write programs to `.tap` or `.tzx` cassette files |
| `rvm` | Run compiled programs in the host VM |

C48 covers small integer types, five-byte Spectrum floats,
functions, pointers, arrays, recursion, and a set of library calls.
The runtime has a 64-column console, simple graphics,
keyboard and timing calls, strings, and a small heap.
See `include/c48.h` for the available functions.

## Run the examples

The C48 sources are checked in at `programs/c48/`. Run:

```sh
python3 tools/mktapes.py
```

The script writes compiled programs and tapes into `build/c48/`.
It also writes group tapes in `build/`.
Two programs can share the screen with `build/c48-multitask.tzx`.

The test settings are in `sdk/tests/runs.json`.
The collection has 56 named programs and 17 extra test cases.
Use `sdk/tests/oracle.py` for independent native and bytecode VM checks.
`sdk/tests/test_z80fast.py` checks that the fast Z80 handlers equal the
bundled core's, and `tests/c48-suite/` checks the toolchain against the
C48 Rev 0.11 specification paragraph by paragraph.
An old SDK comparison requires the explicit `--reference-sdk DIR` flag
and is not needed to build, run, or release ZX-UX.
Use `tests/ssxrun.py` to run programs from tape in ZX-UX.

## Separate compilation

`rcc -c` makes an SSO1 object; `rld -o prog.ssx a.sso b.sso lib/libc48.ssa`
links several.  Such a program gets the library's default heap (1024 bytes)
and UDG bank (32 slots): `--heap` and `--udgs` apply to whole programs built
by `rcc` alone.  Bytecode objects (`-c --bytecode`) use the library's full
SSB1 dispatch table, so they link with each other and with native objects.

## Program formats

`SSO1` holds a relocatable object.
`SSA1` holds a set of objects.
`SSX1` holds a linked program and its relocation data.
`SSB1` is the compact bytecode used for large programs.
For the byte layouts, read `docs/SPEC-SDK-R2.md` and
`docs/SPEC-ELASTIC-R2.md`.

The C48 source programs retain their attribution and licensing notices.
See `programs/c48/README.md` and the repository `LICENSE`.
