; =====================================================================
;  user library - shared "pure text" used by all user-land programs.
;  Runs in user mode; talks to the kernel only through system calls.
; =====================================================================

        MACRO SC num
        ld a,num
        call SYS
        ENDM

; ---- per-process library data (start of user data, cleared by exec)
U_ARGC  equ UDATA+0
U_ARGV  equ UDATA+2
U_NBUF  equ UDATA+4             ; 8 (ps/top run a name on into U_CH, U_T)
U_CH    equ UDATA+12
U_T     equ UDATA+13            ; 8 scratch
U_EI    equ UDATA+21            ; each: index
U_EF    equ UDATA+22            ; each: routine
R_FD    equ UDATA+24            ; buffered reader
R_CNT   equ UDATA+25
R_PTR   equ UDATA+27
R_ERR   equ UDATA+29
R_BUF   equ UDATA+30            ; 128 (also the private buffer of
                                ; programs that never use the reader)
U_UN    equ UDATA+158
U_CT    equ U_UN                ; 26 ctime result
U_STB   equ U_UN+26             ; 34 byte stat buffer (stat prints two
                                ; ctimes of it: they are side by side)
U_CMPF  equ U_STB+32            ; sortp compare routine (set after the
                                ; last stat a sort depends on)
; mkdir1 works in R_BUF and on into U_CT/U_STB: it is used only by mkdir
; and tar's extract, which use neither the reader nor ctime and keep no
; stat result across it.  Paths of up to 92 characters.
MK_Q    equ R_BUF               ; 96 mkdir1: dir/. and dir/..
MK_P    equ R_BUF+96            ; 96 mkdir1: parent directory
TV      equ U_UN+60             ; first free byte for programs

; System call stubs for the calls user programs make most often:
;   "call sc_open" (3 bytes) does what "call sc_open" (5 bytes) does: the
;   stub only jumps, so the stack, registers and flags are the same.
sc_open:  ld a,_open
        jr scgo
sc_close: ld a,_close
        jr scgo
sc_read:  ld a,_read
        jr scgo
sc_stat:  ld a,_stat
        jr scgo
sc_exec:  ld a,_exec
        jr scgo
sc_write: ld a,_write
        jr scgo
sc_unlink: ld a,_unlink
        jr scgo
sc_seek:  ld a,_seek
        jr scgo
sc_intr:  ld a,_intr
        jr scgo
sc_time:  ld a,_time
        jr scgo
sc_sleep: ld a,_sleep
        jr scgo
sc_link:  ld a,_link
        jr scgo
sc_creat: ld a,_creat
        jr scgo
sc_wait:  ld a,_wait
        jr scgo
sc_fork:  ld a,_fork
        jr scgo
sc_chdir: ld a,_chdir
        jr scgo
scgo:   jp SYS

; ---------------------------------------------------------------------
; program start: save argc / argv
;   use:  pop hl / call args   (SP points to argc at entry)
; ---------------------------------------------------------------------
args:   ld (U_ARGC),hl
        ld hl,2
        add hl,sp
        ld (U_ARGV),hl
        ret

; argn: A = n -> HL = argv[n] (Z/HL=0 if n >= argc)
argn:   ld hl,(U_ARGC)
        cp l
        jr nc,.no
        ld hl,(U_ARGV)
        add a,a
        add a,l
        ld l,a
        jr nc,.n
        inc h
.n:     call ldind
        or h
        ret
.no:    ld hl,0
        xor a
        ret

exit0:  ld hl,0
exitc:  SC _exit

; ---------------------------------------------------------------------
; output
; ---------------------------------------------------------------------
; puts: HL = string -> stdout ; eputs -> fd 2 ; fputs A = fd
puts:   ld a,1
fputs:  push hl
        push af
        call strlen
        pop af
        pop de
        ld l,a
        ld h,0
        jp tpadopt.xj1_17  ; (shared tail)
eputs:  ld a,2
        jr fputs

; putc: A -> stdout ; eputc -> fd 2
putc:   push hl
        push de
        push bc
        ld (U_CH),a
        ld hl,1
.w:     ld de,U_CH
        ld bc,1
        call sc_write
        ld a,(U_CH)             ; putc keeps A
        jp getch.xj0_54  ; (shared tail)
eputc:  push hl
        push de
        push bc
        ld (U_CH),a
        ld hl,2
        jr putc.w

crlf:   ld a,10
        jr putc
space:  ld a,' '
        jr putc

; strlen: HL -> BC (HL preserved)
strlen: push hl
        ld bc,0
.l:     ld a,(hl)
        or a
        jr z,.e
        inc hl
        inc bc
        jr .l
.e:     pop hl
        ret

; fmtdec: HL = value, DE = buffer -> digits written, DE after them
fmtdec: push bc
        ld b,0                  ; digits pushed
.d:     push de
        ld de,10
        call udiv16             ; HL = HL / 10, DE = remainder
        ld a,e
        pop de
        add a,'0'
        push af
        inc b
        ld a,h
        or l
        jr nz,.d
.p:     pop af
        ld (de),a
        inc de
        djnz .p
        pop bc
        ret

; putdec: HL -> stdout ; putdecw: A = field width (right aligned)
putdec: xor a
putdecw:
        push af
        ld de,U_NBUF
        call fmtdec
        xor a
        ld (de),a
        ld hl,U_NBUF
        call strlen
        pop af
        sub c
        jr c,.n
        jr z,.n
        ld b,a
.s:     call space
        djnz .s
.n:     jp pname.xj1_7  ; (shared tail)

; put2: A (0..99) two digits with leading zero -> (DE)
put2:   ld b,'0'-1
.l:     inc b
        sub 10
        jr nc,.l
        add a,'0'+10
        ex de,hl
        ld (hl),b
        inc hl
        ld (hl),a
        inc hl
        ex de,hl
        ret

; putoct: HL -> 6 octal digits on stdout
putoct: ld de,U_NBUF
        ld b,6
        ld a,h
        ; first digit: top bit
        rlca
        and 1
        add a,'0'
        ld (de),a
        inc de
        add hl,hl
        ld b,5
.l:     xor a
        add hl,hl
        rla
        add hl,hl
        rla
        add hl,hl
        rla
        add a,'0'
        ld (de),a
        inc de
        djnz .l
        xor a
        ld (de),a
        jp pname.xj0_18  ; (shared tail)

; udiv16: HL = HL / DE, DE = remainder
udiv16: push bc
        ld a,h
        ld c,l
        ld hl,0
        ld b,16
.l:     sla c
        rla
        adc hl,hl
        sbc hl,de
        jr nc,.s
        add hl,de
        jr .n
.s:     inc c
.n:     djnz .l
        ex de,hl
        ld h,a
        ld l,c
        pop bc
        ret

; umul16: HL = HL * DE
umul16: push bc
        ld b,h
        ld c,l
        ld hl,0
        ld a,16
.l:     add hl,hl
        ex de,hl
        add hl,hl
        ex de,hl
        jr nc,.n
        add hl,bc
.n:     dec a
        jr nz,.l
        pop bc
        ret

; udiv32: DE:HL = DE:HL / C (C < 256), A = remainder
;   Pure helpers (no kernel state) are not duplicated in user land: the
;   resident user text calls the kernel's copies (cphl, basenm, adda...)
udiv32  equ div32

; ---------------------------------------------------------------------
; strings
; ---------------------------------------------------------------------
; strcmp: HL, DE -> Z if equal
strcmp: ld a,(de)
        cp (hl)
        ret nz
        or a
        ret z
        inc hl
        inc de
        jr strcmp

; strcpy: HL -> DE (DE left on the terminating 0)
strcpy: ld a,(hl)
        ld (de),a
        or a
        ret z
        inc hl
        inc de
        jr strcpy

; atoi: HL -> DE decimal value, HL after digits; CF if no digits
atoi:   ld de,0
        ld a,(hl)
        sub '0'
        cp 10
        ccf
        ret c
.l:     ld a,(hl)
        sub '0'
        cp 10
        jr nc,.e
        push hl
        ex de,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        add hl,hl
        ld e,a
        ld d,0
        add hl,de
        ex de,hl
        pop hl
        inc hl
        jr .l
.e:     or a
        ret

; atoo: HL -> DE octal value; CF if no digits
atoo:   ld de,0
        ld a,(hl)
        sub '0'
        cp 8
        ccf
        ret c
.l:     ld a,(hl)
        sub '0'
        cp 8
        jr nc,atoi.e
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        or l
        ld l,a
        ex de,hl
        inc hl
        jr .l

; basenm: HL = path -> HL = last component
basenm  equ basename

; catpath: DE = dest buffer, HL = dir, BC = name -> "dir/name" in dest
catpath:
        push bc
        call strcpy
        dec de
        ld a,(de)
        inc de
        cp '/'
        jr z,.s
        ld a,'/'
        ld (de),a
        inc de
.s:     pop hl
        jr strcpy

; mkdir1: HL = path -> make a directory with its . and .. entries
;   (v1 mkdir: the system call makes the node, links make the entries)
;   CF if it cannot be made.  Uses U_T, MK_P, MK_Q.
mkdir1: ld (U_T),hl
        ld de,0Eh               ; rw for owner, r for others
        SC _mkdir
        ret c
        ld bc,s_mkd1            ; dir/. -> dir
        call .cat
        ex de,hl
        ld hl,(U_T)
        call sc_link
        ld hl,(U_T)             ; the parent: dir without its last name
        ld de,MK_P
        call strcpy
        ld hl,MK_P
        call basenm
        ld de,MK_P
        or a
        sbc hl,de
        jr nz,.sl
        ld hl,s_mkd1            ; no '/': the parent is "."
        ld de,MK_P
        call strcpy
        jr .pp
.sl:    add hl,de
        dec hl                  ; the '/'
        ld (hl),0
        ld a,(MK_P)
        or a
        jr nz,.pp
        ld hl,'/'               ; "/name": the parent is "/"
        ld (MK_P),hl
.pp:    ld bc,s_mkd2            ; dir/.. -> parent
        call .cat
        ex de,hl
        ld hl,MK_P
        call sc_link
        or a
        ret
.cat:   ld hl,(U_T)
        ld de,MK_Q
        call catpath
        ld hl,MK_Q
        ret
s_mkd2: db "."
s_mkd1: db ".",0

; isdir: HL = name -> Z if directory (uses U_STB); CF if no file
isdir:  ld de,U_STB
        call sc_stat
        jr nc,.ok
        or 1                    ; NZ and CF: no such file
        scf
        ret
.ok:
        ld a,(U_STB+3)
        and 040h
        xor 040h
        ret

; ---------------------------------------------------------------------
; buffered input  (v1 'getc' / 'getw' style)
; ---------------------------------------------------------------------
; ropen: HL = name -> opens for reading into the reader; CF on error
ropen:  ld de,0
        call sc_open
        ret c
        ld a,l
rsetfd: ld (R_FD),a
        ld hl,0
        ld (R_CNT),hl
        or a
        ret

; getch: -> A = next character; CF at end of file
getch:  push hl
        push de
        push bc
        ld hl,(R_CNT)
        ld a,h
        or l
        jr nz,.h
        ld a,(R_FD)
        ld l,a
        ld h,0
        ld de,R_BUF
        ld bc,128
        call sc_read
        jr c,.eof
        ld a,h
        or l
        jr z,.eof
        ld (R_CNT),hl
        ld hl,R_BUF
        ld (R_PTR),hl
.h:     ld hl,(R_CNT)
        dec hl
        ld (R_CNT),hl
        ld hl,(R_PTR)
        ld a,(hl)
        inc hl
        ld (R_PTR),hl
        or a
.xj0_54:
.x:     jp mputc.xj0_2  ; (shared tail)
.eof:   ld (R_ERR),a
        scf
        jr .x

; getline: DE = buffer, B = size -> line without newline, 0 terminated
;   CF if end of file and nothing was read
getline:
        ld c,0
.l:     call getch
        jr c,.eof
        cp 10
        jr z,.e
        dec b
        inc b
        jr z,.l
        ld (de),a
        inc de
        inc c
        dec b
        jr .l
.eof:   ld a,c
        or a
        scf
        jr z,.z
.e:     or a
.z:     push af
        xor a
        ld (de),a
        pop af
        ret

rclose: ld a,(R_FD)
        ld l,a
        ld h,0
        jp tpsv.xj1_18  ; (shared tail)

; ---------------------------------------------------------------------
; ctime: DE:HL = seconds since 1970 -> U_CT "Thu Jan  1 00:00:00 1970"
; ---------------------------------------------------------------------
ctime:  ld c,60
        call udiv32
        ld (U_T+0),a            ; seconds
        call udiv32
        ld (U_T+1),a            ; minutes
        ld c,24
        call udiv32
        ld (U_T+2),a            ; hours
        ; HL = days since 1970 (fits 16 bits until 2149)
        push hl
        ld de,4                 ; 1970-01-01 was a Thursday
        add hl,de
        ld de,7
        call udiv16
        ld a,e
        ld hl,daynm
        call nm3
        ld de,U_CT
        ld bc,3
        ldir
        ld a,' '
        ld (de),a
        pop hl
        ; year
        ld bc,1970
.y:     push hl
        ld hl,365
        ld a,c
        and 3
        jr nz,.y1
        inc hl
.y1:    ex de,hl
        pop hl
        call cphl
        jr c,.m
        or a
        sbc hl,de
        inc bc
        jr .y
.m:     ld (U_T+4),bc
        ; month
        ld ix,mdays
        ld b,0
.ml:    ld e,(ix+0)
        ld d,0
        ld a,b
        cp 1
        jr nz,.m1
        ld a,c
        and 3
        jr nz,.m1
        inc e                   ; Feb in a leap year
.m1:    call cphl
        jr c,.md
        or a
        sbc hl,de
        inc ix
        inc b
        jr .ml
.md:    inc l                   ; day of month
        ld a,l
        ld (U_T+3),a
        ld a,b
        push hl
        ld hl,monnm
        call nm3
        ld de,U_CT+4
        ld bc,3
        ldir
        pop hl
        ex de,hl
        ld (hl),' '
        inc hl
        ld a,(U_T+3)
        ld b,' '
        cp 10
        jr c,.d1
        ld b,'0'-1
.d0:    inc b
        sub 10
        jr nc,.d0
        add a,10
.d1:    ld (hl),b
        inc hl
        add a,'0'
        ld (hl),a
        inc hl
        ld (hl),' '
        inc hl
        ex de,hl
        ld a,(U_T+2)
        call put2
        ld a,':'
        ld (de),a
        inc de
        ld a,(U_T+1)
        call put2
        ld a,':'
        ld (de),a
        inc de
        ld a,(U_T+0)
        call put2
        ld a,' '
        ld (de),a
        inc de
        ld hl,(U_T+4)
        call fmtdec
        xor a
        ld (de),a
        ld hl,U_CT
        ret

cphl    equ cphlde              ; HL - DE (flags)

; nm3: A = index, HL = table of 3 letter names -> HL = name
nm3:    ld e,a
        add a,a
        add a,e
        ld e,a
        ld d,0
        add hl,de
        ret

daynm:  db "SunMonTueWedThuFriSat"
monnm:  db "JanFebMarAprMayJunJulAugSepOctNovDec"
mdays:  db 31,28,31,30,31,30,31,31,30,31,30,31

; error helpers: print "name: msg" on fd 2 and exit(1) / continue
; perr: HL = name, DE = message
perr:   push de
        call eputs
        ld hl,m_colon
        call eputs
        pop hl
        call eputs
        ld a,10
        jp eputc
m_colon equ s_usage+5           ; ": " (t_file)

; rdent: HL = directory fd, DE = 10 byte entry buffer -> CF at the end;
;   else HL = the entry's name, Z if the slot is free
rdent:  push de
        ld bc,10
        call sc_read
        pop de
        ret c
        ld a,l
        cp 10                   ; a short read: the end
        ret c
        ex de,hl
        ld a,(hl)
        inc hl
        or (hl)
        inc hl
        ret

; isdot: HL = name -> Z if it is "." or ".."
isdot:  ld a,(hl)
        cp '.'
        ret nz
        inc hl
        ld a,(hl)
        or a
        ret z
        cp '.'
        ret nz
        inc hl
        ld a,(hl)
        or a
        ret

; blocks: HL = bytes -> HL = 128-byte blocks (CF: one more, past 32K)
blocks: ld de,127
        add hl,de
        add hl,hl
        ld l,h
        ld h,0
        ret

; tabjp: A = key, HL = table of key bytes and routine words, ended by
;   a 0 byte and the routine for any other key -> jump to the routine
tabjp:  cp (hl)
        inc hl
        jr z,.j
        inc hl
        inc hl
        inc (hl)
        dec (hl)
        jr nz,tabjp
        inc hl
.j:     ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        jp (hl)

; each: call routine HL for every argument from index A on (HL = arg)
each:   ld (U_EF),hl
        ld (U_EI),a
.l:     ld a,(U_EI)
        call argn
        ret z
        ld de,.n
        push de
        push hl
        ld hl,(U_EF)
        ex (sp),hl
        ret
.n:     ld hl,U_EI
        inc (hl)
        jr .l

; sortp: HL = array of B pointers; (U_CMPF) = compare routine
;   called with HL = a[i-1], DE = a[i]; must return CF to swap them
sortp:  ld a,b
        cp 2
        ret c
        ld (U_T+6),hl
        ld c,1
.o:     ld a,c
        cp b
        ret nc
        push bc
.i:     ld a,c
        or a
        jr z,.ni
        ld hl,(U_T+6)
        dec a
        add a,a
        add a,l
        ld l,a
        jr nc,.i0
        inc h
.i0:    push hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        call ldind
        ex de,hl                ; HL = a[c-1], DE = a[c]
        push hl
        push de
        push bc
        ld bc,.ret
        push bc
        ld bc,(U_CMPF)
        push bc
        ret
.ret:   pop bc
        pop de
        pop hl
        jr c,.sw
        pop hl
        jr .ni
.sw:    ex (sp),hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        pop de
        ld (hl),e
        inc hl
        ld (hl),d
        dec c
        jr .i
.ni:    pop bc
        inc c
        jr .o

; copyfd: copy file descriptor (U_T+4) to (U_T+2) through the 128 byte
;   CPBUF -> CF on write error.  Its callers (cat, cp, mv) do not use the
;   buffered reader, so the copy goes through R_BUF.
CPBUF   equ R_BUF
copyfd: ld hl,(U_T+4)
        ld de,CPBUF
        ld bc,128
        call sc_read
        ret c
        ld a,h
        or l
        ret z
        ld b,h
        ld c,l
        push bc
        ld hl,(U_T+2)
        ld de,CPBUF
        call sc_write
        pop bc
        ret c
        or a
        sbc hl,bc
        scf
        ret nz
        jr copyfd

; ptmode: U_STB (stat) -> 6 character v1 mode string at DE
;   [l|s|t] [d|u|x|-] r w r w
ptmode: ld a,(U_STB+3)
        ld c,'s'
        bit 4,a
        jr z,.p1
        ld c,'l'
.p1:    bit 3,a
        jr z,.p2
        ld c,'t'                ; resident ("pure") text
.p2:    bit 2,a
        jr z,.p4
        ld c,'z'                ; packed by zxpack
.p4:    ld b,a
        ld a,c
        ld (de),a
        inc de
        ld a,(U_STB+2)
        ld c,a
        ld a,'d'
        bit 6,b
        jr nz,.p3
        ld a,'u'
        bit 5,c
        jr nz,.p3
        ld a,'x'
        bit 4,c
        jr nz,.p3
        ld a,'-'
.p3:    ld (de),a
        inc de
        ld b,'r'
        bit 3,c
        call .bit
        ld b,'w'
        bit 2,c
        call .bit
        ld b,'r'
        bit 1,c
        call .bit
        ld b,'w'
        bit 0,c
        call .bit
        xor a
        ld (de),a
        ret
.bit:   ld a,b
        jr nz,.y
        ld a,'-'
.y:     ld (de),a
        inc de
        ret
