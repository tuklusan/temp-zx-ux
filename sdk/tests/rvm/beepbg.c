/* beepbg - beeps on and on (sdk/tests/test_rvm.py: typing goes on meanwhile) */
#include <c48.h>
int main(void)
{
    int i;
    for (i = 0; i < 200; i++)
        beep(0.25, (float)(i % 12));
    return 0;
}
