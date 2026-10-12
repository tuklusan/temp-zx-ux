/* ZX-UX suite: beep() plays the pitch it is given, whatever the time
 * of day (the ROM's BEEP reads its pitch from MEMBOT, the kernel clock) */
#include <c48.h>

int main(void)
{
    int a, b;

    a = beep(0.1, 0.0);         /* middle C: about 26 cycles */
    b = beep(0.1, 12.0);        /* an octave up: about 52 */
    if (a == 0 && b == 0) print_at(2, 0, "beep ok"); else print_at(2, 0, "beep bad");
    print_at(3, 0, "beepck done");
    return 0;
}
