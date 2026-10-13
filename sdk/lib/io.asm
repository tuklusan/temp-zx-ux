; rcc runtime: files, through the ZX-UX file system calls   (ZX-UX SDK)
;   int open(char *path, int mode)    mode 0 read, 1 write, 2 both
;   int close(int h)                 0 on success
;   int read(int h, void *p, unsigned int n)
;   int seek(int h, unsigned int pos)
; Results as the kernel gives them: -1 (FFFFh) on an error, with errno set.
SYS     equ 6003h
        section text
        global _open,_close,_read,_seek
_open:  pop bc
        pop de
        push bc
        ex de,hl                ; HL = path, DE = mode
        ld a,5
        jp @sys
_close: ld a,6
        jp @sys0                ; (the kernel leaves HL as it was)
_read:  ld b,h                  ; BC = count
        ld c,l
        pop hl
        pop de                  ; DE = buffer
        ex (sp),hl              ; HL = handle
        ld a,3
        jp @sys
_seek:  ex de,hl                ; DE = position
        pop bc
        pop hl                  ; HL = handle
        push bc
        ld bc,0
        ld a,19
        jp @sys
