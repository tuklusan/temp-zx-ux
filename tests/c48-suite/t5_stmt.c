/* t5_stmt.c - C48 conformance: evaluation order, function calls, the
 * calling convention as seen from C, statements and control flow
 * (spec sections 29-31, 55-69, 77, 89; Appendices C and E).
 */
#include "ck.h"

int lg;
int note(int digit, int value)
{
    lg = lg * 10 + digit;
    return value;
}
int fa(void)
{
    return note(1, 1);
}
int fb(void)
{
    return note(2, 2);
}
int fc(void)
{
    return note(3, 3);
}
int f3(int x, int y, int z)
{
    return x * 100 + y * 10 + z;
}
int f2(int x, int y)
{
    return x * 10 + y;
}
int arr[4];
int *pick(void)
{
    note(1, 0);
    return arr;
}
int sum8(int a, int b, int c, int d, int e, int f, int g, int h)
{
    return a + 2 * b + 3 * c + 4 * d + 5 * e + 6 * f + 7 * g + 8 * h;
}
int sum12(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j, int k, int l)
{
    return a - b + c - d + e - f + g - h + i - j + k - l;
}
char *pchain(char *a, char *b, char *c)
{
    return b;
}
int setp(int x)
{
    x = 99;
    return x;
}
void setref(int *p)
{
    *p = 42;
}
int fact(int n)
{
    if (n <= 1)
        return 1;
    return n * fact(n - 1);
}
int ev;
int od(int n);
int even(int n)
{
    if (n == 0)
        return 1;
    return od(n - 1);
}
int od(int n)
{
    if (n == 0)
        return 0;
    return even(n - 1);
}
unsigned char ret_uc(void)
{
    return 250;
}
char ret_c(int v)
{
    return v;
}
short ret_s(void)
{
    return -3;
}
unsigned short ret_us(void)
{
    return 65535u;
}
int vcount;
void vf(void)
{
    vcount++;
}
void vret(int x)
{
    if (x)
        return;
    vcount = vcount + 10;
}
int local_init(void)
{
    int a = 5;
    a++;
    return a;
}
int block_init(int n)
{
    int t;
    int i;

    t = 0;
    for (i = 0; i < n; i++) {
        int b = 3;
        t = t + b;
        b = 100;
    }
    return t;
}
int argc_only(int argc, int x)
{
    return argc + x;
}

int main(void)
{
    int i;
    int j;
    int k;
    int n;
    char *s;
    float f;
    int *p;

    /* 55, 56, 89: evaluation order and value capture */
    lg = 0;
    ck(6001, f3(fa(), fb(), fc()) == 123 && lg == 123);                 /* P0586 P0587 P0594 P0849 P0850 P0585 P0590 P0848 */
    lg = 0;
    i = fa() + fb();
    ck(6002, i == 3 && lg == 12);                                       /* P0586 P0588 P0849 P0850 */
    lg = 0;
    i = note(2, 5) - note(1, 3);
    ck(6003, i == 2 && lg == 21);                                       /* P0586 P0588 */
    i = 1;
    ck(6004, f2(i++, i) == 12 && i == 2);                               /* P0586 P0587 P0594 P0849 P0850 */
    i = 1;
    ck(6005, f2(i, i++) == 11 && i == 2);                               /* P0594 */
    i = 5;
    ck(6006, f3(i++, i++, i) == 567);                                   /* P0594 P0587 */
    i = 7;
    i = i++;
    ck(6007, i == 7);                                                   /* P0560 P0849 P0850 P1052 */
    lg = 0;
    arr[2] = 0;
    pick()[note(2, 2)] = note(3, 9);
    ck(6008, lg == 123 && arr[2] == 9);                                 /* P0588 P0560 */
    lg = 0;
    i = note(1, 4) * (note(2, 5) + note(3, 6));
    ck(6009, i == 44 && lg == 123);                                     /* P0586 P0589 */
    lg = 0;
    i = note(1, 0) && note(2, 1);
    j = note(3, 1) || note(4, 0);
    ck(6010, i == 0 && j == 1 && lg == 13);                             /* P0522 P0523 P0586 P0851 */
    lg = 0;
    i = note(1, 1) < note(2, 2);
    ck(6011, i == 1 && lg == 12);                                       /* P0588 */

    /* 56, 57, 77: calls, argument counts, pass-by-value */
    ck(6101, sum8(1, 2, 3, 4, 5, 6, 7, 8) == 204);                      /* P0594 P0602 P0603 P0750 */
    ck(6102, sum12(12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1) == 6);        /* P0594 P0602 P0750 P0918 */
    ck(6103, pchain("a", "bc", "def")[1] == 'c');                       /* P0602 P0604 */
    i = 5;
    ck(6104, setp(i) == 99 && i == 5);                                  /* P0595 P1078 */
    setref(&i);
    ck(6105, i == 42);                                                  /* P0595 */
    ck(6106, fact(7) == 5040 && fact(1) == 1);                          /* P0361 */
    ck(6107, even(10) == 1 && od(7) == 1 && even(3) == 0);              /* P0361 P0362 P0273 */
    ck(6108, ret_uc() == 250 && ret_uc() + 10 == 260 && ret_c(300) == 44 && ret_c(-1) + 1 == 256); /* P0605 P0614 P0619 P1062 P0354 P0356 */
    ck(6109, ret_s() == -3 && ret_us() == 65535u && ret_us() > 0);      /* P0614 */
    vcount = 0;
    vf();
    vf();
    vret(1);
    vret(0);
    ck(6110, vcount == 12);                                             /* P0355 P0634 P0643 P0693 */
    ck(6111, argc_only(3, 4) == 7);                                     /* P0367 */

    /* 24, 32, Appendix E: automatic initializers on every activation */
    ck(6201, local_init() == 6 && local_init() == 6);                   /* P0382 P1068 P1077 */
    ck(6202, block_init(4) == 12);                                      /* P0382 P1068 P1077 */

    /* 60-69: statements */
    i = 1;
    if (i)
        if (0)
            i = 9;
        else
            i = 2;
    ck(6301, i == 2);                                                   /* P0650 P0651 P0652 P0653 P0654 P0629 P0630 P0649 P1001 P1002 P1030 */
    i = 0;
    if (i)
        i = 5;
    else {
        i = 6;
    }
    ck(6302, i == 6);                                                   /* P0652 */
    i = 0;
    while (i < 5)
        i++;
    ck(6303, i == 5);                                                   /* P0658 P0659 P0657 */
    i = 10;
    while (i < 5)
        i = 100;
    ck(6304, i == 10);                                                  /* P0659 */
    i = 10;
    do
        i++;
    while (i < 5);
    ck(6305, i == 11);                                                  /* P0664 P0665 P0666 P0667 P0663 */
    k = 0;
    for (i = 0; i < 5; i++)
        k = k + i;
    ck(6306, k == 10 && i == 5);                                        /* P0671 P0672 P0673 P0674 P0670 */
    k = 0;
    for (;;) {
        k++;
        if (k == 3)
            break;
    }
    ck(6307, k == 3);                                                   /* P0634 P0671 P0673 P0679 P0681 */
    k = 0;
    i = 0;
    for (; i < 3;)
        i++;
    ck(6308, i == 3);                                                   /* P0671 */
    k = 0;
    for (i = 0; i < 5; i++) {
        if (i == 2)
            continue;
        k = k + i;
    }
    ck(6309, k == 8);                                                   /* P0675 P0686 P0689 */
    k = 0;
    i = 0;
    while (i < 5) {
        i++;
        if (i == 3)
            continue;
        k = k + i;
    }
    ck(6310, k == 12);                                                  /* P0686 P0687 */
    k = 0;
    i = 0;
    do {
        i++;
        if (i < 4)
            continue;
        k = k + 100;
    } while (i < 3);
    ck(6311, i == 3 && k == 0);                                         /* P0686 P0688 */
    k = 0;
    for (i = 0; i < 3; i++) {
        for (j = 0; j < 10; j++) {
            if (j == 2)
                break;
            k++;
        }
    }
    ck(6312, k == 6);                                                   /* P0679 P0680 P0681 P0682 */
    k = 0;
    i = 0;
    while (1) {
        do {
            k++;
            break;
        } while (1);
        i++;
        if (i == 4)
            break;
    }
    ck(6313, k == 4);                                                   /* P0679 P0680 P0681 */
    i = 3;
    ;
    {
        ;
        {
            i = i + 1;
        }
    }
    ck(6314, i == 4);                                                   /* P0637 P0638 P0639 P0640 P0644 P0646 P0645 */
    p = &i;
    n = 0;
    while (p) {
        n++;
        p = 0;
    }
    f = 0.5;
    if (f)
        n = n + 10;
    for (f = 2.0; f; f = f - 1.0)
        n = n + 100;
    s = "x";
    do
        n = n + 1000;
    while (!s);
    ck(6315, n == 1211);                                                /* P0634 P0653 P0660 P0666 P0674 */
    return ck_done();
}
