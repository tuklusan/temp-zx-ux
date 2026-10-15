#!/usr/bin/env python3
"""Static checks for a rebuilt ZX-UX v1 system image.

These checks do not replace a real ROM tape boot or a display test.
Run them after tools/build.py has completed.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
KBASE = 0x6000


def loader_end():
    """Where the BASIC loader's own memory ends while it loads: its
    program from PROG (5CCBh), VARS' end marker, the 5-byte edit line,
    and the ROM's 34-byte header work space for LOAD (STKBOT = STKEND).
    For the 85-byte loader that is 5D48h, as the ROM's own STKEND reads
    while it loads (measured in the emulator)."""
    tap = (ROOT / 'build/ZX-UX.tap').read_bytes()
    first = int.from_bytes(tap[0:2], 'little')
    second = int.from_bytes(tap[2 + first:4 + first], 'little')
    basic = second - 2                     # (flag and parity bytes)
    return 0x5CCB + basic + 1 + 5 + 34


def main():
    values = {}
    for line in (ROOT / 'src/unix.sym').read_text().splitlines():
        match = re.match(r'(\S+): EQU 0x([0-9A-Fa-f]+)', line)
        if match:
            values[match[1]] = int(match[2], 16)
    kbytes = values['kend'] - KBASE
    fs = (ROOT / 'build/fs.img').read_bytes()
    image = (ROOT / 'build/unix.bin').read_bytes()
    font = (ROOT / 'src/font4x8.bin').read_bytes()
    low = (ROOT / 'build/lowk.bin').read_bytes()
    free_bytes = int.from_bytes(fs[-4:-2], 'little')
    nproc = values['NPROC']
    boot_area = values['bootend'] - values['ZXW']
    start = values['msg_boot'] - KBASE
    end = image.index(0, start)
    banner = image[start:end]
    check = [
        ('kernel size', kbytes <= 8192 and kbytes > 0),
        ('boot area size', boot_area <= 512),   # code and messages; the
                                                # i-node table follows it
        ('memory order', values['kend'] < values['ZXW'] <
         values['ITAB'] < values['AR0'] < values['WINDOW']),
        ('256-byte model area', values['ITAB'] - values['ZXW'] == max(256, boot_area)),
        ('boot banner', banner.startswith(b'\nZX-UX UNIX v1 48K ZX Spectrum Z80 3.5Mhz\n')),
        ('copyright glyph', b'\x7f 2026 SANYALnet Labs' in banner and
         font[8 + (127 - 32) * 4:8 + (128 - 32) * 4] != b'\0' * 4),
        ('kernel and memory values',
         ('%dB free=%dB procs=%d ' % (kbytes, free_bytes, nproc)).encode()
         in banner),
        ('filesystem fits', values['AR0'] + free_bytes <= values['WINDOW']),
        ('login banner', b'  ZX-UX  v1 (tty)\n' in image),
        ('64-column font', len(font) == 392 and values['TROWS'] == 23),
        ('boot success text', image[values['msg_ok'] - KBASE:
                                    values['msg_ok'] - KBASE + 3] == b'ok\n'),
        ('tape names', b'ZX-UX v1' in (ROOT / 'build/ZX-UX.tzx').read_bytes()),
        ('low kernel on the tape',
         low and low in (ROOT / 'build/ZX-UX.tzx').read_bytes() and b'lowk' in
         (ROOT / 'build/ZX-UX.tzx').read_bytes()),
        ('low kernel below the kernel stack',
         values['LOWK'] == values['KV2END'] and
         values['LOWK'] + len(low) <= values['KSTACK'] - 180),
        ('low kernel above the loader while it loads',
         values['LOWK'] > loader_end()),
    ]
    for name, good in check:
        print(('%s ' % name).ljust(32) + ('PASS' if good else 'FAIL'))
    print('Kernel %d bytes; free arena %d bytes; boot code %d bytes' %
          (kbytes, free_bytes, boot_area))
    return 0 if all(good for _, good in check) else 1


if __name__ == '__main__':
    sys.exit(main())
