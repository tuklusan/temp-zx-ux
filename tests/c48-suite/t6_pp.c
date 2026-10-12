/* t6_pp.c - C48 conformance: the preprocessor, local includes and the
 * built-in <c48.h> (spec sections 70-75, 93; Appendix B).
 */
#include "ck.h"
#define SIZE 10
#define MASK (1 << 4)
#define HALF .5
#define NAME "zx-ux"
#define CH 'q'
#define NEG -3
#define TWICE (SIZE * 2)
#define size 3
  #define SP1 11
	#define TB1 12
/* a comment first */ #define CM1 13
#  define SPACED 14
#	define TABBED 15
#define TRAIL 16 // a trailing line comment
#define TRAIL2 17 /* a trailing block comment */
#define SIZE 10
#define REDEF (2 + 3)
#define REDEF (2+3)
#define TEN 10
#define ALIAS2 TEN
#define ALIAS2 10
#define FMIX (HALF * 4 + SIZE)
#define BASE 4
#include "t6_inc.h"
#include "t6_twice.h"
#include "t6_twice.h"
#include <c48.h>
#include <c48.h>
unsigned int strlen(char *s);
int twice_fn(int v)
{
    return v + TWICE_K;
}
int SIZEX;
// #define NOTDEF 1
int NOTDEF;
int after_main(void);

int main(void)
{
    char *s;

    ck(7001, SIZE == 10 && MASK == 16 && TWICE == 20 && NEG == -3); /* P0699 P0706 P0707 P0709 P0710 P0901 */
    ck(7002, HALF == .5 && sizeof(NAME) == 6 && NAME[0] == 'z' && CH == 'q'); /* P0709 P0710 P0901 */
    ck(7003, size == 3 && SIZE == 10);                                 /* P0716 P0901 */
    ck(7004, SP1 == 11 && TB1 == 12 && CM1 == 13 && SPACED == 14 && TABBED == 15); /* P0700 */
    ck(7005, TRAIL == 16 && TRAIL2 == 17);                             /* P0712 */
    ck(7006, REDEF == 5 && ALIAS2 == 10 && FMIX > 11.9 && FMIX < 12.1); /* P0718 P0720 P0721 P0901 P0902 */
    s = "SIZE";
    ck(7007, sizeof("SIZE") == 5 && s[0] == 'S' && s[3] == 'E'); /* P0715 P0718 P0902 */
    SIZEX = 1;
    NOTDEF = 2;
    ck(7008, SIZEX == 1 && NOTDEF == 2);                               /* P0700 P0715 */
    ck(7009, INC_A == 5 && sizeof(INC_STR) == 4 && inc_fn(3) == 6);    /* P0717 P0723 P0724 P0728 P0902 P0903 P0725 P0726 */
    ck(7010, twice_fn(1) == 78 && TWICE_K == 77);                      /* P0729 */
    ck(7011, strlen("abcd") == 4u);                                    /* P0731 P0732 P0733 P0734 P0903 P1003 P1004 */
#define INFN 21
    ck(7012, INFN == 21 && after_main() == 21);                        /* P0702 P0716 */
    return ck_done();
}

int after_main(void)
{
    return INFN;
}
