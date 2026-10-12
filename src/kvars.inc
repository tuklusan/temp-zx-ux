; =====================================================================
;  kernel globals - live in the ZX printer buffer (5B00-5BFF)
; =====================================================================
p_stat  equ KV+0        ; byte[4]  process state
        ASSERT (p_stat & 0FFh) == 0 && NPROC <= 256
p_wchan equ KV+4        ; byte[4]  wait channel
p_sig   equ KV+8        ; byte[4]  pending interrupt (BREAK) signal
p_pid   equ KV+12       ; word[4]
p_ppid  equ KV+20       ; word[4]
p_sp    equ KV+28       ; word[4]  saved stack pointer (context frame)
p_brk   equ KV+36       ; word[4]  program break (low swap extent)
p_xst   equ KV+44       ; word[4]  exit status (zombie)
p_tick  equ KV+52       ; word[4]  sleep tick counters
p_save  equ KV+60       ; word[4]  SAVE block: u-area (+ window image)
p_img   equ KV+68       ; word[4]  SSX1 IMAGE block, 0 = resident text
p_cpu   equ KV+76       ; word[4]  clock ticks used (for ps / top)
idlet   equ KV+84       ; word idle ticks (for top; ps/top read KV+0..85)
runrun  equ KV+86       ; reschedule request
quant   equ KV+87       ; remaining quantum
ticks   equ KV+88       ; 1/50 s counter
brkst   equ KV+89       ; BREAK key state (edge detect)
mpid    equ KV+90       ; word last pid
systime equ KV+92       ; dword seconds since 1970
tmpsp   equ KV+96       ; word
wown    equ KV+98       ; slot whose image is in the window (FF none)
scrown  equ KV+99       ; slots owning the screen (sys screen): bit mask
fticks  equ KV+100      ; word 50 Hz frame counter (sys ticks)
a_dst   equ KV+102      ; word arena: compaction write pointer
ttyhd   equ KV+104      ; raw ring head (ISR writes)
ttytl   equ KV+105      ; raw ring tail
ttymode equ KV+106      ; stty flags
ttycnt  equ KV+107      ; chars in canonical line
ttypos  equ KV+108      ; read position in line
ttyrdy  equ KV+109      ; line complete
a_kind  equ KV+110      ; arena: kind being allocated
                        ; KV+111: zxpack (zx.asm)
spino   equ KV+112      ; 32 bytes: synthesized special-file i-node
xhdr    equ KV+144      ; 8 bytes exec header
fsp     equ KV+152      ; NFILES * 6 : inum.w off.w cnt.b flg.b
FSPSZ   equ 6
a_top   equ KV+224      ; word arena end (WINDOW, CORETOP while lent)
wlend   equ KV+226      ; word image the window is lent to (FFFF: lent,
                        ;   waiting for its space to be free)
ttop    equ KV+228      ; first console row while others own the screen
                        ;   (0: the whole screen; 21: rows 21-22)
                        ; KV+229..232 free
a_try   equ KV+233      ; arena: attempts left
a_new   equ KV+234      ; word arena: moved block's new payload
                        ; KV+236..238: zxpack (zx.asm)
kerrsp  equ KV+239      ; word -> rom_error  (ERR_SP points here)
ktmp    equ KV+241      ; word scratch
                        ; KV+243..246: zxpack (zx.asm)
xargc   equ KV+247      ; exec: argc
xtop    equ KV+248      ; word exec: end of packed args
cur     equ KV+250      ; running slot (its image is in core)
inkern  equ KV+251      ; 1 while executing kernel code
idling  equ KV+252      ; 1 while the scheduler idles
ttat    equ KV+253      ; tty output: parameter bytes still expected
ttcc    equ KV+254      ; tty output: control code being parameterized
ttp1    equ KV+255      ; tty output: first parameter

; free low memory given to zxpack, so that only its model and coder
; state take swap pool space (checked unused by every other part of the
; system and by the ROM routines it calls)
ZLO1    equ 05CCBh      ; 32  dead BASIC area below KV2: txino
ZLO2    equ MEMBOT+15   ; 15  calculator memory past the kernel's (the
                        ;     ROM calculator is never used)
ZLO3    equ TTYBUF+TTYBSZ ; 17 between the tty line and KARGS

; second kernel data area in the dead BASIC / IF1 area
KV2     equ 05CEBh
ttyring equ KV2+0       ; 32 bytes raw keyboard ring
stline  equ KV2+32      ; 4 x 8 bytes: process names (status line, ps)
chslot  equ KV2+64      ; fork: the child's slot
sw_lo   equ KV2+65      ; word window image: data (UDATA .. break)
sw_hi   equ KV2+67      ; word window image: stack (sp .. top)
sw_n    equ KV2+69      ; word window image size (save layout)
a_need  equ KV2+71      ; word arena: block size wanted
a_old   equ KV2+73      ; word arena: moved block's old payload
                        ; KV2+75 free
ZLO4    equ KV2+76      ; 97  zxpack: model tail and coder state (zx.asm)
KV2END  equ ZLO4+97     ; kernel stack grows down to here: 360 bytes.
                        ; Its deepest use is idle or disk-full packing
                        ; with an interrupt on top: 76 bytes measured
                        ; over the test suite, under 150 by inspection.

; fsp flags
F_READ  equ 1
F_WRITE equ 2
F_DEL   equ 080h

; =====================================================================
;  per-process 'u' area (swapped with the process) - at CORE, the top
;  of the window
;  Only what the kernel reads: single user (no uids), no quit key (the
;  quit flag was never consulted), no errno word (results go back in A),
;  no device numbers (one disk, nothing to mount), and the status-line
;  names live in stline.
; =====================================================================
u_sp    equ CORE+0      ; sp at system call entry
u_cdir  equ CORE+2      ; current directory i-number
u_fp    equ CORE+4      ; 10 open files (fsp index+1)
u_intr  equ CORE+14     ; 0 = ignore interrupts
u_dirbuf equ CORE+15    ; 10 bytes directory entry
u_off   equ CORE+25     ; i/o offset
u_base  equ CORE+27     ; i/o address
u_count equ CORE+29     ; i/o count
u_nread equ CORE+31     ; bytes transferred
u_pdir  equ CORE+33     ; namei: parent dir i-number (FFFF = none)
u_dirp  equ CORE+35     ; namei: offset of entry / free slot
u_name  equ CORE+37     ; namei: last component (8)
u_ino   equ CORE+45     ; word scratch
u_tmp   equ CORE+47     ; word scratch
u_tmp2  equ CORE+49     ; word scratch
u_fdi   equ CORE+51     ; byte scratch
u_nmp   equ CORE+52     ; namei: path pointer
u_nmi   equ CORE+54     ; namei: directory i-number
u_nlast equ CORE+56     ; namei: last component
u_nfree equ CORE+57     ; namei: first free slot (word)
u_end   equ CORE+59
        ASSERT u_end - CORE == UASZ
