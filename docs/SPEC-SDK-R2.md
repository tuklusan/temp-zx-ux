# ZX-UX: C48 Tools and Runtime, R2

This file describes the C48 tools and runtime used in version 2.
It explains the compiler, calling rules, libraries, and VM.
It also records the older test results. Those results need a fresh run
after source changes.

R2 takes precedence over R1. The memory layout and executable format
are described in `SPEC-ELASTIC-R2.md`.

## 1. Design choices

| # | Decision | In 2.0 |
|---|---|---|
| S1 | The compiler is a standalone Python tool on the host; no native compiler on ZX-UX | Done: `sdk/bin/rcc` |
| S2 | Source language: C48 Rev 0.11. The ZX-UX C48 SDK compiler is the behaviour reference; the ZX-UX implementation is independent | Done. Every corpus program gives the SDK reference VM's screen byte for byte (§8) |
| S3 | The SDK lives in the ZX-UX repository | `sdk/` |
| S4 | The compiler's output runs in the ZX-UX VM and goes to tape | One file, SSX1, does both: `rvm` runs the same file that `rtap` writes to cassette |
| S5 | Size strategy: (1) size-optimising native code, (2) SSB1 bytecode for what doesn't fit, (3) moving resident commands to tape in reserve | (1) and (2) done; the lever (3) was not needed (§9) |
| S6 | Acceptance: the whole corpus compiles and runs in the VM and on ZX-UX from tape, `ailmzx48` exempt, `queens8`/`hanoi` best effort | All 56 programs, including `queens8`, `hanoi`, `chess` and `write48`, pass in the VM and run on ZX-UX from tape (§8) |
| S7 (new) | Floats and BEEP are computed by the program itself, through the ROM | R1's `sys fp` and `sys beep` are not in the kernel (§5) |
| S8 (new) | A C program draws its own 64-column screen | R1's console colour codes are not in the kernel; the program claims the screen and draws into the display file (§5) |

## 2. Tools

    rcc  [-S|-c] [-o out] [--bytecode|--native] [--max BYTES] [--stack N] [--heap N] file.c
    ras  file.asm -> SSO1 object             rld  objects/archives -> SSX1
    rtap [-o out.tzx|.tap] [--after ZX-UX.tzx] prog.ssx[=NAME] ...     rtap --list tape ...
    rvm  [options] prog.ssx [args]     rvm --shell     rvm --syscall prog.ssx ...   (§7)

- **`rcc`** (`sdk/rcc/`) runs in this order:
  1. preprocessor and lexer (`lex.py`);
  2. parser and type checker, producing a typed AST (`parse.py`);
  3. the native Z80 generator (`z80gen.py`) or the bytecode generator (`bcgen.py`);
  4. `ras` and `rld`, which link it with the runtime archive `sdk/lib/libc48.ssa`.

  Float constants are folded by running the real ROM calculator in an emulated Z80 (`romfp.py`), so
compile-time and run-time results are bit-identical.
- **Native or bytecode:** a program is built native, unless its native image (image + bss + stack) would need more than `--max`, default 14,000 bytes — what ZX-UX can give a program loaded after login. Then it is rebuilt in bytecode, keeping the smaller. `--bytecode` and `--native` force the choice.
- **`ras`** is a Z80 assembler (sjasmplus-compatible syntax for what the runtime uses) producing SSO1. `sdk/tests/test_ras.py` cross-checks 692 instruction forms against sjasmplus.
- **`rld`** resolves symbols, pulls archive members on demand, lays out text, data and bss, and writes SSX1 with its relocation stream and checksum.
- **`rtap`** writes SST1 cassette records (`SPEC-ELASTIC-R2` §6.2). `tools/mktapes.py` builds the corpus tapes. `rtap --list` shows what a `.tap`/`.tzx` holds: programs (as `/dev/cassette/NAME`, size, memory needed), tar archives and their members (kind, size, path), the Spectrum's own files, and blocks that are not well-formed records. On ZX-UX, `tap t` (or `tar t` without an archive name) lists the programs and archives of a cassette.
- **`rvm`** (§7).

## 3. The native code and the rcc ABI

- **Arguments:** evaluated left to right. Arguments 1..n−1 are pushed in that order, argument n is passed in HL, and the callee removes the pushed words.
- **Results:** in HL (a byte result has H = 0); a float result is left in `@fac`. Floats are passed as pointers; the callee copies.
- **Registers:** IX is preserved; everything else may be clobbered.
- **Storage:**
  - A function outside a recursive call cycle keeps its parameters and locals in a static overlay, laid out along the call graph so that functions never live at the same time share bytes.
  - A recursive function builds an IX frame: `[args 1..n−1][return][old IX] ← IX`, the last argument at IX−2, locals below. The frame is built by `@enter`, which also checks the stack against the program's end + 170 bytes and ends the program with status 1 on overflow.
- **Size work in the generator:**
  - operands that need no evaluation are loaded straight into HL/DE;
  - comparisons with constants, and byte comparisons, are done through A;
  - multiplications by constants are strength-reduced;
  - power-of-two divisions and remainders are reduced for unsigned operands;
  - a peephole pass;
  - unreachable functions and data are pruned from `main`;
  - string literals are never merged (C48 Rev 0.11 section 15 requires distinct objects; R1 review, SDK item 1).

## 4. Runtime library (`sdk/lib`, archive `libc48.ssa`)

Members are linked only when referenced. `sdk/lib/build.py` cuts each `.asm` file into many small
members, one per routine or group of routines that fall into each other (a cut is made before a
label that the code above cannot fall into. data and bss stay whole), so a program links only the
routines it reaches. Sizes below are each file's total, code + data:

| Member | Bytes | Contents |
|---|---|---|
| `crt0` | 27 | `start`: argc/argv from the ZX-UX exec layout, screen claim, `main`, `exit` |
| `sys` | 133 | `getchar` (raw keys), `ticks`, `yield`, `sleep`, `getpid`, `exit` (gives the screen and the keyboard back) |
| `console` | 1,098 | `cls`, `putchar`, `puts`, `print_at`, `ink`, `paper`, `bright`, `flash`, `inverse`, `over`, `border`, `plot`, `point`, the UDG functions (`udg_define`/`get`/`draw`/`draw_2x2`/`clear`) over the program's own bank: rcc gives a program that calls them a bank of 32 slots (256 bytes), or N with `rcc --udgs N` (slots 0..N−1; a slot beyond is an error, as slot 32 is), drawn straight into the display file in the 4 × 8 font (the C48 SDK screen's semantics, 64 × 24) |
| `gfx` (C48) | 802 | `draw` (Bresenham), `circle` |
| `string` | 154 | `strlen`, `strcmp`, `strcpy`, `strncpy`, `memcpy`, `memmove`, `memchr`, `memset` |
| `heap` (C48) | 522 | `malloc`/`free`: first fit with coalescing, a 1,024-byte live limit as in the SDK, a bad `free` ends the program with status 1 |
| `float` | 575 | five-byte floats through the ROM calculator (§5): `+ − × ÷`, conversions, compares, `sin` … `fabs`, `pow`, `beep` |
| `arith` | 232 | 16-bit multiply, divide, modulo, shifts, signed compare |
| `frame` | 65 | `@enter`, `@leave` |
| `io` | 36 | `open`, `close`, `read`, `seek` (ZX-UX file calls) |
| `vm` | 1,232 | the SSB1 interpreter (§6); the dispatch table is the program's |

`sdk/include/c48.h` declares exactly these functions; `#include <c48.h>` gives it. The rest of the
C48 Rev 0.11 name list is not provided, and using it is a link error: `spawn`, `wait`, `kill`,
`chdir`, `getcwd`, `getenv`, `write`, `stat`, `remove`, `rename`, `list`, `pipe`, `dup`, `ioctl`,
`read_full`, `write_full`, `tape_save`, `tape_load`, `time_get`, `time_set`, `open_typed`. No corpus
program uses them (R1 review, SDK items 2 and 3).

**Language rules the runtime follows:**
- A float error in arithmetic or a conversion ends the program with status 1.
- `beep` returns 0, or 1 (`E_INVAL`) when the ROM refuses the values.
- `ticks()` is unsigned 16-bit.
- `main`'s result is truncated to 8 bits for the exit status.

## 5. What the kernel does for C programs

| Call | Use |
|---|---|
| 0 `rele` | `yield` |
| 1 `exit` | `exit`, return from `main` |
| 3 `read` (fd 0) | `getchar`: one raw key per call |
| 5/6/19 `open`/`close`/`seek`, 3 `read` | file functions |
| 31/32 `stty`/`gtty` | raw keyboard while the program runs, cooked again at exit |
| 34 `sleep` | `sleep(ticks)` in 50 Hz ticks |
| 36 `getpid` | `getpid` |
| 38 `ticks` | the 50 Hz frame counter |
| 39 `screen` | claim the screen at start-up (no status line, no cursor; returns the font's address), give it back at exit |

**Floats and BEEP need no kernel help** (R1 §5.4–5.5 replaced). The runtime calls the ROM's calculator (`RST 28h`) itself:
1. It turns interrupts off.
2. It points `STKBOT`/`STKEND` at a 60-byte calculator stack in its own bss and `MEM` at its own 30-byte memory.
3. It sets `ERR_SP` to a trap.
4. It puts the kernel's values back afterwards.

ROM error reports ("Number too big", "Invalid argument") come back through the trap as errors.
Integer conversions use the ROM's `truncate` and `FP-TO-BC`. `beep` stacks its two numbers and jumps
into ROM `BEEP` (03F8h), which ends in `BEEPER`.

**After every note `beep` lets one frame interrupt in (`EI`, `HALT`).**
`BEEPER` runs with interrupts off, and a program that calls it again at once never lets the frame
interrupt in: the keyboard, the clock, BREAK and the scheduler all stop until it ends, so the
shell cannot be typed to and no other process runs. With the break, the kernel's interrupt routine
runs after every note: keys are read, the clock and BREAK work, and the scheduler can switch to
another process when the beeper's time slice (4 frames) is up. It costs a gap of up to 20 ms
between notes. (A program built with an earlier library still holds everything up: rebuild it, as
`tools/mktapes.py` does.) `beep` still saves and restores MEMBOT's first five bytes, where kernels
before rev 5 kept their clock; the kernel keeps it elsewhere now (`tod_h` … in the printer buffer).

Results are the ROM's, bit for bit, as C48 requires. The kernel stays within 8 KB, and the C
extensions cost it only `ticks` and `screen` (about 100 bytes).

**The screen.**
- **Owning it:** a C program owns the 64 × 24 screen while it runs. The status line and the cursor stop, and the console is silent, so the shell's prompt and echo don't draw over it.
- **The shell below the picture:** when a process that does not own the screen uses the console (the shell after `prog &`), the console takes text rows 21–22 and the status line comes back on row 23, as BASIC keeps its lower screen. From then on the runtime draws only rows 0–20 (pixel rows 0–167 from the top): text, UDGs and pixels below are skipped and still count as drawn, and `cls` and scrolling stop at row 20. The runtime reads the console's first row from the kernel byte `ttop` (5BE4h; 0 = whole screen). In `rvm --syscall` it is always 0.
- **Sharing it:** several programs can own the screen together. Only the first one clears it at start-up (`sys screen` returns E = 0 for it); the others leave it alone. That is how `hanoi` (left half) and `queens8` (right half) run side by side.
- **The keyboard** turns raw at a program's first `getchar`, and cooked again at its exit. A program that never reads keys leaves the shell's keyboard alone, so you can type the next command while it runs.
- **At exit:** the picture stays, in white on black, and the console continues on a new bottom line.
- **Why the program draws:** drawing in the program instead of in the kernel (R1 §5.1) gives exactly the C48 SDK's screen semantics (attributes per cell, the UDG bank, PLOT/DRAW in pixels).

## 6. SSB1 — the bytecode

A bytecode function keeps the native entry and the rcc ABI, so native and bytecode functions call
each other freely:

    _f:   call @vm           ; enter the interpreter (sdk/lib/vm.asm)
          db frame           ; bytes of locals (255: a word follows)
          <bytecode>

- **Registers:** HL holds the top of the expression stack (the rest is on the Z80 stack), BC is the instruction pointer, and IX is the frame.
- **Frame:** the native recursive layout, plus the saved instruction pointer at IX−4. Every bytecode function's locals are on the stack, so recursion needs nothing special.
- **Floats:** a function that uses floats stays native, so programs mix the two freely.
- **Dispatch:** a 2-byte table lookup, about 120 T-states an instruction. Bytecode runs roughly 5–8 times slower than native code. A chess move is still seconds.
- **Interpreter size:** 1,232 bytes with every instruction; a program links the dispatcher and the handlers of the instructions it uses, plus its own table of 2 bytes per instruction used (`hanoi`: 66 instructions, a 132-byte table). It is linked only when a program has bytecode.

**Program tables**, emitted by the bytecode generator:
- `@gs`: the program's scalar globals, gathered into one block so that they are reached with a 1-byte offset;
- `@ct`: the call table, entries for functions called three times or more from bytecode, so that a call is 2 bytes;
- `@vmtab`: the dispatch table of the instructions used (above).

Range checks on an int variable, `x < A || x > B` and `x >= A && x <= B` with constant A ≤ B and B −
A < 128, become one unsigned compare of x − A with B − A (`jgtuk`, `jleuk`).

**Encoding:**
- one-byte opcodes, with short forms for constants 0/1 and the common frame offsets; a short form is used only when the program uses it often enough to pay for its handler and table entry (a first compilation pass counts the uses);
- fused push-and-load instructions;
- compare-and-branch instructions, also against a signed byte constant;
- array element loads (`ldxb`/`ldxw`: element of a static array indexed by HL);
- branch relaxation, so a branch's offset is one byte unless it must be a word.

The instruction set, in the order of `sdk/rcc/bcops.py`. **Opcodes are numbered per program:** the
generator numbers the instructions a program uses densely, in this order, and emits the program's
own dispatch table `@vmtab` with just those entries, so only their handlers are linked (`@o_NAME equ
n` in the assembly). The index below is the position in the full list:

| Index | Op | Operands | Effect |
|---|---|---|---|
| 00 | `k0` | — | HL = 0 |
| 01 | `k1` | — | HL = 1 |
| 02 | `ldk` | signed byte | HL = signed byte |
| 03 | `ldkw` | word | HL = word |
| 04 | `lda` | address | HL = address |
| 05 | `push` | — | push HL |
| 06 | `pk0` | — | push; HL = 0 |
| 07 | `pk1` | — | push; HL = 1 |
| 08 | `pldk` | signed byte | push; HL = signed byte |
| 09 | `pldkw` | word | push; HL = word |
| 0A | `plda` | address | push; HL = address |
| 0B | `ldl` | frame offset | HL = word at IX+f |
| 0C | `ldlb` | frame offset | HL = byte at IX+f |
| 0D | `stl` | frame offset | word at IX+f = HL |
| 0E | `stlb` | frame offset | byte at IX+f = L |
| 0F | `leal` | frame offset | HL = IX+f |
| 10 | `pldl` | frame offset | push; ldl |
| 11 | `pldlb` | frame offset | push; ldlb |
| 12 | `addl` | frame offset, signed byte | word at IX+f += s |
| 13 | `addlb` | frame offset, signed byte | byte at IX+f += s |
| 14 | `ldg` | address | HL = word at a |
| 15 | `ldgb` | address | HL = byte at a |
| 16 | `stg` | address | word at a = HL |
| 17 | `stgb` | address | byte at a = L |
| 18 | `pldg` | address | push; ldg |
| 19 | `pldgb` | address | push; ldgb |
| 1A | `addg` | address, signed byte | word at a += s |
| 1B | `addgb` | address, signed byte | byte at a += s |
| 1C | `ldi` | — | HL = word at HL |
| 1D | `ldib` | — | HL = byte at HL |
| 1E | `sti` | — | pop address; store HL there |
| 1F | `stib` | — | pop address; store L there |
| 20 | `preiw` | signed byte | word at HL += s; HL = new |
| 21 | `postiw` | signed byte | word at HL += s; HL = old |
| 22 | `preib` | signed byte | byte at HL += s; HL = new |
| 23 | `postib` | signed byte | byte at HL += s; HL = old |
| 24 | `add` | — | HL = pop + HL |
| 25 | `sub` | — | HL = pop - HL |
| 26 | `mul` | — | HL = pop * HL |
| 27 | `divs` | — | signed pop / HL |
| 28 | `divu` | — | unsigned pop / HL |
| 29 | `mods` | — | signed pop % HL |
| 2A | `modu` | — | unsigned pop % HL |
| 2B | `and` | — | HL = pop & HL |
| 2C | `or` | — | HL = pop | HL |
| 2D | `xor` | — | HL = pop ^ HL |
| 2E | `shl` | — | HL = pop << HL |
| 2F | `shr` | — | HL = pop >> HL (logical) |
| 30 | `sar` | — | HL = pop >> HL (arithmetic) |
| 31 | `neg` | — | HL = -HL |
| 32 | `com` | — | HL = ~HL |
| 33 | `not` | — | HL = !HL |
| 34 | `zxb` | — | H = 0 |
| 35 | `addk` | signed byte | HL += s |
| 36 | `addkw` | word | HL += w |
| 37 | `shl1` | — | HL += HL |
| 38 | `andk` | byte | HL = L & b |
| 39 | `jmp` | branch | jump (`jmpl`: word offset) |
| 3B | `jz` | branch | jump if HL = 0 (`jzl`: word offset) |
| 3D | `jnz` | branch | jump if HL != 0 (`jnzl`: word offset) |
| 3F | `jeq` | branch | pop; jump if pop = HL (`jeql`: word offset) |
| 41 | `jne` | branch | pop; jump if pop != HL (`jnel`: word offset) |
| 43 | `jlt` | branch | signed pop < HL (`jltl`: word offset) |
| 45 | `jge` | branch | signed pop >= HL (`jgel`: word offset) |
| 47 | `jgt` | branch | signed pop > HL (`jgtl`: word offset) |
| 49 | `jle` | branch | signed pop <= HL (`jlel`: word offset) |
| 4B | `jltu` | branch | unsigned pop < HL (`jltul`: word offset) |
| 4D | `jgeu` | branch | unsigned pop >= HL (`jgeul`: word offset) |
| 4F | `jgtu` | branch | unsigned pop > HL (`jgtul`: word offset) |
| 51 | `jleu` | branch | unsigned pop <= HL (`jleul`: word offset) |
| 53 | `jeqk` | signed byte, branch | jump if HL = s |
| 54 | `jnek` | signed byte, branch | jump if HL != s |
| 55 | `jltk` | signed byte, branch | signed HL < s |
| 56 | `jgek` | signed byte, branch | signed HL >= s |
| 57 | `jgtk` | signed byte, branch | signed HL > s |
| 58 | `jlek` | signed byte, branch | signed HL <= s |
| 59 | `jgtuk` | byte 0–127, branch | jump if HL > k, unsigned (`x < A \|\| x > B` as one compare of x − A) |
| 5A | `jleuk` | byte 0–127, branch | jump if HL <= k, unsigned (`x >= A && x <= B`) |
| 5B | `adda` | address | HL = a + HL |
| 5C | `addaw` | address | HL = a + 2*HL |
| 5D | `ldxb` | address | HL = byte at a + HL |
| 5E | `ldxw` | address | HL = word at a + 2*HL |
| 5F | `ldgs` | byte | HL = word at @gs+b |
| 60 | `ldgsb` | byte | HL = byte at @gs+b |
| 61 | `stgs` | byte | word at @gs+b = HL |
| 62 | `stgsb` | byte | byte at @gs+b = L |
| 63 | `pldgs` | byte | push; ldgs |
| 64 | `pldgsb` | byte | push; ldgsb |
| 65 | `addgs` | byte, signed byte | word at @gs+b += s |
| 66 | `addgsb` | byte, signed byte | byte at @gs+b += s |
| 67 | `calli` | byte | call the function in @ct entry b |
| 68 | `call` | address | call a (native rcc ABI) |
| 69 | `ret` | byte | return, dropping b pushed arguments |
| 6A | `ret0` | — | return (0 pushed arguments) |
| 6B | `ret1` | — | return (1) |
| 6C | `ret2` | — | return (2) |
| 6D | `noret` | — | end the program, status 1 (fell off a non-void function) |
| 6E | `copy` | word | copy w bytes: pop source, HL = destination |
| 6F | `pop` | — | HL = pop |
| 70–83 | `ldl.d`, `stl.d` | — | short forms: `ldl` for d in -2, 4, 6, 8, -6, -8, -10, -12, -14, -16, -18, -20, `stl` for d in -2, 4, 6, -6, -8, -10, -12, -14 |
| 84–8F | `pldl.d` | — | push; `ldl.d` (the same offsets as `ldl.d`) |


Operand kinds: `f` a frame offset (signed byte, from IX), `a` a 16-bit address (relocated by the
linker), `s`/`b` signed/unsigned bytes, and branches a signed byte relative to the next instruction.
A compare-with-constant branch that is out of range becomes `pldk` + the long compare-and-branch.

**Density.** Against rcc's own native code, which is already dense, SSB1 saves about 30–45 % on code-heavy programs:

| Program | Native image | SSB1 image (with the 1.4 KB interpreter) | Memory needed, native → SSB1 |
|---|---|---|---|
| `chess` | 12,038 | 7,829 | 16,879 → 12,774 |
| `write48` | 8,608 | 6,321 | 13,467 → 11,113 |

R1's target, 2.5 × the density of the C48 SDK's own native backend, is met: `chess` would be about
70 KB there.

## 7. The ZX-UX VM (`rvm`)

`rvm` is a ZX Spectrum 48K that boots the real ZX-UX. No system call is emulated: the kernel,
shell, loader and scheduler on the system tape built from `src/` (`build/ZX-UX.tap`) do all the
work, so a program behaves in `rvm` as on a Spectrum, with the same memory, console, BREAK,
screen sharing and multitasking.

**The machine (`sdk/zxmachine.py`).**
- **Z80:** the bundled z80-python core with the `z80fast.py` handlers, the real 48K ROM.
- **Frames and interrupts:** 69,888 T-states a frame. The maskable interrupt (IM 2 vector byte
  FFh) is taken at the first instruction boundary in the first 32 T-states of a frame with IFF1
  set, not straight after EI. A HALT idles in 4 T-state steps. There is no memory contention.
- **Ports:** IN FEh reads the eight keyboard half-rows selected by the address's high byte and
  the cassette EAR bit; OUT FEh sets the border, MIC and the beeper. Every border and beeper
  change is logged with its T-state.
- **Cassette:** the ROM's LD-BYTES and SA-BYTES are trapped (a block loads or saves in a fixed
  1 ms, saves are captured). What a caller can rely on is the ROM's: the carry, IX, DE, memory,
  the border from BORDCR and interrupts on, including failures (a wrong flag, a short or long
  block, a parity error, a VERIFY difference). A, the other flags, BC, HL and the alternate set
  are not reproduced; ZX-UX reads only the carry. With BREAK held, or no block left, the real ROM
  routine runs. `--real-tape` plays the blocks as EAR pulses, once the command has been typed,
  and lets the ROM load them.
- **Frames:** `run_frame` returns every frame number in turn, even if something moved the clock
  past a frame's end.
- **Snapshots:** `.z80` versions 1–3 in, version 3 out, with the T-state within the frame.
- **Proof:** `tests/rvm_machine.py` runs every scripted corpus session (as `tests/ssxrun.py`, with
  real tape pulses) on this machine and on the SkoolKit simulator side by side. Registers, the
  T-state count and all of RAM are identical every 25 frames and at the end.

**ZX-UX (`sdk/zxux.py`).**
- **Boot:** reset, the ROM, `LOAD ""` from the system tape, login. The logged-in state (a `.z80`
  and its absolute T-state) is cached under a key of the ROM, the tape, the user name, the typing
  and the machine version (`$ZXUX_RVM_CACHE`, `%LOCALAPPDATA%\zx-ux-rvm` or
  `~/.cache/zx-ux-rvm`). A run from the cache is identical to one that booted.
- **Programs:** a program's SST1 records go on the cassette and `/dev/cassette/NAME args` (with
  `&` for `--bg`) is typed at the shell.
- **What rvm watches:** system calls at 6003h (the result of a fork by the shell the command was
  typed to gives the pid; `/etc/ldx`'s sys
  ssxload the loading; the program's first own call the start; sys screen 0 or exit its last
  picture; the parent's wait the exit status, FFFFh for BREAK), and four kernel variables
  (`cur`, `p_pid`, `p_stat`, `scrown`), only read. `tools/build.py` writes their addresses to
  `build/kernel.json` with the kernel's SHA-256; rvm refuses a tape whose kernel is not the one
  described.
- **Typing:** characters become keys as ZX-UX's L mode types them (SYMBOL SHIFT symbols, the
  tty's keyword tokens for `~ | \ { } [ ]`, `` ` `` as SYMBOL SHIFT + X). They are held two
  scans, three apart. A key is only pressed again once the ROM's KEYBOARD routine has let it go
  (five scans), and a third key only once one of its two KSTATE sets is free.
  `--compat-keys` types as the ZX-UX tests do (4 held, 7 apart).
  The keyboard counts the frame interrupts the machine has taken, the scans of ZX-UX's
  interrupt routine, not frames: while interrupts are off (a BEEP, a tape transfer) a key stays
  held until the system has seen it, as a person holds a key until the Spectrum answers. Counted
  in frames, keys typed while a background program beeped were lost.

**The window (`sdk/rvmgui.py`, Tk).**
- **Frames:** the machine runs in a thread at the Spectrum's own rate, 50.08 frames a second
  (69,888 T-states a frame), paced by the sound stream, or by a wall clock when there is no sound.
  It hands each frame through a two-deep queue and the window paints it as it comes. If the host
  is slower the machine waits: no frame is dropped, and a frame is painted when it differs from
  the one before.
- **Picture:** FLASH follows the frame count (16 frames a phase); the border is drawn line by line
  from the colour each scan line started with; the scale is the largest that fits.
- **Keys:** the host's characters, Enter, Backspace (DELETE), the arrows and Esc (EDIT).
  Shift+Space is BREAK (held 30 frames, under the ROM's repeat delay).
- **The end:** the window keeps the program's last picture, the footer turns red and says how it
  ended, and Shift+Space closes it; rvm's exit status is the program's. With `--keep` the window
  stays live at the ZX-UX shell, and `rvm --shell` opens it at the prompt.

**Sound (`sdk/rvmsound.py`).** The beeper edges become 44.1 kHz samples by integrating the
speaker level over each sample period. A BEEP's period is the ROM's own (8 × HL + 236 T-states,
HL = INT(437500 / f − 30.125 + 0.5)), exact to the T-state. `--wav F` writes these samples.
The window plays them as one continuous stream, every frame's samples back to back: the Windows
waveOut API (winmm, through `ctypes`), or one `paplay` / `aplay` process fed raw samples through a
pipe (Linux; `paplay`, or `aplay` if `paplay` fails). The stream is also the clock: the machine
waits while 80 ms of sound is queued, so it runs at the rate the sound card plays. The picture
leads the sound by up to 80 ms with waveOut, and by about 125 ms through a pipe (its 4 KB of
sound come on top of the player's own 80 ms). What
is played passes a 20 Hz DC blocker, as the Spectrum's output does, so a tone starting or stopping
does not click. On a host too slow for 50 frames a second the sound has gaps; the picture does
not lose frames. With no sound device, `--mute`, or macOS (whose `afplay` only plays files, so it
gets short files, with gaps) a wall clock keeps the rate. `--verbose` says which output was used,
and on Windows how many times the speaker ran dry.

**Headless:** `--png`, `--scr`, `--text` (the program's last picture; `--final` for the screen as
ZX-UX left it), `--wav`, `--tape-out` (blocks saved to cassette), `--keys` (typed once the program
runs; `{BREAK}`, `{WAIT n}` ...), `--frames N` (also in the window). A run ends when the program does, when it has
waited 50 frames for keys after the last one (`input`), at the frame limit, or when the cassette
has run out before it loaded (`tape`). Exit status: the program's (255 after BREAK), 0 for `input`
and `frames`, 1 if it did not start, 2 for an error (a bad file, option, snapshot or
`kernel.json`; an output that cannot be written).

**Multitasking.** `--bg P.ssx[:A,B]` starts programs in the background first, so several share
the machine as on ZX-UX (`hanoi` and `queens8` share the screen, and a program that does not
fit is refused by the loader, as on the Spectrum).

**`rvm --syscall`** is the earlier VM: the program at 8000h, the system calls emulated in Python
(`exit`, `read`/`write`/`open`, `break`, `stty`, `sleep`, `ticks` with `--ticks N`, `screen`,
files under `--root`). It has no kernel, scheduler or console, and stays for quick, deterministic
checks (`sdk/tests/vm_checks.py`, the C48 conformance suite).

## 8. Acceptance

**In the VM — `python3 sdk/tests/vm_reference.py [--bytecode] [--png DIR]`.** For every corpus program, in every scripted session in `sdk/tests/runs.json`:
1. compile with the SDK's own compiler and run it in the SDK's reference VM (ROM maths);
2. compile with `rcc` and run it in `rvm`, with the same arguments, keys and fixed `ticks()`;
3. compare the final 6,912-byte screens.

Programs the reference cannot run to completion (`hanoi --verify`, `queens8`, the security probes,
`tune` without an audio device) are checked by screen hash, exit status or text instead.

| Run | Result |
|---|---|
| default build (native, bytecode for `chess` and `write48`) | 73/73 sessions identical |
| `--bytecode` (every function that has no floats in SSB1) | 73/73 sessions identical |

**On ZX-UX — `python3 tests/ssxrun.py [--png DIR]`.** For every corpus program and session:
1. compile it and write its cassette records;
2. boot ZX-UX from the snapshot of the ROM tape load and log in;
3. type `/dev/cassette/NAME args` and play the records;
4. type the scripted keys;
5. check that the program took the screen, ran, and reached its expected text.

The ZX-UX screen is saved as a PNG at the last frame the program owned it.

**Result: 73/73.** `chess` and `write48` run in bytecode, `write48` and `chess` with the window lent.

**In rvm — `python3 tests/rvm_corpus.py [--native|--bytecode]`.** Every session of `runs.json` is run
by `rvm` as a user runs it: ZX-UX booted, the program typed as `/dev/cassette/NAME`, loaded through
the tape trap, keys typed once it runs. A session passes when the program runs, shows its expected
ZX-UX text, and ends with its expected status where that does not depend on the clock. Two
negative cases are checked as well: `security/seckern.c` must not compile, and the LM program
(`ailmzx48`), whose SSX1 file is bigger than ZX-UX can load, must be refused by the loader ("not
enough memory", status 1). All 58 C48 sources other than LM are covered. `tests/rvm_machine.py`
(the machine against SkoolKit) and `tests/rvm_gui.py` (the window) complete the checks. Four scripted games are seeded from `ticks()`, which on ZX-UX is the real clock (`hangman`, `trek`, `snake`, `arith`). For them the ZX-UX check is that the keys were taken (`zxux_text` in `runs.json`), since a different seed plays a different game.

## 9. Sizes

All 56 corpus programs (bytes). "Need" is what the program asks the loader for: image + bss + stack,
and at least the file size. ZX-UX gives up to about 14,200 bytes after login.

| Program | Group | C source | Native image | Native need | Bytecode image | Bytecode need | Built as |
|---|---|---|---|---|---|---|---|
| `gp82` | apps | 5,402 | 3,868 | 4,491 | 3,691 | 4,240 | native |
| `sheet48` | apps | 6,707 | 4,992 | 6,770 | 3,814 | 5,499 | native |
| `wire3d` | apps | 8,276 | 5,838 | 6,764 | 4,848 | 5,543 | native |
| `write48` | apps | 20,258 | 8,608 | 13,467 | 6,321 | 11,113 | native |
| `advent` | games | 4,024 | 2,929 | 3,366 | 2,646 | 3,051 | native |
| `arith` | games | 2,517 | 1,874 | 2,311 | 2,027 | 2,432 | native |
| `bgammon` | games | 7,827 | 4,322 | 4,982 | 3,547 | 4,016 | native |
| `chess` | games | 32,426 | 12,038 | 16,879 | 7,829 | 12,774 | **bytecode** |
| `cribbage` | games | 7,500 | 4,475 | 5,200 | 3,682 | 4,271 | native |
| `fish` | games | 5,785 | 3,478 | 4,003 | 3,083 | 3,566 | native |
| `fortune` | games | 1,234 | 1,548 | 1,965 | 1,896 | 2,301 | native |
| `hangman` | games | 3,654 | 2,969 | 3,444 | 2,726 | 3,131 | native |
| `maze` | games | 2,486 | 2,242 | 2,689 | 2,332 | 2,737 | native |
| `quiz` | games | 1,855 | 2,189 | 2,622 | 2,320 | 2,725 | native |
| `rogue` | games | 4,115 | 3,264 | 3,744 | 2,959 | 3,364 | native |
| `snake` | games | 4,626 | 3,095 | 4,042 | 2,798 | 3,683 | native |
| `trek` | games | 5,623 | 3,621 | 4,139 | 3,342 | 3,747 | native |
| `wump` | games | 4,429 | 2,972 | 3,413 | 2,831 | 3,236 | native |
| `city` | demos | 2,356 | 3,782 | 4,476 | 3,451 | 3,960 | native |
| `dizzy4k` | demos | 5,424 | 5,128 | 5,979 | 4,541 | 5,226 | native |
| `firework` | demos | 2,347 | 3,183 | 3,722 | 3,215 | 3,701 | native |
| `forest` | demos | 2,047 | 3,136 | 4,229 | 3,098 | 4,167 | native |
| `galaxy` | demos | 2,114 | 4,048 | 4,764 | 3,794 | 4,333 | native |
| `goblet` | demos | 2,780 | 4,650 | 5,484 | 4,234 | 4,874 | native |
| `hanoi` | demos | 12,517 | 6,064 | 7,495 | 4,591 | 5,986 | native |
| `julia` | demos | 2,182 | 2,533 | 3,087 | 2,680 | 3,200 | native |
| `kaleido` | demos | 2,301 | 3,194 | 3,700 | 3,209 | 3,676 | native |
| `mandel` | demos | 2,218 | 2,262 | 2,816 | 2,420 | 2,940 | native |
| `mobius` | demos | 2,750 | 4,638 | 5,475 | 4,216 | 4,904 | native |
| `moire` | demos | 2,461 | 3,253 | 3,796 | 3,291 | 3,786 | native |
| `morph3d` | demos | 3,140 | 4,975 | 5,839 | 4,413 | 5,037 | native |
| `ocean` | demos | 2,681 | 4,245 | 4,981 | 3,999 | 4,576 | native |
| `orrery` | demos | 2,855 | 4,403 | 5,190 | 3,973 | 4,511 | native |
| `plasma` | demos | 2,162 | 2,063 | 2,750 | 2,297 | 2,958 | native |
| `queens8` | demos | 11,276 | 5,659 | 7,186 | 4,391 | 5,784 | native |
| `raymaze` | demos | 2,721 | 3,158 | 3,640 | 3,347 | 3,822 | native |
| `spriteanim` | demos | 2,626 | 2,139 | 2,826 | 2,302 | 2,963 | native |
| `sprites` | demos | 2,642 | 2,436 | 3,121 | 2,564 | 3,225 | native |
| `terrain` | demos | 2,825 | 4,296 | 5,043 | 4,018 | 4,596 | native |
| `torus` | demos | 2,772 | 4,675 | 5,513 | 4,239 | 4,879 | native |
| `tunnel` | demos | 2,244 | 3,137 | 3,655 | 3,245 | 3,733 | native |
| `warp` | demos | 2,222 | 2,883 | 3,584 | 3,029 | 3,698 | native |
| `argv` | examples | 3,593 | 2,355 | 2,889 | 2,490 | 3,023 | native |
| `colors` | examples | 1,442 | 1,237 | 1,652 | 1,434 | 1,839 | native |
| `graphics` | examples | 783 | 1,741 | 2,172 | 1,976 | 2,405 | native |
| `hello` | examples | 633 | 671 | 1,076 | 817 | 1,222 | native |
| `udg` | examples | 799 | 863 | 1,540 | 1,045 | 1,708 | native |
| `tune` | sound | 1,472 | 1,485 | 2,007 | 1,485 | 2,007 | native |
| `secdbl` | security | 588 | 1,349 | 3,052 | 1,564 | 3,265 | native |
| `secforge` | security | 777 | 1,418 | 3,129 | 1,669 | 3,370 | native |
| `secfree` | security | 580 | 1,345 | 3,048 | 1,571 | 3,272 | native |
| `secguard` | security | 1,783 | 2,186 | 4,153 | 2,314 | 4,271 | native |
| `secloop` | security | 463 | 731 | 1,136 | 914 | 1,319 | native |
| `secoob` | security | 548 | 803 | 1,214 | 1,003 | 1,408 | native |
| `secrecur` | security | 502 | 823 | 1,868 | 963 | 2,008 | native |
| `secuaf` | security | 535 | 1,313 | 3,016 | 1,538 | 3,239 | native |


`ailmzx48` is exempt (S6). Since 2.2 only `chess` is built as bytecode by default. the largest
native program is `write48` (13,467 bytes). The reserve lever — moving resident commands to tape —
was not needed.

## 10. R1 review items

| Item | Resolution |
|---|---|
| 1 String literals must not be merged | They are not: one label per literal occurrence |
| 2 C48 library name list | `<c48.h>` declares the provided set; the rest is a link error (§4) |
| 3 `fortune`/`secuaf` and files | They don't use files after all; `open`/`close`/`read`/`seek` are provided anyway |
| 4 Comparing at frames | Final screens with fixed `ticks()` and scripted keys, as the SDK verifies (§7, §8) |
| 5 `ticks` width | 16-bit unsigned |
| 6 `beep` result | 0 or 1 (`E_INVAL`) |
| 7 Float errors | Language operations end the program with status 1 |
| 8 `EDOM`/`ERANGE` | Defined in `const.inc` (33, 34); floats no longer go through the kernel |
| 9 Budget | Measured: about 14,200 bytes after login with the window lent; everything fits (§9) |
