/* t13_abi.c - the rcc ABI, rule by rule (C48 Rev 0.11 sections 56-59:
 * P0587 P0596 P0600-P0625; docs/SPEC-SDK-R2.md section 3).  Check 130NN
 * is ABI rule NN of the table in README.md; the hand-written partner
 * routines are in t13_abi.s.  run_suite.py builds it for both back ends
 * (rcc -c, ras, rld) and runs it in rvm; rules 11, 12, 19 and 20 also have
 * link, negative-corpus and generated-code tests in run_suite.py.
 */
#include "ck.h"
#include <c48.h>

int abi_sp0(void);
int abi_sp1(int x);
int abi_sp3(int a, int b, int c);
int abi_sp8(int a, int b, int c, int d, int e, int f, int g, int h);
int abi_words(char a, int b, char *p, unsigned int c);
int abi_echo(unsigned char c);
int abi_fptr(float x);
int abi_call3(void);
int abi_frame(void);
int abi_callret(void);
int abi_callfr(void);
int abi_ixkeep(void);
int abi_clobber(void);
int abi_iy(void);
int abi_alt(void);

int abi_got[8];
char abi_target;
unsigned char abi_fb[5];
char logbuf[8];
int logn;

int lg(int v)
{
    logbuf[logn] = (char)('0' + v);
    logn++;
    return v;
}

int c3(int x, int y, int z)
{
    return x * 100 + y * 10 + z;
}

int deep(int n)
{
    if (n <= 0)
        return 0;
    return 1 + deep(n - 1);
}

int rframe(int a, int b, int n)
{
    if (n > 0)
        return rframe(a, b, n - 1);
    return abi_frame();
}

int ri(void)
{
    return -2;
}

char *rp(void)
{
    return &abi_target;
}

unsigned char rb(void)
{
    return 200;
}

char rc(void)
{
    return 255;
}

int rvn;

void rv(void)
{
    rvn++;
}

float rf(int a)
{
    return (float)a * 2.0;
}

float fm(float a, int k)
{
    a = a + 1.0;                /* the callee's copy */
    return a * (float)k;
}

int main(void)
{
    int s0;
    int s1;
    int s3;
    int s8;
    int i;
    int j;
    int k;
    float x;
    float y;
    char c;

    /* 1: arguments are evaluated left to right */
    logn = 0;
    abi_sp3(lg(1), lg(2), lg(3));
    ck(13001, logn == 3 && logbuf[0] == '1' && logbuf[1] == '2' && logbuf[2] == '3'); /* P0587 P0602 */

    /* 2: arguments 1..n-1 are pushed in order as words (no limit of 3 or 6) */
    abi_sp8(1, 2, 3, 4, 5, 6, 7, 8);
    ck(13002, abi_got[0] == 1 && abi_got[1] == 2 && abi_got[3] == 4 && abi_got[6] == 7); /* P0602 P0603 P0750 */

    /* 3: the last argument is in HL */
    ck(13003, abi_got[7] == 8 && abi_sp1(77) && abi_got[0] == 77);    /* P0602 P0603 P0617 */

    /* 4: no arguments: nothing is pushed (and there is no HL parameter) */
    s0 = abi_sp0();
    s1 = abi_sp1(5);
    s3 = abi_sp3(1, 2, 3);
    s8 = abi_sp8(1, 2, 3, 4, 5, 6, 7, 8);
    ck(13004, s0 == s1 && s0 == s3 && s0 == s8);                      /* P0602 */

    /* 5: no HL/DE/BC three-register scheme: c3(1, 2, 3) called from
     * assembly with junk in DE and BC */
    ck(13005, abi_call3() == 123 && abi_got[0] == 1 && abi_got[1] == 2 && abi_got[2] == 3); /* P0603 */

    /* 6: every scalar and pointer argument takes one 16-bit word */
    abi_words(65, -2, &abi_target, 40000u);
    ck(13006, abi_got[0] == 65 && abi_got[1] == -2 && abi_got[4] == 1 && abi_got[3] == -25536); /* P0604 */

    /* 7: a float argument is a pointer to caller-owned five bytes; the
     * callee's parameter is its own copy (pass by value), also when it is
     * not the last parameter */
    x = 1.5;
    abi_fptr(x);
    i = abi_fb[0] == 0x81 && abi_fb[1] == 0x40 && abi_fb[2] == 0 && abi_fb[4] == 0;
    abi_fptr(x + 1.0);
    i = i && abi_fb[0] == 0x82 && abi_fb[1] == 0x20;
    y = fm(x, 2);
    ck(13007, i && y == 5.0 && x == 1.5);                             /* P0596 P0604 P1061 P1078 */

    /* 8: an 8-bit argument is zero-extended in its word */
    c = 200;
    abi_words(c, 0, &abi_target, 0u);
    ck(13008, abi_got[0] == 200 && abi_echo(c) == 200 && abi_echo(255) == 255); /* P0605 */

    /* 9: the callee removes the pushed words */
    ck(13009, s0 == s3 && abi_call3() == 123);                        /* P0606 */

    /* 10: a recursive function's IX frame: [args 1..n-1][return][old IX],
     * the last argument at IX-2 */
    ck(13010, rframe(0x1111, 0x2222, 1) == 1);                        /* P0607 */

    /* 11: the same ABI between C and hand-written code in both directions
     * (run_suite.py also links native with bytecode objects) */
    s3 = abi_sp3(4, 5, 6);              /* (a statement: SP as for s0) */
    ck(13011, abi_call3() == 123 && s3 == s0 && abi_got[0] == 4 && abi_got[2] == 6); /* P0600 P0608 */

    /* 12: one convention only: the calls above need no selection syntax
     * (the negative corpus rejects calling-convention spellings) */
    ck(13012, c3(7, 8, 9) == 789);                                    /* P0609 P0610 */

    /* 13: void has no value; 16-bit and pointer results in HL */
    rvn = 0;
    ck(13013, abi_callret() == 1 && rvn == 1);                        /* P0613 P0614 */

    /* 14: an 8-bit result is in HL with H = 0 (checked by abi_callret) and
     * promotes as unsigned */
    ck(13014, rb() + 0 == 200 && rc() == 255 && abi_callret() == 1);  /* P0613 P0614 P0619 P1062 */

    /* 15: a float result is in @fac, no hidden result pointer, no extra
     * argument word */
    ck(13015, abi_callfr() == 1 && rf(4) == 8.0);                     /* P0613 P0614 P0615 P0616 */

    /* 16: the caller keeps a float result before the next call replaces @fac */
    x = rf(1) + rf(2);
    y = rf(3) * rf(1) - rf(2);
    ck(13016, x == 6.0 && y == 8.0);                                  /* P0618 */

    /* 17: IX is preserved by the callee */
    ck(13017, abi_ixkeep() == 1 && deep(4) == 4);                     /* P0622 P0623 */

    /* 18: AF BC DE HL belong to the callee: values the caller holds across
     * the call survive */
    i = 3;
    j = 4;
    k = i * 10 + abi_clobber() + j * 100 + abi_clobber();
    ck(13018, k == 432 && i == 3 && j == 4);                          /* P0622 P0623 */

    /* 19: IY is the system's: it still holds 5C3Ah in C code, after
     * floats and library calls (run_suite.py also scans the generated code) */
    x = x * 3.0;
    i = abi_iy();
    i = i + (strlen("abc") == 3u);
    ck(13019, i == 2 && abi_iy() == 1);                               /* P0623 P0624 */

    /* 20: the alternate set is not the program's: scrambling it changes
     * nothing the code relies on */
    i = 5;
    k = i + abi_alt() + abi_alt() * i;
    x = 2.0;
    y = x * x + (float)abi_alt();
    ck(13020, k == 11 && y == 5.0);                                   /* P0623 P0625 */

    return ck_done();
}
