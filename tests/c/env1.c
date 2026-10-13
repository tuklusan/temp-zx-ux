/* ZX-UX suite: ENV1, the C runtime's process-owned environment block
 * (C48 Rev 0.11 P1080).  Test code may look at it through env1.s; C48
 * itself has no getenv API.
 *   env1 r     ENV1 must be empty (one NUL) and stay so: prints its address
 *   env1 w     writes 'X' into its own ENV1 (on purpose, for the isolation
 *              test), sleeps, and checks that nothing else changed it
 *   env1 q     writes 'X' into ENV1 and ends at once
 *   env1 x     writes 'X' into ENV1, then exec /dev/cassette/env1 r: the new
 *              image must start with a fresh, empty ENV1
 */
#include <c48.h>

char *env1(void);
unsigned int env1a(void);
char hx[5];
char *xargv[3];

void hex(unsigned int v)
{
    int i;

    for (i = 3; i >= 0; i--) {
        hx[i] = "0123456789ABCDEF"[v & 15u];
        v = v >> 4;
    }
    hx[4] = 0;
}

int main(int argc, char **argv)
{
    char *e;
    char m;
    unsigned int i;
    int bad;
    int row;

    e = env1();
    m = 'r';
    if (argc > 1)
        m = argv[1][0];
    row = 9;                            /* r prints on rows 1-3, the others 9-11 */
    if (m == 'r')
        row = 1;
    hex(env1a());
    print_at(row, 0, "env1 at");
    print_at(row, 8, hx);
    bad = 0;
    if (m == 'r') {
        if (e[0] != 0)
            bad = 1;
        for (i = 0u; i < 40u; i++) {    /* stays empty while the program runs */
            sleep(2u);
            if (e[0] != 0)
                bad = 1;
        }
        if (bad)
            print_at(row + 1, 0, "env1 r bad");
        else
            print_at(row + 1, 0, "env1 r ok");
        return bad;
    }
    e[0] = 'X';
    if (m == 'q') {
        print_at(row + 1, 0, "env1 q done");
        return 0;
    }
    if (m == 'x') {
        print_at(row + 1, 0, "env1 x exec");
        xargv[0] = "/dev/cassette/env1";
        xargv[1] = "r";
        xargv[2] = NULL;
        exec(xargv[0], xargv);
        print_at(row + 2, 0, "env1 x exec failed");
        return 1;
    }
    for (i = 0u; i < 60u; i++) {        /* 'w': another program runs meanwhile */
        sleep(5u);
        if (e[0] != 'X')
            bad = 1;
    }
    if (bad)
        print_at(row + 2, 0, "env1 w bad");
    else
        print_at(row + 2, 0, "env1 w ok");
    return bad;
}
