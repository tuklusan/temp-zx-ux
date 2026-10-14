/* bordck - border() keeps the ROM's border variable (BORDCR, 5C48h), so
 * that the key click and BEEP put back this colour, not black; bad
 * colours are refused and change nothing (tests/suite.py border_*) */
#include <c48.h>

int main(void)
{
    if (border(2) != 0)
        return 3;
    puts("border 2");
    getchar();                  /* the key click */
    puts("after key");
    beep(0.05, 0.0);
    puts("after beep");
    if (border(8) != 1 || border(-1) != 1 || border(256) != 1)
        return 4;
    puts("bad refused");
    getchar();
    border(5);
    puts("border 5");
    getchar();
    return 0;
}
