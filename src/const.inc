; =====================================================================
;  ZX-UX UNIX v1  -  system constants
;  A fresh Z80 / ZX Spectrum 48K implementation inspired by 8086 UNIX v1
;  (Erdogan Tan) architecture, itself a port of 1971 PDP-11 UNIX v1.
; =====================================================================

; ---------------------------------------------------------------- memory map
;  0000-3FFF  ROM (used for keyboard, screen, beeper, charset, tape)
;  4000-5AFF  display file + attributes
;  5B00-5BFF  printer buffer      -> kernel globals (proc table, fsp ...)
;  5C00-5CB5  system variables    (MEMBOT 5C92..5CAF -> kernel scratch,
;                                  zxpack encoder variables; MEMBOT+0..4
;                                  free: a program's BEEP writes there)
;  5CB6-5CCA  CHANS (needed by ROM PRINT-OUT)
;  5CCB-5EFF  dead BASIC/IF1 area -> zxpack unpack i-node, keyboard ring,
;             process names, swapper scratch, zxpack model tail and coder
;             state, kernel stack (5D98-5EFF)
;  5F01-5F50  tty canonical line buffer
;  5F51-5F61  zxpack variables
;  5F62-5FFF  exec argument buffer
;  6000-....  kernel text + resident user-land text ("pure text")
;  ZXW        256 bytes: the boot code as loaded, then the zxpack literal
;             model
;  ITAB       i-node table (NINODE x 32 bytes)
;  AR0..      the arena: every file and directory, the save image of
;             each resident-text process and loaded SSX1 programs
;             (arena.asm), up to the window, or through it while the
;             window is lent to a program (a_top)
;  F000-FFB8  WINDOW: data/bss + stack of the resident-text process that
;             owns it (UDATA .. CORETOP)
;  FFB9-FFF3  u-area of the running process (UASZ bytes)
;  FFF4-FFF6  JP isr        IM 2 with I = 39h: the vector is read from
;  FFFF       JR (FFF4)     the ROM's FFh filler -> FFFFh; the JR offset
;                           is ROM byte 0000h (F3h = -13).  I stays out
;                           of 40h-7Fh (no ULA 'snow' on real machines)

KBASE   equ 06000h
TRAMP   equ 0FFF4h          ; IM 2 trampoline
UASZ    equ 59              ; u-area size (kvars.inc)
CORE    equ TRAMP-UASZ      ; u-area of the running process
WINDOW  equ 0F000h          ; window: resident-text process images
UDATA   equ WINDOW          ; first byte of user data
CORETOP equ CORE            ; window top: stack and arguments below
STKRES  equ 384             ; most stack a program may reserve (its header's
                            ; second word, saved with its window image)

KV      equ 05B00h          ; kernel globals (printer buffer)
KSTACK  equ 05F00h          ; kernel stack top (grows down to the low kernel's end)
IM2I    equ 039h            ; I register: ROM page full of FFh
TTYBUF  equ 05F01h          ; 80 bytes
TTYBSZ  equ 80
KARGS   equ 05F62h          ; 158 bytes
KARGSZ  equ 158
MEMBOT  equ 05C92h          ; 30 bytes calculator memory -> scratch

; ---------------------------------------------------------------- file system
NINODE  equ 24              ; i-node table entries (i-numbers 41..64)
ROOTINO equ 41              ; v1: root directory is i-number 41
INOSZ   equ 32              ; v1 i-node size
TXINO   equ 128             ; resident programs: i-numbers 128.. (ptab)

; arena block kinds (arena.asm); below K_IMG: movable
K_FREE  equ 0
K_FILE  equ 1               ; file or directory (i.dskp -> payload)
K_SAVE  equ 2               ; process u-area (+ window image)
K_IMG   equ 4               ; loaded SSX1 program (fixed)
K_TEMP  equ 5               ; packer workspace (fixed)

; i-node fields (offsets) - identical to UNIX v1
I_FLGS  equ 0
I_NLKS  equ 2
I_UID   equ 3
I_SIZE  equ 4
I_DSKP  equ 6
I_CTIM  equ 22
I_MTIM  equ 26
I_RSVD  equ 30

; i.flgs bits (v1, octal in comments)
IALLOC  equ 08000h          ; 0100000 allocated
IFDIR   equ 04000h          ; 040000  directory
IFMOD   equ 02000h          ; 020000  modified
IFLARGE equ 01000h          ; 010000  large file
IFTEXT  equ 00800h          ; Z80 extension: resident ("pure") text in core
ISUID   equ 020h            ; 040 set user id
IEXEC   equ 010h            ; 020 executable
IROWN   equ 008h            ; 010 read owner
IWOWN   equ 004h            ; 04  write owner
IROTH   equ 002h            ; 02  read others
IWOTH   equ 001h            ; 01  write others

; special files (i-numbers < 41 are devices, as in v1)
DEV_TTY equ 1
DEV_MEM equ 2
DEV_TAP equ 5
NSPEC   equ 5

; ---------------------------------------------------------------- processes
NPROC   equ 4               ; preemptive multitasking, 4 processes max
NFILES  equ 12              ; system open file table (fsp)
NUFILE  equ 10              ; per-process file descriptors
QUANT   equ 4               ; time quantum in 50Hz ticks (Retro: time_count=4)

SFREE   equ 0
SRUN    equ 1
SSLEEP  equ 2
SZOMB   equ 3

WC_TTY  equ 1               ; wait channels
WC_WAIT equ 2
WC_TIME equ 3

; ---------------------------------------------------------------- errors
EPERM   equ 1
ENOENT  equ 2
EIO     equ 5
EBADF   equ 9
ECHILD  equ 10
EAGAIN  equ 11
ENOMEM  equ 12
EACCES  equ 13
EBUSY   equ 16
EEXIST  equ 17
ENOTDIR equ 20
EISDIR  equ 21
EINVAL  equ 22
ENFILE  equ 23
EMFILE  equ 24
ENOEXEC equ 8
ENOSPC  equ 28
EINTR   equ 4
EFBIG   equ 27
EDOM    equ 33
ERANGE  equ 34

; ---------------------------------------------------------------- syscalls
SYS     equ KBASE+3         ; call SYS with A = number
_rele   equ 0
_exit   equ 1
_fork   equ 2
_read   equ 3
_write  equ 4
_open   equ 5
_close  equ 6
_wait   equ 7
_creat  equ 8
_link   equ 9
_unlink equ 10
_exec   equ 11
_chdir  equ 12
_time   equ 13
_mkdir  equ 14
_chmod  equ 15
_chown  equ 16
_break  equ 17
_stat   equ 18
_seek   equ 19
_tell   equ 20
_mount  equ 21
_umount equ 22
_setuid equ 23
_getuid equ 24
_stime  equ 25
_quit   equ 26
_intr   equ 27
_fstat  equ 28
_emt    equ 29
_mdate  equ 30
_stty   equ 31
_gtty   equ 32
_ilgins equ 33
_sleep  equ 34              ; UNIX v1-compatible extension
_kill   equ 35              ; Z80 extension (needed with a 2-slot proc table)
_getpid equ 36              ; Z80 extension
_zxpack equ 37              ; Z80 extension: HL = name (0: arena status)
_ticks  equ 38              ; C support: HL = 50 Hz frame counter
_screen equ 39              ; C support: HL = 1 claim (-> font), 0 release
_ssxload equ 40             ; BC = file length, DE = memory, HL = argv
NSYS    equ 41

; tty modes (stty word 3)
TT_RAW  equ 020h
TT_ECHO equ 010h

; ---------------------------------------------------------------- ROM
ROM_KEYBOARD  equ 002BFh
ROM_KEYINPUT  equ 010A8h
ROM_CHANOPEN  equ 01601h
ROM_CLS       equ 00D6Bh
ROM_BEEPER    equ 003B5h
ROM_BREAKKEY  equ 01F54h
ROM_SABYTES   equ 004C2h
ROM_LDBYTES   equ 00556h
ROM_CHARSET   equ 03D00h

; system variables
SV_KSTATE equ 05C00h
SV_LASTK  equ 05C08h
SV_FLAGS  equ 05C3Bh
SV_TVFLAG equ 05C3Ch
SV_ERRSP  equ 05C3Dh
SV_MODE   equ 05C41h
SV_BORDCR equ 05C48h
SV_FLAGS2 equ 05C6Ah
SV_DFSZ   equ 05C6Bh
SV_FRAMES equ 05C78h
SV_SPOSN  equ 05C88h
SV_SCRCT  equ 05C8Ch
SV_ATTRP  equ 05C8Dh
SV_ATTRT  equ 05C8Fh
SV_CHANS  equ 05C4Fh
