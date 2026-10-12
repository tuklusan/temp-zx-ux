/* t2_types.c - C48 conformance: types, data model, object representation,
 * declarators, declarations, storage classes, scope, linkage, arrays,
 * pointers, null and void pointers (spec sections 18-28.1, 32-34).
 */
#include "ck.h"

/* 18: every fundamental type spelling; uninitialized file-scope objects */
char g_c;
unsigned char g_uc;
short g_s;
unsigned short g_us;
int g_i;
unsigned int g_ui;
float g_f;
int *g_p;
char g_arr[9];
float g_farr[3];
static int g_static;
static float g_sf;

/* 21, 23.2: definitions and compatible extern declarations, in both orders */
extern int ex_before;
int ex_before;
int ex_after;
extern int ex_after;
extern int ex_rep;
extern int ex_rep;
int ex_rep = 5;
extern int ex_rep;

/* 21: one declaration, several declarators */
int md_a, *md_p, md_arr[2], md_b;

/* 34: pointer constant initializers */
int *pi_null = 0;
char *pi_str = "lit";
void *pi_vstr = "vlit";
int pi_target[4];
int *pi_addr = &pi_target[0];
int *pi_off = &pi_target[0] + 2;
int *pi_arr = pi_target;
int *pi_arr2 = pi_target + 3;
int *pi_arr1 = pi_target + 3 - 2;
int *pi_zero = 1 - 1;
char *pi_tab[3] = { "a", 0, "c" };

/* 32, 33, 37: scalar and array initializers */
int in_i = -5;
unsigned int in_u = 65535u;
char in_c = 'z';
float in_f = 1.5;
int in_conv = 3.75;
float in_fconv = 7;
unsigned char in_narrow = 0x1ff;
int in_fix[3] = { 1, 2, 3 };
int in_inf[] = { 4, 5, 6, 7 };
int in_part[5] = { 8, 9 };
int in_comma[3] = { 1, 2, };
char in_text[] = "abc";
char in_text4[4] = "abc";
char in_text9[9] = "abc";
unsigned char in_utext[] = "xy";
float in_farr[3] = { 0.5, 2, -1.25 };

/* 28.1: alignment of objects that follow 1-byte objects */
char al_c1;
int al_i1;
char al_c2;
int *al_p1;
char al_c3;
short al_s1;
char al_c4;
unsigned int al_u1[2];

void *malloc(unsigned int n);
void free(void *p);

/* 20: declarator binding */
char *dc_a[8];
char **dc_b[8];
char dc_ch;
char *dc_ret(void)
{
    return &dc_ch;
}
char **dc_ret2(void)
{
    return &dc_a[1];
}

/* 23, 23.1, 29: prototypes, repeated prototypes, file-scope static/extern
 * functions, unnamed prototype parameters, pointer returns/parameters */
int add2(int, int);
int add2(int a, int b);
extern int add2(int x, int y);
static int st_fn(void);
static int st_fn(void)
{
    return g_static + 1;
}
int add2(int a, int b)
{
    return a + b;
}
int *ptr_param(int *p, char **pp)
{
    return p + (pp[0][0] == 'q');
}

/* 23: shadowing */
int sh_v = 1;
int shadow_param(int x)
{
    {
        int x;
        x = 20;
    }
    return x;
}

/* bytes of an object through unsigned char * (28.1) */
unsigned char *bytes_of(void *p)
{
    return p;
}
/* the 16-bit logical address held in a pointer object, from its bytes */
unsigned int addr_of(void *pp)
{
    unsigned char *b;

    b = pp;
    return b[0] + 256u * b[1];
}

int main(void)
{
    int x;
    int y;
    unsigned char *b;
    char *cp;
    char *cq;
    int *ip;
    int *iq;
    void *vp;
    void *vq;
    float *fp;
    char c;
    unsigned char uc;
    short s;
    unsigned short us;
    unsigned int u;
    int i;
    int arr3[3];
    char carr[5];
    float farr[2];
    char *parr[4];
    int cbound[2 + sizeof(int) * 3];

    /* 18, 19: sizes */
    ck(2001, sizeof(char) == 1 && sizeof(unsigned char) == 1);          /* P0211 P0212 P0221 P0222 P1006 P0995 P0996 P1092 */
    ck(2002, sizeof(short) == 2 && sizeof(unsigned short) == 2);        /* P0211 P0212 P0221 P0222 P1006 P0996 P1092 */
    ck(2003, sizeof(int) == 2 && sizeof(unsigned int) == 2);            /* P0211 P0212 P0221 P0222 P1006 P0996 P1092 */
    ck(2004, sizeof(float) == 5);                                       /* P0194 P0195 P0221 P0222 P1006 */
    ck(2005, sizeof(int *) == 2 && sizeof(char **) == 2 && sizeof(void *) == 2 && sizeof(float *) == 2); /* P0222 P0225 P0306 P0802 P0801 */
    ck(2006, sizeof(g_c) == 1 && sizeof(g_us) == 2 && sizeof(g_f) == 5 && sizeof(g_p) == 2); /* P0222 */

    /* 18, 19: plain char unsigned, short/int signed, ranges */
    c = 255;
    ck(2101, c > 0 && c == 255);                                        /* P0216 P0230 P1007 P1092 */
    c = -1;
    ck(2102, c == 255);                                                 /* P0216 P0230 P0477 */
    uc = 256;
    ck(2103, uc == 0);                                                  /* P0230 P0476 */
    s = 32767;
    s = s + 1;
    ck(2104, s < 0 && s == (-32767 - 1));                               /* P0103 P0218 P0230 */
    i = 65535u;
    ck(2105, i == -1);                                                  /* P0103 P0218 P0230 P0477 */
    us = -1;
    ck(2106, us == 65535u && us > 0);                                   /* P0230 P0476 */

    /* 19: object representation, little-endian */
    i = 0x1234;
    b = bytes_of(&i);
    ck(2201, b[0] == 0x34 && b[1] == 0x12);                             /* P0229 P0230 P1057 */
    i = -2;
    ck(2202, b[0] == 0xFE && b[1] == 0xFF);                             /* P0229 P0230 P0218 */
    u = 0xABCDu;
    b = bytes_of(&u);
    ck(2203, b[0] == 0xCD && b[1] == 0xAB);                             /* P0229 P0230 */
    s = -32767;
    b = bytes_of(&s);
    ck(2204, b[0] == 0x01 && b[1] == 0x80);                             /* P0230 */
    c = 'A';
    b = bytes_of(&c);
    ck(2205, b[0] == 65);                                               /* P0230 */
    cp = carr;
    cq = carr + 1;
    ck(2206, addr_of(&cq) == addr_of(&cp) + 1u);                        /* P0225 P0230 P1057 P0801 */
    ip = 0;
    b = bytes_of(&ip);
    ck(2207, b[0] == 0 && b[1] == 0);                                   /* P0230 P0313 P0314 */
    /* 19, 21: zero-initialized file-scope objects (BSS) */
    ck(2301, g_c == 0 && g_uc == 0 && g_s == 0 && g_us == 0 && g_i == 0 && g_ui == 0); /* P0232 P0247 P0249 P1076 */
    ck(2302, g_f == 0.0 && !g_f && g_p == 0 && !g_p);                  /* P0232 P0249 P1057 P1076 P0515 */
    b = bytes_of(&g_f);
    ck(2303, b[0] == 0 && b[1] == 0 && b[2] == 0 && b[3] == 0 && b[4] == 0); /* P0232 P1057 */
    b = bytes_of(&g_p);
    ck(2304, b[0] == 0 && b[1] == 0);                                   /* P0230 P0232 */
    x = 0;
    for (i = 0; i < 9; i++)
        x = x + g_arr[i];
    ck(2305, x == 0 && g_farr[0] == 0.0 && g_farr[2] == 0.0);           /* P0249 P0232 */
    ck(2306, g_static == 0 && g_sf == 0.0);                             /* P0247 P0249 */

    /* 19, 25: array size, stride and alignment */
    ck(2401, sizeof(arr3) == 6 && sizeof(carr) == 5 && sizeof(farr) == 10 && sizeof(parr) == 8); /* P0226 P0227 P0231 P0579 P0865 */
    ip = &arr3[1];
    iq = &arr3[0];
    ck(2402, addr_of(&ip) - addr_of(&iq) == 2u);                        /* P0226 P0227 P0231 */
    fp = &farr[1];
    vp = &farr[0];
    ck(2403, addr_of(&fp) - addr_of(&vp) == 5u);                        /* P0197 P0227 P0231 P0196 */
    cp = &carr[4];
    cq = &carr[0];
    ck(2404, addr_of(&cp) - addr_of(&cq) == 4u);                        /* P0227 P0231 */
    vp = &parr[3];
    vq = &parr[0];
    ck(2405, addr_of(&vp) - addr_of(&vq) == 6u);                        /* P0227 P0231 */
    vp = &al_i1;
    ck(2406, addr_of(&vp) % 2u == 0u);                                  /* P0222 P0228 P0330 */
    vp = &al_p1;
    ck(2407, addr_of(&vp) % 2u == 0u);                                  /* P0222 P0228 P0306 P0330 */
    vp = &al_s1;
    ck(2408, addr_of(&vp) % 2u == 0u);                                  /* P0222 P0228 P0330 */
    vp = &al_u1[1];
    ck(2409, addr_of(&vp) % 2u == 0u);                                  /* P0222 P0228 P0231 P0330 */
    vp = &x;
    ck(2410, addr_of(&vp) % 2u == 0u);                                  /* P0228 P0330 */
    vp = &ip;
    ck(2411, addr_of(&vp) % 2u == 0u);                                  /* P0228 P0306 P0330 */
    vp = &arr3[0];
    ck(2412, addr_of(&vp) % 2u == 0u);                                  /* P0228 P0231 P0330 */
    vp = &g_i;
    cp = &g_c;
    ck(2413, addr_of(&vp) != addr_of(&cp));                             /* P1079 */

    /* 20: declarators */
    ck(2501, sizeof(dc_a) == 16 && sizeof(dc_b) == 16 && sizeof(dc_a[0]) == 2 && sizeof(dc_b[0][0]) == 2); /* P0236 P0237 P0877 P0235 P0238 */
    dc_a[0] = "xy";
    dc_b[0] = dc_a;
    ck(2502, dc_a[0][0] == 'x' && dc_b[0][0][1] == 'y' && sizeof(dc_b[0][0][0]) == 1); /* P0236 P0240 P0877 */
    *dc_ret() = 'k';
    ck(2503, dc_ch == 'k' && sizeof(*dc_ret()) == 1);                   /* P0236 P0237 P0240 P0877 */
    *dc_ret2() = "rs";
    ck(2504, dc_a[1][1] == 's');                                        /* P0236 P0240 P0877 */
    parr[0] = "q";
    parr[1] = "argv";
    ck(2505, parr[1][0] == 'a' && parr[1][3] == 'v');                   /* P0241 P0868 */
    md_p = &md_b;
    *md_p = 3;
    ck(2506, md_b == 3 && sizeof(md_arr) == 4 && md_a == 0);            /* P0244 P0245 P0246 */

    /* 21, 22, 23.2: definitions, extern declarations, static, scope */
    ex_before = 1;
    ex_after = 2;
    ck(2601, ex_before == 1 && ex_after == 2 && ex_rep == 5);           /* P0247 P0248 P0253 P0255 P0256 P0879 P0252 P0254 */
    ck(2602, st_fn() == 1 && add2(2, 3) == 5);                          /* P0257 P0262 P0263 P0273 P0335 P0345 P0347 P0348 P0254 P0337 P0338 P0346 P0351 P0352 P0353 */
    ck(2603, ptr_param(&pi_target[0], parr) == &pi_target[1]);          /* P0240 P0358 P0875 */
    ck(2604, shadow_param(7) == 7);                                     /* P0278 P0880 P0266 P0268 */
    {
        int sh_v;
        sh_v = 5;
        {
            int sh_v;
            sh_v = 9;
        }
        ck(2605, sh_v == 5);                                            /* P0269 P0271 P0291 P0640 P0292 */
    }
    ck(2606, sh_v == 1);                                                /* P0267 P0271 */

    /* 32, 33, 34, 37: initializers */
    ck(2701, in_i == -5 && in_u == 65535u && in_c == 'z' && in_f == 1.5); /* P0375 P0376 P0884 P0885 P0886 P0887 P1027 P0548 P0883 */
    ck(2702, in_conv == 3 && in_fconv == 7.0 && in_narrow == 255);     /* P0383 P0549 P0550 P0551 P0548 */
    ck(2703, in_fix[0] == 1 && in_fix[2] == 3 && sizeof(in_fix) == 6);  /* P0378 P0379 P0891 P0422 */
    ck(2704, sizeof(in_inf) == 8 && in_inf[3] == 7);                    /* P0300 P0424 P0425 P0892 P0423 */
    ck(2705, in_part[1] == 9 && in_part[2] == 0 && in_part[4] == 0);    /* P0378 P0893 */
    ck(2706, sizeof(in_comma) == 6 && in_comma[1] == 2 && in_comma[2] == 0); /* P0378 P0379 P0894 */
    ck(2707, sizeof(in_text) == 4 && in_text[0] == 'a' && in_text[2] == 'c' && in_text[3] == 0); /* P0386 P0387 P0388 P0389 P0390 P0895 */
    ck(2708, in_text4[3] == 0 && in_text9[3] == 0 && in_text9[8] == 0 && sizeof(in_utext) == 3 && in_utext[1] == 'y'); /* P0386 P0391 P0396 P0397 */
    ck(2709, in_farr[0] == 0.5 && in_farr[1] == 2.0 && in_farr[2] == -1.25); /* P0427 P0887 */
    ck(2710, pi_null == 0 && pi_str[0] == 'l' && pi_str[3] == 0);       /* P0400 P0401 P0402 P0407 P0888 P0889 */
    cp = pi_vstr;
    ck(2711, cp[0] == 'v');                                             /* P0407 */
    ck(2712, pi_addr == &pi_target[0] && pi_off == &pi_target[2]);      /* P0403 P0404 P0890 */
    ck(2713, pi_arr == pi_target && pi_arr2 == &pi_target[3] && pi_arr1 == &pi_target[1]); /* P0301 P0404 P0864 */
    ck(2714, pi_zero == 0);                                             /* P0315 */
    ck(2715, pi_tab[0][0] == 'a' && pi_tab[1] == 0 && pi_tab[2][0] == 'c'); /* P0426 */

    /* 25, 26, 27, 28: arrays, pointers, null, void * */
    ck(2801, sizeof(cbound) == 16);                                     /* P0300 P0303 */
    ip = arr3;
    ck(2802, ip == &arr3[0] && sizeof((arr3)) == 6);                    /* P0301 P0579 P0864 P0865 */
    {
        int **pp2;
        pp2 = &ip;
        **pp2 = 41;
        ck(2803, arr3[0] == 41);                                        /* P0240 P0307 */
    }
    vp = ip;
    iq = vp;
    ck(2804, iq == ip && vp == ip && ip == vp);                         /* P0324 P0325 P0326 P0328 P0531 P0554 P0863 P0553 */
    ip = 0;
    ck(2805, ip == 0 && 0 == ip && !ip);                                /* P0313 P0315 P0316 P0532 P0555 P0862 */
    vp = 0;
    ck(2806, vp == 0 && !vp);                                           /* P0316 */
    i = 0x0234;
    b = bytes_of(&i);
    b[1] = 0x01;
    ck(2807, i == 0x0134);                                              /* P0331 */
    ip = malloc(4);
    ck(2808, ip != 0);                                                  /* P0332 */
    ip[0] = 7;
    ip[1] = -8;
    ck(2809, ip[0] + ip[1] == -1);                                      /* P0332 */
    free(ip);
    return ck_done();
}
