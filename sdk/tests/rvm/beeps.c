/* beeps - four BEEPs at known pitches (sdk/tests/test_rvm.py) */
#include <c48.h>
int main(void)
{
    beep(0.2, 0.0);
    beep(0.2, 9.0);
    beep(0.1, -20.0);
    beep(0.1, 24.5);
    return 0;
}
