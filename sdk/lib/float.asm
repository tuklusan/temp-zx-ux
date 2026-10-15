; rcc runtime: five-byte floats, computed by the 48K ROM's calculator
;                                                           (ZX-UX SDK)
; The program calls the ROM itself.  Interrupts are off meanwhile, the
; calculator's stack (STKBOT/STKEND) and memory (MEM) are in this
; program's bss, and ERR_SP points at a trap here, so a ROM error report
; ("Number too big", "Invalid argument" ...) comes back as CF.  The
; kernel's values of those system variables are put back afterwards.
ERRSP   equ 5C3Dh
STKBOT  equ 5C63h
STKEND  equ 5C65h
MEMV    equ 5C68h
MEMBOT  equ 5C92h
        section text
        global @fac,@fmov,@fop,@itof,@utof,@ftoi,@ftou,@fcmp,@ftst,@inrom,@ferr
        global _sin,_cos,_tan,_asin,_acos,_atan,_sqrt,_exp,_log,_fabs,_pow,_beep
; copy the five bytes at HL to DE
@fmov:  ld bc,5
        ldir
        ret

; @inrom: run the routine at HL with the ROM calculator set up; it may
;   leave results in BC and the flags.  CF if the ROM reported an error.
@inrom: di
        push ix
        ex de,hl
        ld hl,(ERRSP)
        ld (@sv),hl
        ld hl,(STKBOT)
        ld (@sv+2),hl
        ld hl,(STKEND)
        ld (@sv+4),hl
        ld hl,(MEMV)
        ld (@sv+6),hl
        ld hl,@cstk
        ld (STKBOT),hl
        ld (STKEND),hl
        ld hl,@cmem
        ld (MEMV),hl
        ld hl,.err
        push hl
        ld (ERRSP),sp
        ld hl,.ret
        push hl
        ex de,hl
        jp (hl)
.err:   scf                     ; (the ROM reset SP to the trap's slot)
        push hl
.ret:   pop hl                  ; drop the trap address
        ld hl,(@sv)
        ld (ERRSP),hl
        ld hl,(@sv+2)
        ld (STKBOT),hl
        ld hl,(@sv+4)
        ld (STKEND),hl
        ld hl,(@sv+6)
        ld (MEMV),hl
        pop ix
        ei
        ret

; @fpush: the five bytes at HL onto the calculator stack
@fpush: ld de,(STKEND)
        ld bc,5
        ldir
        ld (STKEND),de
        ret
; @fpop: the top of the calculator stack -> five bytes at (@fx)
@fpop:  ld hl,(STKEND)
        ld bc,-5
        add hl,bc
        ld de,(@fx)
        ld bc,5
        ldir
        or a
        ret

@ferr:  ld hl,1                 ; status 1, as the C48 language requires
        jp _exit
; x = x op y  (HL = x, DE = y, A = op 1..17); an error ends the program
@fop:   ld (@fx),hl
        ld (@fy),de
        ld (@fo),a
        ld hl,.go
        call @inrom
        ret nc
        j @ferr
.go:    ld hl,(@fx)
        call @fpush
        ld a,(@fo)
        cp 6
        j nc,.un
        ld hl,(@fy)
        call @fpush
        ld a,(@fo)
.un:    ld hl,@ftab-1
        add a,l
        ld l,a
        j nc,.nc
        inc h
.nc:    ld a,(hl)
        ld (.code),a
        rst 28h
.code:  db 0,38h
        j @fpop
; ROM calculator codes for ops 1..17
@ftab:  db 0Fh,03h,04h,05h,06h,2Ah,1Bh,3Ah,26h,25h,1Fh,20h,21h,22h,23h,24h,28h

; HL = int, DE = destination: small-integer form, no ROM needed
@itof:  ld a,h
        add a,a
        sbc a,a                 ; FF if negative
        j @icv
@utof:  xor a
@icv:   ex de,hl
        ld (hl),0
        inc hl
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),0
        ret

; HL -> float: HL = int (truncated); out of range ends the program
@ftoi:  call @fbc
        j c,@ferr
        j z,.pos
        ld a,b                  ; negative: up to 32768
        cp 80h
        j c,.ok
        j nz,@ferr
        ld a,c
        or a
        j nz,@ferr
.ok:    xor a
        sub c
        ld l,a
        sbc a,a
        sub b
        ld h,a
        ret
.pos:   bit 7,b                 ; positive: up to 32767
        j nz,@ferr
        ld h,b
        ld l,c
        ret
@ftou:  call @fbc
        j c,@ferr
        j z,.p
        ld a,b                  ; negative: only zero
        or c
        j nz,@ferr
.p:     ld h,b
        ld l,c
        ret
; @fbc: HL -> float: truncate, then ROM FP-TO-BC: BC = magnitude, CF if
;   too big, NZ if negative
@fbc:   ld (@fx),hl
        ld hl,.go
        jp @inrom
.go:    ld hl,(@fx)
        call @fpush
        rst 28h
        db 3Ah,38h              ; truncate
        call 2DA2h              ; FP-TO-BC
        ret

; compare floats at HL and DE: CF if x < y, ZF if equal
@fcmp:  ld bc,@ftmp
        push bc
        push de
        ld d,b
        ld e,c
        call @fmov              ; x -> @ftmp
        pop de
        pop hl
        ld a,2                  ; x - y
        call @fop
        ld hl,@ftmp
        ld a,(hl)
        or a
        j nz,.big
        inc hl                  ; small integer: sign byte, value
        ld b,(hl)
        inc hl
        ld a,(hl)
        inc hl
        or (hl)
        ret z                   ; zero: equal (NC)
        ld a,b
        j .sg
.big:   inc hl
        ld a,(hl)
.sg:    or 1                    ; NZ
        rla                     ; CF = sign
        ret

; ZF if the float at HL is zero
@ftst:  ld a,(hl)
        inc hl
        inc hl
        or (hl)
        inc hl
        or (hl)
        ret
_sin:   ld a,11
        j @fun1
_cos:   ld a,12
        j @fun1
_tan:   ld a,13
        j @fun1
_asin:  ld a,14
        j @fun1
_acos:  ld a,15
        j @fun1
_atan:  ld a,16
        j @fun1
_sqrt:  ld a,17
        j @fun1
_exp:   ld a,9
        j @fun1
_log:   ld a,10
        j @fun1
_fabs:  ld a,6
@fun1:  push af
        ld de,@fac
        call @fmov
        pop af
        ld hl,@fac
        call @fop
        ld hl,@fac
        ret
; pow(x, y): x pushed, y in HL
_pow:   pop bc
        pop de
        push bc
        push hl
        ex de,hl
        ld de,@fac
        call @fmov
        pop de
        ld hl,@fac
        ld a,5
        call @fop
        ld hl,@fac
        ret
; int beep(float duration, float pitch): 0, or 1 if the ROM refuses
;   (ROM BEEP: it computes BEEPER's period and count from the two numbers)
_beep:  ex de,hl
        pop bc
        pop hl
        push bc
        ld (@fx),hl
        ld (@fy),de
        ld hl,.go
        call @inrom
        ld hl,@mem0             ; MEMBOT's bytes back (CF kept), for a
        ld de,MEMBOT            ; kernel that keeps its clock there (ZX-UX
        ld bc,5                 ; before rev 5)
        ldir
        ei                      ; BEEP ran with interrupts off: wait for the
        halt                    ; next frame's interrupt, so that the
        ld hl,0                 ; keyboard, clock, BREAK and scheduler run
                                ; between notes even when a program beeps
                                ; on and on (a gap of up to 20 ms)
        ret nc
        inc l
        ret
; BEEP reads its integer pitch straight from MEMBOT (5C92h), not through
; MEM, so mem-0 must be MEMBOT while it runs.  ZX-UX kernels before
; rev 5 kept their clock there (tod_h, tod_m, tod_s, stdirty, kcon): save
; those 5 bytes and put them back.
.go:    ld hl,MEMBOT
        ld (MEMV),hl
        ld de,@mem0
        ld bc,5
        ldir
        ld hl,(@fx)
        call @fpush
        ld hl,(@fy)
        call @fpush
        jp 03F8h                ; BEEP (ends in BEEPER: EI, RET)
        section bss
@fac:   ds 5
@ftmp:  ds 5
@fx:    ds 2
@fy:    ds 2
@fo:    ds 1
@sv:    ds 8
@mem0:  ds 5                    ; beep: MEMBOT as the kernel left it
@cmem:  ds 30                   ; calculator memory (MEM)
@cstk:  ds 60                   ; calculator stack (STKBOT..STKEND)
