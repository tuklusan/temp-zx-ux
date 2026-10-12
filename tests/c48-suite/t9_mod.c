/* t9_mod.c - C48 conformance: a separately compiled module without main
 * (spec sections 22, 23.2, 31, 79).  run_suite.py compiles it with -c and
 * links it with t9_main.c and libc48.ssa through sdk/rld.
 */
int shared_val = 11;
int Shared_val = 22;
int abcdefghijklmn1 = 1;
int abcdefghijklmn2 = 2;
static int hidden(void)
{
    return 5;
}
static int priv = 3;
int mod_fn(int x)
{
    return x + hidden() + priv;
}
char *mod_str(void)
{
    return "mod";
}
float mod_f = 2.5;
int mod_arr[3] = { 7, 8, 9 };
int main(int argc, char **argv);
