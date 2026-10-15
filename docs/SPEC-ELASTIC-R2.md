# ZX-UX: Memory and File Formats, R2

This file describes the memory model used by the version 2 code.
It replaces earlier plans where they differ. The system shares RAM among
files, running programs, and a common execution window. Each process has
one of four slots. Files can be packed when RAM becomes scarce.

This is a technical reference. It uses hex addresses and exact byte layouts.
The plain-English build guide is in `README.md`.

## 1. Design choices

| # | Decision (R1) | In 2.0 |
|---|---|---|
| D1 | Files live in an elastic arena with real v1 directories | Done: i-nodes, links, `mkdir`/`rmdir`, `..`, `ls -i` all work; there are no blocks and no fixed disk |
| D2 | `fork` kept, by twin swapping for SSX1 programs | `fork` is kept with v1 semantics for every resident program. **SSX1 programs cannot fork** (`EAGAIN`, "Try again"); twin swapping is not built (§3.7) |
| D3 | Formats SSX1, SSO1, SSA1, SST1, SSZ1 | SSX1, SSO1 and SSA1 as in R1 §6–8; SST1 is the plain cassette record of §9; SSZ1 is deferred (§10) |
| D4 | The resident commands stay resident, data linked at the window | Done |
| D5 (new) | The window is **lent** to a program from tape that does not fit in the arena | §3.6 |
| D6 (new) | Programs from tape are loaded by the kernel, from a header found by `/etc/ldx` | §6 |
| D7 (new) | The boot code runs from outside the 8 KB kernel and is overwritten afterwards | §2 |

## 2. Memory map

As built (`python3 tools/build.py` prints these from the symbol table):

| Address | Use |
|---|---|
| 0000–3FFF | ROM |
| 4000–5AFF | display file and attributes |
| 5B00–5D97 | kernel globals, system variables, zxpack low-memory state (as in 1.x) |
| 5D98–5E48 | **low kernel**, 177 bytes (block `lowk`, rev 5): kernel strings, the keyboard token table, the tape clock routine and the tape hold's two variables |
| 5E49–5EFF | kernel stack (183 bytes; its deepest use is under 150 by inspection, 82 measured) |
| 5F00–5FFF | tty line, exec arguments (as in 1.x) |
| 6000–7FE0 | kernel: 8,161 of 8,192 bytes |
| 7FE4–8163 | console font (384 bytes) |
| 8164–B3C4 | resident text: user library and the 38 resident programs (with `/etc/ldx`) |
| B3C6–B4E3 | `ZXW`: the boot code as loaded from tape (286 bytes), then the zxpack literal model (256) |
| B4E4–B7E3 | i-node table: 24 × 32 bytes |
| B7E4–EFFF | **arena**: 14,364 bytes (to `a_top`, which is `WINDOW` normally and `CORETOP` while the window is lent) |
| F000–FFB8 | **window**: data, bss and stack of the resident-text process that owns it (`UDATA` = F000, `CORETOP` = FFB9) |
| FFB9–FFF3 | u-area of the running process (59 bytes) |
| FFF4–FFF6, FFFF | IM 2 trampoline |

**Changes from R1:**
- **The u-area is at the top of the window, not its bottom.** The window and the arena are then adjacent, which is what makes lending (§3.6) possible.
- **The zxpack model is below the arena, not above it,** for the same reason.
- **The boot code lives in `ZXW`.** It runs once, then the first pack or unpack initialises the model over it. Moving about 220 bytes of boot code out of the 8 KB kernel paid for most of the loader and lending code.
- **The low kernel (rev 5).** The BASIC loader loads a fourth block, `lowk`, to 5D98h before the
  kernel: code and data that need not be in the 8 KB, in low memory the arena never had. While the
  loader runs, its own BASIC program, variables and work space end at 5D48h (`STKEND`), and the
  machine stack is just below `RAMTOP` (5FFFh). Afterwards the kernel stack grows down towards it;
  `unix.asm` asserts that it keeps at least 180 bytes. `kernel.json` gives its SHA-256
  (`lowk_sha256`), and rvm checks it as it checks the kernel's.

**Measured** with the default boot file set:

| Point | Arena free |
|---|---|
| At boot (the banner's `free=`) | 12,036 bytes |
| After login (init and sh running; `df`) | 10,084 bytes |
| Biggest program loadable from tape after login (arena + lent window) | about 14,100 bytes |

## 3. Memory model

### 3.1 Blocks

Every allocation in the arena is a block: `+0` size (word, header included, even), `+2` kind, `+3`
spare, then the payload. The smallest block is 4 bytes.

| Kind | Value | Placement | Holds |
|---|---|---|---|
| `K_FREE` | 0 | — | free space |
| `K_FILE` | 1 | movable | a file or directory (`i.dskp` → payload) |
| `K_SAVE` | 2 | movable | a process's u-area, and for a resident-text process room for its whole window image |
| `K_IMG` | 4 | fixed | a loaded SSX1 program |
| `K_TEMP` | 5 | fixed | zxpack's workspace while it packs |

R1 review, item 1: there is no owner byte. "Free" is a kind, so there is no clash with i-node or
slot 0.

### 3.2 Allocator (`arena.asm`)

- **Allocation:** movable blocks are placed first fit from the bottom, and never past `WINDOW` (§3.6). Fixed blocks are carved from the bottom of the highest free block that fits. The free space above a program then stays next to the window, so that a second program can still borrow it (§3.6).
- **When there is no room:**
  1. compact and retry;
  2. then pack one closed file with zxpack and retry, as often as packing frees something;
  3. then fail with `ENOMEM`.
- **Free blocks** are merged lazily, while scanning.
- **Compaction** slides every movable block down over free space. Fixed blocks are barriers: blocks above one slide down to its end. A moved block's single kernel pointer is found by address in the i-node table (`i.dskp`) or the process table (`p_save`) and rewritten (R1 review, items 2 and 3).
- **Pointer rule:** a caller that holds a payload address in a register reloads it after any allocation, because the allocation may have compacted. `writei`, `zpack` and `zunpack` do so.

### 3.3 The window and SAVE blocks

- **Resident commands** are linked with their data at `UDATA`, so one process at a time owns the window.
- **Lazy ownership:** the kernel tracks the owner (`wown`) and saves an image only when another resident-text process needs the window. Switching to or from an SSX1 process copies only the u-area.
- **Reservation rule:** every resident-text process owns a SAVE block for as long as it lives, sized for its whole image: u-area + data up to the break + 384 bytes of stack. A context switch therefore never allocates.
- **Who sizes the SAVE block:** `fork` allocates the child's (`ENOMEM`/"Try again" if it can't). `exec` and `break` resize the caller's through `savefit`. `savefit` shrinks the block when it is too big. When it is too small, it frees the block first, then allocates a new one; if that fails, it allocates the old size again (that room was just freed, so this cannot fail) and reports `ENOMEM`. So `exec` stays atomic while still able to reuse its own memory.
- **R1 review, item 4:** a stack that has outgrown its 384-byte reservation at a switch is still a panic (`stack`). The resident programs are measured to stay well inside it.

### 3.4 SSX1 processes

An SSX1 program runs in one fixed IMAGE block, in this layout from the bottom:
- image
- bss and heap
- stack
- arguments (at the top)

Its SAVE block holds only the u-area. Its `break` moves inside the IMAGE block, below the stack.

### 3.5 Exec and exit

- `exec` runs resident text only: the program's 8-byte header is read from its text address. Programs on cassette run through `/etc/ldx` (§6).
- At exit, or at the point of no return of an `exec`, the process's IMAGE block is freed. If that image had borrowed the window, the window is taken back (§3.6).

### 3.6 Lending the window (new)

**When it happens.** If the SSX1 loader (§6) cannot allocate a program's IMAGE block, the window joins the arena:
1. Its owner's image has already been saved: the loader's own process was the owner.
2. A free block from `a_top` to `CORETOP` is appended.
3. `a_top` becomes `CORETOP`.
4. The allocation is retried.

The borrowing block is recorded in `wlend`.

**While the window is lent:**
- **Scheduling:** only SSX1 processes run (`isrun`). Resident-text processes stay runnable but wait, including background jobs; their timers keep counting.
- **Movable blocks** are never placed past `WINDOW`, so the window can always be emptied again.
- **`exec` of resident text** by any process other than the borrower fails with `ENOMEM`.

**Taking it back.** When an IMAGE block is freed and `wlend` is set, the kernel:
1. compacts the arena;
2. checks that the free space at the top reaches down to `WINDOW` or below;
3. cuts the arena back to `WINDOW`.

A gap of under 4 bytes is left outside the arena. If something still lies in the window, it stays
lent (`wlend` = FFFF) until the next IMAGE block is freed.

### 3.7 Fork of an SSX1 program — not built

R1 planned twin swapping, so that a forked SSX1 program could run at the parent's addresses. It is
not built in 2.0, for two reasons:
- **No program needs it.** C48 has no `fork` (or any way to make a raw system call), and every SSX1 program comes from the C toolchain, so no program can reach it.
- **The budget.** The kernel has 31 bytes left of its 8,192 (rev 5), against roughly 120 for twin exchange, TWIN blocks and the survivor rule.

`fork` from an SSX1 process returns `EAGAIN`. R1 review, items 6 and 7 (twin restore on `exec`, no
`fork` for big programs) are therefore moot.

## 4. Elastic v1 file system

- **I-node table:** 24 entries, i-numbers 41–64, 32-byte v1 i-nodes, at `ITAB`. `i.dskp` (the first block-pointer word) is the payload address of the file's block. `i.size` is the logical size. The spare word (`I_RSVD`) holds the stream length of a packed file, or the time of the last change for the idle packer.
- **Resident programs:** i-numbers 128 and up, synthesised from the program table `PTAB`. Their contents are their text.
- **Devices:** i-numbers 1, 2 and 5 (`/dev/tty`, `/dev/mem`, `/dev/tap` = `/dev/cassette`). `/dev/rd0` is gone.
- **One block per file.** Writing past a file's block allocates a new block with a quarter to spare (else exactly enough), copies, and frees the old one. Closing a file trims its block to its size.
- **Directories** are files of 10-byte v1 entries.
- **`stat`** (R1 review, item 8): 34 bytes, the v1 layout. The i-number, then the 32-byte i-node; `i.dskp` is the payload address and the spare word the stream length.
- **zxpack in the arena:**
  - **Packing** encodes into a `K_TEMP` workspace block, which then becomes the file's block. The workspace asks for the file's size; under pressure it asks for a half, a quarter and so on, because streams are usually half the size or less.
  - **Unpacking** decodes into a new block of the logical size.
  - **Idle packing** and **packing under memory pressure** are as in 1.x.
- **`tar`** reads and writes the 1.x tape format (§9). It marks restored packed files through `/dev/mem`.

## 5. Process model summary

| | Resident text | SSX1 program |
|---|---|---|
| Image | window (`UDATA`–`CORETOP`) | its IMAGE block |
| Saved at a switch | u-area; window image when another resident process needs the window | u-area |
| `fork` | yes (child gets a SAVE copy) | no (`EAGAIN`) |
| `exec` | yes | yes |
| `break` | inside the window, SAVE resized | inside the IMAGE block |
| Started by | `exec` of resident text | `/dev/cassette/NAME` through `/etc/ldx` |

Four process slots, preemptive round robin with a 4-tick quantum, single user, no permissions — as
in 1.x.

## 6. SSX1 — executable, and loading from cassette

### 6.1 Format

As R1 §6.1–6.3, with these clarifications:

**Header** (20 bytes, little-endian):

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `'S' 'S' 'X' '1'` |
| 4 | 1 | flags — 0 (R1's `WINDOW` and `PACKED` flags are not used by 2.0) |
| 5 | 1 | header size = 20 |
| 6 | 2 | image size |
| 8 | 2 | bss size |
| 10 | 2 | stack reserve |
| 12 | 2 | heap reserve (bytes above bss for `brk`) |
| 14 | 2 | entry offset |
| 16 | 2 | relocation count |
| 18 | 2 | checksum: Fletcher-16 over header bytes 0–17, the image and the relocation stream |

**Clarifications:**
- **Checksum** (R1 review, item 9): computed over the bytes as stored, which 2.0 never packs. `rld` writes it and `rld.parse_ssx` checks it. The Spectrum loader relies on the tape blocks' parity instead, to save kernel bytes.
- **Relocation stream** (R1 review, items 10 and 11):
  - **Byte 1–255:** the position advances by that many bytes. Two relocated words can't overlap, so the linker never emits 1.
  - **Escape:** `00 lo hi` sets an absolute offset, which must be past the current position.
  - **First entry:** its byte is its own offset, so offsets 0 and 1 need the escape.
- **Only 16-bit relocations exist** (R1 review, item 13). `high()`/`low()` of a relocatable symbol is a linker error.

### 6.2 SST1 cassette record of a program

One standard Spectrum CODE pair (R1 review, item 12):

- **Header block** (17 bytes, flag 00):
  - type 3
  - name = the program's name, 1–10 characters, space padded
  - length = the SSX1 file's size
  - parameter 1 = bytes of memory the program needs: image + bss + heap + stack, and at least the file size
  - parameter 2 = `'S','S'`
- **Data block:** the SSX1 file, flag FF.

`sdk/rtap.py` writes these records. Any tape browser shows the program names.

### 6.3 Loading

1. `exec /dev/cassette/NAME args` (or `/dev/tap/NAME`) runs `/etc/ldx` in its place. The arguments are unchanged, so `argv[0]` is the path as typed.
2. `ldx` opens the tape and reads headers until it finds a CODE header named NAME with parameter 2 `SS`. Data blocks and other programs are passed over; BREAK stops the search.
   - **`/dev/cassette/*` (rev 5)** takes the first such header, whatever its name (`/dev/tap/*` is
     not supported: `/etc/glob` passes only `/dev/cassette` words on). `ldx` then makes
     `argv[0]` `/dev/cassette/NAME`, with the name found, so the program, the status line and `ps`
     see the name as if it had been typed. Only `*` alone is "any program": `/dev/cassette/ss*` looks
     for a program of that name. `/etc/glob` passes on every word that starts `/dev/cassette` as it
     is (the cassette is not a directory, so there is nothing to match); other words are globbed as
     before.
3. `ldx` adds the room the arguments need to parameter 1. If that exceeds the arena's free bytes, plus the window, plus its own image, it says `not enough memory` and exits.
4. `sys ssxload` (40) takes BC = file length, DE = total memory and HL = the arguments (argv, 0-terminated, as for `exec`; `ldx` passes its own). From here the caller's image is given up, as at an `exec`'s point of no return:
   - The window is freed.
   - The SAVE block shrinks to the u-area.
   - The arena is compacted, so all its free space is one block: the image goes just above the movable blocks, and what is left stays in one piece above it, next to the window (2.2; before, holes left below a first program could keep a second one from fitting).
   - The IMAGE block is allocated, lending the window if needed.
   - The SSX1 file is read into the top of the block.
   - Its header is read before the image is moved down over it.
   - The words are relocated.
   - bss and heap are zeroed, and the break is set after them.
   - The v1 argument layout is built at the top of the block, and the program starts with interrupts on.
5. A load that fails after the point of no return (no memory despite lending, a tape error) ends the process with status 1.
   When there is no memory, the kernel first prints `/dev/cassette/NAME: not enough memory` (rev 5).
   That is the usual end of a background load that does not fit: `ldx`'s check in step 3 counts the
   window, but only a program BREAK can stop (in the foreground) may borrow it, so before, the
   program simply vanished.
6. The kernel names the process from `argv[0]` (its last component) for the status line and `ps`.

**Departure from R1 §6.4:** loading is not atomic. Keeping the caller's image until the end would cost the biggest program the caller's whole SAVE block. `ldx`'s memory check in step 3 makes a late `ENOMEM` rare.

### 6.4 The tape and the other processes (rev 5)

The ROM moves a block with interrupts off, and between blocks a program has only the time of the
gap and the next pilot tone to start reading again.

- **One process at a time.** After every tape transfer, read or write, ended well or not, the
  frame interrupt does not preempt the process that made it for 250 frames (5 s: `tapq`, counted
  down by the interrupt routine, and `tapqp`, its slot; both in the low kernel): it keeps the CPU,
  so no other process (a BEEP runs with interrupts off; any program can take its time slice) can
  hold it while the next block goes by. If it gives the CPU up itself (a sleep, a wait, the tty),
  the others are scheduled as usual. `sys ssxload` ends the hold as soon as the program is in, or
  when it fails, and an exit ends it, so neither a loaded program nor the next process in the slot
  runs alone.
- **The clock goes on.** With interrupts off no frame is counted, so a load stopped the clock: a
  5 KB program lost about 40 s. After a successful transfer, `tclk` (in the low kernel) puts its
  time on the clock, the frame counter (`ticks`) and the sleeping processes' timers: the pilot tone
  (5 s before a header, 2 s before data) and every bit (a 0 is two pulses of 855 T-states, a 1 two
  of 1,710: 41 units of 1,710 T-states make a 69,888 T-state frame). Time spent waiting for the
  tape to start, and blocks passed over (another program's data), are not known and not counted.
  `tclk` itself runs with interrupts on (each frame it adds goes on with them off), so its own
  time is counted by the interrupt routine; a 5 KB load ends within 2 s of the real time (`tape_clock`).
- **The clock's bytes.** `tod_h`, `tod_m`, `tod_s`, `stdirty` and `kcon` were MEMBOT's first five
  bytes, where the ROM's BEEP (run by a program's `beep()`) keeps a number: they are in the printer
  buffer (KV+229..232) and KV2+75 now.
- **Boot time.** The clock starts at Fri Apr 23 1982 09:00:00, the ZX Spectrum's release day at a
  high-street shop's opening hour (there is no record of the day's own hour).

## 7. SSO1 and 8. SSA1

As R1 §7 and §8 (`sdk/ras.py`, `sdk/rld.py`). One addition: an empty section that defines symbols is
still written, so that a label such as an empty call table is defined.

## 9. Cassette archives

`tar` keeps the 1.x tape format. R1's SST1 payload preamble for archive members is deferred: it
would be a user-land change with no effect on the kernel. Archives and programs share a tape freely,
because `ldx` skips `tar` headers (their parameter 2 is not `SS`).

## 10. SSZ1 — deferred

Packed SSX1 images and packed archive members are not built in 2.0. Files in the arena are packed by
zxpack exactly as in 1.x, and `tar` writes packed files as their bare stream, with the stream length
in the member preamble.

## 11. System calls added in 2.x

| No. | Name | Arguments → result |
|---|---|---|
| 37 | `zxpack` | HL = name → stream length (packing it); HL = 0 → HL = arena free bytes, DE = free i-nodes |
| 38 | `ticks` | → HL = 50 Hz frame counter |
| 39 | `screen` | HL = 1: the caller shares the screen (no status line, no cursor, the console is silent for the owners; a process that is not an owner and uses the console moves it to rows 21–22, with the status line on row 23, and sets `ttop` (5BE4h) = 21 so that owners stop drawing there) → HL = the 4 × 8 font, E = 0 if it is the first owner; HL = 0: give its share back. When the last owner gives it back, the picture stays, in white on black, and the console carries on below it. (The status line shows the live processes: a process that has ended leaves it at once, though it stays a zombie until its parent waits - rev 5.) Ownership is a bit per process slot, so several programs can draw at once (`hanoi` and `queens8` each draw one half) |
| 40 | `ssxload` | BC = SSX1 file length, DE = memory, HL = argv → becomes the program (§6.3) |

## 12. Kernel budget

8,161 of 8,192 bytes, and 177 bytes of low kernel (rev 5; 8,171 at the R1 review, item 14).

**Paid for by:**
- the boot code moving to `ZXW` (about 220 bytes);
- the low kernel (rev 5): strings, the keyboard token table and the tape clock routine, loaded
  below the kernel stack;
- dropping block allocation, bitmaps, `bmap`, indirect blocks and the swap pool's compaction;
- reading program headers straight from their text;
- automated tail merging.

**Not in the kernel:**
- the cassette search (in `/etc/ldx`);
- float maths and BEEP (the C runtime calls the ROM itself, `SPEC-SDK-R2` §5);
- console colours (C programs draw their own screen).

## 13. Tests

`tests/suite.py`, 20 sessions, each from a fresh snapshot of the tape-loaded system:
- the 12 1.x sessions, adapted to the arena;
- **cassette programs:** arguments, and searching past other programs;
- **window lending:** state checked through the kernel symbols, memory returned afterwards;
- **a background job** that waits through a lend;
- **two programs from tape at once**, sharing the screen;
- **the shell below a background program**, on rows 21–22;
- **hanoi and queens8 together without lending the window**, the shell answering;
- **a program too big to load.**

Rev 5 adds:
- **`/dev/cassette/*`:** the first program runs with its arguments and `argv[0]` as typed
  (`cassette_star`); past the system tape's BASIC and CODE files, named on the status line and in
  `ps`, never `*` (`cassette_star_names`); only `*` alone, globbing elsewhere as before
  (`cassette_star_only`);
- **the status line** drops a killed process at once, while it is still a zombie
  (`cassette_star_names`);
- **a background load that does not fit** says `not enough memory` (`bg_no_room`);
- **the tape keeps the CPU:** a CPU-bound background job gets no time while `tap t` reads six
  programs, and gets it again afterwards (`tape_keeps_cpu`);
- **the clock** within 2 s of the time a load took (`tape_clock`);
- **BEEPs:** a program calling BEEPER with no break holds everything up, the library's `beep()`
  lets others run (`beep_shares_cpu`);
- **mobius and torus** together in the background (`mobius_torus_together`);
- **the low kernel** byte for byte after a busy session (`low_kernel`).

`tests/ssxrun.py` runs the whole C48 corpus from cassette (`SPEC-SDK-R2` §8).
