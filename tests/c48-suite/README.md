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
python3 tools/build.py                          # --zxux only: ZX-UX build, then
# tap2sna.py build/ZX-UX.tzx -> build/test.z80   (the snapshot tests/suite.py uses)
python3 sdk/lib/build.py                                             # builds sdk/lib/libc48.ssa
python3 tests/c48-suite/run_suite.py --zxux     # about 1 minute
```

`--only run,status,link,cases,lib,tool` selects groups. Without `--zxux`, the cassette runs on
ZX-UX are skipped.

The run writes three files to `build/c48-suite/`:

- `results.json`: every test execution;
- `resolution.csv`: one row per paragraph, with its full text;
- `RESOLUTION.md`: a summary, the failed tests, and the paragraph table with full text.

The exit status is 0 when the run itself worked. Deviations are reported in those files; they
do not change the exit status.

## Files

| File | What it tests |
|---|---|
| `ck.h` | `ck(id, ok)` prints `F<id>` when a check fails, and `ck_done()` prints `N<count>.`. The `/* Pnnnn ... */` comment after each `ck()` call names the paragraphs that check covers. |
| `t1_lex.c` | Source form, comments, identifiers, tokens, integer/char/string/float literals, every operator and punctuator (§4–17) |
| `t2_types.c` | Sizes, plain-char signedness, representation and alignment, declarators, linkage and scope, initializers, pointers (§18–34) |
| `t3_expr.c` | Constant expressions, conversions, promotions, overflow wrap, shifts, comparisons, pointer arithmetic, `sizeof`, lvalues (§35–52) |
| `t4_float.c` | 55 golden float literals, compared byte-for-byte with the 48K ROM's own DEC-TO-FP/STACK-BC/negate (`romoracle.py`); also constant folding vs run time, and float parameters and results |
| `t5_stmt.c` | Evaluation order, calls, returns, locals, every statement form |
| `t6_pp.c` + `t6_*.h` | `#define` and `#include`, including nesting, include-once behaviour and `<c48.h>` |
| `t7_main.c` | `main(argc, argv)` with arguments `alpha b`, and `<c48.h>` calls |
| `t8_status.c` | Run-time traps and exit statuses. There are 19 cases plus a control; the case table is at the top of the file. |
| `t9_main.c`, `t9_mod.c` | Separate compilation (`-c`), `rld` linking, SSA1 archives, and external/static linkage |
| `t10_abi.c`, `t10_abi.s` | The calling convention, checked against hand-written assembler |
| `n1_lex.cases` … `n4_pp.cases` | 474 programs that must be rejected (status 1, an `rcc:` diagnostic, and no output file). `diag=` additionally requires particular diagnostic text. |
| `p_accept.cases` | 44 small programs that must build and exit with status 0 on both back ends. When a case is marked `may`, a failure is reported as NOTE (optional or conditional requirement). |
| `dispositions.tsv` | Explains why each paragraph that no test covers has no test. The kinds are HEADING, FRONT, INFO, SUMMARY, PROCESS, DOC, OTHER-IMPL, UNSPECIFIED and RESOURCE. |
| `romoracle.py` | Runs the ROM's float routines in the emulator to serve as the reference |
| `run_suite.py` | The runner |

Most programs are built with `--native` and with `--bytecode`, and run in `sdk/rvm.py`. t1–t7 are
also loaded from an `rtap` cassette and run on ZX-UX itself; their screens must agree with the
rvm runs. The float literal bytes are also checked on ZX-UX.

## Result (Rev 0.11 docx, tree at the commit that adds this suite)

These are the counts for the commit that adds this suite.

- **Paragraphs:**
  - 688 PASS;
  - **49 FAIL**;
  - 3 NOTE;
  - 250 resolved without a test:
    - 120 HEADING
    - 37 OTHER-IMPL
    - 29 INFO
    - 25 PROCESS
    - 22 DOC
    - 7 FRONT
    - 4 SUMMARY
    - 4 UNSPECIFIED
    - 2 RESOURCE
- **Test executions:** 1562 in total: 1514 PASS, 46 FAIL and 2 NOTE.

All 55 float literals match the ROM on native, bytecode and ZX-UX. Results on ZX-UX are
identical to the rvm results.

### Deviations found (each FAIL in RESOLUTION.md)

1. **Global alignment.**
   - The deviation: when a global `int`, `short` or pointer object follows a `char` object, it
     is placed at an odd address. The native build also places a global `unsigned int` array at
     an odd address.
   - Paragraphs: P0222, P0228, P0231, P0306, P0330. P0029, P0788 and P0919 fail as well,
     because native and bytecode give different results here.
   - Tests: `t2_types.c` ck2406–2409.
   - Locals are aligned correctly.
2. **A declaration is not visible within its own initializer.** `int g = sizeof g;` is rejected
   with "undeclared identifier g" (P0270). `sizeof other` in an initializer is accepted (P0412).
3. **Float `++` and `--` cannot be used as a value.** rcc reports "unsupported … by this back
   end" (P0563–P0565, P1073).
4. **A float parameter that is not the last parameter hangs at run time** (native and bytecode).
   - Paragraphs: P0342, P0596, P0604, P0957, P1061, P1078.
   - Cases: `ac_float_param_first` and `ac_float_params_two`.
   - Likely cause: the float copy helper `@fmov` clobbers BC while BC holds the return address.
5. **Bytecode separate compilation cannot link.**
   - Every bytecode SSO1 defines the VM support symbols `@vmtab`, `@gs` and `@ct`, so linking two
     of them reports duplicate symbols.
   - Paragraphs: P0029, P0255–P0257, P0287, P0288, P0763, P0764, P0768, P0989, P1089.
   - Tests: t9 (bytecode).
   - `rld` names whichever duplicate it finds first (`@vmtab`, `@gs` or `@ct`). The order depends on
     Python's hash seed, so the runner sets `PYTHONHASHSEED=0` to make the report repeatable.
6. **An external function that is never called is dropped from an object that contains
   `main`.** Another module calling that function then fails to link with "undefined: _helper"
   (P0255, P0287, P0288, P0768).
7. **Library link failures.**
   - `udg_get` fails with undefined `_udg_define.cp`.
   - A program whose only heap function is `free` fails with undefined `___heap`, `___heapsz`
     and `___heapw`.
   - Paragraphs: P0735, P0924, P1042.
8. **`rcc -o x.c x.c` overwrites the source file** (P1085).
9. **Constructs accepted that the spec says must be rejected.**
   - A 0xE9 byte inside a comment (P0044, P0045, P0049).
   - A local `int __x` (P0116).
   - `static int f(void); extern int f(void);` (P0284, P0878).
   - `<` or `>` between `void *` values (P0535, P1058).
   - In the preprocessor:
     - `#define A"x"`, with no space before the value (P0708);
     - `#define const 3` (P0720);
     - `#define _start 3` (P0116, P0720);
     - a block comment that runs past the end of a directive line (P0701);
     - `#include < c48.h >` (P0732);
     - a 16-character macro name (P0085, P0087, P0716).
10. **Function-like macros are rejected, but the diagnostic does not say "function-like"**
    (P0708, P0741).

The 3 NOTE paragraphs (P0317–P0319) come from one case: `NULL` is not defined by `<c48.h>`. The
spec requires `NULL` only "once the declaration set is frozen", so this is reported as a NOTE,
not a FAIL.

The following items rest on a reading of the spec and could reasonably be argued the other way:

- the 0xE9 byte in a comment: P0049 lists only ASCII as legal;
- `#include < c48.h >`: P0732 gives the exact spelling;
- the diagnostic wording for function-like macros.

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
   - **NOTE** if none failed but at least one `may` case did not succeed;
   - **PASS** if every tagged test passed;
   - otherwise, its disposition.
   - A paragraph with neither a test nor a disposition would show as UNRESOLVED; none do.
3. The tables were audited separately from the runner:
   - the docx was re-parsed and its text compared, whitespace-normalised, with every CSV row;
   - each verdict was recomputed from `results.json` and `dispositions.tsv`;
   - every failing test was confirmed to be named in its paragraph's row.
4. Every deviation was reproduced by hand before being reported. The expected values in the
   suite were checked against the spec text rather than against what rcc does.
