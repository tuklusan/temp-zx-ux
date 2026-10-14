#!/usr/bin/env python3
"""Independent ZX-UX 24-line TZX structural and source-data verifier."""
import argparse
from pathlib import Path
import struct
import hashlib

def tap_blocks(raw):
    p=0;out=[]
    while p<len(raw):
        n=struct.unpack_from('<H',raw,p)[0];p+=2
        b=raw[p:p+n];p+=n
        assert len(b)==n and n>=2 and (sum([]) if False else True)
        x=0
        for v in b:x^=v
        assert x==0
        out.append(b)
    assert p==len(raw)
    return out

def zq_crc(blob):
    a=1
    for x in blob:
        a=(a+x)&255
        a=((a<<1)|(a>>7))&255
    return a

def generalized(buf,p):
    assert buf[p]==0x19
    size=struct.unpack_from('<I',buf,p+1)[0];p+=5
    end=p+size
    pause,totp,npp,asp,totd,npd,asd=struct.unpack_from('<HIBBIBB',buf,p);p+=14
    assert pause==0 and npd==1 and asd==2 and totd%8==0
    pilots=[]
    for _ in range(asp):
        edge=buf[p];p+=1
        seq=struct.unpack_from('<'+'H'*npp,buf,p);p+=2*npp
        pilots.append((edge,seq))
    reps=[]
    for _ in range(totp):
        idx,rep=struct.unpack_from('<BH',buf,p);p+=3
        reps.append((idx,rep))
    data_alphabet=[]
    for _ in range(asd):
        edge,pulse=struct.unpack_from('<BH',buf,p);p+=3
        data_alphabet.append((edge,pulse))
    assert data_alphabet==[(0,1140),(0,2280)]
    raw=buf[p:p+(totd//8)];p+=len(raw)
    assert p==end
    return p,raw,pilots,reps

def check(tzx,source,lines):
    assert tzx.startswith(b'ZXTape!\\x1a\\x01\\x14'.decode('unicode_escape').encode('latin1')) if False else tzx[:10]==b'ZXTape!\x1a\x01\x14'
    p=10;rom=[];turbo=[];pauses=0
    while p<len(tzx):
        bid=tzx[p]
        if bid==0x10:
            ms,n=struct.unpack_from('<HH',tzx,p+1);p+=5
            rom.append(tzx[p:p+n]);p+=n
        elif bid==0x19:
            p,data,pilots,reps=generalized(tzx,p)
            turbo.append((data,pilots,reps))
        elif bid==0x20:
            pauses+=1;p+=3
        else:raise AssertionError(f'Unexpected TZX block {bid:#x}')
    assert p==len(tzx) and len(rom)==2 and len(turbo)==50 and pauses==24
    assert rom[0][2:12]==b'ZX-UX UNIX'
    assert rom[1][0x38]==0x08 and rom[1][0x3a]==0x41
    assert rom[1][288:292]==bytes.fromhex('79ee004f')
    text=''.join(lines).encode('ascii')
    assert len(lines)==24 and len(text)==768
    assert turbo[1][0].endswith(text) and len(turbo[1][0])==891
    chunks=[];nextaddr=0x6000
    for i in range(25):
        hdr,pilots,reps=turbo[2*i]
        data=turbo[2*i+1][0]
        assert len(hdr)==17
        n,load,dest,typ,crc,after,*_=struct.unpack('<HHHBBHHBHBB',hdr)
        assert n==len(data) and crc==zq_crc(data) and dest==0 and typ==0
        assert pilots==[(0,(450,450)),(0,(250,499))]
        assert reps==[(0,800),(1,1)]
        if i==0:
            assert load==0xc100 and after==0xc100
        else:
            assert load==nextaddr and after==0xc127
            nextaddr+=len(data);chunks.append(data)
    source_blocks=tap_blocks(source)
    original=b''.join(source_blocks[j][1:-1] for j in range(1,len(source_blocks),2)
                      if source_blocks[j-1][1]==3)
    assembled=b''.join(chunks)
    assert assembled==original and nextaddr==0xc05e and len(assembled)==24670
    print('PASS: ZX-UX UNIX, black/blue, 24 status rows, 24 payload chunks, exact source bytes')
    print('TZX SHA-256',hashlib.sha256(tzx).hexdigest(),'size',len(tzx))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tzx',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--text-lines',type=Path,required=True)
    opt=parser.parse_args()
    check(opt.tzx.read_bytes(),opt.source.read_bytes(),opt.text_lines.read_text('ascii').splitlines())
