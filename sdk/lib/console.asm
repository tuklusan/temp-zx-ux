; rcc runtime: the C48 screen - 64 x 24 text in the 4 x 8 font, colours,
; PLOT/POINT and user-defined graphics, written straight into the display
; file (semantics of the C48 SDK reference screen).              (ZX-UX SDK)
SYS     equ 6003h
TTOP    equ 5BE4h               ; kernel: the console's first row while it
                                ; shares the screen (0: it does not)
        section text
        global @scrinit,_cls,_putchar,_puts,_print_at,_ink,_paper,_bright,_flash
        global _inverse,_over,_border,_plot,_point,@pixel,@pxok
        global _udg_define,_udg_get,_udg_clear,_udg_draw,_udg_draw_2x2
        global @attr,@ttyb,___pixel

; start-up: own the screen, clear it in white on black (unless another
; program shares it).  The keyboard turns raw at the first getchar.
@scrinit:
        ld hl,1
        ld a,39                 ; sys screen: claim -> HL = font
        call SYS
        ld (@font),hl
        ld a,e                  ; E != 0: another program draws too
        or a
        ld (@shared),a
        ld a,7
        ld (@attr),a
        ld a,(@shared)          ; sharing the screen: leave the others'
        or a                    ; part alone
        j nz,@ok
; int cls(void): the rows above the console's
_cls:   call @lim
        ld c,a
        ld b,0
.r:     ld a,b
        call @clrow
        inc b
        ld a,b
        cp c
        j nz,.r
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        dec bc
        ld hl,5800h
        ld de,5801h
        ld a,(@attr)
        ld (hl),a
        ldir
        xor a
        ld (@row),a
        ld (@col),a
        ld (@wrap),a
@ok:    ld hl,0
        ret
; @lim: A = the first text row programs may not draw on: 24, or the
;   console's first row when the shell works below the pictures
@lim:   ld a,(TTOP)
        or a
        ret nz
        ld a,24
        ret
@bad:   ld hl,1
        ret

; ink/paper/bright/flash: HL = value; bad value -> 1
_ink:   ld c,0F8h
        ld b,0
        j @col7
_paper: ld c,0C7h
        ld b,3
@col7:  ld a,h
        or a
        j nz,@bad
        ld a,l
        cp 8
        j nc,@bad
        inc b
.s:     dec b
        j z,.d
        add a,a
        j .s
.d:     ld b,a
        ld a,(@attr)
        and c
        or b
        ld (@attr),a
        j @ok
_bright:
        ld c,0BFh
        ld b,40h
        j @flag
_flash: ld c,07Fh
        ld b,80h
@flag:  call @bool
        j nc,@bad
        ld a,(@attr)
        and c
        bit 0,l
        j z,.z
        or b
.z:     ld (@attr),a
        j @ok
_inverse:
        call @bool
        j nc,@bad
        ld a,l
        neg
        ld (@inv),a
        j @ok
_over:  call @bool
        j nc,@bad
        ld a,l
        ld (@ovr),a
        j @ok
_border:
        ld a,h
        or a
        j nz,@bad
        ld a,l
        cp 8
        j nc,@bad
        out (0FEh),a
        j @ok
; CF if HL is 0 or 1
@bool:  ld a,h
        or a
        ret nz
        ld a,l
        cp 2
        ret

; ---------------------------------------------------------------- text
; int putchar(int c)
_putchar:
        push hl
        ld a,l
        call @putc
        pop hl
        ld h,0
        ret
; int puts(char *s)
_puts:  call @puts
        ld a,10
        call @putc
        j @ok
@puts:  ld a,(hl)
        or a
        ret z
        push hl
        call @putc
        pop hl
        inc hl
        j @puts
; int print_at(int row, int col, char *s)
_print_at:
        ld (@tmp),hl
        pop bc
        pop de                  ; col
        pop hl                  ; row
        push bc
        ld a,h
        or d
        jp nz,@bad
        ld a,l
        cp 24
        jp nc,@bad
        ld b,a
        ld a,e
        cp 64
        jp nc,@bad
        ld c,a
        ld hl,(@row)            ; save row, col and the wrap flag
        push hl
        ld a,(@wrap)
        push af
        ld a,b
        ld (@row),a
        ld a,c
        ld (@col),a
        xor a
        ld (@wrap),a
        ld hl,(@tmp)
        call @puts
        pop af
        ld (@wrap),a
        pop hl
        ld (@row),hl
        jp @ok

; print character A at the cursor (C48 SDK screen semantics)
@putc:  cp 10
        j z,.nl
        cp 13
        j z,.cr
        cp 8
        j z,.bs
        cp 9
        j z,.tab
        cp 12
        jp z,_cls
        cp 32
        ret c
        cp 128
        ret nc
        ld c,a
        ld a,(@wrap)
        or a
        j z,.g
        xor a
        ld (@wrap),a
        push bc
        call .lf
        pop bc
.g:     ld a,c
        call @glyph
        ld hl,@col
        ld a,(hl)
        cp 63
        j nc,.w
        inc (hl)
        ret
.w:     ld a,1
        ld (@wrap),a
        ret
.nl:    call @nowrap
.lf:    call @lim
        dec a
        ld hl,@row
        cp (hl)
        j z,.sc
        j c,.sc
        inc (hl)
        j .c0
.sc:    ld (hl),a
        call @scroll
.c0:    xor a
        ld (@col),a
        ret
.cr:    call @nowrap
        j .c0
.bs:    call @nowrap
        ld hl,@col
        ld a,(hl)
        or a
        ret z
        dec (hl)
        ret
.tab:   call @nowrap
        ld a,(@col)
        add a,8
        and 0F8h
        cp 64
        j nc,.lf
        ld (@col),a
        ret
@nowrap:
        xor a
        ld (@wrap),a
        ret

; draw glyph A (32-127) at (@row, @col)
@glyph: ld c,a
        call @lim
        ld b,a
        ld a,(@row)
        cp b
        ret nc                  ; the console's rows
        ld a,c
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld de,(@font)
        add hl,de
        ex de,hl                ; DE = glyph (4 bytes, two rows each)
        ld a,(@row)
        ld b,a
        and 18h
        or 40h
        ld h,a
        ld a,b
        and 7
        rrca
        rrca
        rrca
        ld l,a
        ld a,(@col)
        ld c,0F0h
        srl a
        j nc,.e
        ld c,0Fh
.e:     or l
        ld l,a                  ; HL = top pixel row of the cell
        push hl
        ld b,4
.lp:    ld a,(de)
        call @gput
        inc h
        ld a,(de)
        rlca
        rlca
        rlca
        rlca
        call @gput
        inc h
        inc de
        djnz .lp
        pop hl                  ; attribute cell
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or 58h
        ld h,a
        ld a,(@attr)
        ld (hl),a
        ret
; A = font byte, this row in the high nibble; C = F0h (even column) / 0Fh
@gput:  bit 0,c
        j z,.h
        rrca
        rrca
        rrca
        rrca
.h:     and c
        push bc
        ld b,a
        ld a,(@inv)
        and c
        xor b
        ld b,a                  ; nibble, inverted if INVERSE 1
        ld a,(@ovr)
        or a
        j nz,.ov
        ld a,c
        cpl
        and (hl)
        or b
        j .st
.ov:    ld a,b
        xor (hl)
.st:    ld (hl),a
        pop bc
        ret

; scroll the screen (above the console) up one text row
@scroll:
        call @lim
        dec a
        ld (@last),a
        ld b,0
.r:     push bc
        ld a,b
        call @rowad
        ex de,hl                ; DE = row b
        pop bc
        push bc
        ld a,b
        inc a
        call @rowad             ; HL = row b+1
        ld a,8
.l8:    push hl
        push de
        ld bc,32
        ldir
        pop de
        pop hl
        inc d
        inc h
        dec a
        j nz,.l8
        pop bc
        inc b
        ld a,(@last)
        cp b
        j nz,.r
        call @clrow
        ld a,(@last)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        ld hl,5820h
        ld de,5800h
        ldir
        ld a,(@attr)
        ld b,32
.a1:    ld (de),a
        inc de
        djnz .a1
        ret
; clear the pixels of text row A (BC kept)
@clrow: call @rowad
        ld a,8
.c8:    push hl
        ld (hl),0
        ld d,h
        ld e,l
        inc de
        push bc
        ld bc,31
        ldir
        pop bc
        pop hl
        inc h
        dec a
        j nz,.c8
        ret
; HL = display address of text row A, pixel line 0
@rowad: ld l,a
        and 18h
        or 40h
        ld h,a
        ld a,l
        and 7
        rrca
        rrca
        rrca
        ld l,a
        ret

; ---------------------------------------------------------------- graphics
; plot(x, y): bottom-left origin
_plot:  pop bc
        pop de                  ; x
        push bc
        call @pxok
        jp nc,@bad
        call @pixel
        jp @ok
; __pixel(x, y): an on-screen pixel for draw/circle
___pixel:
        pop bc
        pop de
        push bc
        call @pxok
        ret nc
        jp @pixel
; int point(x, y): 1 if set; 1 also when out of range (as the reference)
_point: pop bc
        pop de
        push bc
        call @pxok
        jp nc,@bad
        call @pxad
        and (hl)
        jp z,@ok
        jp @bad
; DE = x, HL = y -> CF if on screen; then C = x, B = 191 - y
@pxok:  ld a,d
        or h
        ret nz
        ld a,l
        cp 192
        ret nc
        cpl
        add a,192
        ld b,a
        ld c,e
        scf
        ret
; HL = byte address of pixel (C, B=row from top), A = bit mask
@pxad:  ld a,b
        and 7
        or 40h
        ld h,a
        ld a,b
        rra
        rra
        rra
        and 18h
        or h
        ld h,a
        ld a,b
        rla
        rla
        and 0E0h
        ld l,a
        ld a,c
        rra
        rra
        rra
        and 1Fh
        or l
        ld l,a
        ld a,c
        and 7
        ld b,a
        ld a,80h
        ret z
.m:     rrca
        djnz .m
        ret
; set pixel C, B (row from top) by OVER/INVERSE, and its attribute
;   (not on the console's rows)
@pixel: call @lim
        add a,a
        add a,a
        add a,a
        cp b
        ret c
        ret z
        push hl
        call @pxad
        ld c,a
        ld a,(@ovr)
        or a
        j z,.n
        ld a,(@inv)
        or a
        j nz,.at
        ld a,c
        xor (hl)
        j .st
.n:     ld a,(@inv)
        or a
        ld a,c
        j z,.set
        cpl
        and (hl)
        j .st
.set:   or (hl)
.st:    ld (hl),a
.at:    ld a,h
        rrca
        rrca
        rrca
        and 3
        or 58h
        ld h,a
        ld a,(@attr)
        ld (hl),a
        pop hl
        ret

; ---------------------------------------------------------------- UDGs
; CF if HL is a slot 0..N-1 -> HL = bank address.  The bank (@udgs,
; @nudg slots: 32, or rcc --udgs N) is the program's, made by rcc when
; the program uses UDGs.
@slot:  ld a,h
        or a
        ret nz
        ld a,(@nudg)
        dec a
        cp l
        ccf
        ret nc
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,@udgs
        add hl,de
        scf
        ret
; int udg_define(int slot, unsigned char *bytes)
_udg_define:
        ex de,hl
        pop bc
        pop hl
        push bc
        push de
        call @slot
        pop de
        jp nc,@bad
        ex de,hl
@udgcp: ld bc,8                 ; (udg_get copies the other way from here)
        ldir
        jp @ok
; int udg_get(int slot, unsigned char *bytes)
_udg_get:
        ex de,hl
        pop bc
        pop hl
        push bc
        push de
        call @slot
        pop de
        jp nc,@bad
        j @udgcp
; int udg_clear(int slot)
_udg_clear:
        call @slot
        jp nc,@bad
        ld b,8
.z:     ld (hl),0
        inc hl
        djnz .z
        jp @ok
; int udg_draw(int slot, int row, int col)
_udg_draw:
        pop bc
        pop de                  ; row
        ex (sp),hl              ; HL = slot, col on stack
        push bc
        ld b,h
        ld c,l
        pop hl                  ; ret
        ex (sp),hl              ; HL = col
        call @udg1
        jp nc,@bad
        jp @ok
; BC = slot, DE = row, HL = col: draw; CF on success
@udg1:  ld a,h
        or d
        or b
        ret nz
        ld a,l
        cp 32
        ret nc
        ld a,e
        cp 24
        ret nc
        ld a,(@nudg)
        dec a
        cp c
        ccf
        ret nc
        call @lim               ; the console's rows: "drawn"
        dec a
        cp e
        ret c
        ld a,e                  ; cell address
        and 18h
        or 40h
        ld d,a
        ld a,e
        and 7
        rrca
        rrca
        rrca
        or l
        ld e,a                  ; DE = cell
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,@udgs
        add hl,bc               ; HL = pattern
        ex de,hl                ; HL = cell, DE = pattern
        push hl
        ld b,8
.r:     ld a,(@inv)
        ld c,a
        ld a,(de)
        xor c
        ld c,a
        ld a,(@ovr)
        or a
        ld a,c
        j z,.s
        xor (hl)
.s:     ld (hl),a
        inc h
        inc de
        djnz .r
        pop hl
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or 58h
        ld h,a
        ld a,(@attr)
        ld (hl),a
        scf
        ret
; int udg_draw_2x2(int base, int row, int col)
_udg_draw_2x2:
        pop bc
        pop de
        ex (sp),hl
        push bc
        ld b,h
        ld c,l                  ; BC = base
        pop hl
        ex (sp),hl              ; HL = col
        ld a,b
        or a
        jp nz,@bad
        ld a,(@nudg)            ; base .. base+3 in the bank
        sub 4
        cp c
        jp c,@bad
        ld a,h
        or d
        jp nz,@bad
        ld a,l
        cp 31
        jp nc,@bad
        ld a,e
        cp 23
        jp nc,@bad
        ld a,0
.q:     push af
        push bc
        push de
        push hl
        call @udg1
        pop hl
        pop de
        pop bc
        pop af
        inc bc
        inc a
        cp 4
        jp z,@ok
        cp 2
        j z,.nr
        inc hl
        j .q
.nr:    dec hl
        inc de
        j .q

        section bss
@shared: ds 1
@last:  ds 1
@font:  ds 2
@row:   ds 1
@col:   ds 1
@wrap:  ds 1
@attr:  ds 1
@inv:   ds 1
@ovr:   ds 1
@ttyb:  ds 6
@tmp:   ds 2
