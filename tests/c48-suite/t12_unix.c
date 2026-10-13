/* t12_unix.c - every ZX-UX system call through <c48.h> (Appendix B: the
 * header is the authoritative public-name inventory, P1041 P1042).
 *
 * Expected results are the kernel's (src/unix.asm, src/fs.asm, src/dev.asm):
 * the same program runs in rvm and on ZX-UX from cassette, and both must
 * pass every check.  It works in a directory of its own (/t12d) and removes
 * it again; the clock is put back after the stime check.  As in v1, the
 * mkdir call makes an empty directory: no "." or ".." entries (the mkdir
 * command links those itself), so ".." inside it is just a missing name.
 */
#include "ck.h"
#include <c48.h>

char sbuf[34];
unsigned char tb[6];
int bssvar;

unsigned int w16(char *p)
{
    return p[0] | (unsigned int)p[1] << 8;   /* (a char shift stays 8 bits wide) */
}

int main(void)
{
    int h;
    int st;
    char c;
    char *av[2];
    unsigned int t[2];
    unsigned int t2[2];
    unsigned int info[2];

    av[0] = "t12";
    av[1] = NULL;

    /* processes */
    ck(12001, fork() == -1 && errno == 11);                         /* P1041 P1042 */
    ck(12002, wait(&st) == -1 && errno == 10);                      /* P1041 P1042 */
    ck(12003, kill(9999) == -1 && errno == 3);                      /* P1041 P1042 */
    ck(12004, ssxload(av, 0u, 0u) == -1 && errno == 22);            /* P1041 P1042 */
    ck(12005, exec("/no/such/prog", av) == -1 && errno == 2);       /* P1041 P1042 */
    errno = 0;
    ck(12006, getuid() == 0 && setuid(0) == 0 && quit(0) == 0 && errno == 0); /* P1041 P1042 */
    ck(12007, cemt(NULL) == 0 && ilgins(NULL) == 0 && intr(1) == 0); /* P1041 P1042 */
    ck(12008, brk(NULL) == -1 && errno == 12);                      /* P1041 P1042 */
    ck(12009, brk(&bssvar) != -1);                                  /* P1041 P1042 */

    /* directories */
    ck(12010, mkdir("/t12d", 15) == 0);                             /* P1041 P1042 */
    ck(12011, mkdir("/t12d", 15) == -1 && errno == 17);             /* P1041 P1042 */
    ck(12012, chdir("/t12d") == 0);                                 /* P1041 P1042 */
    ck(12013, chdir("nope") == -1 && errno == 2);                   /* P1041 P1042 */
    ck(12014, open("/t12d", 1) == -1 && errno == 21);               /* P1041 P1042 */
    ck(12015, creat("/t12d", 15) == -1 && errno == 21);             /* P1041 P1042 */
    ck(12048, open("..", 0) == -1 && errno == 2 && open("/", 0) >= 3); /* P1041 P1042 */

    /* files */
    h = creat("f", 15);
    ck(12016, h >= 3 && write(h, "hello", 5u) == 5 && tell(h) == 5); /* P1041 P1042 */
    ck(12017, fstat(h, sbuf) == 0 && w16(sbuf + 6) == 5);           /* P1041 P1042 */
    ck(12018, read(h, &c, 1u) == -1 && errno == 9);                 /* P1041 P1042 */
    ck(12019, close(h) == 0 && close(h) == -1 && errno == 9);       /* P1041 P1042 */
    h = open("f", 0);
    c = 0;
    ck(12020, h >= 3 && read(h, &c, 1u) == 1 && c == 'h');          /* P1041 P1042 */
    ck(12021, lseek(h, 1, 0) == 1 && read(h, &c, 1u) == 1 && c == 'e'); /* P1041 P1042 */
    ck(12022, lseek(h, -2, 2) == 3 && read(h, &c, 1u) == 1 && c == 'l'); /* P1041 P1042 */
    ck(12023, lseek(h, -4, 1) == 0 && tell(h) == 0);                /* P1041 P1042 */
    ck(12024, write(h, "x", 1u) == -1 && errno == 9);               /* P1041 P1042 */
    close(h);
    ck(12025, write(9, "x", 1u) == -1 && errno == 9);               /* P1041 P1042 */
    ck(12026, write(1, "", 0u) == 0);                               /* P1041 P1042 */

    /* i-nodes: stat, link, unlink, chmod, mdate */
    ck(12027, stat("f", sbuf) == 0 && w16(sbuf + 6) == 5 && sbuf[4] == 1); /* P1041 P1042 */
    ck(12028, (w16(sbuf + 2) & 0xC000u) == 0x8000u);                /* P1041 P1042 */
    ck(12029, link("f", "g") == 0 && stat("f", sbuf) == 0 && sbuf[4] == 2); /* P1041 P1042 */
    ck(12030, link("f", "g") == -1 && errno == 17);                 /* P1041 P1042 */
    ck(12031, unlink("g") == 0 && unlink("g") == -1 && errno == 2); /* P1041 P1042 */
    ck(12032, stat("f", sbuf) == 0 && sbuf[4] == 1);                /* P1041 P1042 */
    ck(12033, chmod("f", 5) == 0 && stat("f", sbuf) == 0 && (sbuf[2] & 63) == 5); /* P1041 P1042 */
    ck(12034, chown("f", 0) == 0);                                  /* P1041 P1042 */
    t[0] = 0x1234u;
    t[1] = 0x0056u;
    ck(12035, mdate("f", t) == 0 && stat("f", sbuf) == 0 && w16(sbuf + 28) == 0x1234u && w16(sbuf + 30) == 0x56u); /* P1041 P1042 */
    ck(12036, stat("nope", sbuf) == -1 && errno == 2 && mdate("nope", t) == -1 && errno == 2); /* P1041 P1042 */
    ck(12037, zxpack("f") > 0u);                                    /* P1041 P1042 */
    h = open("f", 0);
    c = 0;
    ck(12038, h >= 3 && read(h, &c, 1u) == 1 && c == 'h');         /* P1041 P1042 */
    close(h);

    /* terminal */
    ck(12039, gtty(0, tb) == 0 && stty(0, tb) == 0);               /* P1041 P1042 */
    h = open("f", 0);
    ck(12040, gtty(h, tb) == -1 && errno == 25);                    /* P1041 P1042 */
    close(h);
    ck(12041, gtty(9, tb) == -1 && errno == 9);                     /* P1041 P1042 */

    /* clean up: the file and the directory */
    ck(12042, unlink("f") == 0 && chdir("/") == 0 && unlink("/t12d") == 0); /* P1041 P1042 */
    ck(12043, chdir("/t12d") == -1 && errno == 2);                  /* P1041 P1042 */

    /* the clock */
    ck(12044, time(t) == 0);                                        /* P1041 P1042 */
    t2[0] = t[0] + 100u;
    t2[1] = t[1] + (t[0] + 100u < t[0]);
    ck(12045, stime(t2) == 0 && time(t) == 0 && t[1] == t2[1] && t[0] - t2[0] < 5u); /* P1041 P1042 */
    t2[0] = t[0] - 100u;
    t2[1] = t[1] - (t[0] < 100u);
    stime(t2);

    /* arena and screen */
    ck(12046, zxinfo(info) == 0 && info[0] > 0u && info[1] <= 24u); /* P1041 P1042 */
    ck(12047, screen(1) != NULL);                                   /* P1041 P1042 */
    return ck_done();
}
