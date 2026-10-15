/* ZX-UX suite: a background program that waits 2 s, then beeps and
 * beeps through the library's beep() (each BEEP runs with interrupts
 * off; the library lets a frame interrupt in after each note) */
#include <c48.h>

int main(void)
{
    int i;
    sleep(100);
    for (i = 0; i < 400; i++)
        beep(0.25, (float)(i % 12));
    return 0;
}
