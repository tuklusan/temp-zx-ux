; helpers for kfix.c: a raw sys ssxload with M1's arguments, an IY probe
; and peek (the other calls come from <c48.h> and the library).
; Same convention as sdk/lib/io.asm: last argument in HL, the others on
; the stack (pushed left to right), the callee removes them.
SYS     equ 6003h
        section text
        global _kssxl,_iyprobe,_peek
_peek:  ld l,(hl)                ; peek(address): the byte there
        ld h,0
        ret
_kssxl: ex de,hl                ; DE = memory   (raw sys ssxload, M1)
        pop hl
        pop bc                  ; BC = length
        push hl
        ld a,40
        jp SYS
; iyprobe(p): run 10 frames with IY = p (sleeping and preempted), then
; put IY back
_iyprobe: push iy
        push hl
        pop iy
        ld hl,10
        ld a,34                 ; sys sleep
        call SYS
        ld b,0
.spin:  djnz .spin              ; and some user-mode time under interrupts
        ld b,0
.spin2: djnz .spin2
        pop iy
        ld hl,0
        ret
