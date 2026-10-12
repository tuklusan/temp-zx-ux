# C48 conformance suite

This suite checks `sdk/rcc`, `sdk/ras`, `sdk/rld`, `sdk/rtap` and `sdk/lib/libc48.ssa` against
`docs/04-C48 Language Specification Rev 0.11.docx`. The runner checks the spec's SHA-256
(`577a9327…037ec`) before it starts. It also resolves every non-empty paragraph of the
specification (990 in all) to a test result or to a stated reason why the paragraph has no
test.

Paragraph numbers (`P0123`) are the 0-based indexes of the `w:p` elements in the docx body.
These are the same numbers as in `tests/c48/traceability.json`. Of the 1094 body paragraphs,
104 are empty and are skipped. The one body-level table (before P0000) contains no text.

**Use the docx.** `docs/C48-Language-Spec-Rev011-Standalone.txt` is an older edition: 164 of
the docx paragraphs are not in it.

## Running

```
python3 tests/c48-suite/run_suite.py            # about 1.5 minutes; Python 3.11+ only
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
| `n1_lex.cases` .. `n4_pp.cases` | 481 programs that must be rejected (status 1, `rcc:` diagnostic, no output); `diag=REGEX` checks the wording; `deviation` marks an accepted documented deviation |
| `p_accept.cases` | 47 programs that must build and exit 0 on both back ends (`may`: optional requirement, NOTE on failure) |
| `dispositions.tsv` | why each paragraph without a test has none (HEADING, FRONT, INFO, SUMMARY, PROCESS, DOC, OTHER-IMPL, UNSPECIFIED, RESOURCE) |
| `romoracle.py` | the ROM's float routines on the bundled plain z80-python core (and SkoolKit, when present) |
| `run_suite.py` | the runner |

Programs run as `--native` and `--bytecode` builds in `sdk/rvm.py`;
with `--zxux`, t1-t7 also run on ZX-UX loaded from an `rtap` cassette, and
their results must equal the rvm results.

## Result

Rev 0.11 docx, the fixed SDK (this commit), `--zxux`:

- **Paragraphs (990):** 737 PASS, 3 DEVIATION (P0044, P0045, P0049), 0 FAIL,
  0 NOTE; 250 resolved without a test (120 HEADING, 37 OTHER-IMPL, 29 INFO,
  25 PROCESS, 22 DOC, 7 FRONT, 4 SUMMARY, 4 UNSPECIFIED, 2 RESOURCE).
- **Test executions:** 1579: 1578 PASS, 1 DEVIATION.
- All 55 float literals equal the ROM's bytes on native, bytecode and
  ZX-UX, with the ROM run on two independent emulators.

**The one documented deviation:** rcc accepts bytes 0x80-0xFF inside
comments (maintainer decision: the corpus's header comments carry a UTF-8
`©`).  P0044/P0045/P0049 forbid them anywhere; `lex_high_byte` reports this
as DEVIATION.  Outside comments such bytes, and CR, NUL, DEL and other
control bytes everywhere, are rejected.

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
   - **DEVIATION** if none failed but a `deviation` case was accepted;
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
5. After the fixes, the new tests were also run against the old SDK: all fail
   there except `ac_float_params_recursive`, a guard for the recursive-function
   path, which was already right; so each fix is guarded.
