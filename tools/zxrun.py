#!/usr/bin/env python3
"""Headless ZX Spectrum 48K test runner for ZX-UX UNIX v1.

Loads a snapshot (made by tap2sna.py from the TZX, i.e. after a real
ROM tape load), runs it with 50 Hz interrupts, types keys through the
keyboard half-row ports and dumps the screen as text (ROM font OCR).

  zxrun.py SNAPSHOT [script]

script lines:  wait N        run N frames
               type TEXT     type characters (\\n = ENTER)
               key K [K..]   press keys together (CS SS ENTER SPACE a ..)
               screen        print the screen
               until TEXT [N]  run until TEXT appears on screen (max N frames)
               png FILE      save a PNG of the screen
"""
import sys
from skoolkit import CSimulator
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot

FRAME = 69888
ROWS = {  # key -> (half-row index (address bit), bit)
}
_rows = [
    ['CS', 'z', 'x', 'c', 'v'],        # FEFE  bit A8
    ['a', 's', 'd', 'f', 'g'],         # FDFE  A9
    ['q', 'w', 'e', 'r', 't'],         # FBFE  A10
    ['1', '2', '3', '4', '5'],         # F7FE  A11
    ['0', '9', '8', '7', '6'],         # EFFE  A12
    ['p', 'o', 'i', 'u', 'y'],         # DFFE  A13
    ['ENTER', 'l', 'k', 'j', 'h'],     # BFFE  A14
    ['SPACE', 'SS', 'm', 'n', 'b'],    # 7FFE  A15
]
for r, keys in enumerate(_rows):
    for b, k in enumerate(keys):
        ROWS[k] = (r, b)

# character -> key combination (L mode, Spectrum 48K)
SYM = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '&': '6', "'": '7',
       '(': '8', ')': '9', '_': '0', '<': 'r', '>': 't', ';': 'o', '"': 'p',
       '^': 'h', '-': 'j', '+': 'k', '=': 'l', ':': 'z', '?': 'c', '/': 'v',
       '*': 'b', ',': 'n', '.': 'm',
       # mapped keyword tokens (see dev.asm toktab)
       '~': 'a', '|': 's', '\\': 'd', '{': 'f', '}': 'g', '[': 'y', ']': 'u'}

def keys_for(ch):
    if ch == '\n':
        return ['ENTER']
    if ch == ' ':
        return ['SPACE']
    if ch.isdigit() or ch.islower():
        return [ch]
    if ch.isupper():
        return ['CS', ch.lower()]
    if ch in SYM:
        return ['SS', SYM[ch]]
    raise ValueError('cannot type %r' % ch)

import bisect

def tape_pulses(blocks, t0):
    """ROM-timing pulse edges for a list of (flag+data+parity) blocks."""
    edges, t = [], t0
    for blk in blocks:
        pilot = 8063 if blk[0] < 128 else 3223
        for _ in range(pilot):
            t += 2168; edges.append(t)
        t += 667; edges.append(t)
        t += 735; edges.append(t)
        for byte in blk:
            for i in range(7, -1, -1):
                d = 1710 if byte >> i & 1 else 855
                t += d; edges.append(t)
                t += d; edges.append(t)
        t += 3500000          # 1 s pause
        edges.append(t)
    return edges

def decode_mic(changes):
    """Decode (tstate, level) MIC changes written by SA-BYTES into blocks."""
    blocks, cur, bits = [], None, []
    durs = [b[0] - a[0] for a, b in zip(changes, changes[1:])]
    i = 0
    while i < len(durs):
        d = durs[i]
        if 600 < d < 800 and i + 1 < len(durs) and 600 < durs[i + 1] < 800:
            # sync: data follows
            i += 2
            bits = []
            while i + 1 < len(durs) and 700 < durs[i] < 2000:
                bits.append(1 if durs[i] > 1300 else 0)
                i += 2
            data = bytes(int(''.join(map(str, bits[k:k + 8])), 2)
                         for k in range(0, len(bits) - 7, 8))
            blocks.append(data)
        else:
            i += 1
    return blocks

class Tracer:
    def __init__(self):
        self.pressed = set()
        self.edges = []
        self.mic = []
        self.lastmic = None
        self.border = 0
        self.outfe = 0
        self.out7ffd = 0
        self.outfffd = 0
        self.ay = [0] * 16

    def read_port(self, registers, port):
        if port & 1:
            return 0xFF
        hi = port >> 8
        v = 0x1F
        ear = 0
        if self.edges:
            ear = (bisect.bisect_right(self.edges, registers[25]) & 1) << 6
        for k in self.pressed:
            r, b = ROWS[k]
            if not hi & (1 << r):
                v &= ~(1 << b)
        return v | 0xA0 | ear

    def write_port(self, registers, port, value, *rest):
        if not port & 1:
            self.border = value & 7
            m = value & 8
            if m != self.lastmic:
                self.lastmic = m
                self.mic.append((registers[25], m))

class ZX:
    def __init__(self, snapfile):
        snap = Snapshot.get(snapfile)
        self.sim = from_snapshot(CSimulator, snap, config={'fast_djnz': False})
        self.mem = self.sim.memory
        self.tr = Tracer()
        self.sim.set_tracer(self.tr)
        # the console's 4 x 8 font (two pixel rows a byte, 96 glyphs)
        import os
        fb = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'src', 'font4x8.bin'), 'rb').read()[8:8 + 384]
        self.font = {}
        for c in range(32, 128):
            g = fb[(c - 32) * 4:(c - 32) * 4 + 4]
            rows = bytes(n for b in g for n in (b >> 4, b & 15))
            self.font.setdefault(rows, chr(c))
            self.font.setdefault(bytes(15 - x for x in rows), chr(c))
        self.frames = 0

    def run(self, frames):
        regs = self.sim.registers
        for _ in range(frames):
            t = regs[25]
            self.sim.trace(regs[24], -1, 0, t + FRAME, 1, None, None, None, None, None)
            self.frames += 1

    def press(self, keys, hold=4, gap=7):
        self.tr.pressed = set(keys)
        self.run(hold)
        self.tr.pressed = set()
        self.run(gap)

    def type(self, text):
        for ch in text:
            self.press(keys_for(ch))

    def screen(self):
        lines = []
        for row in range(24):
            s = ''
            for col in range(64):
                a = 0x4000 + ((row & 0x18) << 8) + ((row & 7) << 5) + col // 2
                sh = 4 if col % 2 == 0 else 0
                g = bytes((self.mem[a + (i << 8)] >> sh) & 15 for i in range(8))
                s += self.font.get(g, '#' if any(g) else ' ')
            lines.append(s.rstrip())
        return '\n'.join(lines)

    def flash_cells(self):
        return [i for i in range(768) if self.mem[0x5800 + i] & 0x80]

    def until(self, text, limit=3000):
        for _ in range(limit // 10):
            if text in self.screen():
                return True
            self.run(10)
        return text in self.screen()

    def png(self, fname, scale=2, border=16):
        """Write the screen (with border) as a PNG, flash shown as 'on'."""
        import zlib, struct
        pal = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205),
               (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
               (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255),
               (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
        bc = pal[self.tr.border & 7]
        W, H = 256 + 2 * border, 192 + 2 * border
        rows = []
        for y in range(H):
            row = []
            sy = y - border
            for x in range(W):
                sx = x - border
                if 0 <= sx < 256 and 0 <= sy < 192:
                    a = 0x4000 | ((sy & 0xC0) << 5) | ((sy & 7) << 8) | ((sy & 0x38) << 2) | (sx >> 3)
                    at = self.mem[0x5800 + (sy >> 3) * 32 + (sx >> 3)]
                    bit = self.mem[a] >> (7 - (sx & 7)) & 1
                    br = 8 if at & 0x40 else 0
                    ink, pap = (at & 7) + br, ((at >> 3) & 7) + br
                    if at & 0x80:
                        ink, pap = pap, ink
                    row.append(pal[ink if bit else pap])
                else:
                    row.append(bc)
            row = [c for c in row for _ in range(scale)]
            for _ in range(scale):
                rows.append(row)
        raw = b''.join(b'\0' + bytes(v for c in r for v in c) for r in rows)
        def chunk(t, d):
            c = struct.pack('>I', len(d)) + t + d
            return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        png = (b'\x89PNG\r\n\x1a\n' +
               chunk(b'IHDR', struct.pack('>IIBBBBB', W * scale, H * scale, 8, 2, 0, 0, 0)) +
               chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
        open(fname, 'wb').write(png)

def main():
    zx = ZX(sys.argv[1])
    script = open(sys.argv[2]).read() if len(sys.argv) > 2 else 'wait 200\nscreen\n'
    for line in script.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        cmd, _, arg = line.partition(' ')
        if cmd == 'wait':
            zx.run(int(arg))
        elif cmd == 'type':
            zx.type(arg.encode().decode('unicode_escape'))
        elif cmd == 'key':
            zx.press(arg.split())
        elif cmd == 'screen':
            print('-' * 66)
            print('\n'.join('|' + l for l in zx.screen().splitlines()))
            print('-' * 66, 'frame', zx.frames)
        elif cmd == 'until':
            parts = arg.rsplit(' ', 1)
            if len(parts) == 2 and parts[1].isdigit():
                ok = zx.until(parts[0].encode().decode('unicode_escape'), int(parts[1]))
            else:
                ok = zx.until(arg.encode().decode('unicode_escape'))
            if not ok:
                print('TIMEOUT waiting for %r' % arg)
        elif cmd == 'untilnot':      # run until TEXT is gone (max N)
            t, _, n = arg.rpartition(' ')
            for _ in range(int(n) // 10):
                if t not in zx.screen():
                    break
                zx.run(10)
            else:
                print('TIMEOUT waiting for %r to go' % t)
        elif cmd == 'png':
            zx.png(arg)
        elif cmd == 'tapesave':      # decode what was SAVEd, keep it
            zx.saved = decode_mic(zx.tr.mic)
            print('saved %d tape blocks:' % len(zx.saved),
                  [(len(b), b[:12]) for b in zx.saved])
            zx.tr.mic = []
        elif cmd == 'tapewrite':     # the saved blocks as a .tap file
            open(arg, 'wb').write(b''.join(len(b).to_bytes(2, 'little') + b
                                           for b in zx.saved))
        elif cmd == 'tapeplay':      # play the saved blocks back
            zx.tr.edges = tape_pulses(zx.saved, zx.sim.registers[25] + 3500000)
        elif cmd == 'dump':          # save the 64K memory
            open(arg, 'wb').write(bytes(zx.mem[:65536]))
        elif cmd == 'frames':        # print the frame counter
            print('frame', zx.frames, arg)
        elif cmd == 'pc':
            r = zx.sim.registers
            print('PC=%04X SP=%04X' % (r[24], r[12]))
        else:
            raise SystemExit('bad command ' + cmd)

if __name__ == '__main__':
    main()
