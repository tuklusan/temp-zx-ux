#!/usr/bin/env python3
"""Assemble 48K ZX Spectrum 24-row turbo progress display with no external toolchain.

The first turbo segment installs this resident helper above the source payload.
The helper writes all 24x32 cells directly, including rows 22/23 which ROM
PRINT cannot reach. Turbo decoding continues at pinned ZQLoader 0x5CFA.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct

HOOK_BASE = 0xC100
NEXT_BLOCK = 0x5CFA
ROWS = 24
COLS = 32

class Assembler:
    def __init__(self, origin: int):
        self.origin=origin
        self.data=bytearray()
        self.labels={}
        self.fixups=[]
    @property
    def pc(self):return self.origin+len(self.data)
    def mark(self,name):
        if name in self.labels:raise ValueError(f'duplicate label {name}')
        self.labels[name]=self.pc
    def emit(self,*bytes_):
        for val in bytes_:
            if not 0<=val<=255:raise ValueError(val)
            self.data.append(val)
    def word(self,val):self.data.extend(struct.pack('<H',val))
    def absolute(self,name):self.fixups.append((len(self.data),name,'abs'));self.word(0)
    def relative(self,name):self.fixups.append((len(self.data),name,'rel'));self.emit(0)
    def ld_hl(self,name):self.emit(0x21);self.absolute(name)
    def jp(self,name,opcode=0xC3):self.emit(opcode);self.absolute(name)
    def finalize(self):
        for pos,name,typ in self.fixups:
            value=self.labels[name]
            if typ=='abs':struct.pack_into('<H',self.data,pos,value)
            else:
                relative=value-(self.origin+pos+1)
                if not -128<=relative<=127:raise ValueError(f'JR {name}: {relative} out of range')
                self.data[pos]=relative & 255
        return bytes(self.data)

@dataclass(frozen=True)
class DisplayHook:
    load_address: int
    initializer: int
    progress_callback: int
    data: bytes
    line_addresses: tuple[int, ...]


def build_display_hook(lines: list[str], *, base: int=HOOK_BASE, entry: int=0x6000):
    if len(lines)!=ROWS:raise ValueError(f'exactly {ROWS} progress lines required')
    for i,line in enumerate(lines,1):
        if len(line)!=COLS or any(ord(ch)<32 or ord(ch)>126 for ch in line):
            raise ValueError(f'progress line {i} must be exactly {COLS} printable ASCII bytes')
    a=Assembler(base)
    # Init executes only once after the display-program turbo block, before
    # loading any of the 24 real source payload blocks.
    a.mark('init')
    a.emit(0x21,0x00,0x40)  # LD HL,4000 (bitmap)
    a.emit(0x11,0x01,0x40)  # LD DE,4001
    a.emit(0x01,0xFF,0x17)  # LD BC,17FF
    a.emit(0xAF,0x77,0xED,0xB0) # XOR A; LD (HL),A; LDIR
    a.emit(0x21,0x00,0x58)  # LD HL,5800 (attributes)
    a.emit(0x11,0x01,0x58)  # LD DE,5801
    a.emit(0x01,0xFF,0x02)  # LD BC,02FF
    a.emit(0x36,0x07,0xED,0xB0) # white ink, black paper; LDIR
    a.emit(0xAF,0x32);a.absolute('row')  # XOR A; LD(row),A
    a.ld_hl('text')
    a.emit(0x22);a.absolute('pointer')  # LD(pointer),HL
    a.emit(0xC3);a.word(NEXT_BLOCK)
    # Each completed payload segment jumps here. Rendering 32 glyphs is
    # substantially shorter than the 206ms following pilot, allowing resync.
    a.mark('progress')
    a.emit(0x3A);a.absolute('row') # LD A,(row)
    a.emit(0xFE,ROWS)            # CP 24
    a.emit(0xD2);a.word(entry)   # JP NC,entry, safety for overflow
    a.emit(0x4F,0x3C,0x32);a.absolute('row') # LD C,A ; INC A ; LD (row),A
    a.emit(0x79,0xE6,0x18,0xF6,0x40,0x57) # D = 40h | (row&18h)
    a.emit(0x79,0xE6,0x07)     # A=row&7
    a.emit(0x87,0x87,0x87,0x87,0x87,0x5F) # E=A<<5
    a.emit(0x2A);a.absolute('pointer') # LD HL,(pointer)
    a.emit(0x0E,COLS)          # LD C,32
    a.mark('character')
    a.emit(0x7E,0x23,0xE5,0xC5) # LD A,(HL); INC HL; PUSH HL; PUSH BC
    a.emit(0xD6,0x20,0x6F,0x26,0x00) # CHAR-32 -> L ; H=0
    a.emit(0x29,0x29,0x29)      # 8x glyph offset
    a.emit(0x01,0x00,0x3D,0x09) # BC=ROM_FONT; ADD HL,BC
    a.emit(0x06,0x08)           # B=8 scans
    a.mark('glyph')
    a.emit(0x7E,0x12,0x23,0x14) # LD A,(HL);LD(DE),A;INC HL;INC D
    a.emit(0x10);a.relative('glyph')
    a.emit(0x7A,0xD6,0x08,0x57,0x1C) # restore D; INC E (next column)
    a.emit(0xC1,0xE1,0x0D)      # restore BC and HL, DEC C
    a.emit(0x20);a.relative('character')
    a.emit(0x22);a.absolute('pointer') # next 32 bytes
    a.emit(0x3A);a.absolute('row')
    a.emit(0xFE,ROWS)
    a.emit(0xCA);a.word(entry)   # last row -> exact handoff
    a.emit(0xC3);a.word(NEXT_BLOCK)
    a.mark('row')
    a.emit(0)
    a.mark('pointer')
    a.word(0)
    a.mark('text')
    line_addresses=tuple(a.pc+i*COLS for i in range(ROWS))
    a.data.extend(''.join(lines).encode('ascii'))
    data=a.finalize()
    if base+len(data)>0xFF47:raise ValueError('display hook collides with upper ZQLoader')
    # Source overlap is checked against the actual payload size by build.py.
    return DisplayHook(base,a.labels['init'],a.labels['progress'],data,line_addresses)

if __name__=='__main__':
    from pathlib import Path
    x=build_display_hook(Path(__file__).with_name('text-lines.txt').read_text().splitlines())
    print(hex(x.initializer),hex(x.progress_callback),len(x.data),hex(x.load_address+len(x.data)-1))
