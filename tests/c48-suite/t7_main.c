/* t7_main.c - C48 conformance: main(argc, argv) and the built-in <c48.h>
 * library functions that run on any host (spec sections 31, 74, 96;
 * Appendix B).  run_suite.py runs it with the arguments "alpha" and "b",
 * and links one small program per Appendix B name separately.
 */
#include "ck.h"
#include <c48.h>

int main(int argc, char **argv);
extern int main(int argc, char **argv);

int main(int argc, char **argv)
{
    char buf[10];
    char *p;
    int i;
    int n;

    /* 31: argc and argv */
    ck(8001, argc == 3);                                                /* P0366 P0367 P0369 */
    ck(8002, argv[argc] == 0 && argv[1][0] == 'a' && argv[1][5] == 0 && argv[2][0] == 'b' && argv[2][1] == 0); /* P0369 P0370 */
    ck(8003, argv[0] != 0 && argv[0][0] != 0);                          /* P0369 */
    n = 0;
    for (i = 0; i < argc; i++)
        n = n + strlen(argv[i]);
    ck(8004, n == strlen(argv[0]) + 6);                                 /* P0369 P0370 */

    /* 74, 96: <c48.h> functions that run anywhere */
    ck(8101, strlen("hello") == 5u && strcmp("abc", "abc") == 0 && strcmp("abc", "abd") < 0); /* P0732 P0735 P0924 P1041 P1042 */
    p = strcpy(buf, "zx");
    ck(8102, p == buf && buf[0] == 'z' && buf[2] == 0);                 /* P0735 P1042 */
    memset(buf, 'q', 4);
    buf[4] = 0;
    ck(8103, strlen(buf) == 4u && buf[3] == 'q');                       /* P0735 P1042 */
    memcpy(buf, "abcdef", 7);
    memmove(buf + 1, buf, 3);
    ck(8104, buf[0] == 'a' && buf[1] == 'a' && buf[3] == 'c' && buf[4] == 'e'); /* P0735 P1042 */
    p = memchr(buf, 'e', 6);
    ck(8105, p == buf + 4 && memchr(buf, 'z', 6) == 0);                 /* P0735 P1042 */
    strncpy(buf, "xy", 5);
    ck(8106, buf[0] == 'x' && buf[2] == 0 && buf[4] == 0);              /* P0735 P1042 */
    p = malloc(10);
    ck(8107, p != 0);                                                   /* P0326 P0735 P1042 */
    free(p);
    ck(8108, fabs(-2.0) == 2.0 && getpid() > 0);                       /* P0735 P1042 */
    return ck_done();
}
