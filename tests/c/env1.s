; helpers for env1.c: the address of the runtime's ENV1 block (@env1, the
; C runtime's crt0) - test code only; C48 has no getenv API.
        section text
        global _env1,_env1a
_env1:
_env1a: ld hl,@env1
        ret
