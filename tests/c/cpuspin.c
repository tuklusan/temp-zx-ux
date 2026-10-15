/* ZX-UX suite: a background program that only computes (never makes a
 * system call), so it runs whenever the scheduler gives it the CPU */
#include <c48.h>

unsigned int n;

int main(void)
{
    for (;;)
        n++;
    return 0;
}
