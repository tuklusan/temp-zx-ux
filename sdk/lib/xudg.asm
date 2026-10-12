; The default UDG bank (32 slots) for a program linked from separately
; compiled objects (rcc -c); rcc makes a whole program's own bank (--udgs).
        section data
@nudg:  db 32
        section bss
@udgs:  ds 256
