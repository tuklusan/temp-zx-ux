/* keys - echoes the keys it reads as their codes until q, then exits
 * with the number of keys read (sdk/tests/test_rvm.py) */
#include <c48.h>
int main(void)
{
    int c;
    int n;
    n = 0;
    puts("ready");
    while ((c = getchar()) != 'q') {
        n++;
        print_at(1, 0, "    ");
        print_at(1, 0, "");
        putchar(c);
    }
    return n;
}
