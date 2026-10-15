; beephog: 5 notes of about 1 s through ROM BEEPER (03B5h), each called
; with interrupts off straight after the last (BEEPER ends EI, RET): no
; frame interrupt gets in for the whole 5 s
        section text
        global _hog
_hog:   ld b,5
.l:     push bc
        ld hl,1000              ; 8 * 1000 + 236 T-states a cycle: 425 Hz
        ld de,425               ; cycles: about 1 s
        di
        call 03B5h
        pop bc
        djnz .l
        ld hl,0
        ret
