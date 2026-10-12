; =====================================================================
;  tar - tape archiver on the Spectrum cassette
;
;   tar c[v]f /dev/cassette/label file ...   write an archive
;   tar t[v]f /dev/cassette/label [file ...] list it
;   tar x[v]f /dev/cassette/label [file ...] extract it (or some files)
;   tap r|t|x [file ...]                     v1 'tap', same archives
;
;  Directories are archived with everything below them.  Extracting
;  replaces existing files without asking and makes missing directories.
;  Packed files travel as their packed stream and come back packed.
;
;  Tape format: standard Spectrum blocks, so tape browsers show names.
;   archive  header "label", CODE, length 0, p1 = 'A', p2 = "RU"
;   member   header "basename", CODE, length n, p1 = 'F', p2 = "RU",
;            then n bytes in data blocks of up to 512 (a 17 byte block
;            is sent as 18: 17 bytes are a header to the tape driver):
;              kind (1 packed, 2 directory), i-node flags (2),
;              size (2), stored bytes (2), mtime (4), path, 0, data
;   end      header "", CODE, length 0, p1 = 'E', p2 = "RU"
; =====================================================================
TP_FD   equ TV                  ; tape fd
TP_F    equ TV+2                ; member file fd (FFFF: none)
TP_K    equ TV+4                ; c t x
TP_A    equ TV+5                ; first file argument
TP_V    equ TV+6                ; verbose
TP_IN   equ TV+7                ; inside the wanted archive
TP_N    equ TV+8                ; member bytes still on tape
TP_W    equ TV+10               ; tape buffer fill pointer
TP_S    equ TV+12               ; payload bytes still to send
TP_BK   equ TV+14               ; packed stream block number
TP_RD   equ TV+16               ; /dev/mem fd (packed streams, i-nodes)
TP_X    equ TV+19               ; the file existed (extract)
TP_ERR  equ TV+20               ; write failed (extract)
TP_I    equ TV+21               ; argument scan index
TP_LB   equ TV+22               ; 10 archive label
TP_HD   equ TV+32               ; 17 tape header
TP_PH   equ TV+49               ; 11 member preamble (path follows)
TP_E    equ TV+50               ; 10 directory entry (saving only)
TP_P    equ TV+60               ; 80 path
TP_SB   equ R_BUF               ; 128 staging block (saving only: the
                                ; extract's mkdir1 is the R_BUF user)
TP_B    equ TV+140              ; 512 tape block
TPBSZ   equ 512
PRE     equ 11                  ; preamble before the path

t_tar:  db 18h,6
        dw STKRES, TP_B+TPBSZ-UDATA, tar_m
tar_m:  pop hl
        call args
        ld hl,TP_LB             ; no label: any archive
        ld b,10
.sp:    ld (hl),' '
        inc hl
        djnz .sp
        xor a
        ld (TP_V),a
        call argn               ; called as tap?
        call basenm
        inc hl
        inc hl
        ld a,(hl)
        cp 'p'
        jr nz,.tar
        ld (TP_V),a             ; tap: v1 lists what it does
.tar:   ld a,1
        call argn
        jr z,tpuse
        ld b,2                  ; next argument
.k:     ld a,(hl)
        inc hl
        or a
        jr z,.kd
        cp 'v'
        jr nz,.k1
        ld (TP_V),a
        jr .k
.k1:    cp 'f'
        jr nz,.k2
        push hl
        push bc
        ld a,b
        call argn
        jr z,tpuse
        call tparc
        pop bc
        pop hl
        inc b
        jr .k
.k2:    cp 'r'                  ; tap r = tar c
        jr nz,.k3
        ld a,'c'
.k3:    ld (TP_K),a
        jr .k
.kd:    ld a,b
        ld (TP_A),a
        ld hl,s_tap
        ld de,2
        call sc_open
        ld (TP_FD),hl
        jp c,tperr
        ld hl,s_mem
        ld de,2
        call sc_open
        ld (TP_RD),hl
        ld a,(TP_K)
        cp 'c'
        jr z,tpcrt
        cp 't'
        jp z,tpget
        cp 'x'
        jp z,tpget
tpuse:  ld hl,s_taru
        jp usage

; tparc: HL = archive name: /dev/cassette[/label] or /dev/tap[/label]
tparc:  ld (TP_W),hl
        ld de,s_cas
        call tppfx
        jr z,.ok
        ld hl,(TP_W)
        ld de,s_tap
        call tppfx
        jr nz,.bad
.ok:    ld a,(hl)
        or a
        ret z
        cp '/'
        jr nz,.bad
        inc hl
        ld de,TP_LB
        ld b,10
.l:     ld a,(hl)
        or a
        ret z
        ld (de),a
        inc hl
        inc de
        djnz .l
        ret
.bad:   ld hl,(TP_W)
        ld de,s_tpnc
.xj1_3:
        call perr
        jp tpex1

; tppfx: HL = string, DE = prefix -> Z and HL after it if it starts so
tppfx:  ld a,(de)
        or a
        ret z
        cp (hl)
        ret nz
        inc hl
        inc de
        jr tppfx

; ---------------------------------------------------------------------
;  write an archive
; ---------------------------------------------------------------------
tpcrt:  ld a,(TP_A)
        call argn
        jr z,tpuse
        ld a,'A'                ; archive header: the label
        ld hl,TP_LB
        call tphead
        ld a,(TP_A)
        ld hl,.one
        call each
        ld hl,0                 ; end of the archive
        ld (TP_N),hl
        ld a,'E'
        ld hl,s_tpnil
        call tphead
        jp exit0
.one:   ld de,TP_P
        call strcpy
; tpsv: archive TP_P, and everything under it if it is a directory
tpsv:   ld hl,TP_P
        ld de,U_STB
        call sc_stat
        jr nc,.ok
        ld hl,TP_P
.xj0_14:
        ld de,s_tpnf
        jp perr
.ok:    ld hl,(U_STB)
        ld de,ROOTINO
        or a
        sbc hl,de
        jr c,.skip              ; a device
        ld a,(U_STB+3)
        bit 3,a                 ; a resident program
        jr z,.go
.skip:  ld hl,TP_P
        ld de,s_tpsk
        jp perr
.go:    call tpobj
        ld a,(U_STB+3)
        bit 6,a
        ret z
        ld hl,TP_P              ; a directory: its entries
        ld de,0
        call sc_open
        ret c
        push hl
.e:     pop hl
        push hl
        ld de,TP_E
        call rdent
        jr c,.x
        jr z,.e                 ; free slot
        call isdot              ; not "." or ".."
        jr z,.e
.sub:   ld hl,TP_P              ; path/name, then cut it off again
        call strlen
        add hl,bc
        push hl
        dec hl
        ld a,(hl)
        inc hl
        cp '/'
        jr z,.ns
        ld (hl),'/'
        inc hl
.ns:    ex de,hl
        ld hl,TP_E+2
        call ldir8
        xor a
        ld (de),a
        call tpsv
        pop hl
        ld (hl),0
        jr .e
.x:     pop hl
.xj0_47:
.xj1_18:
        jp sc_close

; tpobj: one member: header, preamble, data (U_STB = its i-node)
tpobj:  ld hl,TP_PH
        ld a,(U_STB+3)
        ld c,0
        bit 2,a
        jr z,.k1
        inc c                   ; packed
.k1:    bit 6,a
        jr z,.k2
        set 1,c                 ; directory
.k2:    ld (hl),c
        inc hl
        ld de,(U_STB+2)         ; i-node flags
        call tpw16
        ld de,(U_STB+6)         ; size
        call tpw16
        bit 0,c                 ; bytes stored: the packed stream,
        jr z,.k3                ; nothing for a directory
        ld de,(U_STB+32)
.k3:    bit 1,c
        jr z,.k4
        ld de,0
.k4:    ld (TP_S),de
        call tpw16
        ex de,hl
        ld hl,U_STB+28          ; mtime (the path follows in TP_P)
        ld bc,4
        ldir
        ld hl,TP_P              ; preamble and path -> the tape block
        call strlen
        ld hl,PRE+1
        add hl,bc               ; preamble length
        ld b,h
        ld c,l
        push hl
        ld hl,TP_PH
        ld de,TP_B
        ldir
        ld (TP_W),de
        pop hl                  ; member length = preamble + stored
        ld de,(TP_S)
        add hl,de
        ld (TP_N),hl
        ld hl,TP_P
        call basenm
        ld a,(hl)
        or a
        jr nz,.h
        ld hl,TP_P              ; "/"
.h:     ld a,'F'
        call tphead
        call tpvl
        ld a,(TP_PH)
        rra
        jr c,.pk
        rra
        jr c,.done              ; directory: no data
        ld hl,TP_P              ; plain file: read it
        ld de,0
        call sc_open
        jr c,.done
        ld (TP_F),hl
.r:     call tpnb
        jr z,.rc
        push bc
        ld hl,(TP_F)
        ld de,TP_SB
        call sc_read
        pop bc
        call tpcopy
        jr .r
.rc:    ld hl,(TP_F)
        call sc_close
        jr .done
.pk:    ld hl,0                 ; packed: its stream, piece by piece,
        ld (TP_BK),hl           ; from memory
.p:     call tpnb
        jr z,.done
        push bc
        call tpblk
        pop bc
        call tpcopy
        ld hl,(TP_BK)
        inc hl
        ld (TP_BK),hl
        jr .p
.done:  jr tpflush

; tpw16: DE -> (HL), HL += 2
tpw16:  ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ret

; tpnb: BC = next piece of the payload (up to 128); Z if none left
tpnb:   ld hl,(TP_S)
        ld bc,128
        call tpmin
        ld a,b
        or c
        ret

; tpmin: BC = min(HL, BC)
tpmin:  push hl
        or a
        sbc hl,bc
        pop hl
        ret nc
        ld b,h
        ld c,l
        ret

; tpcopy: BC bytes from TP_SB to the tape
tpcopy: ld hl,(TP_S)
        or a
        sbc hl,bc
        ld (TP_S),hl
        ld hl,TP_SB
.l:     ld a,b
        or c
        ret z
        ld a,(hl)
        inc hl
        push hl
        push bc
        call tpput
        pop bc
        pop hl
        dec bc
        jr .l

; tpput: A -> tape buffer, sent when full
tpput:  ld hl,(TP_W)
        ld (hl),a
        inc hl
        ld (TP_W),hl
        ld de,TP_B+TPBSZ
        or a
        sbc hl,de
        ret nz
tpflush:
        ld hl,(TP_W)
        ld de,TP_B
        ld (TP_W),de
        or a
        sbc hl,de
        ret z
        ld b,h
        ld c,l
        call tp17
; tpwr: DE, BC -> one tape block
tpwr:   ld hl,(TP_FD)
        call sc_write
        ret nc
tperr:  ld hl,s_tperr
        call eputs
.xj0_13:
.xj1_2:
.xj2_0:
.xj3_0:
tpex1:  jp ldx_m.xj0_1  ; (shared tail)

; tp17: BC = 17 -> 18 (a 17 byte block would be a header)
tp17:   ld a,b
        or a
        ret nz
        ld a,c
        cp 17
        ret nz
        inc c
        ret

; tphead: A = kind, HL = name -> header block, length TP_N
tphead: push hl
        ld hl,TP_HD
        ld (hl),3               ; CODE
        inc hl
        ld b,10
.s:     ld (hl),' '
        inc hl
        djnz .s
        ld de,(TP_N)
        call tpw16
        ld (hl),a               ; p1: kind
        inc hl
        ld (hl),80h
        inc hl
        ld (hl),'R'             ; p2: "RU"
        inc hl
        ld (hl),'U'
        pop hl
        ld de,TP_HD+1
        ld b,10
.n:     ld a,(hl)
        or a
        jr z,.w
        cp ' '
        jr z,.w
        ld (de),a
        inc hl
        inc de
        djnz .n
.w:     ld de,TP_HD
        ld bc,17
        jr tpwr

; tpblk: piece TP_BK (128 bytes) of the packed stream of the file in
;   U_STB (the stream is its block: i.dskp) -> TP_SB
tpblk:  ld hl,(TP_BK)
        call rdoff
        ld de,(U_STB+8)
        add hl,de
        ld de,TP_SB
        ld bc,128
; rdat: HL = address (/dev/mem), DE = buffer, BC = count -> read
rdat:   push bc
        push de
        ex de,hl
        ld hl,(TP_RD)
        ld bc,0
        call sc_seek
        pop de
        pop bc
        ld hl,(TP_RD)
.xj0_46:
        jp sc_read
; rdoff: HL = piece -> HL = its byte offset
rdoff:  ld b,7
.m:     add hl,hl
        djnz .m
        ret

; tpvl: verbose: kind, size, path of the member (TP_PH, TP_P)
tpvl:   ld a,(TP_V)
        or a
        ret z
tpls:   ld a,(TP_PH)
        ld c,'-'
        rra
        jr nc,.a
        ld c,'z'
.a:     rra
        jr nc,.b
        ld c,'d'
.b:     ld a,c
        call putc
        ld hl,(TP_PH+3)
        ld a,6
        call putdecw
        call space
        ld hl,TP_P
.xj0_12:
.xj1_1:
        call puts
        jp crlf

; ---------------------------------------------------------------------
;  list or extract
; ---------------------------------------------------------------------
tpget:  xor a
        ld (TP_IN),a
.h:     ld de,TP_HD             ; next header (other blocks are passed)
        ld bc,17
        ld hl,(TP_FD)
        call sc_read
        jr c,.h
        ld hl,(TP_HD+15)
        ld de,'R'+256*'U'
        or a
        sbc hl,de
        jr nz,.h
        ld a,(TP_HD+13)
        cp 'A'
        jr nz,.f
        ld hl,TP_LB             ; an archive: is it the one?
        ld de,TP_HD+1
        ld b,10
        ld a,(hl)
        cp ' '
        jr z,.in                ; no label asked for: the first one
.lc:    ld a,(de)
        cp (hl)
        jr nz,.h
        inc hl
        inc de
        djnz .lc
.in:    ld a,1
        ld (TP_IN),a
        jr .h
.f:     cp 'E'
        jr nz,.m
        ld a,(TP_IN)
        or a
        jp nz,exit0
        jr .h
.m:     cp 'F'
        jr nz,.h
        ld hl,(TP_HD+11)
        ld (TP_N),hl
        call tpnext             ; the preamble: keep it
        ld hl,TP_B
        ld de,TP_PH
        ld bc,PRE+80
        ldir
        ld a,(TP_IN)
        or a
        jr z,.dr
        call tpsel
        jr nz,.dr
        ld a,(TP_K)
        cp 'x'
        jr z,.x
        ld a,(TP_V)             ; t: names, or the long form with v
        or a
        jr nz,.tv
        ld hl,TP_P
        call puts
        call crlf
        jr .dr
.tv:    call tpls
.dr:    call tpdrain
        jp .h
.x:     call tpext
        jp .h

; tpnext: next data block of the member -> TP_B, BC = its length,
;   TP_W = its end
tpnext: ld hl,(TP_N)
        ld bc,TPBSZ
        call tpmin
        ld hl,(TP_N)
        or a
        sbc hl,bc
        ld (TP_N),hl
        push bc
        call tp17
        ld de,TP_B
        ld hl,(TP_FD)
        call sc_read
        pop bc
        jp c,tperr
        ld hl,TP_B
        add hl,bc
        ld (TP_W),hl
        ret

; tpdrain: read past the rest of the member
tpdrain:
        ld hl,(TP_N)
        ld a,h
        or l
        ret z
        call tpnext
        jr tpdrain

; tpsel: Z if the member is wanted (no names given, or its path is a
;   name given or lies under one)
tpsel:  ld a,(TP_A)
        ld (TP_I),a
        call argn
        jr nz,.l
        xor a
        ret
.l:     ld de,TP_P
.c:     ld a,(hl)
        or a
        jr z,.e
        ld b,a
        ld a,(de)
        cp b
        jr nz,.n
        inc hl
        inc de
        jr .c
.e:     ld a,(de)
        or a
        ret z
        cp '/'
        ret z
.n:     ld hl,TP_I
        inc (hl)
        ld a,(hl)
        call argn
        jr nz,.l
        or 1
        ret

; tpext: extract the member (TP_PH, TP_P; first block in TP_B)
tpext:  call tpvl
        ld hl,TP_P+1        ; make the missing directories
.d:     ld a,(hl)
        or a
        jr z,.dd
        cp '/'
        jr nz,.dn
        ld (hl),0
        push hl
        call tpmk
        pop hl
        ld (hl),'/'
.dn:    inc hl
        jr .d
.dd:    ld a,(TP_PH)
        bit 1,a
        jr z,.fl
        call tpmk               ; a directory
        jp .attr
.fl:    ld hl,TP_P          ; a file: replace it, no questions
        ld de,U_STB
        call sc_stat
        ld a,0
        jr c,.new
        inc a
.new:   ld (TP_X),a
        xor a
        ld (TP_ERR),a
        ld hl,TP_P
        ld de,0Eh
        call sc_creat
        jr nc,.op
        ld hl,0FFFFh
        ld a,1
        ld (TP_ERR),a
.op:    ld (TP_F),hl
        ld hl,TP_B+PRE          ; the data in the first block
        call strlen
        add hl,bc
        inc hl
        ex de,hl
        ld hl,(TP_W)
        or a
        sbc hl,de
        ld b,h
        ld c,l
        call tpout
.mo:    ld hl,(TP_N)            ; and in the others
        ld a,h
        or l
        jr z,.cl
        call tpnext
        ld de,TP_B
        call tpout
        jr .mo
.cl:    ld hl,(TP_F)
        inc h
        jr z,.ng
        dec h
        call sc_close
.ng:    ld a,(TP_ERR)
        or a
        jr z,.ok
        ld hl,TP_P          ; no room: do not leave half a file
        call sc_unlink
        ld hl,TP_P
        ld de,s_tpfull
        jp perr
.ok:    ld a,(TP_X)
        or a
        jr z,.pk
        ld hl,TP_P
        ld de,s_tprep
        call perr
.pk:    ld a,(TP_PH)             ; a packed stream: mark it packed
        rra
        call c,tpadopt
.attr:  ld hl,TP_P          ; mode and modification time
        ld a,(TP_PH+1)
        ld e,a
        ld d,0
        SC _chmod
        ld hl,TP_P
        ld de,(TP_PH+7)
        ld bc,(TP_PH+9)
        SC _mdate
        ret

; tpmk: make the directory TP_P if it is not there
tpmk:   ld hl,TP_P
        call isdir
        ret nc
        ld hl,TP_P
        jp mkdir1

; tpout: DE, BC -> the member file (keeps going after an error)
tpout:  ld a,b
        or c
        ret z
        ld a,(TP_ERR)
        or a
        ret nz
        ld hl,(TP_F)
        push bc
        call sc_write
        pop bc
        jr c,.e
        or a
        sbc hl,bc
        ret z
.e:     ld a,1
        ld (TP_ERR),a
        ret

; tpadopt: the file holds a packed stream: mark its i-node packed
;   (IFPACK, logical size, stream length) in the kernel's i-node table
;   through /dev/mem, as v1's icheck and clri worked on the raw disk
tpadopt:
        ld hl,TP_P
        ld de,U_STB
        call sc_stat
        ret c
        ld hl,U_STB+3
        set 2,(hl)
        ld hl,(TP_PH+3)
        ld (U_STB+6),hl
        ld hl,(TP_PH+5)
        ld (U_STB+32),hl
        ld de,1                 ; flags (high byte)
        ld bc,1
        call .w
        ld de,4                 ; size
        ld bc,2
        call .w
        ld de,30                ; stored length
        ld bc,2
; .w: i-node bytes DE.., BC of them, from the stat buffer
.w:     push bc
        push de
        ld hl,(U_STB)
        push de
        ld de,-ROOTINO
        add hl,de
        ld b,5
.m:     add hl,hl
        djnz .m
        pop de
        add hl,de
        ld de,ITAB
        add hl,de
        ex de,hl
        ld hl,(TP_RD)
        ld bc,0
        call sc_seek
        pop de
        ld hl,U_STB+2
        add hl,de
        ex de,hl
        pop bc
        ld hl,(TP_RD)
.xj0_45:
.xj1_17:
        jp sc_write

s_taru: db "tar [ctx][v]f /dev/cassette/name [file...]",0
s_tap:  db "/dev/tap",0
s_cas:  db "/dev/cassette",0
s_tpnc: db "not a cassette",0
s_tpnf  equ s_nf                ; "not found" (sh)
s_tpsk: db "not archived",0
s_tperr: db "tape error",10,0
s_tpfull: db "not written",0
s_tprep: db "replaced",0
s_tpnil equ s_null              ; ""
e_tar:
