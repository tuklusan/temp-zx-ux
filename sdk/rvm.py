#!/usr/bin/env python3
"""rvm - the ZX-UX virtual machine: run an SSX1 C48 program on the host.

The program runs on the SDK's bundled Z80 (zxcore.py: z80-python core and the
real 48K ROM, no other dependencies); the ZX-UX kernel's
system-call interface (call 6003h) is emulated in Python, including the C
support calls (ticks, screen).  Floats and BEEP are the program's own calls
into the ROM, run here as on the Spectrum.  What runs is the same SSX1 file
that goes to tape.

  rvm.py prog.ssx [args...] [--keys TEXT] [--frames N] [--scr F] [--png F]
         [--text] [--root DIR] [--ticks N] [--load ADDR] [--trace]

  --keys TEXT   keyboard input for getchar (\\n = ENTER); end of input ends
                the run (status 'input')
  --frames N    stop after N emulated 50 Hz frames (default 3000)
  --scr/--png   write the final screen (6912-byte .scr / PNG)
  --text        print the final screen as text
  --ticks N     fixed value returned by ticks() (deterministic runs)
  --root DIR    host directory whose files the program can open (read on
                first use); rvm keeps the program's file system in memory
                for the run and never writes to the host.  A program's exec
                ends the run (status 'exec')
"""
import os
import sys
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rld                                               # noqa: E402
import zxcore                                            # noqa: E402

FRAME = 69888
SYS = 0x6003
FONT = 0x5E00
EINVAL, ENOENT, EBADF, EIO = 22, 2, 9, 5
ESRCH, ECHILD, EAGAIN, ENOMEM, EEXIST, ENOTDIR, EISDIR, EMFILE, ENOTTY = 3, 10, 11, 12, 17, 20, 21, 24, 25
PID = 1
EPOCH = 378691200                   # 1 Jan 1982 00:00 (ZX-UX's default date)
NAMES = dict(enumerate('rele exit fork read write open close wait creat link unlink exec '
                       'chdir time mkdir chmod chown break stat seek tell mount umount '
                       'setuid getuid stime quit intr fstat cemt mdate stty gtty ilgins '
                       'sleep kill getpid zxpack ticks screen ssxload'.split()))


def font_bytes():
    return open(zxcore.FONT, 'rb').read()[8:8 + 384]


class FSError(Exception):
    def __init__(self, code):
        self.code = code


class Node:
    _ino = 41

    def __init__(self, isdir, mode=0o17, data=b''):
        Node._ino += 1
        self.ino = Node._ino
        self.isdir = isdir
        self.mode = mode & 0x3F
        self.data = bytearray(data)
        self.nlink = 1
        self.mtime = EPOCH
        self.entries = {} if isdir else None


class VFS:
    """rvm's file system: kept in memory for the run, never written back to
    the host.  --root DIR supplies files (read on first use).  Results and
    error numbers follow the ZX-UX kernel's calls (src/fs.asm)."""
    NUFILE = 10

    def __init__(self, root):
        self.root = root
        self.top = Node(True)
        self._dots(self.top, self.top)
        self.cwd = self.top
        self.fds = {}

    @staticmethod
    def _dots(d, parent):
        # '.' and '..' are ordinary entries, as in v1: the system's own
        # directories have them, a directory made by the mkdir call does not
        d.entries[b'.'] = d
        d.entries[b'..'] = parent

    # path lookup: (directory node, last name)
    def _walk(self, path, want_parent=False):
        node = self.top if path.startswith(b'/') else self.cwd
        parts = [p for p in path.split(b'/') if p]
        trail = []
        if want_parent:
            if not parts:
                raise FSError(ENOENT)
            parts, last = parts[:-1], parts[-1]
        for p in parts:
            node = self._child(node, p, trail)
            if node is None:
                raise FSError(ENOENT)
            if not node.isdir:
                raise FSError(ENOTDIR)
        return (node, last) if want_parent else node

    def _child(self, d, name, trail):
        n = d.entries.get(name)
        if n is None and self.root and getattr(d, 'host', d is self.top):
            hp = os.path.join(self.root, *self._hostpath(d), name.decode('latin-1'))
            if os.path.isdir(hp):
                n = Node(True)
                n.host = True
                self._dots(n, d)
            elif os.path.isfile(hp):
                n = Node(False, data=open(hp, 'rb').read())
            if n is not None:
                n.parent = d
                n.hostname = name
                d.entries[name] = n
        return n

    def _hostpath(self, d):
        out = []
        while d is not self.top and d is not None:
            out.append(d.hostname.decode('latin-1'))
            d = d.parent
        return out[::-1]

    def lookup(self, path):
        d, name = self._walk(path, True) if path.strip(b'/') else (None, None)
        if d is None:
            return self.top
        n = self._child(d, name, [])
        if n is None:
            raise FSError(ENOENT)
        return n

    def _fd(self, node, flags):
        for fd in range(3, self.NUFILE):
            if fd not in self.fds:
                self.fds[fd] = {'node': node, 'pos': 0, 'flags': flags}
                return fd
        raise FSError(EMFILE)

    def _get(self, fd):
        f = self.fds.get(fd)
        if f is None:
            raise FSError(EBADF)
        return f

    def open(self, path, mode):
        n = self.lookup(path)
        flags = 1 if mode == 0 else 2 if mode == 1 else 3
        if flags & 2 and n.isdir:
            raise FSError(EISDIR)
        return self._fd(n, flags)

    def creat(self, path, mode):
        try:
            n = self.lookup(path)
        except FSError:
            d, name = self._walk(path, True)
            n = Node(False, mode)
            n.parent = d
            n.hostname = name
            d.entries[name] = n
        else:
            if n.isdir:
                raise FSError(EISDIR)
            n.data = bytearray()
        return self._fd(n, 2)

    def close(self, fd):
        if fd <= 2 and fd not in self.fds:
            return
        self._get(fd)
        del self.fds[fd]

    def read(self, fd, count):
        f = self._get(fd)
        if not f['flags'] & 1:
            raise FSError(EBADF)
        data = self._bytes(f['node'])[f['pos']:f['pos'] + count]
        f['pos'] += len(data)
        return bytes(data)

    def _bytes(self, n):
        if n.isdir:
            out = bytearray()
            for name, c in n.entries.items():
                out += bytes((c.ino & 255, c.ino >> 8)) + name[:8].ljust(8, b'\0')
            return out
        return n.data

    def write(self, fd, data):
        f = self._get(fd)
        if not f['flags'] & 2:
            raise FSError(EBADF)
        n = f['node']
        end = f['pos'] + len(data)
        if len(n.data) < f['pos']:
            n.data += bytes(f['pos'] - len(n.data))
        n.data[f['pos']:end] = data
        f['pos'] = end
        return len(data)

    def seek(self, fd, off, whence):
        f = self._get(fd)
        if whence == 0:
            pos = off
        elif whence == 1:
            pos = f['pos'] + off
        else:
            pos = len(self._bytes(f['node'])) + off
        f['pos'] = pos & 0xFFFF
        return f['pos']

    def tell(self, fd):
        return self._get(fd)['pos']

    def link(self, old, new):
        n = self.lookup(old)
        try:
            self.lookup(new)
        except FSError:
            pass
        else:
            raise FSError(EEXIST)
        d, name = self._walk(new, True)
        d.entries[name] = n
        n.nlink += 1

    def unlink(self, path):
        d, name = self._walk(path, True)
        n = self._child(d, name, [])
        if n is None:
            raise FSError(ENOENT)
        del d.entries[name]
        n.nlink -= 1

    def chdir(self, path):
        n = self.lookup(path)
        if not n.isdir:
            raise FSError(ENOTDIR)
        self.cwd = n

    def mkdir(self, path, mode):
        try:
            self.lookup(path)
        except FSError:
            pass
        else:
            raise FSError(EEXIST)
        d, name = self._walk(path, True)
        n = Node(True, mode)
        n.parent = d
        n.hostname = name
        d.entries[name] = n

    def chmod(self, path, mode):
        n = self.lookup(path)
        n.mode = mode & 0x3F

    def mdate(self, path, t):
        self.lookup(path).mtime = t

    def _stat(self, n):
        flags = 0x8000 | (0x4000 if n.isdir else 0) | n.mode
        size = len(self._bytes(n))
        b = bytearray(34)
        b[0:2] = bytes((n.ino & 255, n.ino >> 8))
        b[2:4] = bytes((flags & 255, flags >> 8))
        b[4] = n.nlink & 255
        b[6:8] = bytes((size & 255, (size >> 8) & 255))
        b[28:32] = n.mtime.to_bytes(4, 'little')      # i.mtim (i-node +26, after the i-number)
        return bytes(b)

    def stat(self, path):
        return self._stat(self.lookup(path))

    def fstat(self, fd):
        if fd <= 2 and fd not in self.fds:
            raise FSError(EBADF)
        return self._stat(self._get(fd)['node'])

    def size(self, path):
        n = self.lookup(path)
        return len(self._bytes(n)) & 0xFFFF

    def free_bytes(self):
        return 10000

    def free_inodes(self):
        return 16


class Stop(Exception):
    def __init__(self, why, status=0):
        self.why = why
        self.status = status


class Tracer:
    def __init__(self):
        self.border = 0
        self.spk = 0
        self.edges = 0          # speaker (EAR/MIC bit 4) changes: BEEP

    def read_port(self, port):
        return 0xFF

    def write_port(self, port, value):
        if not port & 1:
            self.border = value & 7
            if (value ^ self.spk) & 0x10:
                self.edges += 1
            self.spk = value


class VM:
    def __init__(self, ssx, args=(), keys=b'', root=None, fixed_ticks=None, load=0x8000):
        hdr = rld.parse_ssx(ssx)
        self.hdr = hdr
        self.tr = Tracer()
        self.zx = zxcore.Spectrum(self.tr.write_port, self.tr.read_port)
        mem = self.zx.mem
        mem[FONT:FONT + 384] = font_bytes()
        img = rld.relocate(hdr['image'], hdr['relocs'], load)
        mem[load:load + len(img)] = bytes(img)
        end = load + len(img) + hdr['bss'] + hdr['heap']
        argv0 = [b'prog'] + [a.encode() for a in args]
        # as ZX-UX's loader: image, bss, heap, stack, then the arguments
        top = load + max(len(img) + hdr['bss'] + hdr['heap'] + hdr['stack'], len(ssx)) \
            + sum(len(a) + 1 for a in argv0) + 2 * len(argv0) + 6
        if top > 0x10000:
            raise SystemExit('rvm: program does not fit (needs %d bytes)' % (top - load))
        top = min(top, 0x10000)
        # arguments (ZX-UX exec layout): SP -> argc, argv..., 0, strings
        argv = [b'prog'] + [a.encode() for a in args]
        strs = b''.join(a + b'\0' for a in argv)
        sp = (top - len(strs)) & 0xFFFE
        mem[sp:sp + len(strs)] = strs
        ptrs = []
        p = sp
        for a in argv:
            ptrs.append(p)
            p += len(a) + 1
        vec = [len(argv)] + ptrs + [0]
        sp -= 2 * len(vec)
        for i, v in enumerate(vec):
            mem[sp + 2 * i] = v & 255
            mem[sp + 2 * i + 1] = v >> 8
        self.load = load
        self.top = top
        self.brk = end
        self.zx.set(sp=sp, pc=(load + hdr['entry']) & 0xFFFF, iy=0x5C3A, im=1)
        self.mem = mem
        self.keys = list(keys)
        self.fixed_ticks = fixed_ticks
        self.root = root
        self.fs = VFS(root)
        self.brk0 = end
        self.time0 = EPOCH
        self.intr = 1
        self.ttymode = 0x10
        self.exec_req = None
        self.out = bytearray()
        self.screen_owned = False
        self.tbase = 0
        self.syscalls = 0

    # ------------------------------------------------------------ memory
    def rd(self, a):
        return self.mem[a] | self.mem[a + 1] << 8

    def wr(self, a, v):
        self.mem[a] = v & 255
        self.mem[(a + 1) & 0xFFFF] = (v >> 8) & 255

    def cstr(self, a):
        out = bytearray()
        while self.mem[a]:
            out.append(self.mem[a])
            a += 1
        return bytes(out)

    def clock(self):
        return (self.time0 + self.frames() // 50) & 0xFFFFFFFF

    def frames(self):
        return (self.zx.t + self.tbase) // FRAME

    # ------------------------------------------------------------ run
    def run(self, max_frames=3000, trace=False):
        zx = self.zx
        limit = max_frames * FRAME
        try:
            while True:
                t = zx.t + self.tbase
                if t >= limit:
                    raise Stop('frames')
                if zx.run((SYS,), min(zx.t + FRAME, limit - self.tbase)):
                    self.syscall(trace)
        except Stop as s:
            self.status = s.status
            return s.why

    def syscall(self, trace):
        zx = self.zx
        a = zx.a
        hl = zx.hl
        de = zx.de
        bc = zx.bc
        self.syscalls += 1
        if trace:
            print('sys %s(%d) hl=%04x de=%04x bc=%04x' % (NAMES.get(a, '?'), a, hl, de, bc), file=sys.stderr)
        fs = self.fs
        err = None
        res = 0
        try:
            if a == 0:                       # rele / yield
                pass
            elif a == 1:                     # exit
                raise Stop('exit', hl & 255)
            elif a == 2:                     # fork: an SSX1 program cannot
                err = EAGAIN
            elif a == 3:                     # read
                if hl == 0:
                    if not self.keys:
                        raise Stop('input')
                    n = 0
                    if bc and self.keys:
                        self.mem[de] = self.keys.pop(0)
                        n = 1
                    res = n
                else:
                    data = fs.read(hl, min(bc, 0x10000 - de))
                    self.mem[de:de + len(data)] = data
                    res = len(data)
            elif a == 4:                     # write
                data = bytes(self.mem[de:min(de + bc, 0x10000)])
                if hl in (1, 2):
                    self.out += data
                    res = bc
                else:
                    res = fs.write(hl, data)
            elif a == 5:                     # open
                res = fs.open(self.cstr(hl), de & 0xFF)
            elif a == 6:                     # close
                fs.close(hl)
            elif a == 7:                     # wait: no children
                err = ECHILD
            elif a == 8:                     # creat
                res = fs.creat(self.cstr(hl), de)
            elif a == 9:                     # link
                fs.link(self.cstr(hl), self.cstr(de))
            elif a == 10:                    # unlink
                fs.unlink(self.cstr(hl))
            elif a == 11:                    # exec: rvm runs one program
                path = self.cstr(hl)
                if not path.startswith((b'/dev/cassette/', b'/dev/tap/')):
                    fs.lookup(path)          # ENOENT as the kernel would
                argv = []
                p = de
                while de and self.rd(p):
                    argv.append(self.cstr(self.rd(p)).decode('latin-1'))
                    p += 2
                self.exec_req = (path.decode('latin-1'), argv)
                raise Stop('exec')
            elif a == 12:                    # chdir
                fs.chdir(self.cstr(hl))
            elif a == 13:                    # time -> DE:HL
                t = self.clock()
                res = t & 0xFFFF
                zx.de = t >> 16
            elif a == 14:                    # mkdir
                fs.mkdir(self.cstr(hl), de)
            elif a == 15:                    # chmod
                fs.chmod(self.cstr(hl), de)
            elif a in (16, 23, 26, 29, 33):  # chown setuid quit cemt ilgins
                pass
            elif a == 17:                    # break
                # as the kernel for an SSX1 program: inside its block, at
                # least 128 bytes below the stack pointer
                if hl < self.load or hl > ((zx.cpu.sp - 128) & 0xFFFF):
                    err = ENOMEM
                else:
                    self.brk = hl
                    res = hl
            elif a == 18:                    # stat
                self.mem[de:de + 34] = fs.stat(self.cstr(hl))
            elif a == 19:                    # seek
                res = fs.seek(hl, de, bc)
            elif a == 20:                    # tell
                res = fs.tell(hl)
            elif a == 24:                    # getuid
                res = 0
            elif a == 25:                    # stime: DE:HL
                self.time0 = (de << 16 | hl) - self.frames() // 50
            elif a == 27:                    # intr
                self.intr = hl & 0xFF
            elif a == 28:                    # fstat
                self.mem[de:de + 34] = fs.fstat(hl)
            elif a == 30:                    # mdate
                fs.mdate(self.cstr(hl), bc << 16 | de)
            elif a in (31, 32):              # stty / gtty: the terminal only
                if hl > 2 and hl not in fs.fds:
                    err = EBADF
                elif hl > 2:
                    err = ENOTTY
                elif a == 32:
                    for i in range(6):
                        self.mem[de + i] = 0
                    self.mem[de + 4] = self.ttymode
                else:
                    self.ttymode = self.mem[de + 4] & 0x30
            elif a == 34:                    # sleep (ticks)
                self.tbase += hl * FRAME
            elif a == 35:                    # kill
                if hl == PID:
                    raise Stop('killed', 0xFF)
                err = ESRCH
            elif a == 36:
                res = PID
            elif a == 37:                    # zxpack
                if hl == 0:
                    res = fs.free_bytes()
                    zx.de = fs.free_inodes()
                else:
                    res = fs.size(self.cstr(hl))
            elif a == 38:                    # ticks
                if self.fixed_ticks is not None:
                    res = self.fixed_ticks
                else:
                    res = self.frames() & 0xFFFF
                zx.de = 0
            elif a == 39:                    # screen
                self.screen_owned = bool(hl)
                res = FONT
                zx.de = 0                       # DE = 0: the only owner
            elif a == 40:                    # ssxload: /etc/ldx only
                err = EINVAL
            else:                            # 21, 22 (mount, umount), >40
                err = EINVAL
        except FSError as e:
            err = e.code
        # return from the call: result in HL, CF/A on error
        cpu = zx.cpu
        if err is not None:
            zx.hl = 0xFFFF
            cpu.a = err
            cpu._f |= 1
        else:
            zx.hl = res & 0xFFFF
            cpu._f &= 0xFE
            cpu.a = 0
        sp = cpu.sp
        cpu.pc = self.rd(sp)
        cpu.sp = (sp + 2) & 0xFFFF
        zx.t += 200                       # system call overhead

    # ------------------------------------------------------------ output
    def screen(self):
        return bytes(self.mem[0x4000:0x5B00])


def screen_text(scr, font=None):
    fb = font or font_bytes()
    glyphs = {}
    for c in range(32, 128):
        g = fb[(c - 32) * 4:(c - 32) * 4 + 4]
        rows = bytes(n for b in g for n in (b >> 4, b & 15))
        glyphs.setdefault(rows, chr(c))
        glyphs.setdefault(bytes(15 - x for x in rows), chr(c))
    lines = []
    for row in range(24):
        s = ''
        for col in range(64):
            a = ((row & 0x18) << 8) + ((row & 7) << 5) + col // 2
            sh = 4 if col % 2 == 0 else 0
            g = bytes((scr[a + (i << 8)] >> sh) & 15 for i in range(8))
            s += glyphs.get(g, '#' if any(g) else ' ')
        lines.append(s.rstrip())
    return '\n'.join(lines)


def write_png(scr, fname, border=0, scale=2, bw=16):
    import zlib
    pal = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
           (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]
    W, H = 256 + 2 * bw, 192 + 2 * bw
    bc = pal[border & 7]
    rows = []
    for y in range(H):
        row = []
        sy = y - bw
        for x in range(W):
            sx = x - bw
            if 0 <= sx < 256 and 0 <= sy < 192:
                a = ((sy & 0xC0) << 5) | ((sy & 7) << 8) | ((sy & 0x38) << 2) | (sx >> 3)
                at = scr[6144 + (sy >> 3) * 32 + (sx >> 3)]
                bit = scr[a] >> (7 - (sx & 7)) & 1
                br = 8 if at & 0x40 else 0
                ink, pap = (at & 7) + br, ((at >> 3) & 7) + br
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


def main(argv):
    opts = {'--keys': None, '--frames': '3000', '--scr': None, '--png': None, '--root': None,
            '--ticks': None, '--load': '0x8000'}
    flags = set()
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in opts:
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a in ('--text', '--trace'):
            flags.add(a)
            i += 1
            continue
        pos.append(a)
        i += 1
    if not pos:
        print(__doc__)
        return 2
    keys = (opts['--keys'] or '').encode().decode('unicode_escape').encode('latin-1')
    vm = VM(open(pos[0], 'rb').read(), pos[1:], keys, opts['--root'],
            int(opts['--ticks']) if opts['--ticks'] else None, int(opts['--load'], 0))
    why = vm.run(int(opts['--frames']), '--trace' in flags)
    scr = vm.screen()
    if opts['--scr']:
        open(opts['--scr'], 'wb').write(scr)
    if opts['--png']:
        write_png(scr, opts['--png'], vm.tr.border)
    if '--text' in flags:
        print(screen_text(scr))
    if vm.out:
        sys.stdout.write(vm.out.decode('latin-1'))
    print('rvm: stopped (%s) status %d after %d frames, %d system calls, %d speaker edges'
          % (why, vm.status, vm.frames(), vm.syscalls, vm.tr.edges), file=sys.stderr)
    return vm.status if why == 'exit' else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
