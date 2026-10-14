#!/usr/bin/env python3
"""rtap --list: every kind of block a ZX-UX tape can hold, and the bad ones.

  python3 sdk/tests/test_rtap.py

The tar blocks are built here from the format in src/t_tar.asm (header
"label"/"basename", CODE, p1 = kind A/F/E, p2 "RU"; a member's data is an
11-byte preamble - kind, i-node flags, size, stored bytes, mtime - then
the path, a 0 and the bytes, in blocks of up to 512, a 17-byte block sent
as 18).  tests/suite.py tap_t_whole_tape compares rtap --list with ZX-UX's
own listing of a tape that ZX-UX's tar wrote.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(HERE)
sys.path.insert(0, SDK)
import rtap  # noqa: E402

FAILS = []


def check(what, cond):
    print('%s %s' % ('PASS' if cond else 'FAIL', what))
    if not cond:
        FAILS.append(what)


def header(kind, name, length, p1, p2):
    return rtap.tap_block(0, bytes([kind]) + name.encode().ljust(10) +
                          struct.pack('<HH', length, p1) + p2)


def tar_header(kind, name, length):
    return rtap.tap_block(0, bytes([3]) + name.encode().ljust(10) +
                          struct.pack('<H', length) + bytes([ord(kind), 0x80]) + b'RU')


def member(path, data, kind=0, size=None):
    pre = bytes([kind]) + struct.pack('<HHH', 0x8F, len(data) if size is None else size,
                                      len(data)) + bytes(4)
    body = pre + path.encode() + b'\0' + data
    blocks = [tar_header('F', path.rsplit('/', 1)[-1] or '/', len(body))]
    for p in range(0, len(body), 512):
        piece = body[p:p + 512]
        if len(piece) == 17:
            piece += b'\0'                    # 17 bytes travel as 18
        blocks.append(rtap.tap_block(0xFF, piece))
    return blocks


def main():
    ssx_path = os.path.join(tempfile.mkdtemp(), 'h.ssx')
    from rcc import driver
    src = os.path.join(SDK, '..', 'programs', 'c48', 'examples', 'hello.c')
    if driver.main([src, '-o', ssx_path]):
        raise SystemExit('rcc failed')
    ssx = open(ssx_path, 'rb').read()
    prog = rtap.records(ssx, 'hello')
    arch = ([tar_header('A', 'demo', 0)] + member('/tmp/t', b'', kind=2) +
            member('/tmp/t/one', b'one\n') + member('/abcd', b'') +
            member('/big', bytes(range(256)) * 3) + member('/p', b'z' * 40, kind=1, size=99) +
            [tar_header('E', '', 0)])
    basic = [header(0, 'ZX-UX', 3, 10, b'\x03\x00'), rtap.tap_block(0xFF, b'abc')]
    code = [header(3, 'unix', 2, 24576, b'\x00\x80'), rtap.tap_block(0xFF, b'xy')]
    arrays = [header(1, 'nums', 1, 0, b'\0\0'), rtap.tap_block(0xFF, b'n'),
              header(2, 'chrs', 1, 0, b'\0\0'), rtap.tap_block(0xFF, b'c')]
    lines = rtap.list_blocks(prog + arch + basic + code + arrays)
    want = ['program  /dev/cassette/hello  %d bytes, needs %d' % (len(ssx), rtap.need(ssx)),
            'archive  /dev/cassette/demo:',
            '  d      0 /tmp/t',
            '  -      4 /tmp/t/one',
            '  -      0 /abcd',
            '  -    768 /big',
            '  z     99 /p',
            '         end of archive',
            'basic    "ZX-UX"  3 bytes LINE 10',
            'code     "unix"  2 bytes at 24576',
            'numbers  "nums"  1 bytes',
            'chars    "chrs"  1 bytes']
    check('every kind of block is listed as tar tv and the ROM would name it', lines == want)
    if lines != want:
        print('\n'.join(lines))
    # preamble (11) + "/abcd" + 0 (6) = 17 bytes, sent as 18 (flag and
    # parity make the block 20)
    blk = member('/abcd', b'')[1]
    check('a 17-byte member travels as an 18-byte block', len(blk) == 20)

    # negative: what is not a well-formed record is shown as such, never
    # listed as a program or a member
    bad = bytearray(prog[1])
    bad[5] ^= 1                               # data parity broken
    lines = rtap.list_blocks([prog[0], bytes(bad)])
    check('a program with a bad data block is flagged',
          len(lines) == 1 and lines[0].endswith('(its data block is missing or bad)'))
    h = bytearray(prog[0])
    h[-1] ^= 0x55                             # header parity broken
    lines = rtap.list_blocks([bytes(h), prog[1]])
    check('a header with a bad parity byte is not taken as a header',
          lines[0].startswith('?') and 'parity' in lines[0] and 'program' not in ' '.join(lines))
    lines = rtap.list_blocks([rtap.tap_block(0xFF, bytes([3]) + b'notahdr   ' + bytes(4) + b'SS')])
    check('a 17-byte data block is a data block', lines == ['         data block, 17 bytes'])
    lines = rtap.list_blocks([tar_header('A', '', 0)] + member('/x', b'xy') + [tar_header('E', '', 0)])
    check('an archive saved without a name is /dev/cassette:', lines[0] == 'archive  /dev/cassette:')
    m = member('/x', b'0123456789' * 5)
    m[1] = m[1][:-1] + bytes([m[1][-1] ^ 1])
    lines = rtap.list_blocks(m)
    check('a member whose data block has a parity error is flagged',
          lines == ['  ? member x: a data block has a parity error'])
    lines = rtap.list_blocks([tar_header('F', 'gone', 40)])
    check('a member without its data is flagged', lines == ['  ? member gone: its data is missing or short'])
    lines = rtap.list_blocks([header(7, 'odd', 0, 0, b'\0\0'), b'\x00'])
    check('an unknown header type and a 1-byte block are flagged',
          lines[0].startswith('?        header type 7') and 'too short' in lines[1])

    # the command line: a .tap and a .tzx of the same blocks list the same;
    # a truncated .tap is an error, not a partial listing
    d = tempfile.mkdtemp()
    tap = os.path.join(d, 't.tap')
    tzx = os.path.join(d, 't.tzx')
    rtap.write(tap, b'', [(0, b) for b in prog + arch])
    rtap.write(tzx, b'ZXTape!\x1a\x01\x14', [(1000, b) for b in prog + arch])
    rt = os.path.join(SDK, 'rtap.py')
    a = subprocess.run([sys.executable, rt, '--list', tap], capture_output=True, text=True)
    b = subprocess.run([sys.executable, rt, '--list', tzx], capture_output=True, text=True)
    check('rtap --list reads .tap and .tzx alike', a.returncode == 0 and a.stdout == b.stdout
          and a.stdout.startswith('program  /dev/cassette/hello'))
    open(tap, 'ab').write(b'\x10\x00\x00')
    c = subprocess.run([sys.executable, rt, '--list', tap], capture_output=True, text=True)
    check('a truncated .tap is an error', c.returncode != 0 and 'truncated' in c.stderr + c.stdout)
    print('%d failed' % len(FAILS))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
