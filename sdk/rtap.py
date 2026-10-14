#!/usr/bin/env python3
"""rtap - ZX-UX SDK tape writer: SSX1 programs -> SST1 cassette records.

  rtap.py [-o out.tzx|out.tap] [--after ZX-UX.tzx] [--title T] prog.ssx[=NAME] ...
  rtap.py --list tape.tzx|tape.tap ...

Each program becomes one standard Spectrum CODE pair (header + data block)
that ZX-UX's loader recognises (SPEC-SDK-R2 section 9):

  header   type 3, name = the program name (1..10 characters, the name
           typed as /dev/cassette/NAME), length = SSX1 file size,
           parameter 1 = bytes of memory the program needs (image, bss,
           heap and stack; at least the file size), parameter 2 = 'SS'
  data     the SSX1 file, flag FFh

--after appends the records to a copy of an existing tape (e.g. the ZX-UX
boot tape), so that one tape boots ZX-UX and then holds the programs.

--list shows what a tape file holds, block by block, without changing
it: ZX-UX programs (as /dev/cassette/NAME, with their size and the
memory they need), tar archives and their members (kind, size and path
from each member's preamble, as tar tv shows them), the Spectrum's own
files (BASIC, arrays, CODE), and anything else (data blocks without a
header, blocks whose parity is wrong).  On ZX-UX, tap t (or tar t
without an archive name) lists the programs and archives of a real
cassette.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rld  # noqa: E402

ARGS_ROOM = 0       # the loader adds the argument bytes itself


def tap_block(flag, data):
    body = bytes([flag]) + data
    x = 0
    for c in body:
        x ^= c
    return body + bytes([x])


def need(ssx):
    h = rld.parse_ssx(ssx)
    n = len(h['image']) + h['bss'] + h['heap'] + h['stack']
    return max(n, len(ssx))


def records(ssx, name):
    if not 1 <= len(name) <= 10 or not all(32 < ord(c) < 127 and c != '/' for c in name):
        raise SystemExit('rtap: bad program name %r' % name)
    n = need(ssx)
    if n > 0xFFFF:
        raise SystemExit('rtap: %s needs %d bytes' % (name, n))
    hdr = tap_block(0, bytes([3]) + name.encode().ljust(10) +
                    struct.pack('<HHH', len(ssx), n, 0x5353))
    return [hdr, tap_block(0xFF, ssx)]


def tzx_blocks(data):
    """-> list of (pause, block) from a TZX (standard speed blocks only)."""
    if data[:8] != b'ZXTape!\x1a':
        raise SystemExit('rtap: not a TZX file')
    p = 10
    out = []
    head = bytearray(data[:10])
    while p < len(data):
        t = data[p]
        if t == 0x10:
            pause, n = struct.unpack_from('<HH', data, p + 1)
            out.append((pause, data[p + 5:p + 5 + n]))
            p += 5 + n
        elif t == 0x30:
            n = data[p + 1]
            head += data[p:p + 2 + n]
            p += 2 + n
        elif t == 0x32:
            n = struct.unpack_from('<H', data, p + 1)[0]
            head += data[p:p + 3 + n]
            p += 3 + n
        else:
            raise SystemExit('rtap: TZX block %02X not supported' % t)
    return bytes(head), out


def _name(b):
    return b[2:12].decode('latin-1').rstrip(' ')


def _parity_ok(b):
    x = 0
    for c in b:
        x ^= c
    return x == 0


def list_blocks(blocks):
    """Lines describing a tape's blocks (flag + data + parity each)."""
    out = []
    i = 0
    n = len(blocks)
    while i < n:
        b = blocks[i]
        if len(b) < 2:
            out.append('?        block %d: %d bytes, too short' % (i, len(b)))
            i += 1
            continue
        if not _parity_ok(b):
            out.append('?        block %d: parity error (%d bytes)' % (i, len(b) - 2))
            i += 1
            continue
        if b[0] != 0 or len(b) != 19:
            out.append('         data block, %d bytes' % (len(b) - 2))
            i += 1
            continue
        kind = b[1]
        name = _name(b)
        length, p1, p2 = struct.unpack_from('<HHH', b, 12)
        data = blocks[i + 1] if i + 1 < n and blocks[i + 1][:1] == b'\xff' else None
        i += 1 + (data is not None)
        if kind == 3 and b[16:18] == b'SS':
            ok = data is not None and _parity_ok(data) and len(data) - 2 == length
            out.append('program  /dev/cassette/%s  %d bytes, needs %d%s'
                       % (name, length, p1, '' if ok else '  (its data block is missing or bad)'))
        elif kind == 3 and b[16:18] == b'RU' and b[14] in (0x41, 0x45, 0x46):
            if b[14] == 0x41:
                out.append('archive  /dev/cassette%s:' % ('/' + name if name else ''))
                i -= data is not None          # an archive header has no data
            elif b[14] == 0x45:
                out.append('         end of archive')
                i -= data is not None
            else:
                got = bytearray()              # the member's data blocks
                bad = False
                j = i - (data is not None)
                while len(got) < length and j < n and blocks[j][:1] == b'\xff':
                    bad = bad or not _parity_ok(blocks[j])
                    blk = blocks[j][1:-1]
                    if len(blk) == 18 and len(got) + 17 == length:
                        blk = blk[:17]         # (17 bytes travel as 18)
                    got += blk
                    j += 1
                i = j
                if bad:
                    out.append('  ? member %s: a data block has a parity error' % name)
                elif len(got) >= 12 and 0 in got[11:]:
                    k, size = got[0], struct.unpack_from('<H', got, 3)[0]
                    path = got[11:got.index(0, 11)].decode('latin-1')
                    mark = 'd' if k & 2 else ('z' if k & 1 else '-')
                    out.append('  %s %6d %s' % (mark, size, path))
                else:
                    out.append('  ? member %s: its data is missing or short' % name)
        elif kind == 0:
            line = (' LINE %d' % p1) if p1 < 32768 else ''
            out.append('basic    "%s"  %d bytes%s' % (name, length, line))
        elif kind in (1, 2):
            out.append('%s "%s"  %d bytes' % ('numbers ' if kind == 1 else 'chars   ', name, length))
        elif kind == 3:
            out.append('code     "%s"  %d bytes at %d' % (name, length, p1))
        else:
            out.append('?        header type %d "%s"' % (kind, name))
    return out


def read_tape(path):
    data = open(path, 'rb').read()
    if data[:8] == b'ZXTape!\x1a':
        return [b for _, b in tzx_blocks(data)[1]]
    blocks = []
    p = 0
    while p < len(data):
        if p + 2 > len(data):
            raise SystemExit('rtap: %s: truncated .tap file' % path)
        n = data[p] | data[p + 1] << 8
        if p + 2 + n > len(data):
            raise SystemExit('rtap: %s: truncated .tap block at offset %d' % (path, p))
        blocks.append(data[p + 2:p + 2 + n])
        p += 2 + n
    return blocks


def write(out, head, blocks):
    if out.lower().endswith('.tap'):
        open(out, 'wb').write(b''.join(struct.pack('<H', len(b)) + b for _, b in blocks))
    else:
        body = bytearray(head)
        for pause, b in blocks:
            body += bytes([0x10]) + struct.pack('<HH', pause, len(b)) + b
        open(out, 'wb').write(bytes(body))


def main(argv):
    if argv[:1] == ['--list']:
        if len(argv) < 2:
            print(__doc__)
            return 2
        for path in argv[1:]:
            if len(argv) > 2:
                print('%s:' % path)
            for line in list_blocks(read_tape(path)):
                print(line)
        return 0
    out, after, title = 'a.tzx', None, None
    progs = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-o', '--after', '--title'):
            v = argv[i + 1]
            i += 2
            if a == '-o':
                out = v
            elif a == '--after':
                after = v
            else:
                title = v
            continue
        progs.append(a)
        i += 1
    if not progs:
        print(__doc__)
        return 2
    head = b'ZXTape!\x1a\x01\x14'
    blocks = []
    if after:
        head, blocks = tzx_blocks(open(after, 'rb').read())
    elif title:
        t = title.encode()
        head += bytes([0x30, len(t)]) + t
    for p in progs:
        path, _, name = p.partition('=')
        name = name or os.path.splitext(os.path.basename(path))[0][:10]
        ssx = open(path, 'rb').read()
        try:
            hdr, dat = records(ssx, name)
        except rld.LinkError as e:
            raise SystemExit('rtap: %s: %s' % (path, e))
        blocks += [(1000, hdr), (2000, dat)]
        print('%-10s %5d bytes, needs %5d' % (name, len(ssx), need(ssx)))
    write(out, head, blocks)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
