/* ZX-UX suite: a program that beeps for 5 s through the ROM's BEEPER
 * with interrupts off between the notes too (beephog.s), as programs
 * built before the library let a frame interrupt in after each note */
#include <c48.h>

int hog(void);

int main(void)
{
    hog();
    return 0;
}
