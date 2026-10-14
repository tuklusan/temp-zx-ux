/* spin - draws a counter forever (BREAK ends it; sdk/tests/test_rvm.py) */
#include <c48.h>
int main(void)
{
    unsigned int i;
    i = 0;
    for (;;) {
        print_at(0, 0, "spin ");
        putchar('0' + (i & 7));         /* the screen changes all the time */
        i++;
        if ((i & 63) == 0)
            yield();
    }
    return 0;
}
