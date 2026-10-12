/* t9_main.c - C48 conformance: external linkage across translation units,
 * case-sensitive and untruncated linker symbols, static (internal) names
 * that do not clash (spec sections 22, 23.2, 79).  Linked with t9_mod.c.
 */
#include "ck.h"

extern int shared_val;
extern int Shared_val;
extern int abcdefghijklmn1;
extern int abcdefghijklmn2;
int mod_fn(int x);
char *mod_str(void);
extern float mod_f;
extern int mod_arr[3];

static int hidden(void)
{
    return 100;
}
static int priv = 50;

int main(void)
{
    ck(9001, shared_val == 11 && Shared_val == 22);                     /* P0287 P0768 */
    ck(9002, abcdefghijklmn1 == 1 && abcdefghijklmn2 == 2);            /* P0287 P0768 */
    ck(9003, mod_fn(1) == 9 && hidden() == 100 && priv == 50);          /* P0255 P0256 P0257 P0288 P0768 */
    ck(9004, mod_str()[0] == 'm' && mod_f == 2.5 && mod_arr[2] == 9);   /* P0256 P0288 */
    shared_val = 12;
    ck(9005, shared_val == 12 && mod_fn(0) == 8);                       /* P0288 */
    return ck_done();
}
