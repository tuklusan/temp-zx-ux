; rcc runtime: the rest of the ZX-UX system calls               (ZX-UX SDK)
;
; One C function per kernel call (src/unix.asm systab), with the kernel's
; registers: A = call number, HL, DE, BC = arguments, result in HL, CF and
; A = error number on failure.  Every wrapper returns -1 (FFFFh) on an
; error and sets errno to the kernel's error number (it leaves errno alone
; on success); a call with no result of its own returns 0 on success.  The calls already in sys.asm / io.asm (rele = yield, exit,
; read, open, close, seek, sleep, getpid, ticks) are not repeated here.
;
; rcc ABI: arguments 1..n-1 pushed in order, argument n in HL, the callee
; removes the pushed words; IX preserved (the kernel preserves IX and IY).
SYS     equ 6003h
        section text
        global @sys,@sys0,_fork,_write,_wait,_creat,_link,_unlink,_exec,_chdir
        global _time,_mkdir,_chmod,_chown,_brk,_stat,_lseek,_tell,_setuid
        global _getuid,_stime,_quit,_intr,_fstat,_cemt,_mdate,_stty,_gtty
        global _ilgins,_kill,_zxpack,_zxinfo,_screen,_ssxload,@a2,@a3,_errno

; @sys: A = call, HL/DE/BC as the kernel takes them -> HL, CF on error
; (then HL = -1 and errno = the error number)
@sys:   call SYS
        ret nc
        ld (_errno),a
        xor a
        ld (_errno+1),a
        ld hl,-1
        scf
        ret

; @sys0: as @sys for a call with no result: HL = 0 on success (the kernel
; leaves HL as it was, the argument, for these calls)
@sys0:  call @sys
        ret c
        ld hl,0
        ret

; two arguments f(a1, a2): HL = a1, DE = a2
@a2:    ex de,hl                ; DE = a2
        pop bc                  ; (@a2's own return)
        pop hl                  ; the wrapper's return
        ex (sp),hl              ; HL = a1, the wrapper's return on top
        push bc
        ret

; three arguments f(a1, a2, a3): HL = a1, DE = a2, BC = a3
@a3:    ld b,h
        ld c,l                  ; BC = a3
        pop hl                  ; (@a3's own return)
        ld (@t),hl
        pop hl                  ; the wrapper's return
        pop de                  ; DE = a2
        ex (sp),hl              ; HL = a1, the wrapper's return on top
        push hl
        ld hl,(@t)
        ex (sp),hl
        ret

; int fork(void): child pid in the parent, 0 in the child.  ZX-UX does not
; fork SSX1 programs (SPEC-ELASTIC-R2 3.7): from C it is -1, errno EAGAIN.
_fork:  ld a,2
        jp @sys

; int write(int h, void *p, unsigned int n): bytes written
_write: call @a3
        ld a,4
        jp @sys

; int wait(int *status): pid of an ended child, its exit status in *status
; (when status is not NULL); -1 with errno ECHILD when there is none
_wait:  push hl
        ld a,7
        call @sys
        pop bc
        ret c
        ld a,b
        or c
        ret z
        ld a,e
        ld (bc),a
        inc bc
        ld a,d
        ld (bc),a
        ret

; int creat(char *path, int mode): a new (or emptied) file, open to write
_creat: call @a2
        ld a,8
        jp @sys

; int link(char *old, char *new)
_link:  call @a2
        ld a,9
        jp @sys0

; int unlink(char *path)
_unlink:
        ld a,10
        jp @sys0

; int exec(char *path, char **argv): argv 0-terminated (NULL: argv[0] =
; path).  Before it the program gives back the keyboard and the screen, as
; at exit; if exec fails it takes the screen again and returns -1.  The new
; image starts with its own ARG1 and a fresh, empty ENV1.
_exec:  push hl                 ; argv
        ld a,(@israw)
        or a
        ld a,10h                ; keyboard: cooked, echo again
        call nz,@stty
        xor a
        ld (@israw),a           ; (the next getchar makes it raw again)
        ld hl,0
        ld a,39                 ; give the screen back
        call SYS
        pop de                  ; DE = argv
        pop bc
        pop hl                  ; HL = path
        push bc
        ld a,11
        call @sys               ; returns only on an error
        push hl
        ld hl,1
        ld a,39                 ; take the screen again
        call SYS
        pop hl
        scf
        ret

; int chdir(char *path)
_chdir: ld a,12
        jp @sys0

; int time(unsigned int *t): t[0] = low, t[1] = high word of the seconds
; since 1970 (the kernel's clock)
_time:  push hl
        ld a,13
        call @sys
        ex (sp),hl              ; HL = t, low word on the stack
        pop bc
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        ld hl,0
        ret

; int stime(unsigned int *t): set the clock to t[1]:t[0] seconds
_stime: ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; DE = high
        pop hl                  ; HL = low
        ld a,25
        call @sys
        ld hl,0
        ret

; int mkdir(char *path, int mode)
_mkdir: call @a2
        ld a,14
        jp @sys0

; int chmod(char *path, int mode)
_chmod: call @a2
        ld a,15
        jp @sys0

; int chown(char *path, int owner): accepted (ZX-UX is single user)
_chown: call @a2
        ld a,16
        jp @sys0

; int brk(void *addr): set the program's break (inside its own block, below
; the stack): the new break, or -1 with errno ENOMEM
_brk:   ld a,17
        jp @sys

; int stat(char *path, void *buf): 34 bytes, the i-number then the v1 i-node
_stat:  call @a2
        ld a,18
        jp @sys0

; int lseek(int h, int offset, int whence): whence 0 from the start, 1 from
; the current position, 2 from the end; the new position
_lseek: call @a3
        ld a,19
        jp @sys

; int tell(int h): the current position
_tell:  ld a,20
        jp @sys

; int setuid(int uid): accepted (single user)
_setuid:
        ld a,23
        jp @sys0

; int getuid(void): 0, everybody is root
_getuid:
        ld a,24
        jp @sys

; int quit(int on): accepted and ignored (there is no quit key)
_quit:  ld a,26
        jp @sys0

; int intr(int on): 0: the interrupt key (BREAK) is ignored, else it ends
; the process
_intr:  ld a,27
        jp @sys0

; int fstat(int h, void *buf): as stat, for an open file
_fstat: call @a2
        ld a,28
        jp @sys0

; int cemt(void *p): v1's emulator-trap call: accepted, does nothing
_cemt:  ld a,29
        jp @sys0

; int mdate(char *path, unsigned int *t): set the file's modification time
; to t[1]:t[0]
_mdate: ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)               ; BC = high, DE = low
        pop hl                  ; return
        ex (sp),hl              ; HL = path
        ld a,30
        jp @sys0

; int stty(int h, void *buf), int gtty(int h, void *buf): the terminal's
; 6-byte mode block (byte 4: 20h raw, 10h echo)
_stty:  call @a2
        ld a,31
        jp @sys0
_gtty:  call @a2
        ld a,32
        jp @sys0

; int ilgins(void *p): v1's illegal-instruction-trap call: accepted, does
; nothing
_ilgins:
        ld a,33
        jp @sys0

; int kill(int pid): end process pid (it cannot ignore it)
_kill:  ld a,35
        jp @sys0

; unsigned int zxpack(char *path): pack the file with zxpack (if it is not
; packed yet) and return its stream length
_zxpack:
        ld a,37
        jp @sys

; int zxinfo(unsigned int *info): info[0] = free bytes in the arena,
; info[1] = free i-nodes
_zxinfo:
        push hl
        ld hl,0
        ld a,37
        call @sys
        ex (sp),hl
        pop bc
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        ld hl,0
        ret

; unsigned char *screen(int claim): 1 claims the screen (the C runtime has
; already done so at start-up), 0 gives it back; the 4x8 font's address
_screen:
        ld a,39
        jp @sys

; int ssxload(char **argv, unsigned int memory, unsigned int length): become
; the SSX1 program on the tape; only the resident loader /etc/ldx may make
; this call, so from C it is -1 with errno EINVAL
_ssxload:
        call @a3
        ld a,40
        jp @sys

        section bss
@t:     ds 2
_errno: ds 2                    ; int errno: the last failed call's error
