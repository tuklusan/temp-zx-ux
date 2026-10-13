# C48 conformance suite

This suite checks `sdk/rcc`, `sdk/ras`, `sdk/rld`, `sdk/rtap` and `sdk/lib/libc48.ssa` against
`docs/04-C48 Language Specification Rev 0.11.docx`. The runner checks the spec's SHA-256
(`6368abb4…e150d7e`, the edition in which comments may hold any byte) before it starts. It also resolves every non-empty paragraph of the
specification (990 in all) to a test result or to a stated reason why the paragraph has no
test.

Paragraph numbers (`P0123`) are the 0-based indexes of the `w:p` elements in the docx body.
These are the same numbers as in `tests/c48/traceability.json`. Of the 1094 body paragraphs,
104 are empty and are skipped. The one body-level table (before P0000) contains no text.

**Use the docx.** `docs/C48-Language-Spec-Rev011-Standalone.txt` is an older edition: 164 of
the docx paragraphs are not in it.

## Running

```
python3 tests/c48-suite/run_suite.py            # about 1 minute; Python 3.11+ only
python3 tests/c48-suite/run_suite.py --zxux     # also on ZX-UX itself (see below)
```

The SDK needs nothing but Python (its Z80 core and the 48K ROM are bundled in
`sdk/`), and so does the suite.  If SkoolKit happens to be installed, the
float oracle also runs the ROM on SkoolKit's simulator and requires both
emulators to agree.  `--zxux` boots ZX-UX from `build/test.z80` (made by
`python3 tools/build.py` and SkoolKit's `tap2sna.py`) with the repository's
`tools/zxrun.py`, which needs SkoolKit: that is the ZX-UX test harness, not
the SDK.

`--only run,status,link,cases,lib,tool` selects groups.  The run writes to
`build/c48-suite/`: `results.json` (every test execution), `resolution.csv`
and `RESOLUTION.md` (one row per paragraph with its full text, how it was
resolved and the result).  The copies of the two tables in this directory are
from the run recorded below.  The exit status is 0 when the run itself worked.

## Files

| File | What it tests |
|---|---|
| `ck.h` | `ck(id, ok)` prints `F<id>` on failure, `ck_done()` prints `N<count>.`; the `/* Pnnnn */` comment after each `ck()` names its paragraphs |
| `t1_lex.c` | source form, comments, identifiers, tokens, literals, every operator (sections 4-17) |
| `t2_types.c` | sizes, signedness, representation, alignment of globals and locals (static area and recursive frame), declarators, linkage, initializers, pointers (18-34) |
| `t3_expr.c` | constant expressions, conversions, promotions, wrap, shifts, comparisons, pointer arithmetic, `sizeof`, lvalues (35-52) |
| `t4_float.c` | 55 float literals compared byte for byte with the 48K ROM's own conversion (`romoracle.py`); folding vs run time; float parameters and results |
| `t5_stmt.c` | evaluation order, calls, returns, locals, every statement |
| `t6_pp.c`, `t6_*.h` | `#define`, `#include`, `<c48.h>` |
| `t7_main.c` | `main(argc, argv)` and library calls |
| `t8_status.c` | run-time traps and exit statuses (19 cases and a control) |
| `t9_main.c`, `t9_mod.c` | separate compilation (`-c`), `rld`, SSA1 archives, linkage; `run_suite.py` adds further multi-unit link tests |
| `t10_abi.c`, `t10_abi.s` | the calling convention against hand-written assembler |
| `t12_unix.c` | every ZX-UX system call through `<c48.h>`, with the kernel's results and error numbers (48 checks) |
| `t13_abi.c`, `t13_abi.s` | the 20 ABI rules (table below), one check each, against hand-written assembler |
| `n1_lex.cases` .. `n4_pp.cases` | 488 programs that must be rejected (status 1, `rcc:` diagnostic, no output); `diag=REGEX` checks the wording |
| `p_accept.cases` | 53 programs that must build and exit 0 on both back ends (`may`: optional requirement, NOTE on failure), among them comments holding every byte value |
| `dispositions.tsv` | why each paragraph without a test has none (HEADING, FRONT, INFO, SUMMARY, PROCESS, DOC, OTHER-IMPL, UNSPECIFIED, RESOURCE) |
| `romoracle.py` | the ROM's float routines on the bundled plain z80-python core (and SkoolKit, when present) |
| `run_suite.py` | the runner |

Programs run as `--native` and `--bytecode` builds in `sdk/rvm.py`.  With
`--zxux`, t1-t7 and t12 (t12 on both back ends), and t10 and t13 (both back
ends), also run on ZX-UX loaded from an `rtap` cassette, and must pass there
with the same results as in rvm; and the ENV1/ARG1 tests of
`tests/suite.py` (`env1_*`, below) run on ZX-UX.

## The 20 ABI rules (C48 Rev 0.11 sections 56-59)

Check 130NN in `t13_abi.c` is rule NN, on both back ends, in rvm and on ZX-UX.

| # | Rule | Paragraphs | Also |
|---|---|---|---|
| 1 | arguments evaluated left to right | P0587 P0602 | |
| 2 | arguments 1..n-1 pushed in order as words; no 3- or 6-argument limit (8 used) | P0602 P0603 P0750 | |
| 3 | the last argument in HL | P0602 P0603 P0617 | |
| 4 | no arguments: nothing pushed, no HL parameter | P0602 | |
| 5 | no HL/DE/BC three-register scheme (C callee called with junk in DE, BC) | P0603 | |
| 6 | each scalar and pointer argument is one 16-bit word | P0604 | |
| 7 | a float argument is a pointer to caller-owned bytes; the callee's copy is its own, also before the last parameter | P0596 P0604 P1061 P1078 | |
| 8 | an 8-bit argument zero-extended | P0605 | |
| 9 | the callee removes the pushed words | P0606 | |
| 10 | recursive IX frame `[args 1..n-1][return][old IX] <- IX`, last argument at IX-2 | P0607 | |
| 11 | the same ABI between C and assembly, both directions | P0600 P0608 | `abi:mixed_*`: native and bytecode objects linked together, each calling the other |
| 12 | one convention, no selection syntax | P0609 P0610 | `abi_cdecl`, `abi_stdcall`, `abi_fastcall`, `abi_attribute`, `abi_regcall`, `abi_register_param`, `fn_callconv_syntax` rejected |
| 13 | void has no value; 16-bit and pointer results in HL | P0613 P0614 | |
| 14 | an 8-bit result in HL with H = 0 | P0613 P0614 P0619 P1062 | |
| 15 | a float result in `@fac`; no hidden pointer, no extra word | P0613-P0616 | |
| 16 | a float result kept before the next call replaces `@fac` | P0618 | |
| 17 | IX preserved by the callee | P0622 P0623 | |
| 18 | AF BC DE HL clobbered by the callee | P0622 P0623 | |
| 19 | IY is the system's (5C3Ah in C code) | P0623 P0624 | `abi:codegen_no_iy_no_alternates` (every suite program, `rcc -S`, both back ends), `abi:library_no_iy_no_alternates` |
| 20 | the alternate set is not the program's | P0623 P0625 | the same two scans |

## ENV1 and ARG1 (P1080, P0369, P0370)

ENV1 is one byte of `crt0` bss (`@env1`) that `crt0` makes empty before
`main`: process-owned memory in the program's own image, separate from ARG1
(the `argv` vector and strings the kernel builds at the top of the image's
block) and from the kernel's `KARGS`; no kernel bytes; no `getenv` (C48
defines none).  Proved on ZX-UX by `tests/suite.py`, sampling memory at every
frame:

- `env1_arg1_argv_example`: `programs/c48/examples/argv.c` (unchanged) run as
  `argv alpha beta`: ENV1 (its address read from the loaded image's first
  instruction) lies in the program's bss below ARG1, ARG1 lies inside the
  IMAGE block and holds exactly the three arguments, neither is in the
  kernel; ENV1 stays empty and ARG1 unchanged at every frame until exit; the
  program shows its arguments; the block is freed at exit;
- `env1_isolation`: two copies at once have separate ENV1s; the one that
  writes its own (on purpose) does not change the other's;
- `env1_exec`: after `exec`, the new image (at the same address here) starts
  with an empty ENV1 and ARG1 holding the exec's arguments;
- `env1_fresh`: a program that wrote its ENV1 ends; the next one, loaded at
  the same address, starts with it empty.

## Result

Rev 0.11 docx (SHA `6368abb4…`), the fixed SDK (this commit), `--zxux`:

- **Paragraphs (990):** 741 PASS, 0 FAIL, 0 NOTE; 249 resolved without a test
  (120 HEADING, 37 OTHER-IMPL, 29 INFO, 25 PROCESS, 22 DOC, 7 FRONT,
  4 SUMMARY, 3 UNSPECIFIED, 2 RESOURCE).
- **Test executions:** 1843, all PASS (768 run, 488 rejection cases,
  106 acceptance builds, 165 float literal comparisons, 88 library, 64 ABI,
  77 on ZX-UX, 38 status, 25 tool, 24 link).
- All 55 float literals equal the ROM's bytes on native, bytecode and
  ZX-UX, with the ROM run on two independent emulators.

**Comments may hold any byte** (the updated P0039, P0042, P0044, P0049):
NUL, CR, other control bytes and 0x80-0xFF are accepted inside `/* */` and
`//` comments (cases `ac_comment_*`, among them every byte value 0-255) and
rejected everywhere else, string and character literals included.

**Every ZX-UX system call** has a function in `<c48.h>` (`lib:every_system_call`
checks the header against the kernel's `systab`); `t12_unix.c` checks each
call's result and error number in rvm and on ZX-UX.

The deviations the first run of this suite found, all fixed in the SDK and
each guarded by tests that fail on the old SDK:

| Was | Fix | Paragraphs |
|---|---|---|
| global `int`/`short`/pointer objects after a `char` at odd addresses; locals aligned only by chance | `align_of()` in rcc (globals, static-area and frame locals, frames kept even, bytecode `@gs`); `ras` records section alignment in SSO1; `rld` honours it | P0222 P0228 P0231 P0306 P0330 |
| `int g = sizeof g;` rejected | a name is visible from the end of its declarator (globals and locals) | P0270 |
| float `++`/`--` as a value rejected; the statement form evaluated an operand such as `*p++` twice | new `gfinc`: address evaluated once, old/new value as required | P0563-P0565 P1073 |
| a float parameter before the last one hung the program | the prologue keeps the return address across `@fmov` | P0342 P0596 P0604 P0957 P1061 P1078 |
| two `-c --bytecode` objects did not link (`@vmtab`/`@gs`/`@ct` in each) | `-c` builds use the library's full dispatch table; no per-unit `@gs`/`@ct` | P0029 P0255-P0257 P0287 P0288 P0763 P0764 P0768 P0989 P1089 |
| an uncalled external function or object dropped from a `-c` unit with `main` | `-c` keeps everything with external linkage | P0255 P0287 P0288 P0768 |
| `udg_get` did not link; `free` alone did not link; UDG bank duplicated across units | `@udgcp` label; heap made when `malloc` or `free` is used; library default heap and UDG bank for `-c` programs | P0735 P0924 P1042 |
| `rcc -o x.c x.c` overwrote the source; missing input or unwritable output gave a Python traceback | refused with status 2; `rcc:` messages, status 1, no partial output | P1085 P0773 P0782 P1087 |
| accepted: local/parameter `__x`; `static` then `extern` function; `<` on `void *`; `#define A"x"`; `#define const 3`; `#define _start 3`; comment crossing a directive line; `#include < c48.h >`; 16-character macro names | each now rejected | P0116 P0284 P0535 P0701 P0708 P0720 P0732 P0085 P0087 P0716 |
| function-like macro diagnostic unspecific | "function-like macro F is not supported" | P0708 P0741 |
| `NULL` not defined | `#define NULL 0` in `<c48.h>` | P0317-P0319 |
| only a subset of the ZX-UX system calls in `<c48.h>` | a function for every kernel call, `errno`; `close` and the calls with no result return 0 on success | P1041 P1042 |
| ENV1 had no storage | one empty byte of `crt0` bss per process | P1080 |

## Method

1. Every non-empty docx paragraph was read in full and either tagged on at least one test or
   given a disposition, as follows:
   - **Runtime programs:** each check (`ck()` call) is tagged with paragraph numbers.
   - **Case files:** each case's `//==` header line lists its paragraph numbers.
   - **Built-in tests:** the lib, tool, link and status tests in `run_suite.py` carry paragraph
     lists in code.
   - **Dispositions:** paragraphs with no test get an entry in `dispositions.tsv` saying why.
2. The verdict for each paragraph is worked out as follows:
   - **FAIL** if any test tagged with it failed;
   - **NOTE** if none of those, but a `may` case did not succeed;
   - **PASS** if every tagged test passed;
   - otherwise, its disposition.
   - A paragraph with neither a test nor a disposition would show as UNRESOLVED; none do.
3. The tables were audited separately from the runner:
   - the docx was re-parsed and its text compared, whitespace-normalised, with every CSV row;
   - each verdict was recomputed from `results.json` and `dispositions.tsv`;
   - every failing test was confirmed to be named in its paragraph's row.
4. Every deviation was reproduced by hand before being reported. The expected values in the
   suite were checked against the spec text rather than against what rcc does.
5. The final suite was also run against the SDK before the fixes (commit
   `c912b47`, SkoolKit-based): 78 paragraphs FAIL or NOTE there, including
   every one the first run reported except P0044/P0045/P0049 (bytes in
   comments, which the updated spec now permits); none do with the fixed SDK.
