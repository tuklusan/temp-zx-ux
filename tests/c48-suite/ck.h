/* ck.h - check helpers shared by the C48 conformance suite programs.
 *
 * ck(id, ok) counts a check and, when ok is false, prints "F<id> " on the
 * console.  ck_done() prints "N<count>." and returns the program's exit
 * status (0: every check passed).  run_suite.py reads the screen text; the
 * paragraph tags after each ck() call map checks to the specification
 * (docs/04-C48 Language Specification Rev 0.11.docx).
 */
int putchar(int c);

int ck_fails;
int ck_count;

void ck_dec(unsigned int v)
{
    char buf[6];
    int n;

    n = 0;
    do {
        buf[n] = '0' + v % 10u;
        n++;
        v = v / 10u;
    } while (v != 0u);
    while (n > 0) {
        n--;
        putchar(buf[n]);
    }
}

void ck(unsigned int id, int ok)
{
    ck_count++;
    if (!ok) {
        ck_fails++;
        putchar('F');
        ck_dec(id);
        putchar(' ');
    }
}

/* ck_hex: print the n bytes at p in hexadecimal, each after a space */
void ck_hex(unsigned char *p, int n)
{
    int i;
    char *hex;

    hex = "0123456789abcdef";
    i = 0;
    while (i < n) {
        putchar(' ');
        putchar(hex[p[i] >> 4]);
        putchar(hex[p[i] & 15]);
        i++;
    }
}

int ck_done(void)
{
    putchar('N');
    ck_dec(ck_count);
    putchar('.');
    return ck_fails != 0;
}
