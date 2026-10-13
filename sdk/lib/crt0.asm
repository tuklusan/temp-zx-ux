; rcc runtime: program start-up and exit                    (ZX-UX SDK)
;
; The kernel starts a program with SP -> argc, argv[0..argc-1], 0, strings.
; @main is defined by the compiled program: it adapts main(void) or
; main(int argc, char **argv) to DE = argc, HL = argv.
;
; ENV1 (C48 Rev 0.11 P1080): the process's environment block, separate from
; ARG1 (the kernel-built argument strings at the top of the program's
; block).  It is process-owned bss in the program's own image, made empty
; (one NUL) here before main: it lives exactly as long as the image and an
; exec starts the new image with a fresh, empty ENV1.  It never points into
; the kernel's KARGS buffer.  There is no getenv() API (C48 Rev 0.11 does
; not define one); @env1 is the bootstrap storage only.
SYS     equ 6003h
        section text
        global start,@noret,@divz,@env1
start:  xor a
        ld (@env1),a            ; ENV1: empty
        ld hl,0
        add hl,sp
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        push de
        call @scrinit
        pop de
        pop hl
        call @main
        jp _exit
@divz:
@noret: ld hl,1
        jp _exit
        section bss
@env1:  ds 1
