/* t10_abi.c - C48 conformance: the rcc calling convention, return ABI and
 * register ownership as seen by hand-written assembly (spec sections 57-59,
 * Appendix C).  run_suite.py compiles this file with -c, assembles
 * t10_abi.s with sdk/ras and links both with libc48.ssa through sdk/rld.
 */
#include "ck.h"

int abi_args(int a, int b, int c);
int abi_echo(unsigned char c);
int abi_echo2(char a, int b);
int abi_clobber(void);
float abi_fret(void);
int abi_fbyte(float x);
int abi_callc(void);
int abi_ixkeep(void);

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
int depth(int n)
{
    int v;

    if (n <= 0)
        return abi_clobber();
    v = n;
    return depth(n - 1) * (v == n);
}

int main(void)
{
    int i;
    int k;
    char c;
    float f;

    ck(10010, c3(4, 5, 6) == 456 && deep(3) == 3);                      /* P0361 */
    ck(10001, abi_args(1, 2, 3) == 0x0123 && abi_args(15, 0, 9) == 0x0F09); /* P0587 P0602 P0603 P0606 P0600 P0601 */
    c = 200;
    ck(10002, abi_echo(c) == 200 && abi_echo(255) == 255);              /* P0604 P0605 */
    ck(10003, abi_echo2(c, 7) == 200);                                  /* P0603 P0604 P0605 */
    i = 7;
    k = abi_clobber() + i;
    ck(10004, k == 8);                                                  /* P0622 P0623 P0624 P0625 P0626 */
    ck(10005, depth(5) == 1);                                           /* P0607 P0622 P0623 P0625 */
    f = abi_fret();
    ck(10006, f == 7.0 && abi_fret() + 1.0 == 8.0);                     /* P0613 P0614 P0615 P0617 P0618 */
    ck(10007, abi_fbyte(0.5) == 0x7F && abi_fbyte(1.5) == 0x81);         /* P0596 P0604 */
    ck(10008, abi_callc() == 123);                                      /* P0602 P0606 P0608 P0600 */
    ck(10009, abi_ixkeep() == 1);                                       /* P0607 P0622 */
    return ck_done();
}
