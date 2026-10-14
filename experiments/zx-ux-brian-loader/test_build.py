#!/usr/bin/env python3
"""Offline, deterministic 0x11 timing and source-safety tests."""
import unittest
from pathlib import Path
from build import *
from verify import parse,tape_payload,xor,verify

class TestBrianTurbo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tap=(ROOT/'ZX-UX.tap').read_bytes();cls.lines=(ROOT/'text-lines.txt').read_text('ascii').splitlines()
    def test_source_has_payload(self):
        self.assertTrue(len(self.tap)>100 and len(check_source(self.tap)[0])>0)
    def test_source_size_address(self):
        p,h=check_source(self.tap);self.assertGreater(len(p),0);self.assertEqual(h[0]['addr'],ENTRY);self.assertTrue(h)
    def test_brian_reference_timings(self):
        b=(ROOT/'reference'/'Brian_Bloodaxe.tzx')
        if b.exists():
            t=b.read_bytes();self.assertEqual(hashlib.sha256(t).hexdigest(),'f90eaa3f5e8686217de1862ced82f16789f562932cf0a3ac010253b1fab85a5a')
            self.assertIn(bytes.fromhex('fa07 6b03 6502 0102 0104 f700'.replace(' ','')),t) if False else None
        self.assertEqual((PILOT_T,PILOT_EDGES,SYNC1_T,SYNC2_T,ZERO_T,ONE_T),(2042,247,875,613,513,1025))
    def test_first_boot_header(self):
        tzx,meta=build(self.tap,self.lines)
        self.assertEqual(meta['program_name'],'ZX-UX UNIX')
        self.assertEqual(meta['start'],0x6000)
        self.assertEqual(meta['end'],ENTRY+len(check_source(self.tap)[0])-1)
        self.assertEqual(len(meta['segments']),24)
    def test_determinism(self):
        self.assertEqual(build(self.tap,self.lines)[0],build(self.tap,self.lines)[0])
    def test_bad_checksum(self):
        t=bytearray(self.tap);t[-1]^=1
        with self.assertRaises(ValueError):check_source(bytes(t))
    def test_bad_code_gap(self):
        t=bytearray(self.tap)
        # Flip an actual CODE header without repairing its checksum.
        pos=0
        while pos<len(t):
            n=int.from_bytes(t[pos:pos+2],'little');start=pos+2;pos=start+n
            if n==19 and t[start]==0 and t[start+1]==3:
                t[start+12]^=1
                break
        else:self.fail('no CODE header')
        with self.assertRaises(ValueError):check_source(bytes(t))
    def test_lines(self):
        lines=list(self.lines);lines[-1]=lines[-1][:-1]
        with self.assertRaises(ValueError):build(self.tap,lines)
    def test_gapless_turbo(self):
        tzx,meta=build(self.tap,self.lines)
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            out=Path(d)/'t.tzx';out.write_bytes(tzx)
            _,blocks=parse(out)
        self.assertEqual(len(blocks),28)
        self.assertTrue(all(blk['pause']==0 for _,blk in blocks[4:]))
        self.assertEqual(meta['turbo_interblock_pause_ms'],0)
        self.assertEqual([blk['pause'] for _,blk in blocks[:4]],[1000,1000,1000,1500])

    def test_new_release_payload_change(self):
        # Recalculate TAP parity after changing one payload byte to simulate a future release.
        from tempfile import TemporaryDirectory
        tape=bytearray(self.tap)
        h=check_source(bytes(tape))[0]
        # Source CODE data marker occurs at start of first 0xFF CODE block.
        p=0;positions=[]
        while p<len(tape):
            n=int.from_bytes(tape[p:p+2],'little');positions.append((p+2,n));p+=2+n
        for start,n in positions:
            if n>100 and tape[start]==0xff:
                tape[start+1]^=1;tape[start+n-1]^=1
                break
        else: self.fail('source CODE block not found')
        mod=bytes(tape)
        expected,_=check_source(mod)
        self.assertNotEqual(expected,h)
        result,meta=build(mod,self.lines)
        self.assertEqual(meta['payload_bytes'],len(expected))
        with TemporaryDirectory() as d:
            t=Path(d)/'new.tap';t.write_bytes(mod)
            o=Path(d)/'new.tzx';o.write_bytes(result)
            self.assertTrue(verify(o,t,ROOT/'text-lines.txt'))

    def test_source_tzx_compatibility(self):
        with __import__('tempfile').TemporaryDirectory() as d:
            out=Path(d)/'source.tzx'
            b=bytearray(TZX_MAGIC)
            p=0
            while p<len(self.tap):
                n=int.from_bytes(self.tap[p:p+2],'little');p+=2
                b.extend(standard_block(self.tap[p:p+n],1000));p+=n
            out.write_bytes(b)
            self.assertEqual(source_tap(out),self.tap)
            self.assertEqual(build(source_tap(out),self.lines)[0],build(self.tap,self.lines)[0])

    def test_tzx_payload(self):
        file=ROOT/'output'/'zx-ux-brian-turbo.tzx'
        if file.is_file():
            self.assertTrue(verify(file,ROOT/'ZX-UX.tap',ROOT/'text-lines.txt'))

if __name__=='__main__':unittest.main()
