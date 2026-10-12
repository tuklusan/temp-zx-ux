; t10_abi.s - hand-written Z80 routines for t10_abi.c, written from
; docs/SPEC-SDK-R2.md section 3 (the rcc ABI): arguments 1..n-1 pushed in
; order, argument n in HL, the callee removes the pushed words; results in
; HL (H = 0 for a byte), floats as pointers and results in @fac; IX is
; preserved, AF BC DE HL may be clobbered, IY and the alternate set are the
; system's.  (C48 spec sections 57-59.)
        section text
        global _abi_args,_abi_echo,_abi_echo2,_abi_clobber,_abi_fret,_abi_fbyte
        global _abi_callc,_abi_ixkeep

; int abi_args(int a, int b, int c) -> a*256 + b*16 + c   (a, b, c < 16)
_abi_args:
        ld (tmp),hl             ; c
        pop bc                  ; return address
        pop de                  ; b
        pop hl                  ; a
        push bc
        ld h,l                  ; H = a
        ld a,e
        add a,a
        add a,a
        add a,a
        add a,a                 ; b * 16
        ld l,a
        ld a,(tmp)
        add a,l
        ld l,a
        ret

; int abi_echo(unsigned char c): the argument word exactly as passed in HL
_abi_echo:
        ret

; int abi_echo2(char a, int b): the pushed word for a, exactly as passed
_abi_echo2:
        pop bc
        pop hl
        push bc
        ret

; int abi_clobber(void): clobbers AF BC DE HL and the alternate set;
; returns 1 if IY held 5C3Ah (the system's value) when called
_abi_clobber:
        exx
        ld bc,0xBEEF
        ld de,0xDEAD
        ld hl,0xF00D
        exx
        ex af,af'
        ld a,0x55
        ex af,af'
        ld bc,0x1111
        ld de,0x2222
        push iy
        pop hl
        ld a,h
        cp 0x5C
        jr nz,.no
        ld a,l
        cp 0x3A
        jr nz,.no
        ld hl,1
        scf
        ret
.no:    ld hl,0
        ret

; float abi_fret(void): 7.0 in @fac
_abi_fret:
        ld hl,seven
        ld de,@fac
        ld bc,5
        ldir
        ld hl,0xFFFF            ; (HL is not the float result)
        ret

; int abi_fbyte(float x): the exponent byte of the five bytes at HL
_abi_fbyte:
        ld l,(hl)
        ld h,0
        ret

; int abi_callc(void): calls int c3(int, int, int) as (1, 2, 3); returns
; its result, or -1 if SP is not back where it was (the callee removes the
; pushed words)
_abi_callc:
        ld (spsave),sp
        ld hl,1
        push hl
        ld hl,2
        push hl
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

; int abi_ixkeep(void): IX survives a call to the recursive C function
; int deep(int n); returns 1 if it did
_abi_ixkeep:
        push ix
        ld ix,0x1357
        ld hl,6
        call _deep
        push ix
        pop de
        pop ix
        ld hl,0
        ld a,d
        cp 0x13
        ret nz
        ld a,e
        cp 0x57
        ret nz
        inc hl
        ret

        section data
seven:  db 0,0,7,0,0
        section bss
tmp:    ds 2
spsave: ds 2
res:    ds 2
