/* t6_inc.h - local include for t6_pp.c: sees the includer's macros and
 * leaves its own definitions visible after it returns */
#define INC_A (BASE + 1)
#define INC_STR "inc"
int inc_fn(int x)
{
    return x * 2;
}
