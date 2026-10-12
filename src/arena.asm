; =====================================================================
;  arena - the elastic memory of ZX-UX v1
;
;  One region (AR0 .. a_top) holds every file, directory, process save
;  image and loaded program.  A block is
;       +0 size (word, header included, even)  +2 kind  +3 spare
;  followed by its payload.  Movable blocks (files, saves, twins) are
;  allocated first fit from the bottom (never into the window, which
;  may be lent: see lend) and slide down when the arena is
;  compacted; fixed blocks (loaded program images, packer workspace)
;  go at the bottom of the highest free block that fits, and never move.  Only the kernel points
;  at movable blocks - from the i-node table (i.dskp) and p_save - and
;  compaction rewrites those pointers.  A caller holding a
;  payload address in a register reloads it after any allocation.
; =====================================================================

; aalloc: BC = payload bytes, A = kind -> HL = payload (not cleared)
;   CF + A = ENOMEM.  Tries the arena as it is, then compacted, then
;   after packing closed files one at a time.
aalloc: ld (a_kind),a
        ld hl,5
        add hl,bc
        jr c,.nom
        res 0,l
        ld (a_need),hl
        ld a,2
        ld (a_try),a
.again: call afind
        ret nc
        ld hl,a_try
        dec (hl)
        jr nz,.cmp
        ; no room even compacted: pack a closed file and try again
        ld hl,(a_need)
        push hl
        ld a,(a_kind)
        push af
        call zpress
        pop bc
        pop hl
        jr c,.nom
        ld (a_need),hl
        ld a,b
        ld (a_kind),a
        ld a,1
        ld (a_try),a
.cmp:   call acompact
        jr .again
.xj0_7:
.xj1_0:
.nom:   ld a,ENOMEM
        scf
        ret

; afind: one pass for a_need bytes of a_kind -> HL = payload, CF if none
afind:  ld hl,AR0
        ld de,0                 ; fixed: the highest free block that fits
.l:     call aend
        jr nc,.end
        call ahdr               ; BC = size, A = kind
        or a
        jr nz,.nx
.co:    push hl                 ; free: absorb the free blocks that follow
        add hl,bc
        call aend
        jr nc,.cx
        inc hl
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        or a
        jr nz,.cx
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        add hl,bc
        ld b,h
        ld c,l
        pop hl
        ld (hl),c
        inc hl
        ld (hl),b
        dec hl
        jr .co
.cx:    pop hl
        push hl
        ld hl,(a_need)
        call cpbchl             ; CF if BC < need
        pop hl
        jr c,.nx
        ld a,(a_kind)
        cp K_IMG
        jr nc,.fixed
        push de                 ; movable: first fit below the window
        push hl
        ld de,(a_need)
        add hl,de
        ld de,WINDOW+1
        call cphlde
        pop hl
        pop de
        jr c,.take
        jr .nx
.fixed:   ld d,h                  ; fixed: remember it, look further up
        ld e,l
.nx:    add hl,bc
        jr .l
.end:   ld a,d
        or e
        scf
        ret z
        ; fixed: the bottom of the highest free block that fits, so the
        ; free space above it stays next to the window (which may be lent)
        ex de,hl
        call ahdr
; HL = free block of BC bytes; split off what is not needed
.take:  ld de,(a_need)
        push hl
        call .rem
        jr c,.whole
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
        push hl
        add hl,de
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),K_FREE
.whole: pop hl
.kind:  inc hl
        inc hl
        ld a,(a_kind)
        ld (hl),a
        inc hl
        inc hl
        or a
        ret
; .rem: BC = size, DE = need -> BC = size - need; CF if under 4 (no split)
.rem:   ld h,b
        ld l,c
        or a
        sbc hl,de
        ld b,h
        ld c,l
        ld a,h
        or a
        ret nz
        ld a,l
        cp 4
        ret

; ahdr: HL = block -> BC = size, A = kind
ahdr:   ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        dec hl
        dec hl
        ret
; aend: CF while HL is below the end of the arena
aend:   push de
        ld de,(a_top)
        call cphlde
        pop de
        ret
; cpbchl: CF if BC < HL (BC, DE, HL kept)
cpbchl: push hl
        push de
        ex de,hl
        ld h,b
        ld l,c
.xj0_3:
        or a
        sbc hl,de
        pop de
        pop hl
        ret

; afree: HL = payload (0: nothing)
afree:  ld a,h
        or l
        ret z
        push hl
        dec hl
        dec hl
        ld (hl),K_FREE
        pop hl
        ret

; ashrink: HL = payload, BC = payload bytes to keep -> the tail is freed
ashrink:
        push hl
        ld hl,5
        add hl,bc
        res 0,l
        ex de,hl                ; DE = new block size
        pop hl
        push hl
        ld bc,-4
        add hl,bc               ; HL = block
        call ahdr
        push hl
        call afind.rem
        pop hl
        jr c,.x
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
        add hl,de
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),K_FREE
.x:     pop hl
        ret

; acap: HL = payload -> BC = its capacity
acap:   push hl
        dec hl
        dec hl
        dec hl
        ld b,(hl)
        dec hl
        ld c,(hl)
        ld hl,-4
        add hl,bc
        ld b,h
        ld c,l
        pop hl
        ret

; ---------------------------------------------------------------------
; acompact: slide every movable block down over free space
; ---------------------------------------------------------------------
acompact:
        ld hl,AR0
        ld (a_dst),hl
.l:     call aend
        jr nc,.gap
        call ahdr
        or a
        jr z,.nx                ; free: skip it
        cp K_IMG
        jr c,.mov
        push hl                 ; fixed: the space below it is free
        call .gap
        pop hl
        add hl,bc
        ld (a_dst),hl
        jr .l
.mov:   ld de,(a_dst)
        call cphlde
        jr z,.same
        push bc
        push hl
        push de
        ldir                    ; downwards: a forward copy is safe
        pop de
        pop hl
        push hl
        ld bc,4
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        call afix
        pop hl
        pop bc
.same:  push hl
        ld hl,(a_dst)
        add hl,bc
        ld (a_dst),hl
        pop hl
.nx:    add hl,bc
        jr .l
; .gap: a free block from a_dst up to HL (if any)
.gap:   ld de,(a_dst)
        or a
        sbc hl,de
        ret z
        ex de,hl
        ld (hl),e
        inc hl
        ld (hl),d
.xj0_6:
        inc hl
        ld (hl),K_FREE
        ret

; afix: HL = old payload address, DE = new -> every kernel pointer to it
afix:   ld (a_old),hl
        ld (a_new),de
        ld hl,ITAB+I_DSKP
        ld b,NINODE
        ld de,INOSZ
        call .tab
        ld hl,p_save
        ld b,NPROC
        ld de,2
; .tab: HL -> first word, B words DE apart
.tab:   push de
        push hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld de,(a_old)
        or a
        sbc hl,de
        pop hl
        jr nz,.n
        ld de,(a_new)
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
.n:     pop de
        add hl,de
        djnz .tab
        ret

; afreeb: free bytes in the arena (all free blocks) -> HL
afreeb: ld hl,AR0
        ld de,0
.l:     call aend
        jr nc,.x
        call ahdr
        or a
        jr nz,.n
        ex de,hl
        add hl,bc
        ex de,hl
.n:     add hl,bc
        jr .l
.x:     ex de,hl
        ret

; ---------------------------------------------------------------------
;  lending the window.  When a program loaded from tape does not fit,
;  the window's memory (WINDOW .. CORETOP) joins the arena for as long as
;  the program lives; resident-text processes wait meanwhile (isrun).
; ---------------------------------------------------------------------
; lend: (the window is free) the window into the arena
lend:   ld hl,0FFFFh
        ld (wlend),hl
        ld hl,(a_top)           ; a free block from the arena's end
        ld de,CORETOP
        ex de,hl
        or a
        sbc hl,de
        ex de,hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),K_FREE
        ld hl,CORETOP
        ld (a_top),hl
        ret

; unlend: the window back, if no block is left in it (else it stays
;   lent, wlend unchanged, until the next image is freed)
unlend: call acompact           ; free space slides to the top
        ld de,(a_dst)           ; the top free block starts here
        ld hl,WINDOW
        or a
        sbc hl,de
        ret c                   ; something is still in the window
        ld (a_top),de
        ld a,h                  ; [start, WINDOW) stays free (a gap under
        or a                    ; 4 bytes is left out of the arena)
        jr nz,.b
        ld a,l
        cp 4
        jr c,.z
.b:     ex de,hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),K_FREE
        ld hl,WINDOW
        ld (a_top),hl
.z:     ld hl,0
        ld (wlend),hl
        ret
