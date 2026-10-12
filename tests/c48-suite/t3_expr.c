/* t3_expr.c - C48 conformance: constant expressions, precedence, lvalues,
 * promotions, conversions, integer arithmetic, division, shifts, bitwise
 * and logical operators, comparisons, pointer arithmetic, assignment,
 * increment/decrement, casts and sizeof (spec sections 35-54, 88, 90,
 * Appendices C and D).
 */
#include "ck.h"

/* 35: constant expressions in file-scope initializers and array bounds */
int ce_cast = (int)0x8000u;
int ce_fcmp = 1.0 < 2.0;
int ce_shift = 1 << 4;
int ce_logic = !0 + (3 && 0) + (0 || 2) + ~0;
unsigned int ce_size = sizeof(float) * 3 + sizeof(char *);
char ce_bound[(10 - 2) * 2 % 7];
int ce_div = -7 / 2;
float ce_fexpr = 1.5 * 4 - 0.5;
float ce_fint = (float)7 / 2;
int ce_ftoi = (int)(2.5 * 3.0);
int ce_char = 'A' + 1;
unsigned char ce_uc = (unsigned char)300;
int ce_wrap = 32767 + 1;
int ce_shneg = (int)0x8000u >> 15;

int log_v;
int note(int digit, int value)
{
    log_v = log_v * 10 + digit;
    return value;
}
int idx_arr[3];
int *base_fn(void)
{
    note(1, 0);
    return idx_arr;
}
char ret_char(void)
{
    return 200;
}
unsigned int addrv(void *x)
{
    unsigned char *b;
    void *t;

    t = &x;
    b = t;
    return b[0] + 256u * b[1];
}
int never(void)
{
    log_v = 99;
    return 1;
}

int main(void)
{
    int i;
    int j;
    int k;
    unsigned int u;
    unsigned int v;
    char c;
    char c2;
    unsigned char uc;
    short s;
    unsigned short us;
    float f;
    int a[6];
    int *p;
    int *q;
    char *cp;
    float fa[3];
    float *fp;
    void *vp;
    char ca[4];

    /* 35, 36: constant expressions */
    ck(3001, ce_cast < 0 && ce_cast == (-32767 - 1) && ce_fcmp == 1);  /* P0410 P0411 P0413 P0565 P1069 P1035 */
    ck(3002, ce_shift == 16 && ce_logic == 1 + 0 + 1 - 1);              /* P0411 P0501 */
    ck(3003, ce_size == 17 && sizeof(ce_bound) == 2);                   /* P0410 P0411 P1035 */
    ck(3004, ce_div == -3 && ce_char == 66 && ce_uc == 44);             /* P0411 P0413 */
    ck(3005, ce_fexpr == 5.5 && ce_fint == 3.5 && ce_ftoi == 7);        /* P0411 P0417 P0418 P1069 */
    ck(3006, ce_wrap == (-32767 - 1) && ce_shneg == -1);                /* P0411 P0414 P0501 */

    /* 38: precedence and associativity */
    ck(3101, 1 + 2 * 3 == 7 && (1 + 2) * 3 == 9);                       /* P0434 P0435 P1032 */
    ck(3102, 8 - 2 - 1 == 5 && 64 / 4 / 2 == 8 && 17 % 5 * 3 == 6);     /* P0435 */
    ck(3103, (1 << 2 + 1) == 8 && (16 >> 1 >> 1) == 4);                 /* P0435 */
    ck(3104, (1 < 2 == 1) == 1 && (3 > 2 > 1) == 0);                    /* P0435 */
    ck(3105, (6 & 3 == 3) == 0 && (5 & 3 ^ 6) == 7 && (1 | 2 ^ 3) == 1); /* P0435 */
    ck(3106, (1 || 0 && 0) == 1 && (0 && 1 || 1) == 1);                 /* P0435 */
    i = 1;
    ck(3107, -i++ == -1 && i == 2 && - -3 == 3 && !~0 == 0);            /* P0435 */
    ck(3108, (char)255 + 1 == 256 && sizeof i + 1 == 3);                /* P0435 */
    i = j = k = 4;
    ck(3109, i == 4 && j == 4 && k == 4);                               /* P0435 P0547 P0446 */
    a[0] = 10;
    a[1] = 20;
    p = a;
    ck(3110, *p++ == 10 && *p == 20 && &a[1] == p);                     /* P0435 P0440 P0441 */
    ck(3111, base_fn()[2] == 0 && ret_char() == 200);                   /* P0435 */

    /* 40, 51: assignment value and type */
    i = (c = 300);
    ck(3201, i == 44 && c == 44);                                       /* P0547 P0476 P0454 */
    i = (u = -1);
    ck(3202, i == -1 && u == 65535u);                                   /* P0547 */
    f = (i = 3.9);
    ck(3203, f == 3.0);                                                 /* P0547 P0551 */
    i = 7;
    i = i++;
    ck(3204, i == 7);                                                   /* P0560 P0849 P0850 P1052 */
    i = 0;
    a[0] = 5;
    a[1] = 6;
    a[i] = i++;
    ck(3205, a[0] == 0 && a[1] == 6 && i == 1);                         /* P0560 P0588 */

    /* 41, 42: promotions and usual arithmetic conversions */
    c = 200;
    c2 = 100;
    ck(3301, c + c2 == 300 && sizeof(c + c2) == 2);                     /* P0460 P0461 P0462 P0469 P0471 */
    uc = 255;
    ck(3302, uc + 1 == 256 && -uc == -255);                             /* P0461 P0462 */
    s = -1;
    ck(3303, s + 0 == -1 && s < 0);                                     /* P0461 P0462 */
    us = 65535u;
    ck(3304, us + 1 == 0 && (us > -1) == 0);                            /* P0461 P0470 */
    ck(3305, (-1 < 1u) == 0 && -1 + 0u == 65535u && (-1 < 1) == 1);     /* P0470 P0471 P0473 P0467 */
    ck(3306, 1 + 0.5 == 1.5 && 3 / 2.0 == 1.5 && 3 / 2 == 1);           /* P0468 P0442 P0443 */
    c = 0;
    ck(3307, ~c == -1 && sizeof(~c) == 2);                              /* P0505 */
    ck(3308, ('A' << 8) == 0x4100 && sizeof('A' << 8) == 2);            /* P0464 P0444 */

    /* 43: integer conversion */
    uc = 0x1234;
    c = 0x1281;
    ck(3401, uc == 0x34 && c == 0x81);                                  /* P0476 P0477 */
    s = 40000u;
    ck(3402, s == -25536);                                              /* P0477 P0478 */
    u = -2;
    us = 70000.0 - 69999.0;
    ck(3403, u == 65534u && us == 1);                                   /* P0476 P0479 */
    i = -5;
    f = i;
    ck(3404, f == -5.0);                                                /* P0479 P0480 P0550 */
    u = 65535u;
    f = u;
    ck(3405, f == 65535.0);                                             /* P0480 */
    c = 255;
    f = c;
    s = -32767;
    ck(3406, f == 255.0 && s * 1.0 == -32767.0);                        /* P0480 */
    i = 3.9;
    j = -3.9;
    u = 65535.0;
    ck(3407, i == 3 && j == -3 && u == 65535u);                         /* P0481 P0551 P0572 */
    ck(3408, (char)300.0 == 44 && (unsigned char)255.9 == 255);         /* P0481 P1060 */
    f = 32767.9;
    i = f;
    f = -32768.0;
    j = f;
    ck(3409, i == 32767 && j == (-32767 - 1));                          /* P0481 */

    /* 44: wrap-around */
    c = 255;
    c = c + 1;
    ck(3501, c == 0);                                                   /* P0484 P0486 P0843 P0842 */
    i = 32767;
    i = i + 1;
    ck(3502, i == (-32767 - 1) && i < 0);                               /* P0484 P0843 */
    i = (-32767 - 1) - 1;
    ck(3503, i == 32767);                                               /* P0484 P0843 */
    u = 65535u + 1u;
    ck(3504, u == 0 && 65535u + 1u == 0);                               /* P0484 P0843 */
    i = 300;
    i = i * i;
    ck(3505, i == 24464);                                               /* P0484 P0485 */
    i = (int)0x8000u;
    ck(3506, -i == i && i * -1 == i && i - 1 == 32767);                 /* P0484 */
    i = 1;
    ck(3507, (i << 15) < 0 && (i << 15) == (int)0x8000u);               /* P0484 P0498 */

    /* 45: division and remainder */
    i = -7;
    j = 3;
    ck(3601, i / j == -2 && i % j == -1);                               /* P0489 P0843 */
    i = 7;
    j = -3;
    ck(3602, i / j == -2 && i % j == 1);                                /* P0489 P0843 */
    ck(3603, -7 / 3 == -2 && -7 % 3 == -1 && 7 / -3 == -2 && 7 % -3 == 1); /* P0489 P0843 */
    i = (int)0x8000u;
    j = -1;
    ck(3604, i / j == (int)0x8000u && i % j == 0);                      /* P0490 P0491 P0492 P0843 */
    ck(3605, ((int)0x8000u) / -1 == (int)0x8000u && ((int)0x8000u) % -1 == 0); /* P0490 P0491 P0843 */
    u = 65535u;
    v = 10u;
    ck(3606, u / v == 6553u && u % v == 5u && u / 2u == 32767u);        /* P0493 P1059 */
    ck(3607, -7 / 2u == 32764u && -7 % 2u == 1u);                       /* P0493 P0470 */

    /* 46: shifts */
    c = 1;
    ck(3701, (c << 0) == 1 && (c << 7) == 128 && (c << 8) == 1);        /* P0496 P0497 P0844 P1047 */
    ck(3702, (c << 15) == 128 && (c << 16) == 1 && (c << 31) == 128 && (c << 255) == 128); /* P0497 P0844 */
    ck(3703, sizeof(c << 1) == 1 && sizeof(c >> 1) == 1);               /* P0463 P0498 P1047 P1008 */
    c = 0x81;
    ck(3704, (c << 1) == 2 && (c >> 7) == 1);                           /* P0496 P0498 */
    uc = 0xFF;
    ck(3705, (uc << 4) == 0xF0 && sizeof(uc << 4) == 1);                /* P0496 P0498 */
    i = 1;
    ck(3706, (i << 0) == 1 && (i << 7) == 128 && (i << 8) == 256);      /* P0497 P0844 */
    ck(3707, (i << 15) == (int)0x8000u && (i << 16) == 1 && (i << 31) == (int)0x8000u && (i << 255) == (int)0x8000u); /* P0497 P0844 P1048 */
    ck(3708, sizeof(i << 1) == 2);                                      /* P0498 */
    i = -16;
    ck(3709, (i >> 2) == -4 && ((int)0x8000u >> 15) == -1);             /* P0498 */
    u = 0x8000u;
    ck(3710, (u >> 15) == 1 && (u >> 16) == 0x8000u);                   /* P0497 P0498 */
    s = -2;
    us = 0x8000u;
    ck(3711, (s >> 1) == -1 && (us >> 15) == 1 && sizeof(s << 1) == 2); /* P0497 P0498 */
    c = 1;
    i = 1;
    j = -1;
    ck(3712, (c << j) == 128 && (i << j) == (int)0x8000u && (u >> j) == 1); /* P0500 P1059 */
    ck(3713, (i << 3u) == 8 && (c << 9u) == 2);                         /* P0499 */
    c = 0x80;
    ck(3714, (c >> 7) == 1 && (c >> 8) == 0x80);                        /* P0497 P0498 */

    /* 47: bitwise */
    ck(3801, (0x55 & 0x0F) == 5 && (0x0F | 0xF0) == 0xFF && (0xFF ^ 0x0F) == 0xF0); /* P0504 P0505 */
    ck(3802, ~0 == -1 && ~0u == 65535u && ~0x00FF == (int)0xFF00u);     /* P0504 P0505 */
    c = 0xF0;
    uc = 0x0F;
    ck(3803, (c | uc) == 0xFF && sizeof(c | uc) == 2 && sizeof(c & c) == 2); /* P0505 P0506 */
    ck(3804, ((-1 & 0xFFFFu) > 0) == 1);                                /* P0505 */

    /* 48: logical */
    p = 0;
    f = 0.0;
    ck(3901, !0 == 1 && !5 == 0 && !p == 1 && !f == 1 && !0.5 == 0);    /* P0511 P0512 P0513 P0514 P0515 P0516 P0509 P0510 */
    ck(3902, (2 && 3) == 1 && (0 || 7) == 1 && (0 && 7) == 0 && (0 || 0) == 0); /* P0517 P0518 P0519 P0520 */
    ck(3903, (0.5 && 2) == 1 && (f || p) == 0 && sizeof(1 && 2) == 2);  /* P0511 P0518 */
    log_v = 0;
    i = 0 && never();
    j = 1 || never();
    ck(3904, log_v == 0 && i == 0 && j == 1);                           /* P0521 P0522 P0523 P0851 */
    k = 0;
    i = 1 && (k = 5);
    ck(3905, k == 5 && i == 1);                                         /* P0521 */

    /* 49: comparisons */
    ck(4001, (32767 < 32768) == 1 && ((int)0x8000u < 32767) == 1 && ((int)0x8000u < 32767u) == 0); /* P0526 P0845 */
    ck(4002, (0x7FFF < 0x8000) == 1 && (-1 > 0x7FFF) == 0 && ((int)0x7FFF > (int)0x8000u) == 1); /* P0526 P0845 */
    ck(4003, (2 < 3) == 1 && (3 <= 3) == 1 && (4 > 5) == 0 && (5 >= 6) == 0 && (1 == 1) == 1 && (1 != 1) == 0); /* P0528 */
    ck(4004, 0.1 < 0.2 && -1.0 < 0.0 && 2.5 == 2.5 && 2.5 != 2.6 && 3.0 >= 3.0); /* P0527 */
    ck(4005, sizeof(1 < 2) == 2 && sizeof(1.0 < 2.0) == 2);             /* P0528 */
    p = &a[1];
    q = &a[3];
    ck(4006, p < q && q > p && p <= p && q >= p && (p == q) == 0 && p != q); /* P0529 P0530 P0533 P0535 */
    q = a + 6;
    ck(4007, p < q && q == &a[5] + 1);                                  /* P0535 P0542 */
    vp = p;
    ck(4008, vp == p && p == vp && p != 0 && vp != 0);                  /* P0531 P0532 P0535 P1058 */

    /* 50: pointer arithmetic */
    cp = "abc";
    ck(4101, *(cp + 1) == 'b' && *(1 + cp) == 'b' && cp[2] == 'c');     /* P0309 P0538 P0539 P0856 P0859 P0445 P0855 */
    p = &a[0];
    q = p + 1;
    ck(4102, addrv(q) - addrv(p) == 2u && addrv(cp + 1) - addrv(cp) == 1u); /* P0538 P0539 P0856 P0857 */
    fp = &fa[0];
    ck(4103, addrv(fp + 1) - addrv(fp) == 5u);                          /* P0538 P0539 P0858 */
    q = &a[4];
    ck(4104, q - 2 == &a[2] && 2 + p == &a[2] && p + 4 - 1 == &a[3]);   /* P0309 P0538 P0859 */
    p = &a[2];
    ++p;
    ck(4105, p == &a[3]);                                               /* P0538 P0564 P0860 */
    --p;
    p--;
    ck(4106, p == &a[1]);                                               /* P0538 P0564 P0860 */
    p++;
    ck(4107, p == &a[2]);                                               /* P0564 P0860 */
    p = &a[1];
    q = &a[5];
    ck(4108, q - p == 4 && p - q == -4 && p - p == 0 && sizeof(q - p) == 2); /* P0309 P0540 P0861 P1073 */
    ck(4109, (p - q) < 0 && (q - p) > 0);                               /* P0309 P0540 P0861 */
    fp = &fa[2];
    ck(4110, fp - &fa[0] == 2 && &fa[0] - fp == -2);                    /* P0540 */
    a[3] = 33;
    ck(4111, *(a + 3) == 33 && p[2] == 33 && *(3 + a) == 33 && a[3] == *(a + 3)); /* P0310 P0543 P0867 */
    ck(4112, sizeof(p + 1) == 2 && (p + 1)[1] == 33);                   /* P1073 */

    /* 52: increment and decrement */
    c = 255;
    c++;
    uc = 0;
    uc--;
    ck(4201, c == 0 && uc == 255);                                      /* P0563 P0564 */
    i = 32767;
    i++;
    u = 0;
    u--;
    ck(4202, i == (-32767 - 1) && u == 65535u);                         /* P0564 */
    f = 1.5;
    f++;
    ck(4203, f == 2.5);                                                 /* P0564 */
    f = 3.0;
    --f;
    f--;
    ck(4204, f == 1.0);                                                 /* P0564 */
    i = 5;
    j = i++;
    k = ++i;
    ck(4205, j == 5 && k == 7 && i == 7);                               /* P0565 */
    j = i--;
    k = --i;
    ck(4206, j == 7 && k == 5 && i == 5);                               /* P0565 */
    ck(4207, sizeof(c++) == 1 && sizeof(f++) == 5 && sizeof(p++) == 2 && c == 0); /* P0565 P1073 */
    fp = &fa[0];
    fp++;
    ck(4208, fp == &fa[1]);                                             /* P0564 */
    s = 32767;
    s++;
    us = 0;
    --us;
    ck(4209, s == (-32767 - 1) && us == 65535u);                        /* P0564 */

    /* 53: casts */
    ck(4301, (int)3.7 == 3 && (int)-3.7 == -3 && (unsigned int)65535.0 == 65535u); /* P0569 P0570 P0572 */
    ck(4302, (float)7 / 2 == 3.5 && (unsigned char)-1 == 255 && (short)65535u == -1); /* P0569 P0570 */
    ck(4303, (unsigned short)-1 == 65535u && (char)256 == 0 && (int)(char)-1 == 255); /* P0569 P0570 P0486 */
    ck(4304, sizeof((char)1) == 1 && sizeof((float)1) == 5 && sizeof((unsigned short)1) == 2); /* P1073 */
    f = 2.75;
    ck(4305, (int)f == 2 && (char)f == 2 && (int)-f == -2);             /* P0572 */

    /* 54: sizeof */
    ck(4401, sizeof(char) == 1 && sizeof(short) == 2 && sizeof(int) == 2 && sizeof(void *) == 2); /* P0577 P0578 */
    ck(4402, sizeof(float) == 5 && sizeof("abc") == 4 && sizeof(1.5) == 5 && sizeof('A') == 2); /* P0577 P0578 */
    ck(4403, sizeof i == 2 && sizeof(i) == 2 && sizeof a == 12 && sizeof (a) == 12 && sizeof((a)) == 12); /* P0577 P0579 */
    ck(4404, (sizeof(int) - 3 > 0) == 1 && sizeof(sizeof(int)) == 2);  /* P0577 P1073 */
    i = 0;
    j = sizeof(i++);
    k = sizeof(a[i++]);
    ck(4405, i == 0 && j == 2 && k == 2);                               /* P0577 P0580 P0852 */
    log_v = 0;
    ck(4406, sizeof(note(1, 1)) == 2 && log_v == 0);                    /* P0577 P0580 P0851 */
    p = 0;
    fp = 0;
    ck(4407, sizeof *p == 2 && sizeof *fp == 5 && sizeof(*fp) == 5);   /* P0580 P0852 */
    c = 1;
    ck(4408, sizeof(c) == 1 && sizeof(c + 1) == 2 && sizeof(-c) == 2 && sizeof(+f) == 5 && sizeof(!f) == 2); /* P1073 P1072 */
    ck(4409, sizeof(int *) == 2 && sizeof(char **) == 2 && sizeof(unsigned char) == 1); /* P0578 P0581 */
    ck(4410, sizeof(&a[0]) == 2 && sizeof(f * 2) == 5 && sizeof(c * 2) == 2); /* P1073 */
    return ck_done();
}
