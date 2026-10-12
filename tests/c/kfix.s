; helpers for kfix.c: system calls the SDK library does not wrap.
; Same convention as sdk/lib/io.asm: last argument in HL, the others on
; the stack (pushed left to right), the callee removes them.
SYS     equ 6003h
        section text
        global _creat,_write,_unlink,_ssxload,_iyprobe,_exec,_peek
_creat: pop bc
        pop de
        push bc
        ex de,hl                ; HL = path, DE = mode
        ld a,8
        jp SYS
_write: ld b,h                  ; BC = count
        ld c,l
        pop hl
        pop de                  ; DE = buffer
        ex (sp),hl              ; HL = handle
        ld a,4
        jp SYS
_unlink: ld a,10
        jp SYS
_peek:  ld l,(hl)                ; peek(address): the byte there
        ld h,0
        ret
_exec:  ex de,hl                ; DE = argv
        pop bc
        pop hl                  ; HL = path
        push bc
        ld a,11
        jp SYS
_ssxload: ex de,hl              ; DE = memory
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
