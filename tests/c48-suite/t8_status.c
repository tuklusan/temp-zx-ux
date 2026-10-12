/* t8_status.c - C48 conformance: run-time error traps and the process exit
 * status (spec sections 31, 43, 45, 53, 69; Appendix C).
 *
 * run_suite.py runs "t8_status N" for each case N below and checks the exit
 * status and that the program printed "B" (before) but not "A" (after the
 * operation that must end it).  Case table (N: expected status, paragraphs):
 *   1: 1  int division by zero              P0489
 *   2: 1  int remainder by zero             P0489
 *   3: 1  unsigned division by zero         P0493
 *   4: 1  unsigned remainder by zero        P0493
 *   5: 1  float -> int out of range         P0479 P0481 P0551 P0572 P0573
 *   6: 1  float -> char of a negative value P0481 P1060
 *   7: 1  float -> unsigned int of -1.0     P0481 P0572
 *   8: 1  float multiplication overflow     P0573 P1054
 *   9: 1  float division by zero            P0573 P1054
 *  10: 1  non-void function falls through   P0695 P1053
 *  11: 1  main falls through (prints "BA ")  P0695
 *  12: 0  main returns 256                  P0372 P1063
 *  13: 1  main returns 257                  P0372 P1063
 *  14: 255 main returns -1                  P0372 P1063
 *  15: 1  main returns 1                    P0372
 *  16: 3  exit(3)                           P0573 P1042
 *  17: 0  main returns 0                    P0372 P0696
 *  18: 1  float -> short of -32769.0        P0481 P0572
 *  19: 1  float -> int cast out of range    P0572 P0573
 */
#include "ck.h"
void exit(int status);

int zero;
float fzero;

int ends(int x)
{
    if (x)
        return 1;
}

int main(int argc, char **argv)
{
    int n;
    int i;
    unsigned int u;
    char c;
    short s;
    float f;
    char *a;

    n = 0;
    a = argv[1];
    while (*a) {
        n = n * 10 + (*a - '0');
        a++;
    }
    i = 7;
    u = 7u;
    putchar('B');
    if (n == 1)
        i = i / zero;
    if (n == 2)
        i = i % zero;
    if (n == 3)
        u = u / zero;
    if (n == 4)
        u = u % zero;
    if (n == 5) {
        f = 40000.0;
        i = f;
    }
    if (n == 6) {
        f = -1.0;
        c = f;
    }
    if (n == 7) {
        f = -1.0;
        u = f;
    }
    if (n == 8) {
        f = 1e38;
        f = f * f;
    }
    if (n == 9) {
        f = 1.0;
        f = f / fzero;
    }
    if (n == 10)
        i = ends(zero);
    if (n == 11) {
        putchar('A');
        putchar(' ');
    }
    if (n == 12)
        return 256;
    if (n == 13)
        return 257;
    if (n == 14)
        return -1;
    if (n == 15)
        return 1;
    if (n == 16)
        exit(3);
    if (n == 17)
        return 0;
    if (n == 18) {
        f = -32769.0;
        s = f;
    }
    if (n == 19) {
        f = 1e5;
        i = (int)f;
    }
    if (n == 11)
        ;
    else {
        putchar('A');
        return 0;
    }
}
