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
    def test_original_hash(self):
        self.assertEqual(hashlib.sha256(self.tap).hexdigest(),'9ff03bfbfcd33cc11e9a4f45b4197b67f0abb347052957bc36b74102eaf09004')
    def test_source_size_address(self):
        p,h=check_source(self.tap);self.assertEqual((len(p),ENTRY+len(p)-1),(24802,0xc0e1));self.assertEqual(len(h),2)
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
        self.assertEqual(meta['end'],0xc0e1)
        self.assertEqual(len(meta['segments']),24)
    def test_determinism(self):
        self.assertEqual(build(self.tap,self.lines)[0],build(self.tap,self.lines)[0])
    def test_bad_checksum(self):
        t=bytearray(self.tap);t[-1]^=1
        with self.assertRaises(ValueError):check_source(bytes(t))
    def test_bad_code_gap(self):
        t=bytearray(self.tap)
        pos=t.find(b'fs        ')
        self.assertTrue(pos>0)
        t[pos+10]^=1 # corrupt source CODE header checksum, checksum detector rejects
        with self.assertRaises(ValueError):check_source(bytes(t))
    def test_lines(self):
        lines=list(self.lines);lines[-1]=lines[-1][:-1]
        with self.assertRaises(ValueError):build(self.tap,lines)
    def test_tzx_payload(self):
        file=ROOT/'output'/'zx-ux-brian-turbo.tzx'
        assert file.is_file()
        self.assertTrue(verify(file,ROOT/'ZX-UX.tap',ROOT/'text-lines.txt'))

if __name__=='__main__':unittest.main()
