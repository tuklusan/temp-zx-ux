#!/usr/bin/env python3
"""ZX-UX 48K: independent Brian Bloodaxe-timed 0x11 turbo tape builder.

No ZQLoader dependency, no third-party libraries, no external assembler.
The 48K ROM provides standard CODE bootstrap loading and the documented
LD-EDGE-1/2 pulse samplers at 0x05E7/0x05E3, as in the Brian tape.
"""
from __future__ import annotations
import argparse,hashlib,json,struct,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ENTRY=0x6000
LOADER_ADDR=0xD000
STACK_ADDR=0xCEFF  # above exact ZX-UX CODE payload; below loader
ROWS=24
COLS=32
PILOT_T=2042       # Brian Bloodaxe second 0x11 data block
PILOT_EDGES=247    # Brian Bloodaxe short leader
SYNC1_T=875
SYNC2_T=613
ZERO_T=513         # each bit consists of two equal-length half-pulses
ONE_T=1025
PAUSE_MS=0  # continuous turbo segments; zero pause in TZX 0x11 does not stop the tape
PROG_NAME=b'ZX-UX UNIX'   # exactly 10 bytes, replaces ZQLOADER
LOAD_CODE_NAME=b'ZX-UX BOOT'  # exactly 10 bytes
TZX_MAGIC=b'ZXTape!\x1a\x01\x14'

class AssembleError(ValueError):pass
class A:
    def __init__(self,addr=LOADER_ADDR):
        self.origin=addr;self.data=bytearray();self.labels={};self.fixups=[]
    @property
    def pc(self):return self.origin+len(self.data)
    def mark(self,name):
        if name in self.labels:raise AssembleError('duplicate '+name)
        self.labels[name]=self.pc
    def b(self,*vals):
        for v in vals:
            if not 0<=v<=255:raise AssembleError(f'bad byte {v}')
            self.data.append(v)
    def w(self,v):self.data.extend(struct.pack('<H',v))
    def addr(self,name):self.fixups.append((len(self.data),name,'abs'));self.w(0)
    def rel(self,name):self.fixups.append((len(self.data),name,'rel'));self.b(0)
    def jp(self,name,op=0xc3):self.b(op);self.addr(name)
    def jr(self,name,op=0x18):self.b(op);self.rel(name)
    def call(self,name):self.jp(name,0xcd)
    def ldhl(self,name):self.b(0x21);self.addr(name)
    def ldaddr_hl(self,name):self.b(0x22);self.addr(name)
    def ldhl_addr(self,name):self.b(0x2a);self.addr(name)
    def lda_addr(self,name):self.b(0x3a);self.addr(name)
    def ldaddr_a(self,name):self.b(0x32);self.addr(name)
    def done(self):
        for i,name,typ in self.fixups:
            if name not in self.labels:raise AssembleError('undefined label '+name)
            target=self.labels[name]
            if typ=='abs':struct.pack_into('<H',self.data,i,target)
            else:
                displacement=target-(self.origin+i+1)
                if not -128<=displacement<=127:raise AssembleError(f'JR {name} distance {displacement} out of range')
                self.data[i]=displacement&255
        return bytes(self.data)

def xor8(data):
    x=0
    for v in data:x^=v
    return x

def tape_block(flag,payload):
    raw=bytes([flag])+payload
    return raw+bytes([xor8(raw)])

def rom_header(kind,name,size,param1,param2):
    if len(name)!=10:raise ValueError('name must contain exactly ten bytes')
    return tape_block(0,bytes([kind])+name+struct.pack('<HHH',size,param1,param2))

def standard_block(raw,pause):
    assert len(raw)<=65535
    return b'\x10'+struct.pack('<HH',pause,len(raw))+raw

def turbo_block(raw,pause):
    assert 1<=len(raw)<=0xffffff
    # TZX block ID 0x11: six 16-bit pulse/pilot values, used-bits byte,
    # pause 16-bit ms, 24-bit byte count, then raw bytes.
    return (b'\x11'+struct.pack('<6H',PILOT_T,SYNC1_T,SYNC2_T,ZERO_T,ONE_T,PILOT_EDGES)
      +bytes([8])+struct.pack('<H',pause)+len(raw).to_bytes(3,'little')+raw)

def spectrum_int(n):
    if not 0<=n<=65535:raise ValueError(n)
    return str(n).encode('ascii')+b'\x0e\x00\x00'+struct.pack('<H',n)+b'\x00'

def basic_program():
    # 10 CLEAR 52991: LOAD "" CODE: RANDOMIZE USR 53248
    # Lexical numbers carry their 5-byte Spectrum numeric representations.
    body=(b'\xfd '+spectrum_int(STACK_ADDR)
      +b':\xef "" \xaf'
      +b':\xf9 \xc0 '+spectrum_int(LOADER_ADDR)+b'\x0d')
    line=struct.pack('>H',10)+struct.pack('<H',len(body))+body
    return line

def source_tap(path:Path)->bytes:
    """Read source Spectrum .tap or standard-speed .tzx as validated TAP records.

    TZX input must contain only standard-speed data (0x10) blocks; rejecting
    unsupported recording modes prevents silently discarding kernel bytes.
    """
    src=path.read_bytes()
    if src[:8]!=b'ZXTape!\x1a':
        return src
    if len(src)<10:raise ValueError('truncated TZX header')
    pos=10
    tape=bytearray()
    while pos<len(src):
        kind=src[pos];pos+=1
        if kind!=0x10:
            raise ValueError(f'source TZX block 0x{kind:02x} unsupported; provide standard-speed TZX or TAP')
        if pos+4>len(src):raise ValueError('truncated TZX standard header')
        _pause,n=struct.unpack_from('<HH',src,pos);pos+=4
        if n<2 or pos+n>len(src):raise ValueError('truncated TZX data block')
        raw=src[pos:pos+n];pos+=n
        if xor8(raw):raise ValueError('bad source TZX checksum')
        tape.extend(struct.pack('<H',n));tape.extend(raw)
    return bytes(tape)

def check_source(tape:bytes):
    blocks=[];p=0
    while p<len(tape):
        if p+2>len(tape):raise ValueError('truncated TAP length')
        n=struct.unpack_from('<H',tape,p)[0];p+=2
        if n<2 or p+n>len(tape):raise ValueError('invalid TAP block length')
        raw=tape[p:p+n];p+=n
        if xor8(raw):raise ValueError('bad TAP checksum')
        blocks.append(raw)
    if len(blocks)%2:raise ValueError('odd header/data TAP blocks')
    combined=bytearray();info=[]
    for i in range(0,len(blocks),2):
        h,d=blocks[i:i+2]
        if len(h)!=19 or h[0]!=0:raise ValueError('expected Spectrum header')
        if h[1]!=3:continue  # ignore source BASIC autorun, load original CODE only
        n,start,_=struct.unpack_from('<HHH',h,12)
        if d[0]!=0xff or len(d)!=n+2:raise ValueError('CODE data/header length mismatch')
        wanted=ENTRY+len(combined)
        if start!=wanted:raise ValueError(f'noncontiguous CODE address 0x{start:04x} expected 0x{wanted:04x}')
        combined.extend(d[1:-1]);info.append({'addr':start,'size':n,'name':h[2:12].decode('ascii')})
    if not combined or ENTRY+len(combined)>STACK_ADDR-256:
        raise ValueError('payload overlaps reserved stack region')
    return bytes(combined),info

def build_machine_code(lines,sizes):
    if len(lines)!=ROWS or len(sizes)!=ROWS:raise ValueError('require 24 lines and segment sizes')
    for i,line in enumerate(lines,1):
        if len(line)!=COLS or not all(32<=ord(c)<=126 for c in line):
            raise ValueError(f'line {i} must be 32 ASCII columns')
    a=A()
    a.mark('start')
    a.b(0xf3)                    # DI
    a.b(0x31);a.w(STACK_ADDR)    # LD SP,CEFF safe while loading 0x6000-C0E1
    # Clear screen bitmap and attributes (white ink / black paper).
    a.b(0x21);a.w(0x4000)        # LD HL,4000
    a.b(0x11);a.w(0x4001)        # LD DE,4001
    a.b(0x01);a.w(0x17ff)       # LD BC,17FF
    a.b(0xaf,0x77,0xed,0xb0)    # XOR A; LD (HL),A; LDIR
    a.b(0x21);a.w(0x5800)
    a.b(0x11);a.w(0x5801)
    a.b(0x01);a.w(0x02ff)
    a.b(0x36,0x07,0xed,0xb0)    # LD (HL),7; LDIR
    a.b(0xaf);a.ldaddr_a('row') # row = 0
    a.ldhl('text');a.ldaddr_hl('text_cursor')
    a.b(0x21);a.w(ENTRY);a.ldaddr_hl('dest')
    a.ldhl('sizes');a.ldaddr_hl('size_cursor')
    a.mark('loop')
    a.lda_addr('row');a.b(0xfe,ROWS);a.jp('final',0xca) # CP 24; JP Z
    # Read segment length from size table (two bytes) and save cursor.
    a.ldhl_addr('size_cursor')
    a.b(0x5e,0x23,0x56,0x23)    # LD E,(HL); INC HL;LD D,(HL);INC HL
    a.ldaddr_hl('size_cursor')
    a.ldhl_addr('dest')
    a.b(0xe5,0xdd,0xe1)         # PUSH HL;POP IX
    a.b(0x19)                   # ADD HL,DE
    a.ldaddr_hl('dest')
    a.call('read_turbo')
    a.jp('error',0xc2)          # JP NZ error (XOR parity or pulse failure)
    a.call('print_row')
    a.jp('loop')
    a.mark('final')
    # Wait 1 video frame for physical row 23 to be visible.
    a.b(0xfb,0x76)              # EI; HALT
    a.b(0x11);a.w(250)          # LD DE,250   ~=1000Hz x 250ms
    a.b(0x21);a.w(407)          # LD HL,407 for BEEPER
    a.mark('beep_call')
    a.b(0xcd);a.w(0x03b5)       # CALL ROM BEEPER, once
    a.b(0xfb)                  # EI: ensure frame HALTs receive interrupts
    a.b(0x06,25)                # LD B,25; 500 ms dwell at 50Hz
    a.mark('hold_final')
    a.b(0x76,0x10);a.rel('hold_final') # HALT; DJNZ
    a.mark('jump_kernel')
    a.b(0xc3);a.w(ENTRY)        # JP 0x6000
    a.mark('error')
    a.b(0x3e,0x02,0xd3,0xfe)    # red border on error
    a.mark('error_halt')
    a.b(0x76);a.jp('error_halt')

    # Nearly exact edge timings and pilot/sync decoder from supplied Brian
    # Bloodaxe BASIC-contained loader (resident code originally at FF19-FF8B).
    # Relocated to D000 with separate memory addressing / progress UI.
    # ROM sampler at 05E3/05E7 is called unchanged to preserve pulse timing.
    a.mark('read_turbo')
    a.b(0xf3,0x3e,0x0f,0xd3,0xfe,0xdb,0xfe,0x1f,0xe6,0x20,0xf6,0x02,0x4f,0xbf)
    a.mark('find_first_edge')
    a.b(0xcd);a.w(0x05e7)
    a.jr('find_first_edge',0x30)
    a.b(0x2e,0x18)              # LD L,24: warmup delay
    a.mark('warmup_spin')
    a.b(0x10);a.rel('warmup_spin') # DJNZ
    a.b(0x2d);a.jr('warmup_spin',0x20)
    a.b(0xcd);a.w(0x05e3)
    a.jr('find_first_edge',0x30)
    a.b(0x26,0xc4,0x2e,0x00)   # LD H,0xC4 ; LD L,0
    a.mark('pilot')
    a.b(0x06,0x9c,0xcd);a.w(0x05e3)
    a.jr('find_first_edge',0x30)
    a.b(0x3e,0xc6,0xb8)
    a.jr('find_first_edge',0x30)
    a.b(0x24);a.jr('pilot',0x20)
    a.mark('sync')
    a.b(0x06,0xc9,0xcd);a.w(0x05e7)
    a.jr('find_first_edge',0x30)
    a.b(0x78,0xfe,0xd4);a.jr('sync',0x30)
    a.b(0xcd);a.w(0x05e7)
    a.jr('read_fail',0x30)
    a.b(0x79,0xee,0x05,0x4f,0x26,0x00,0x06,0xb0)
    a.jr('next_byte')
    a.mark('store')
    a.b(0xdd,0x75,0x00,0xdd,0x23,0x1b,0x06,0xb2) # LD(IX),L; INC IX; DEC DE
    a.mark('next_byte')
    a.b(0x2e,0x01)               # LD L,1 sentinel
    a.mark('next_bit')
    a.b(0xcd);a.w(0x05e3)       # ROM twin half-pulse edge sampler
    a.jr('read_fail',0x30)
    a.b(0x3e,0xbd,0xb8,0xcb,0x15,0x06,0xb0) # CP B ; RL L; LD B,B0
    a.jp('next_bit',0xd2)       # JP NC, until 8 bits done
    a.b(0x7c,0xad,0x67,0x7a,0xb3)
    a.jr('store',0x20)
    a.b(0x7c,0xb7,0xc9)         # LD A,H;OR A; RET Z if xor checksum matched
    a.mark('read_fail')
    a.b(0x3e,0x01,0xb7,0xc9)   # LD A,1;OR A;RET (NZ)

    # Print one fixed 32-column string to the physical screen row, including
    # rows 22-23 that ROM PRINT will never render in the main 22-line window.
    a.mark('print_row')
    a.lda_addr('row');a.b(0x4f,0x3c);a.ldaddr_a('row')
    a.b(0x79,0xe6,0x18,0xf6,0x40,0x57)
    a.b(0x79,0xe6,0x07,0x87,0x87,0x87,0x87,0x87,0x5f)
    a.ldhl_addr('text_cursor');a.b(0x0e,COLS)
    a.mark('glyph_char')
    a.b(0x7e,0x23,0xe5,0xc5,0xd6,0x20,0x6f,0x26,0x00)
    a.b(0x29,0x29,0x29,0x01);a.w(0x3d00);a.b(0x09,0x06,0x08)
    a.mark('glyph_scan')
    a.b(0x7e,0x12,0x23,0x14,0x10);a.rel('glyph_scan')
    a.b(0x7a,0xd6,0x08,0x57,0x1c,0xc1,0xe1,0x0d,0x20);a.rel('glyph_char')
    a.ldaddr_hl('text_cursor');a.b(0xc9)
    # Pinned data inside CODE block (no additional turbo installer required).
    a.mark('row');a.b(0)
    a.mark('text_cursor');a.w(0)
    a.mark('dest');a.w(ENTRY)
    a.mark('size_cursor');a.w(0)
    a.mark('sizes')
    for n in sizes:a.w(n)
    a.mark('text');a.data.extend(''.join(lines).encode('ascii'))
    data=a.done()
    if LOADER_ADDR+len(data)>=0xf000:raise ValueError('machine code too big')
    return data,a.labels

def build(tap:bytes, lines:list[str]):
    payload,source_segments=check_source(tap)
    base,extra=divmod(len(payload),ROWS)
    sizes=[base+(i<extra) for i in range(ROWS)]
    machine,labels=build_machine_code(lines,sizes)
    prog=basic_program()
    tzx=bytearray(TZX_MAGIC)
    tzx.extend(standard_block(rom_header(0,PROG_NAME,len(prog),10,len(prog)),1000))
    tzx.extend(standard_block(tape_block(0xff,prog),1000))
    tzx.extend(standard_block(rom_header(3,LOAD_CODE_NAME,len(machine),LOADER_ADDR,32768),1000))
    tzx.extend(standard_block(tape_block(0xff,machine),1500))
    cursor=0;segments=[]
    for i,n in enumerate(sizes):
        data=payload[cursor:cursor+n]
        raw=data+bytes([xor8(data)])
        pause=PAUSE_MS
        tzx.extend(turbo_block(raw,pause))
        segments.append({'block':i+1,'address':ENTRY+cursor,'bytes':n,'xor':raw[-1], 'pause_ms':pause})
        cursor+=n
    meta={'source_tap_sha256':hashlib.sha256(tap).hexdigest(),
        'payload_sha256':hashlib.sha256(payload).hexdigest(),
        'payload_bytes':len(payload),'source_code_blocks':source_segments,
        'start':ENTRY,'end':ENTRY+len(payload)-1,'entry':ENTRY,
        'program_name':PROG_NAME.decode(),'loader_address':LOADER_ADDR,
        'loader_bytes':len(machine),'labels':labels,
        'turbo':{'block':'0x11','pilot':PILOT_T,'pilot_edges':PILOT_EDGES,
          'sync_1':SYNC1_T,'sync_2':SYNC2_T,'zero_half':ZERO_T,'one_half':ONE_T,
          'data_bit_speed_multiplier_vs_ROM':round(855/ZERO_T,3)},
        'turbo_interblock_pause_ms':PAUSE_MS,'segments':segments,'tzx_bytes':len(tzx),'tzx_sha256':hashlib.sha256(tzx).hexdigest(),
        'beep':'one ROM 0x03B5 BEEPER call, DE=250 HL=407, then 25x 50Hz HALT'}
    return bytes(tzx),meta

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'ZX-UX.tap')
    parser.add_argument('--text',type=Path,default=ROOT/'text-lines.txt')
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'zx-ux-brian-turbo.tzx')
    args=parser.parse_args()
    data,meta=build(source_tap(args.source),args.text.read_text('ascii').splitlines())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(data)
    args.output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    zipout=args.output.with_suffix('.tzx.zip')
    with zipfile.ZipFile(zipout,'w') as z:
        zi=zipfile.ZipInfo(args.output.name,date_time=(2026,10,14,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(zi,data)
    print(json.dumps({'tzx':str(args.output),'zip':str(zipout),'sha256':meta['tzx_sha256'],
      'size':len(data),'payload_bytes':meta['payload_bytes'],'loader_bytes':meta['loader_bytes'],
      'start':hex(meta['start']),'end':hex(meta['end'])},indent=2))
if __name__=='__main__':main()
