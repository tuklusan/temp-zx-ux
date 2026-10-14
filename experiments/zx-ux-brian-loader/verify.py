#!/usr/bin/env python3
"""Independent static verifier for ZX-UX Brian-timed compact TZX outputs."""
from __future__ import annotations
import argparse,hashlib,struct
from pathlib import Path

def parse(path):
    b=Path(path).read_bytes()
    assert b[:8]==b'ZXTape!\x1a', 'TZX magic'
    pos=10;blocks=[]
    while pos<len(b):
        typ=b[pos];pos+=1
        if typ==0x10:
            pause,n=struct.unpack_from('<HH',b,pos);pos+=4
            raw=b[pos:pos+n];pos+=n;blocks.append((typ,{'pause':pause,'raw':raw}))
        elif typ==0x11:
            timing=struct.unpack_from('<6H',b,pos);bits=b[pos+12];pause=struct.unpack_from('<H',b,pos+13)[0];n=int.from_bytes(b[pos+15:pos+18],'little');pos+=18
            raw=b[pos:pos+n];pos+=n
            assert len(raw)==n,'truncated turbo data'
            blocks.append((typ,{'timing':timing,'bits':bits,'pause':pause,'raw':raw}))
        else:raise AssertionError(f'unexpected TZX block 0x{typ:02x}')
    assert pos==len(b)
    return b,blocks

def tape_payload(path):
    from build import source_tap
    tape=source_tap(Path(path));out=b'';p=0;CODE=[]
    while p<len(tape):
        n=int.from_bytes(tape[p:p+2],'little');p+=2;h=tape[p:p+n];p+=n
        n=int.from_bytes(tape[p:p+2],'little');p+=2;d=tape[p:p+n];p+=n
        assert (len(h),h[0])==(19,0)
        assert xor(h)==0 and xor(d)==0
        if h[1]==3:
            ln,start=struct.unpack_from('<HH',h,12)
            assert d[0]==0xff and len(d)==ln+2
            CODE.append((start,d[1:-1]));out+=d[1:-1]
    assert p==len(tape)
    assert CODE and CODE[0][0]==0x6000
    assert all(CODE[i][0]==CODE[i-1][0]+len(CODE[i-1][1]) for i in range(1,len(CODE)))
    return out

def xor(raw):
    v=0
    for byte in raw:v^=byte
    return v

def verify(tzx,tap,text):
    b,blocks=parse(tzx)
    assert len(blocks)==28 and [i for i,_ in blocks]==[0x10]*4+[0x11]*24
    for i,(_,blk) in enumerate(blocks[:4]):
        assert xor(blk['raw'])==0
    assert blocks[0][1]['raw'][2:12]==b'ZX-UX UNIX'
    assert blocks[2][1]['raw'][2:12]==b'ZX-UX BOOT'
    assert blocks[2][1]['raw'][14:16]==b'\x00\xd0'
    loader=blocks[3][1]['raw'][1:-1]
    assert len(loader)>1000
    line_bytes=''.join(Path(text).read_text('ascii').splitlines()).encode('ascii')
    assert len(line_bytes)==768 and line_bytes in loader
    sizes=[];data=[]
    for typ,blk in blocks[4:]:
        assert blk['timing']==(2042,875,613,513,1025,247)
        assert blk['bits']==8
        assert xor(blk['raw'])==0
        sizes.append(len(blk['raw'])-1)
        data.extend(blk['raw'][:-1])
    original=tape_payload(tap)
    assert bytes(data)==original, 'payload differs from source TAP'
    assert sum(sizes)==len(original) and max(sizes)-min(sizes)<=1
    assert all(blk['pause']==0 for _,blk in blocks[4:]), 'unexpected turbo inter-block silence'
    digest=hashlib.sha256(b).hexdigest()
    print(f'PASS: {len(b)} TZX bytes; {len(original)} payload bytes; 24 turbo blocks; SHA256={digest}')
    return digest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tzx',type=Path,default=Path(__file__).with_name('output')/'zx-ux-brian-turbo.tzx')
    parser.add_argument('--tap',type=Path,default=Path(__file__).with_name('ZX-UX.tap'))
    parser.add_argument('--text',type=Path,default=Path(__file__).with_name('text-lines.txt'))
    args=parser.parse_args();verify(args.tzx,args.tap,args.text)
