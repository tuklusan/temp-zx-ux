; t13_abi.s - hand-written Z80 partners for t13_abi.c: the 20 rules of the
; rcc ABI (C48 Rev 0.11 sections 56-59, docs/SPEC-SDK-R2.md section 3),
; written from the documents, not from rcc's output.
;   arguments 1..n-1 pushed in order as words, argument n in HL, the callee
;   removes the pushed words; results in HL (H = 0 for a byte), a float
;   result in @fac, float arguments as pointers to five bytes; IX preserved,
;   AF BC DE HL clobbered, IY and the alternate set not the program's.
        section text
        global _abi_sp0,_abi_sp1,_abi_sp3,_abi_sp8,_abi_words,_abi_echo
        global _abi_fptr,_abi_call3,_abi_frame,_abi_callret,_abi_callfr
        global _abi_ixkeep,_abi_clobber,_abi_iy,_abi_alt

; int abi_sp0(void): the caller's SP (before the call)
_abi_sp0:
        ld hl,2
        add hl,sp
        ret

; int abi_sp1(int x): records x (from HL) in abi_got[0]; the caller's SP
_abi_sp1:
        ld (_abi_got),hl
        ld hl,2
        add hl,sp
        ret

; int abi_sp3(int a, int b, int c): a, b, c -> abi_got[0..2], taken from
; the stack (a deepest) and HL only; removes its pushed words; returns the
; caller's SP as it was before the arguments were pushed
_abi_sp3:
        ld (_abi_got+4),hl      ; c: HL
        pop bc                  ; return address
        pop de
        ld (_abi_got+2),de      ; b: last pushed
        pop de
        ld (_abi_got),de        ; a: first pushed
        ld hl,0
        add hl,sp
        push bc
        ret

; int abi_sp8(int a, ..., int h): the eight arguments -> abi_got[0..7]
_abi_sp8:
        ld (_abi_got+14),hl
        pop bc
        ld hl,_abi_got+12
        ld a,7
.l:     pop de
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
        dec hl
        dec hl
        dec a
        jr nz,.l
        ld hl,0
        add hl,sp
        push bc
        ret

; int abi_words(char a, int b, char *p, unsigned int c): the three pushed
; words and HL -> abi_got[0..3]; abi_got[4] = 1 if p is &abi_target
_abi_words:
        ld (_abi_got+6),hl
        pop bc
        pop de
        ld (_abi_got+4),de      ; p
        ld hl,_abi_target
        or a
        sbc hl,de
        ld hl,0
        jr nz,.n
        inc hl
.n:     ld (_abi_got+8),hl
        pop de
        ld (_abi_got+2),de      ; b
        pop de
        ld (_abi_got),de        ; a
        push bc
        ret

; int abi_echo(unsigned char c): HL as passed
_abi_echo:
        ret

; int abi_fptr(float x): copies the five bytes HL points at to abi_fb
_abi_fptr:
        ld de,_abi_fb
        ld bc,5
        ldir
        ld hl,0
        ret

; int abi_call3(void): calls int c3(int, int, int) as c3(1, 2, 3) with DE
; and BC holding junk (no three-register scheme); returns its result, or
; -1 if SP is not back where it was (the callee removes the pushed words)
_abi_call3:
        ld (spsave),sp
        ld hl,1
        push hl
        ld hl,2
        push hl
        ld de,0DEADh
        ld bc,0BEEFh
        ld hl,3
        call _c3
        ld (res),hl
        ld hl,0
        add hl,sp
        ld de,(spsave)
        or a
        sbc hl,de
        ld hl,(res)
        ret z
        ld sp,(spsave)
        ld hl,-1
        ret

; int abi_frame(void), called from the recursive int rframe(int a, int b,
; int n) at n = 0: the caller's IX frame is [a][b][return][old IX] <- IX
; with the last argument n at IX-2; 1 if this frame and the one it links
; to (n = 1) both have that layout
_abi_frame:
        push ix
        pop hl
        call .chk               ; this frame: n = 0
        jr nz,.no
        ld l,(ix+0)
        ld h,(ix+1)             ; the caller's caller (n = 1)
        push hl
        ex (sp),ix
        ld de,1
        call .chk1
        pop ix
        jr nz,.no
        ld hl,1
        ret
.no:    ld hl,0
        ret
.chk:   ld de,0
.chk1:  ld a,(ix-2)
        cp e
        ret nz
        ld a,(ix-1)
        cp d
        ret nz
        ld a,(ix+4)
        cp 22h                  ; b = 2222h
        ret nz
        ld a,(ix+5)
        cp 22h
        ret nz
        ld a,(ix+6)
        cp 11h                  ; a = 1111h
        ret nz
        ld a,(ix+7)
        cp 11h
        ret

; int abi_callret(void): calls the C functions ri, rp, rb, rc and rv;
; 1 if ri() = -2 in HL, rp() = &abi_target, rb() = 200 and rc() = 255
; with H = 0, and rv() leaves SP alone
_abi_callret:
        call _ri
        ld de,-2
        or a
        sbc hl,de
        jr nz,.no
        call _rp
        ld de,_abi_target
        or a
        sbc hl,de
        jr nz,.no
        call _rb
        ld de,200
        or a
        sbc hl,de
        jr nz,.no
        call _rc
        ld de,255
        or a
        sbc hl,de
        jr nz,.no
        ld (spsave),sp
        call _rv
        ld hl,0
        add hl,sp
        ld de,(spsave)
        or a
        sbc hl,de
        jr nz,.no
        ld hl,1
        ret
.no:    ld hl,0
        ret

; int abi_callfr(void): calls float rf(int a) with a = 3 in HL and nothing
; pushed: 1 if SP is unchanged and @fac holds 6.0 (00 00 06 00 00)
_abi_callfr:
        ld (spsave),sp
        ld hl,3
        call _rf
        ld hl,0
        add hl,sp
        ld de,(spsave)
        or a
        sbc hl,de
        jr nz,.no
        ld hl,@fac
        ld a,(hl)
        inc hl
        or (hl)
        inc hl
        cp 0
        jr nz,.no
        ld a,(hl)
        cp 6
        jr nz,.no
        inc hl
        ld a,(hl)
        inc hl
        or (hl)
        jr nz,.no
        ld hl,1
        ret
.no:    ld hl,0
        ret

; int abi_ixkeep(void): IX survives calls to the C functions c3
; (non-recursive) and deep (recursive); 1 if it did
_abi_ixkeep:
        push ix
        ld ix,1357h
        ld hl,1
        push hl
        ld hl,2
        push hl
        ld hl,3
        call _c3
        ld hl,6
        call _deep
        push ix
        pop de
        pop ix
        ld hl,0
        ld a,d
        cp 13h
        ret nz
        ld a,e
        cp 57h
        ret nz
        inc hl
        ret

; int abi_clobber(void): clobbers AF, BC, DE and HL (flags too); returns 1
_abi_clobber:
        ld bc,1111h
        ld de,2222h
        ld a,0FFh
        add a,1                 ; Z C H set
        ld hl,1
        ret

; int abi_iy(void): 1 if IY holds 5C3Ah, the value the ROM and the
; kernel keep in it
_abi_iy:
        push iy
        pop de
        ld hl,5C3Ah
        or a
        sbc hl,de
        ld hl,0
        ret nz
        inc hl
        ret

; int abi_alt(void): scrambles the alternate set (BC' DE' HL' AF');
; returns 1
_abi_alt:
        exx
        ld bc,0BEEFh
        ld de,0DEADh
        ld hl,0F00Dh
        exx
        ex af,af'
        ld a,55h
        ex af,af'
        ld hl,1
        ret

        section bss
spsave: ds 2
res:    ds 2
