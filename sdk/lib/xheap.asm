; The default heap (1024 bytes, as rcc --heap's default) for a program
; linked from separately compiled objects (rcc -c): a whole program built
; by rcc defines its own heap, sized by --heap, and never links this.
        section data
        align 2
___heapw:       dw 640                  ; (1024 + 256) / 2 words
___heapsz:      dw 1024
        section bss
        align 2
___heap:        ds 1280
