/* t4_float.c - C48 conformance: five-byte floating literals and arithmetic
 * (spec sections 16, 17, 36, 43, 56, 58, 84, 94; Appendix C).
 *
 * show(id, literal) prints "L<id>" and the five bytes the compiler produced
 * for the literal; run_suite.py compares them with the bytes the 48K ROM's
 * own DEC-TO-FP, STACK-BC and negate routines give (romoracle.py).
 * Golden-set paragraphs: P0193 P0198 P0199 P0200 P0201 P0202 P0203 P0204
 * P0205 P0906 P0907 P0908 P0909 P0910 P0911 P0913 P0808 P0810.
 */
#include "ck.h"

void show(unsigned int id, float x)
{
    void *t;

    t = &x;
    putchar('L');
    ck_dec(id);
    ck_hex(t, 5);
    putchar(' ');
}

/* 36: constants folded by the compiler, compared below with the same
 * operations done at run time */
float k_third = 1.0 / 3.0;
float k_back = 1.0 / 3.0 * 3.0;
float k_tenth = 2.0 * 0.1;
float k_mix = 7 / 2.0 + 1;
float k_cast = (float)7 / 3;
float k_neg = -2.5 * 4.0e-3;
int k_cmp = 0.1 + 0.2 < 0.3;

/* same5: the five bytes at a and at b are equal */
float s5_a;
int same5(float *pb)
{
    unsigned char *x;
    unsigned char *y;
    void *t;
    int i;

    t = &s5_a;
    x = t;
    t = pb;
    y = t;
    for (i = 0; i < 5; i++)
        if (x[i] != y[i])
            return 0;
    return 1;
}

/* 56, Appendix E: float parameters are values; 58: float results */
float bump(float x)
{
    x = x + 1.0;
    return x;
}
float half(float x)
{
    return x / 2;
}

int main(void)
{
    float a;
    float b;
    float c;
    float r;

    /* 94: golden set */
    show(1, 0.0);
    show(2, 0);
    show(3, 1);
    show(4, 1.0);
    show(5, -1);
    show(6, -1.0);
    show(7, .5);
    show(8, 0.5);
    show(9, 0.25);
    show(10, 1.25);
    show(11, 2);
    show(12, 2.0);
    show(13, 10);
    show(14, 10.0);
    show(15, -12);
    show(16, -12.0);
    show(17, 0.1);
    show(18, 0.2);
    show(19, 0.3);
    show(20, 3.14159);
    show(21, 2.71828);
    show(22, 1.5);
    show(23, 100.5);
    show(24, 12345.678);
    show(25, 0.001);
    show(26, 1e3);
    show(27, 1E-2);
    show(28, 1.25e2);
    show(29, 2.5E+3);
    show(30, .25e+1);
    show(31, 1e10);
    show(32, 1e-10);
    show(33, 1e38);
    show(34, 1.7e38);
    show(35, 1e-38);
    show(36, 1e-39);
    show(37, 65535.0);
    show(38, 65536.0);
    show(39, 32768.0);
    show(40, 1.25f);
    show(41, 1.25F);
    show(42, 7e0f);
    show(43, 123456789.0);
    show(44, 0.999999999);
    show(45, 1.);
    show(46, 65535);
    show(47, 32767);
    show(48, -32767);
    show(49, 0x7f);
    show(50, 1.0e0);
    show(51, 000.5);
    show(52, 99999.0);
    show(53, 1.70141183e38);
    show(54, -0.5);
    show(55, 5e-1);

    /* 36: compile-time and run-time evaluation agree */
    a = 1.0;
    b = 3.0;
    s5_a = a / b;
    ck(5001, same5(&k_third));                                          /* P0418 P0807 P1069 */
    s5_a = s5_a * b;
    ck(5002, same5(&k_back));                                           /* P0418 P0807 P1069 */
    a = 2.0;
    b = 0.1;
    s5_a = a * b;
    ck(5003, same5(&k_tenth));                                          /* P0418 P0807 */
    a = 7;
    s5_a = a / 2.0 + 1;
    ck(5004, same5(&k_mix) && k_mix == 4.5);                            /* P0417 P0418 */
    s5_a = a / 3;
    ck(5005, same5(&k_cast));                                           /* P0417 P0418 */
    a = -2.5;
    b = 4.0e-3;
    s5_a = a * b;
    ck(5006, same5(&k_neg));                                            /* P0418 */
    a = 0.1;
    b = 0.2;
    c = 0.3;
    ck(5007, (a + b < c) == k_cmp);                                     /* P0418 P0413 */

    /* 17, 19: float objects are five bytes; zero is all-zero bytes */
    ck(5101, sizeof(a) == 5 && sizeof(float) == 5);                     /* P0194 P0195 */
    a = 0;
    s5_a = 0.0;
    ck(5102, same5(&a) && a == 0.0 && !a);                              /* P0232 P0515 */

    /* 56, Appendix E: pass-by-value of floats; 58: float returns */
    a = 2.0;
    r = bump(a);
    ck(5201, a == 2.0 && r == 3.0);                                     /* P0595 P0596 P1061 P1078 P0354 P0357 */
    r = bump(1.0) + bump(2.0);
    ck(5202, r == 5.0);                                                 /* P0613 P0614 P0615 P0618 */
    r = (half(8.0) + half(4.0)) * half(6.0);
    ck(5203, r == 18.0);                                                /* P0616 P0617 P0618 */
    a = 6.0;
    b = 2.0;
    ck(5204, half(a) - b == 1.0 && bump(half(a)) == 4.0);               /* P0614 P0618 */

    /* 42-44: integer/float mixing */
    ck(5301, 1 + 1.5 == 2.5 && 5 / 2.0 == 2.5 && 1.5 * 2 == 3.0);       /* P0468 P0550 */
    a = 32767;
    b = -32767;
    ck(5302, a == 32767.0 && b == -32767.0 && a + b == 0);              /* P0480 */
    return ck_done();
}
