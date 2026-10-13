/* ZX-UX suite: kernel fixes from the 2026-10 review, driven from an SSX1
 * program (<c48.h> has every system call; kfix.s adds a raw sys ssxload
 * with the arguments M1 needs, an IY probe and peek) */
#include <c48.h>

int kssxl(unsigned int len, unsigned int tot);
int iyprobe(char *buf);
int peek(unsigned int address);

char buf[8];
char probe[128];
char *av[21];

int main(void)
{
    int a, b, n, i;

    /* M6: a read past the end of a file returns 0 bytes, no error */
    a = creat("/tmp/k1", 14);
    write(a, "abc", 3);
    close(a);
    a = open("/tmp/k1", 0);
    seek(a, 100);
    n = read(a, buf, 1);
    close(a);
    if (n == 0) print_at(2, 0, "eof ok"); else print_at(2, 0, "eof bad");

    /* C1: a write ending past 52K fails cleanly (no arena wipe) */
    a = open("/tmp/k1", 1);
    seek(a, 52428);             /* end 52429: end + end/4 wraps to 0 */
    n = write(a, "x", 1);
    close(a);
    if (n == -1) print_at(3, 0, "far ok"); else print_at(3, 0, "far bad");

    /* C2: unlink a file that is open twice; the data stays readable
     * until the last close, whichever closes first */
    a = open("/tmp/k1", 0);
    b = open("/tmp/k1", 0);
    unlink("/tmp/k1");
    close(a);
    n = read(b, buf, 3);
    close(b);
    if (n == 3 && buf[0] == 'a') print_at(4, 0, "unlink ok");
    else print_at(4, 0, "unlink bad");

    /* M1: sys ssxload is refused to an SSX1 program */
    n = kssxl(10, 5);
    if (n == -1) print_at(5, 0, "ssxload ok"); else print_at(5, 0, "ssxload bad");

    /* M3: the clock interrupt does not write through a user IY */
    for (i = 0; i < 128; i++)
        probe[i] = 0x55;
    iyprobe(probe + 64);
    n = 0;
    for (i = 0; i < 128; i++)
        if (probe[i] != 0x55)
            n++;
    if (n == 0) print_at(6, 0, "iy ok"); else print_at(6, 0, "iy bad");
    /* exec: arguments longer than the kernel's buffer are refused
     * before a byte is written past it (6000h: the kernel's jp boot) */
    for (i = 0; i < 20; i++)
        av[i] = "abcdefghi";
    av[20] = 0;
    n = exec("/bin/echo", av);
    if (n == -1 && peek(0x6000) == 0xC3) print_at(7, 0, "args ok");
    else print_at(7, 0, "args bad");
    print_at(8, 0, "kfix done");
    return 0;
}
