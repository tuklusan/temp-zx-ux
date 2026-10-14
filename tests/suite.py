#!/usr/bin/env python3
"""Regression suite for ZX-UX UNIX v1.

  python3 tests/suite.py [SNAPSHOT] [-k name] [-v]

Every test starts from a fresh copy of the snapshot that tap2sna.py made
from build/ZX-UX.tzx (a real ROM tape load), logs in and drives the
shell through the emulated keyboard.  A command's output is what appears
between its echoed line and the next "# " prompt.  Exit status 1 if any
test fails.
"""
import os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import zxrun                                    # noqa: E402

VERBOSE = False


class Fail(Exception):
    pass


class Session:
    def __init__(self, snap):
        self.zx = zxrun.ZX(snap)
        self.log = []

    # ---- low level
    def screen(self):
        return self.zx.screen()

    def rows(self):
        return self.screen().splitlines()[:23]  # text rows (23 = status)

    def status(self):
        lines = self.screen().splitlines()
        return lines[23] if len(lines) > 23 else ''

    def until(self, text, frames=3000):
        if not self.zx.until(text, frames):
            raise Fail('timeout waiting for %r\n%s' % (text, self.screen()))

    def type(self, s):
        self.zx.type(s)

    def key(self, *k):
        self.zx.press(list(k))

    def wait(self, n):
        self.zx.run(n)

    def last_line(self):
        r = [l for l in self.rows() if l.strip()]
        return r[-1] if r else ''

    def wait_prompt(self, frames=6000):
        """run until the last text line is a bare prompt"""
        for _ in range(frames // 10):
            if self.last_line() in ('#', '@'):
                # make sure it stays (output can still be coming)
                self.zx.run(10)
                if self.last_line() in ('#', '@'):
                    return
            self.zx.run(10)
        raise Fail('no prompt\n' + self.screen())

    # ---- shell
    def login(self, name='root'):
        self.until('login:', 3000)
        self.type(name + '\n')
        self.wait_prompt()

    def sh(self, cmd, frames=6000, after_typing=None):
        """type a command, wait for the prompt, return its output lines"""
        self.zx.type(cmd + '\n')
        if after_typing:                # e.g. press PLAY on the tape
            after_typing()
        self.wait_prompt(frames)
        rows = self.rows()
        # the last prompt is the last non-empty row
        end = max(i for i, l in enumerate(rows) if l.strip())
        echo = '# ' + cmd
        start = None
        for i in range(end - 1, -1, -1):
            if rows[i].rstrip() == echo.rstrip() or (
                    rows[i].startswith('# ') and echo.startswith(rows[i].rstrip())):
                start = i
                break
        out = rows[(start + 1 if start is not None else 0):end]
        # a long command wraps after 64 columns
        if start is not None and len(echo) > 64:
            out = out[(len(echo) - 1) // 64:]
        self.log.append((cmd, out))
        if VERBOSE:
            print('   # %s' % cmd)
            for l in out:
                print('     ' + l)
        return out

    def expect(self, cmd, *want, absent=(), frames=6000, after_typing=None):
        out = self.sh(cmd, frames, after_typing)
        text = '\n'.join(out)
        for w in want:
            if isinstance(w, re.Pattern):
                if not w.search(text):
                    raise Fail('%r: no match for /%s/ in:\n%s' % (cmd, w.pattern, text))
            elif w not in text:
                raise Fail('%r: %r not in:\n%s' % (cmd, w, text))
        for a in absent:
            if a in text:
                raise Fail('%r: unexpected %r in:\n%s' % (cmd, a, text))
        return out


# ---------------------------------------------------------------------
TESTS = []


def test(f):
    TESTS.append(f)
    return f


@test
def boot_login_logout(s):
    s.until('procs=4 ok', 2000)
    if 'ZX-UX UNIX v1' not in s.screen():
        raise Fail('ZX-UX v1 boot title is missing')
    s.login('ken')
    s.expect('ps', 'init', 'sh')
    s.key('CS', '1')                    # EDIT = EOF: log out
    s.until('login:', 3000)             # getty respawned by init
    s.login('dmr')
    s.expect('echo again', 'again')
    s.type('login\n')                   # the shell's login built-in
    s.until('login:', 3000)
    s.type('123456789\n')               # names are 1..8 characters
    s.until('Login incorrect', 3000)


@test
def glob(s):
    s.login()
    s.expect('echo /bin/c*', '/bin/cat /bin/chmod /bin/clock /bin/cls /bin/cmp /bin/cp')
    s.expect('ls /etc/*', '/etc/getty', '/etc/glob', '/etc/init', '/etc/motd')
    s.expect('echo /bin/[l-n]?', '/bin/ln /bin/ls /bin/mv')
    s.expect('echo /bin/z*', '/bin/zxpack')
    s.expect('echo /bin/q*', 'No match')
    s.expect('echo "*"', '*')
    out = s.sh('echo /bin/*')           # 43 names: more than exec takes
    text = ' '.join(out)
    if 'Arg list too long' not in text and 'not found' not in text:
        raise Fail('echo /bin/*: ' + text)
    s.expect('echo ok', 'ok')           # the shell survives


@test
def file_ops(s):
    s.login()
    s.sh('echo hello world > /tmp/a')
    s.expect('cat /tmp/a', 'hello world')
    s.sh('cp /tmp/a /tmp/b')
    s.expect('cmp /tmp/a /tmp/b', absent=('differ', 'EOF'))
    s.sh('mv /tmp/b /tmp/c')
    s.expect('ls /tmp', 'a', 'c', absent=('b',))
    s.sh('ln /tmp/c /tmp/d')
    s.expect('ls -l /tmp', re.compile(r'2 +12 .* c'), re.compile(r'2 +12 .* d'))
    s.sh('echo again >> /tmp/a')
    s.expect('cat /tmp/a', 'hello world', 'again')
    s.expect('wc /tmp/a', re.compile(r'2 +3 +18 /tmp/a'))
    s.expect('cmp /tmp/a /tmp/c', 'EOF on /tmp/c')
    s.expect('sum /tmp/c', re.compile(r'\d+ +1'))
    s.expect('od /tmp/c', '000000 062550 066154 020157 067567 066162 005144',
             '000014')
    s.sh('rm /tmp/d /tmp/c')
    s.expect('ls /tmp', 'a', absent=('c', 'd'))
    s.expect('rm /tmp/nothing', 'nonexistent')
    s.sh('chmod 17 /tmp/a')
    s.expect('ls -l /tmp/a', 's-rwrw')
    s.sh('chmod 37 /tmp/a')
    s.expect('ls -l /tmp/a', 'sxrwrw')
    s.expect('cat </tmp/a', 'again')
    s.sh('cat /tmp/a /tmp/a > /tmp/e')
    s.expect('wc /tmp/e', re.compile(r'4 +6 +36 /tmp/e'))


@test
def dirs(s):
    s.login()
    s.sh('mkdir /tmp/x')
    s.sh('cd /tmp/x')
    s.expect('pwd', '/tmp/x')
    s.sh('mkdir y z')
    s.expect('ls -a', '.', '..', 'y', 'z')
    s.sh('cd y')
    s.expect('pwd', '/tmp/x/y')
    s.sh('cd /')
    s.expect('rmdir /tmp/x', 'not empty')
    s.sh('rmdir /tmp/x/y /tmp/x/z')
    s.sh('rmdir /tmp/x')
    s.expect('ls /tmp', absent=('x',))
    s.expect('du /usr', re.compile(r'\d+ /usr/doc'), re.compile(r'\d+ /usr$'))
    s.expect('df', re.compile(r'\d+ bytes free, \d+ i-nodes free'))
    s.expect('stat /tmp', 'i-number', 'mod', 'cre')
    s.expect('ls -ls /etc', 'motd')
    s.expect('ls -i /', re.compile(r'\d+ bin'))
    s.expect('ls -d /usr', 'usr', absent=('doc',))


@test
def misc_cmds(s):
    s.login()
    s.expect('date', 'Fri Apr 23 00:0', '1982')   # the ZX Spectrum's release
    s.sh('date 0704120076')
    s.expect('date', 'Jul  4 12:00', '1976')
    s.expect('hello', 'Hello World!')
    s.expect('echo a  b   c', 'a b c')
    s.expect('cls')
    s.expect('beep')
    s.expect('nonesuch', 'nonesuch: not found')
    s.expect('sleep 1')
    s.expect('ls -t /usr/doc', 'tar', 'zxpack')


@test
def vi_session(s):
    s.login()
    s.zx.type('vi /tmp/v\n')
    s.until('new file', 1000)
    s.zx.type('ihello vi')
    s.key('ENTER')
    s.zx.type('second')
    s.key('CS', '1')                     # EDIT = ESC
    s.zx.type('kddp')                    # move line 1 below line 2
    s.zx.type(':wq')
    s.key('ENTER')
    s.wait_prompt()
    out = s.expect('cat /tmp/v', 'second', 'hello vi')
    i1 = [i for i, l in enumerate(out) if 'second' in l][0]
    i2 = [i for i, l in enumerate(out) if 'hello vi' in l][0]
    if i1 > i2:
        raise Fail('vi dd/p did not move the line: %r' % out)


@test
def tar_roundtrip(s):
    s.login()
    s.sh('mkdir /tmp/t')
    s.sh('echo one > /tmp/t/one')
    s.sh('echo two two > /tmp/t/two')
    s.expect('tar cvf /dev/cassette/demo /tmp/t /usr/doc/zxpack',
             'd    40 /tmp/t', '-     4 /tmp/t/one', '-     8 /tmp/t/two',
             'z  1293 /usr/doc/zxpack', frames=60000)
    s.zx.saved = zxrun.decode_mic(s.zx.tr.mic)
    if len(s.zx.saved) < 10:
        raise Fail('only %d tape blocks' % len(s.zx.saved))
    s.sh('rm /tmp/t/one /tmp/t/two')
    s.sh('rmdir /tmp/t')

    def play():                         # PLAY once the command is typed
        s.zx.tr.edges = zxrun.tape_pulses(s.zx.saved,
                                          s.zx.sim.registers[25] + 3500000)
    s.expect('tar tf /dev/cassette/demo', '/tmp/t/two', '/usr/doc/zxpack',
             frames=200000, after_typing=play)
    s.expect('tar xvf /dev/cassette/demo', '/tmp/t/one', '/usr/doc/zxpack: replaced',
             frames=200000, after_typing=play)
    s.expect('cat /tmp/t/one /tmp/t/two', 'one', 'two two')
    s.expect('ls -l /usr/doc/zxpack', 'z-rwr- 1  1293')
    s.expect('wc /usr/doc/zxpack', re.compile(r'1293 /usr/doc/zxpack'), frames=20000)


@test
def zxpack_cmd(s):
    s.login()
    s.expect('zxpack', 'files packed', 'free')
    s.expect('ls -l /usr/doc', re.compile(r'z.rwr- 1 +1293 .*zxpack'))
    s.expect('wc /usr/doc/zxpack', re.compile(r'1293 /usr/doc/zxpack'), frames=20000)
    s.expect('ls -l /usr/doc', re.compile(r's.rwr- 1 +1293 .*zxpack'))
    s.expect('zxpack /usr/doc/zxpack', '1293 -> 584 bytes', frames=60000)
    s.sh('echo x > /tmp/s')
    s.expect('zxpack /tmp/s', 'would not be smaller')
    import build, zxpack
    motd = build.MOTD.encode()
    packed = zxpack.pack(motd)
    if len(motd) < 129:                 # zok: smaller files are never packed
        expected = 'would not be smaller'
    else:
        expected = '%d -> %d bytes' % (len(motd), len(packed))
    s.expect('zxpack /etc/motd', expected, frames=60000)


@test
def idle_pack(s):
    """closed files left alone for ZAGE seconds are packed by the idle loop"""
    s.login()
    s.sh('cp /usr/doc/zxpack /tmp/i')          # a raw copy (unpacks the doc)
    want = s.sh('sum /tmp/i', frames=20000)
    s.expect('ls -l /tmp/i', re.compile(r's.rw.. 1 +1293 '))
    s.wait(50 * 60)                            # a minute of idling
    s.expect('ls -l /tmp/i', re.compile(r'z.rw.. 1 +1293 '))
    s.expect('sum /tmp/i', *want, frames=20000)     # unpacks on reading


@test
def pack_under_pressure(s):
    """an unpack that runs out of room packs other files meanwhile.

    The arena is brought to a state where the doc's 1293 raw bytes do not
    fit but packing one closed 1293-byte copy can still start (zpack's
    workspace halves down to 646 bytes) and gives enough back.  Copies
    and packs move the free space in measured steps (a copy costs about
    1297 bytes, packing one gives about 709 back, so the two together
    move it by about 588, less than the window's width), so the window
    is reached whatever the system's size; the first version filled
    greedily and passed or failed with the resident size (a change of a
    few dozen bytes could flip it)."""
    LOW, HIGH = 660, 1290
    s.login()
    s.sh('cp /usr/doc/zxpack /tmp/a')          # raw 1293 bytes, packable
    s.expect('zxpack /usr/doc/zxpack', '1293 -> 584 bytes', frames=60000)
    sum_a = s.sh('sum /tmp/a', frames=20000)
    copies, raw = [], []

    def copy():
        name = '/tmp/f%d' % len(copies)
        before = df_free(s)
        s.sh('cp /tmp/a ' + name, frames=20000)
        copies.append(name)
        raw.append(name)
        return before - df_free(s)
    step = 1300                                # a copy costs 1293 bytes and
    while df_free(s) - step > HIGH:            # its arena block's header
        copy()
    while df_free(s) > HIGH:                   # pack one, copy one
        if not raw or len(copies) > 12:
            raise Fail('cannot reach %d bytes free:\n%s' % (HIGH, s.screen()))
        s.sh('zxpack ' + raw.pop(0), frames=60000)
        copy()
    free = df_free(s)
    if not LOW <= free <= HIGH:
        raise Fail('could not bring the arena to %d..%d bytes free: %d' % (LOW, HIGH, free))

    # the room has to come from packing closed files during the unpack:
    # zpress called by the allocator (zidlem 0), not by the idle packer
    def packed():
        return len(re.findall(r'^z', '\n'.join(s.sh('ls -l /tmp')), re.M))
    before = packed()
    pressed = []
    zidlem = ksym('zidlem')
    with watching(s, ksym('zpress'), lambda: pressed.append(s.zx.mem[zidlem])):
        s.expect('wc /usr/doc/zxpack', re.compile(r'38 +213 +1293 /usr/doc/zxpack'),
                 frames=200000)
    if 0 not in pressed or packed() <= before:
        raise Fail('the unpack (%d bytes free) did not pack another file to make room '
                   '(zpress calls: %s; packed files %d -> %d)'
                   % (free, pressed, before, packed()))
    s.expect('ls -l /usr/doc/zxpack', re.compile(r's.rw.. 1 +1293 '))
    s.expect('sum /tmp/a', *sum_a, frames=60000)
    for f in copies:
        s.expect('cmp /tmp/a ' + f, absent=('differ', 'EOF'), frames=60000)


@test
def processes(s):
    s.login()
    out = s.sh('sleep 20 &')
    pid = out[0].strip() if out else ''
    if not pid.isdigit():
        raise Fail('no pid from &: %r' % out)
    s.expect('ps', 'init', 'sh', 'sleep', 'ps', re.compile(r'\s%s\s' % pid))
    s.sh('kill %s' % pid)
    s.wait(100)
    s.expect('ps', absent=('sleep',))
    s.zx.type('top\n')
    s.wait(400)
    if 'idle%' not in s.screen():
        raise Fail('top:\n' + s.screen())
    s.key('CS', 'SPACE')                 # BREAK stops it
    s.wait_prompt()
    s.zx.type('forktest\n')
    s.wait_prompt(20000)
    scr = s.screen()
    if not ('P' in scr and 'c' in scr):
        raise Fail('forktest:\n' + scr)


@test
def pool_capacity(s):
    """a background job holds a slot while ls, glob and vi run"""
    s.login()
    s.sh('sleep 30 &')
    s.expect('ls /bin', 'zxpack', absent=('not found', 'Try again'))
    s.expect('echo /etc/[gi]*', '/etc/getty /etc/glob /etc/init')


# ---- programs from the cassette (ZX-UX v1, SDK-compiled SSX1)
sys.path.insert(0, os.path.join(ROOT, 'sdk'))


def ksym(name):
    import re as _re
    for l in open(os.path.join(ROOT, 'src', 'unix.sym')):
        m = _re.match(r'(\S+): EQU 0x([0-9A-Fa-f]+)', l)
        if m and m.group(1) == name:
            return int(m.group(2), 16)
    raise KeyError(name)


def kword(s, name):
    a = ksym(name)
    return s.zx.mem[a] | s.zx.mem[a + 1] << 8


def ssx_tape(name):
    """tests/c/NAME.c compiled by rcc -> its cassette records (rtap)"""
    import rtap
    from rcc import driver
    out = os.path.join(ROOT, 'build', 'ssx', name + '.ssx')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if driver.main([os.path.join(HERE, 'c', name + '.c'), '-o', out]):
        raise Fail('rcc failed for ' + name)
    return rtap.records(open(out, 'rb').read(), name)


def ssx_tape_asm(name):
    """tests/c/NAME.c plus the helpers in tests/c/NAME.s -> cassette records"""
    import ras, rld, rtap
    from rcc import driver
    src = os.path.join(HERE, 'c', name + '.c')
    text, prog, g = driver.compile_to_asm(src, {'heap': 1024})
    text += open(os.path.join(HERE, 'c', name + '.s')).read()
    obj = ras.assemble_text(text, name + '.s')
    libp = os.path.join(ROOT, 'sdk', 'lib', 'libc48.ssa')
    data = rld.link([rld.Obj(obj, name)], [rld.read_archive(open(libp, 'rb').read(), libp)],
                    'start', driver.stack_estimate(g), 0)[0]
    return rtap.records(data, name)


def run_cassette(s, name, args='', before=()):
    blocks = [b for n in before for b in ssx_tape(n)] + ssx_tape(name)
    s.zx.type('/dev/cassette/%s%s\n' % (name, args))
    s.zx.tr.edges = zxrun.tape_pulses(blocks, s.zx.sim.registers[25] + 350000)


def df_free(s):
    out = s.sh('df')
    return int(re.search(r'(\d+) bytes free', '\n'.join(out)).group(1))


@test
def cassette_args(s):
    """an SSX1 program loaded from tape, with arguments"""
    s.login()
    free = df_free(s)
    run_cassette(s, 'ssxargs', ' one two')
    s.wait_prompt(4000)
    scr = s.screen()
    for w in ('ssx args:', '/dev/cassette/ssxargs', 'one', 'two'):
        if w not in scr:
            raise Fail('%r missing:\n%s' % (w, scr))
    if df_free(s) < free - 8:
        raise Fail('memory not given back: %d -> %d' % (free, df_free(s)))


@test
def cassette_search(s):
    """the loader winds past other programs to the one named"""
    s.login()
    run_cassette(s, 'ssxargs', ' x', before=('ssxhuge', 'ssxbig'))
    s.wait_prompt(9000)
    if 'ssx args:' not in s.screen():
        raise Fail('not run:\n' + s.screen())


@test
def window_lending(s):
    """a program bigger than the free arena borrows the window"""
    s.login()
    free = df_free(s)
    run_cassette(s, 'ssxbig')
    s.until('big ok', 4000)
    if kword(s, 'wlend') == 0 or kword(s, 'a_top') != ksym('CORETOP'):
        raise Fail('window not lent: wlend %04X a_top %04X' % (kword(s, 'wlend'), kword(s, 'a_top')))
    s.key('ENTER')                          # the program ends
    s.wait_prompt(3000)
    if kword(s, 'wlend') != 0 or kword(s, 'a_top') > ksym('WINDOW'):
        raise Fail('window not given back')
    after = df_free(s)
    if after < free - 8:
        raise Fail('memory not given back: %d -> %d' % (free, after))
    s.expect('ps', 'init', 'sh', absent=('ssxbig',))
    s.expect('ls /etc', 'motd')


@test
def lending_background(s):
    """a background job waits while the window is lent, then goes on"""
    s.login()
    s.sh('sleep 2 &')
    run_cassette(s, 'ssxbig')
    s.until('big ok', 4000)
    s.wait(200)                             # the job's time is up meanwhile
    s.key('ENTER')
    s.wait_prompt(3000)
    s.wait(100)
    s.expect('ps', absent=('sleep',))


@test
def cassette_multitask(s):
    """two programs from tape run at once, sharing the screen"""
    s.login()
    m = s.zx.mem
    own = ksym('scrown')
    run_cassette(s, 'mtleft', ' &')
    for _ in range(300):
        if m[own]:
            break
        s.wait(10)
    else:
        raise Fail('mtleft did not start')
    s.wait(20)
    run_cassette(s, 'mtright')          # typed while mtleft owns the screen
    both = False
    for _ in range(600):
        if bin(m[own]).count('1') == 2:
            both = True
            if 'left running' in s.screen() and 'right running' in s.screen():
                break
        s.wait(10)
    if not both:
        raise Fail('not both at once:\n' + s.screen())
    for _ in range(600):                # until both are done
        if not m[own]:
            break
        s.wait(10)
    s.key('ENTER')                      # (the prompt came while the screen was owned)
    s.wait_prompt(1000)
    scr = s.screen()
    for w in ('left done', 'right done'):
        if w not in scr:
            raise Fail('%r missing:\n%s' % (w, scr))
    s.expect('ps', 'init', 'sh', absent=('mtleft', 'mtright'))


@test
def shell_below_picture(s):
    """a program in the background: the shell works on rows 21-22"""
    s.login()
    m = s.zx.mem
    own, top = ksym('scrown'), ksym('ttop')
    run_cassette(s, 'mtleft', ' &')
    for _ in range(300):
        if m[own]:
            break
        s.wait(10)
    else:
        raise Fail('mtleft did not start')
    s.wait(20)
    s.type('ps\n')
    for _ in range(100):
        rows = s.screen().splitlines()
        if 'R' in rows[21] and 'ps' in rows[21] and rows[22].strip() == '#':
            break
        s.wait(10)
    else:
        raise Fail('no ps below the picture:\n' + s.screen())
    if m[top] != 21 or 'init' not in s.status() or 'left running' not in s.screen():
        raise Fail('console not below the picture (ttop %d):\n%s' % (m[top], s.screen()))
    for _ in range(600):                # mtleft ends: the whole screen again
        if not m[own]:
            break
        s.wait(10)
    s.wait(20)
    if m[top] != 0:
        raise Fail('ttop %d after the program' % m[top])
    s.expect('ps', 'init', 'sh', absent=('mtleft',))


@test
def pair_after_prompt(s):
    """the release's multitask snapshot (tools/mtsnap.py): hanoi in the
    background, a prompt below its picture, then queens8 - both run"""
    import rtap
    s.login()
    own = ksym('scrown')
    for n, count in (('hanoi', 1), ('queens8', 2)):
        f = os.path.join(ROOT, 'build', 'c48', n + '-mt.ssx')
        if not os.path.exists(f):
            raise Fail('%s missing: run tools/mktapes.py' % f)
        s.zx.type('/dev/cassette/%s &\n' % n)
        s.zx.tr.edges = zxrun.tape_pulses(rtap.records(open(f, 'rb').read(), n),
                                          s.zx.sim.registers[25] + 350000)
        for _ in range(500):
            if bin(s.zx.mem[own]).count('1') == count:
                break
            s.wait(10)
        else:
            raise Fail('%s did not start:\n%s' % (n, s.screen()))
        if n == 'hanoi':
            s.wait(100)
            s.zx.type('\n')                # a prompt below the picture
            s.wait(100)


class watching:
    """with watching(s, addr, on_stop): s.zx.run stops before every
    instruction at addr and calls on_stop() (the kernel at a routine).
    Not nestable: leaving the block restores the class's run."""
    def __init__(self, s, addr, on_stop):
        self.zx, self.addr, self.on_stop = s.zx, addr, on_stop

    def __enter__(self):
        from skoolkit.simutils import PC, T
        zx, addr, on_stop = self.zx, self.addr, self.on_stop

        def run(frames):
            regs = zx.sim.registers
            for _ in range(frames):
                end = regs[T] + zxrun.FRAME
                while regs[T] < end:
                    if regs[PC] == addr:
                        on_stop()
                        zx.sim.trace(regs[PC], -1, 1, end, 1, None, None, None, None, None)
                        continue
                    zx.sim.trace(regs[PC], addr, 0, end, 1, None, None, None, None, None)
                zx.frames += 1
        zx.run = run
        return self

    def __exit__(self, *exc):
        del self.zx.run                 # the class's run again


def saves_watched(s, frames, before=None):
    """before() (e.g. typing a command), then frames, stopping at each
    window save (wsave): the deepest stack (CORETOP - saved SP) per
    program name.  The typing is watched too: a fork saves the shell's
    window as the ENTER is pressed."""
    from skoolkit.simutils import A
    coretop, p_sp, stline = ksym('CORETOP'), ksym('p_sp'), ksym('stline')
    regs, m = s.zx.sim.registers, s.zx.mem
    deep = {}

    def saved():
        slot = regs[A]
        sp = m[p_sp + 2 * slot] | m[p_sp + 2 * slot + 1] << 8
        name = bytes(m[stline + 8 * slot:stline + 8 * slot + 8]).split(b'\0')[0]
        name = name.decode('latin-1').strip()
        deep[name] = max(deep.get(name, 0), coretop - sp)
    with watching(s, ksym('wsave'), saved):
        if before:
            before()
        s.zx.run(frames)
    return deep


@test
def shell_save_depth(s):
    """the shell's stack stays well inside its reserve (STK_SH, t_sys.asm)
    when its window image is saved: a resident job in the background takes
    the window while the shell globs, redirects and runs a script"""
    s.login()
    s.sh('echo echo $1 $2 > /tmp/s')
    s.sh('echo ls /bin/c* >> /tmp/s')
    deep = {}
    for cmd in ('sleep 2 &', 'ls -l /bin/c* > /tmp/l', 'sh /tmp/s a b', 'sleep 1 &',
                'echo a b c d e f g h i j k l m n o p > /tmp/m', 'cat /tmp/m /tmp/l'):
        for k, v in saves_watched(s, 400, lambda: s.zx.type(cmd + '\n')).items():
            deep[k] = max(deep.get(k, 0), v)
    reserve = 256                       # STK_SH
    if 'sh' not in deep:
        raise Fail('the shell was never saved: %s' % deep)
    if deep['sh'] > reserve // 2:
        raise Fail('the shell saved %d bytes of stack; its reserve is %d' % (deep['sh'], reserve))
    s.wait_prompt()
    s.expect('echo alive', 'alive')


@test
def pair_without_lending(s):
    """hanoi and queens8 (tools/mktapes.py) both fit in the arena: the shell keeps running"""
    import rtap
    s.login()
    m = s.zx.mem
    own = ksym('scrown')
    for n, count in (('hanoi', 1), ('queens8', 2)):
        f = os.path.join(ROOT, 'build', 'c48', n + '-mt.ssx')
        if not os.path.exists(f):
            raise Fail('%s missing: run tools/mktapes.py' % f)
        s.zx.type('/dev/cassette/%s &\n' % n)
        s.zx.tr.edges = zxrun.tape_pulses(rtap.records(open(f, 'rb').read(), n),
                                          s.zx.sim.registers[25] + 350000)
        for _ in range(500):
            if bin(m[own]).count('1') == count:
                break
            s.wait(10)
        else:
            raise Fail('%s did not start:\n%s' % (n, s.screen()))
        s.wait(100)
        if kword(s, 'wlend'):
            raise Fail('%s was lent the window' % n)
    s.type('cd /bin\n')                 # the shell runs (a built-in; the four slots are taken)
    for _ in range(100):
        rows = s.screen().splitlines()
        if 'cd /bin' in rows[21] and rows[22].strip() == '#':
            break
        s.wait(10)
    else:
        raise Fail('the shell does not answer:\n' + s.screen())


@test
def cassette_too_big(s):
    s.login()
    run_cassette(s, 'ssxhuge')
    s.until('not enough memory', 3000)
    s.wait_prompt(1000)
    s.expect('echo still here', 'still here')


@test
def banner_motd(s):
    """boot banner year, the message of the day, init's small SAVE"""
    s.until('procs=4 ok', 2000)
    scr = s.screen()
    if '2026 SANYALnet Labs' not in scr or '2006' in scr:
        raise Fail('copyright line:\n' + scr)
    s.login()
    scr = s.screen()
    if 'Spectrum 48K.' not in scr or 'Erdogan' in scr:
        raise Fail('motd:\n' + scr)
    save = kword(s, 'p_save')           # init is slot 0: u-area, U_T, 160 stack
    size = s.zx.mem[save - 4] | s.zx.mem[save - 3] << 8
    if size > 59 + 15 + 160 + 8:
        raise Fail('init SAVE block is %d bytes' % size)


@test
def more_pager(s):
    s.login()
    s.sh('od /usr/doc/zxpack > /tmp/m', frames=20000)
    s.zx.type('more /tmp/m\n')
    s.until('--More--', 3000)
    first = s.rows()[0]
    s.key('SPACE')                      # the next page
    s.wait(200)
    s.until('--More--', 3000)
    if s.rows()[0] == first:
        raise Fail('SPACE did not page:\n' + s.screen())
    s.key('ENTER')                      # one more line
    s.wait(100)
    s.until('--More--', 1000)
    s.type('q')
    s.wait_prompt()
    s.expect('echo echoed', 'echoed')   # the terminal is back in echo mode
    s.zx.type('more < /tmp/m\n')
    s.until('--More--', 3000)
    s.key('CS', 'SPACE')                # BREAK quits too
    s.wait_prompt()
    s.expect('echo again', 'again')
    s.sh('echo short > /tmp/n')
    s.expect('more /tmp/n /tmp/n', '::: /tmp/n', 'short', absent=('--More--',))
    s.expect('more', 'usage: more')


@test
def sh_script_args(s):
    """sh file args: the script buffers are above the break only meanwhile"""
    s.login()
    s.sh("echo 'echo arg $1 $2' > /tmp/s")
    free = df_free(s)
    s.expect('sh /tmp/s one two', 'arg one two')
    s.expect('df', re.compile(r'\d+ bytes free'))
    if df_free(s) != free:
        raise Fail('memory not given back: %d -> %d' % (free, df_free(s)))


@test
def exit_logout(s):
    """exit and logout end the shell; in a command file, exit ends the file"""
    s.login()
    # a command file: exit ends it (later lines and the rest of its line
    # are not run) and the calling shell carries on
    s.sh('echo echo a > /tmp/x1')
    s.sh('echo exit >> /tmp/x1')
    s.sh('echo echo b >> /tmp/x1')
    out = s.sh('sh /tmp/x1')
    if out != ['a']:
        raise Fail('sh /tmp/x1 gave %r, want [\'a\']' % out)
    s.sh('echo "echo c; exit; echo d" > /tmp/x2')
    out = s.sh('sh /tmp/x2')
    if out != ['c']:
        raise Fail('sh /tmp/x2 gave %r, want [\'c\']' % out)
    s.expect('echo still here', 'still here')
    # a second shell: exit returns to the first
    s.type('sh\n')
    s.wait(150)
    s.type('exit\n')
    s.wait_prompt()
    s.expect('echo top', 'top')
    # a background job survives logout; logout and exit end the login shell
    s.sh('sleep 30 &')
    for cmd in ('logout', 'exit'):
        s.type(cmd + '\n')
        for _ in range(60):                 # a new getty's prompt, last line
            s.wait(10)
            if s.last_line().rstrip() == 'login:':
                break
        else:
            raise Fail('%s: no login prompt:\n%s' % (cmd, s.screen()))
        s.type('root\n')
        s.wait_prompt()
    s.expect('ps', 'sleep', 'init')


@test
def kernel_fixes(s):
    """review fixes C1, C2, M1, M3, M6 and the exec argument bound (tests/c/kfix.c)"""
    s.login()
    inodes = lambda: int(re.search(r'(\d+) i-nodes free', '\n'.join(s.sh('df'))).group(1))
    before = inodes()
    s.zx.type('/dev/cassette/kfix\n')
    s.zx.tr.edges = zxrun.tape_pulses(ssx_tape_asm('kfix'), s.zx.sim.registers[25] + 350000)
    s.until('kfix done', 6000)
    scr = s.screen()
    for w in ('eof ok', 'far ok', 'unlink ok', 'ssxload ok', 'iy ok', 'args ok'):
        if w not in scr:
            raise Fail('%r missing:\n%s' % (w, scr))
    s.wait_prompt(3000)
    s.expect('ls /tmp', absent=('k1',))
    if inodes() != before:
        raise Fail('i-node leaked: %d -> %d' % (before, inodes()))
    s.expect('echo alive', 'alive')


@test
def path_safety(s):
    """a file used as a directory, mv and cp onto the same file, mv of a
    missing file: nothing is lost (namei ENOTDIR, t_file mv and cp)"""
    s.login()
    s.sh('echo a > /tmp/f')
    s.sh('echo b > /tmp/f/x')
    s.sh('mkdir /tmp/f/d')
    s.expect('ls /tmp', 'f', absent=('x', 'd'))
    s.expect('cat /tmp/f', 'a')
    s.sh('mv /tmp/f /tmp/f')
    s.expect('cat /tmp/f', 'a')
    s.expect('cp /tmp/f /tmp/f', 'same file')
    s.expect('cat /tmp/f', 'a')
    s.sh('cd /tmp')
    s.expect('cp f .', 'same file')
    s.sh('mv f .')
    s.expect('mv nothere f', "can't open")
    s.expect('cat f', 'a')
    s.sh('mkdir d')
    s.sh('cp f d')
    s.sh('mv f d/g')
    s.expect('ls /tmp/d', 'f', 'g')
    s.expect('cat d/g', 'a')


@test
def unpack_sizes(s):
    """an unpack that packs a file of another size meanwhile keeps its own
    size (zx.asm zunpack: zn was the other file's)"""
    s.login()
    s.sh('cp /usr/doc/tar /tmp/t', frames=20000)       # 1480 bytes, raw
    sum_z = s.sh('sum /usr/doc/zxpack', frames=60000)
    s.expect('zxpack /usr/doc/zxpack', '1293 -> 584 bytes', frames=60000)
    n = 0
    while df_free(s) > 1300 and n < 12:
        s.sh('cp /tmp/t /tmp/f%d' % n, frames=20000)
        n += 1
    s.expect('wc /usr/doc/zxpack', re.compile(r'38 +213 +1293 /usr/doc/zxpack'),
             frames=200000)
    s.expect('sum /usr/doc/zxpack', *sum_z, frames=60000)
    for i in range(n):
        s.sh('rm /tmp/f%d' % i)
    s.expect('cmp /tmp/t /usr/doc/tar', absent=('differ', 'EOF'), frames=60000)


@test
def tape_break(s):
    """BREAK during a tape read: the ROM's error path (interrupts already
    on) unwinds to a trap on the caller's stack, not into the kernel
    globals; ERR_SP is the kernel's again afterwards"""
    s.login()
    m = s.zx.mem
    errsp = lambda: m[0x5C3D] | m[0x5C3E] << 8
    home = errsp()
    for i in range(3):
        s.zx.type('cat /dev/tap\n')
        s.zx.run(60 + 7 * i)
        if not 0xF000 <= errsp() < 0xFFB9:
            raise Fail('ERR_SP %04X during the read: not on the stack' % errsp())
        s.key('CS', 'SPACE')
        s.wait_prompt(3000)
        if errsp() != home or m[0x5C92 + 5]:
            raise Fail('after BREAK: ERR_SP %04X (want %04X), tapbusy %d'
                       % (errsp(), home, m[0x5C92 + 5]))
    s.expect('echo alive', 'alive')


@test
def ssx_own_args(s):
    """the program from tape gets /etc/ldx's arguments even if another
    process has exec'd meanwhile (KARGS is global; sys ssxload takes argv)"""
    s.login()
    s.zx.type('/dev/cassette/ssxargs one two\n')
    s.zx.run(150)                       # /etc/ldx is waiting for the tape
    k = ksym('KARGS')                   # another exec's arguments
    junk = b'echo\0QQQQQQQQ\0'
    s.zx.mem[k:k + len(junk)] = junk
    s.zx.mem[ksym('xargc')] = 2
    s.zx.mem[ksym('xtop')] = (k + len(junk)) & 255
    s.zx.mem[ksym('xtop') + 1] = (k + len(junk)) >> 8
    s.zx.tr.edges = zxrun.tape_pulses(ssx_tape('ssxargs'), s.zx.sim.registers[25] + 350000)
    s.wait_prompt(9000)
    scr = s.screen()
    if 'ssx args:' not in scr or '\n  one' not in scr or '\n  two' not in scr or 'QQQ' in scr:
        raise Fail('wrong arguments:\n' + scr)


@test
def vi_big_file(s):
    """vi on a file bigger than its buffer: ':wq' must not cut it short"""
    s.login()
    s.sh('cat /usr/doc/zxpack /usr/doc/tar /usr/doc/more > /tmp/big', frames=60000)
    ref = s.sh('sum /tmp/big', frames=60000)
    s.zx.type('vi /tmp/big\n')
    s.until('buffer full', 3000)
    s.zx.type(':wq')
    s.key('ENTER')
    s.until("can't write", 3000)
    s.zx.type(':q')
    s.key('ENTER')
    s.wait_prompt(3000)
    size = sum(os.path.getsize(os.path.join(ROOT, 'src', d + '.doc'))
               for d in ('zxpack', 'tar', 'more'))
    s.expect('ls -l /tmp/big', ' %d ' % size)
    s.expect('sum /tmp/big', *ref, frames=60000)


@test
def beep_pitch(s):
    """beep() at 12:34 on the status clock plays C4 then C5 (sdk float.asm)"""
    s.login()
    s.zx.mem[0x5C92] = 12           # tod_h, tod_m (dev.asm): past the first
    s.zx.mem[0x5C93] = 34           # minute, BEEP used to read these bytes
    tr = s.zx.tr
    spk = []
    plain = type(tr).write_port

    def write_port(registers, port, value, *rest):
        if not port & 1:
            if (value ^ tr.outfe) & 0x10:
                spk.append(registers[25])
            tr.outfe = value
        return plain(tr, registers, port, value, *rest)
    tr.write_port = write_port
    s.zx.sim.set_tracer(tr)
    s.zx.type('/dev/cassette/beepck\n')
    tr.edges = zxrun.tape_pulses(ssx_tape('beepck'), s.zx.sim.registers[25] + 350000)
    s.until('beepck done', 6000)
    if 'beep ok' not in s.screen():
        raise Fail('beep failed:\n' + s.screen())
    if s.zx.mem[0x5C92] != 12 or s.zx.mem[0x5C93] != 34:
        raise Fail('clock bytes not put back: %d %d' % (s.zx.mem[0x5C92], s.zx.mem[0x5C93]))
    gaps = [b - a for a, b in zip(spk, spk[1:])]
    # half periods: C4 261.6 Hz is 6689 T-states, C5 3344; 0.1 s of each
    # is about 51 and 104 of them (the key clicks are 540 T-states)
    n1 = sum(1 for g in gaps if 6000 < g < 7400)
    n2 = sum(1 for g in gaps if 3000 < g < 3700)
    if not (46 <= n1 <= 56 and 98 <= n2 <= 110):
        raise Fail('half periods: %d of C4, %d of C5; want about 51 and 104' % (n1, n2))
    s.wait_prompt(3000)


@test
def border_kept(s):
    """border() sets BORDCR as well as the border, so the key click and
    BEEP (which put the border back from BORDCR) keep the colour; bad
    colours change neither; when the screen goes back to the console the
    border is black again and BORDCR is 07h, as the ROM's BORDER 0 leaves
    it (or the next key click would bring the colour back)"""
    s.login()
    m = s.zx.mem
    tr = s.zx.tr

    def want(what, border, bordcr):
        if (tr.border, m[0x5C48]) != (border, bordcr):
            raise Fail('%s: border %d BORDCR %02X, want %d %02X\n%s'
                       % (what, tr.border, m[0x5C48], border, bordcr, s.screen()))
    want('at login', 0, 0x07)
    s.expect('beep', absent=('usage',))         # BEEP with BORDCR black
    want('beep at the shell', 0, 0x07)
    run_cassette(s, 'bordck')
    s.until('border 2', 6000)
    s.zx.run(5)
    want('border(2)', 2, 0x17)                  # 2*8 + white lower ink
    s.zx.type('x')                              # key click
    s.until('after beep', 3000)
    s.zx.run(5)
    want('after the key click and BEEP', 2, 0x17)
    s.until('bad refused', 3000)
    want('border(8), border(-1), border(256)', 2, 0x17)
    s.zx.type('x')
    s.until('border 5', 3000)
    s.zx.run(5)
    want('border(5)', 5, 0x28)                  # light colours: black ink
    s.zx.type('x')                              # the program ends
    s.wait_prompt(3000)
    want('after the program', 0, 0x07)       # as BORDER 0 leaves it
    s.expect('echo still', 'still')             # key clicks at the shell
    want('typing at the shell', 0, 0x07)


def mixed_tape(s):
    """tar sets made on ZX-UX (one named, one not) between two programs, the system tape's
    BASIC and CODE headers, and two blocks that are not headers to list:
    a header with a bad parity byte, and a 17-byte data block"""
    import rtap
    s.sh('mkdir /tmp/t')
    s.sh('echo one > /tmp/t/one')
    s.sh('tar cf /dev/cassette/demo /tmp/t', frames=60000)
    arch = zxrun.decode_mic(s.zx.tr.mic)
    if len(arch) != 6:
        raise Fail('tar wrote %d blocks, want 6' % len(arch))
    s.sh('tar cf /dev/cassette /tmp/t/one', frames=60000)    # no name
    anon = zxrun.decode_mic(s.zx.tr.mic)[6:]
    if len(anon) != 4:
        raise Fail('tar wrote %d blocks for the unnamed set, want 4' % len(anon))
    prog = ssx_tape('ssxargs')
    data = open(os.path.join(ROOT, 'build', 'ZX-UX.tap'), 'rb').read()
    sysb, p = [], 0
    while p < len(data):
        n = data[p] | data[p + 1] << 8
        sysb.append(data[p + 2:p + 2 + n])
        p += 2 + n
    bad = bytearray(rtap.tap_block(0, bytes([3]) + b'badparity ' + bytes(4) + b'SS'))
    bad[-1] ^= 0x55
    fake = rtap.tap_block(0xFF, bytes([3]) + b'notahdr   ' + bytes(4) + b'SS')
    zz9 = rtap.records(open(os.path.join(ROOT, 'build', 'ssx', 'ssxargs.ssx'), 'rb').read(), 'zz9')
    return prog + arch + sysb[:4] + [bytes(bad), fake] + anon + zz9


def listing(s, cmd):
    """the lines after the last prompt line that holds cmd (a held BREAK
    can leave spaces before it: the ROM repeats the SPACE)"""
    rows = s.rows()
    hit = [i for i, l in enumerate(rows) if re.match(r'#\s+' + re.escape(cmd) + r'$', l.rstrip())]
    if not hit:
        raise Fail('%r not on the screen:\n%s' % (cmd, s.screen()))
    return [l.rstrip() for l in rows[hit[-1] + 1:] if l.strip() and l.strip() != '#']


def list_until(s, cmd, last, frames=80000):
    for _ in range(frames // 50):
        got = listing(s, cmd)
        if got and got[-1] == last:
            s.zx.run(100)
            return listing(s, cmd)
        s.zx.run(50)
    raise Fail('%s: %r not listed:\n%s' % (cmd, last, s.screen()))


@test
def tap_t_whole_tape(s):
    """tap t (tar t without a name) lists the whole tape - each program
    as /dev/cassette/NAME, each tar set as /dev/cassette/LABEL: and its
    members - and skips everything else, loading and running nothing,
    until BREAK (held as a user would: the ROM loader waits about a
    second after an edge without looking at BREAK)"""
    s.login()
    tape = mixed_tape(s)
    free = df_free(s)
    s.zx.type('tap t\n')
    s.zx.tr.edges = zxrun.tape_pulses(tape, s.zx.sim.registers[25] + 3500000)
    list_until(s, 'tap t', '/dev/cassette/zz9')
    # (tap lists in the long form, as v1's did)
    want = ['/dev/cassette/ssxargs', '/dev/cassette/demo:', 'd    30 /tmp/t',
            '-     4 /tmp/t/one', '/dev/cassette:', '-     4 /tmp/t/one', '/dev/cassette/zz9']
    got = listing(s, 'tap t')
    if got != want:
        raise Fail('tap t listed %s, want %s' % (got, want))
    # the SDK's rtap --list says the same of these blocks (and more: the
    # BASIC and CODE files, the blocks that are not records)
    import rtap
    host = [' '.join(l.split()) for l in rtap.list_blocks(tape)]
    for item in (' '.join(g.split()) for g in got):
        if not any(h == item or h.startswith('program ' + item + ' ')
                   or h == 'archive ' + item for h in host):
            raise Fail('rtap --list does not show %r:\n%s' % (item, '\n'.join(host)))
    for word in ('badparity', 'notahdr', 'ZX-UX', 'unix', 'ssx args:'):
        if word in '\n'.join(got):
            raise Fail('%r listed' % word)
    s.zx.tr.pressed = {'CS', 'SPACE'}           # hold BREAK 1.5 seconds
    s.zx.run(75)
    s.zx.tr.pressed = set()
    s.wait_prompt(3000)
    procs = [m.group(1) for m in (re.match(r'\s*\d+\s+\d+\s+\S\s+\S+\s+(\S+)$', l)
                                  for l in s.sh('ps')) if m]
    if procs != ['init', 'sh', 'ps']:
        raise Fail('processes after BREAK: %s' % procs)
    if df_free(s) != free:
        raise Fail('memory changed: %d -> %d bytes free' % (free, df_free(s)))
    # tar tf /dev/cassette: the same, members by path only
    s.zx.type('tar tf /dev/cassette\n')
    s.zx.tr.edges = zxrun.tape_pulses(tape, s.zx.sim.registers[25] + 3500000)
    list_until(s, 'tar tf /dev/cassette', '/dev/cassette/zz9')
    want = ['/dev/cassette/ssxargs', '/dev/cassette/demo:', '/tmp/t', '/tmp/t/one',
            '/dev/cassette:', '/tmp/t/one', '/dev/cassette/zz9']
    got = listing(s, 'tar tf /dev/cassette')
    if got != want:
        raise Fail('tar tf /dev/cassette listed %s, want %s' % (got, want))
    s.zx.tr.pressed = {'CS', 'SPACE'}
    s.zx.run(75)
    s.zx.tr.pressed = set()
    s.wait_prompt(3000)


@test
def tar_t_named(s):
    """with an archive name, t lists that archive only - no programs, no
    other headers - and ends by itself at the archive's end; x without a
    name still takes the first archive"""
    s.login()
    tape = mixed_tape(s)
    s.zx.type('tar tf /dev/cassette/demo\n')
    s.zx.tr.edges = zxrun.tape_pulses(tape, s.zx.sim.registers[25] + 3500000)
    s.wait_prompt(80000)
    got = listing(s, 'tar tf /dev/cassette/demo')
    if got != ['/tmp/t', '/tmp/t/one']:
        raise Fail('tar tf /dev/cassette/demo listed %s' % got)
    s.sh('rm /tmp/t/one')
    s.zx.type('tap x\n')
    s.zx.tr.edges = zxrun.tape_pulses(tape, s.zx.sim.registers[25] + 3500000)
    s.wait_prompt(80000)
    s.expect('cat /tmp/t/one', 'one')


@test
def boot_figures(s):
    """line 3 of the boot banner: the kernel's size is the resident
    kernel (kend - 6000h, the 8K limit's measure), the free figure is
    what the kernel itself counts free in the arena (afreeb) when it
    prints the banner - before init, getty and the shell take their
    share, so df after login shows less - and procs is NPROC"""
    from skoolkit.simutils import H, L, PC, SP, T
    zx = s.zx
    r = zx.sim.registers
    zx.sim.trace(r[PC], ksym('kinit'), 0, r[T] + zxrun.FRAME * 600, 1,
                 None, None, None, None, None)
    if r[PC] != ksym('kinit'):
        raise Fail('the boot did not reach kinit')
    line = [l for l in zx.screen().splitlines() if 'kernel' in l]
    m = re.search(r'kernel (\d+)B free=(\d+)B procs=(\d+) ok', line[0] if line else '')
    if not m:
        raise Fail('no boot figures:\n' + zx.screen())
    sp = (r[SP] - 2) & 0xFFFF                     # call afreeb, return to kinit
    zx.mem[sp], zx.mem[sp + 1] = ksym('kinit') & 255, ksym('kinit') >> 8
    r[SP] = sp
    zx.sim.trace(ksym('afreeb'), ksym('kinit'), 0, r[T] + 1000000, 0,
                 None, None, None, None, None)
    free = r[H] * 256 + r[L]
    want = (ksym('kend') - 0x6000, free, ksym('NPROC'))
    got = tuple(int(x) for x in m.groups())
    if got != want:
        raise Fail('banner says kernel %d, free %d, procs %d; the kernel has %d, %d, %d'
                   % (got + want))


TESTS_BY_NAME = {f.__name__: f for f in TESTS}


def main():
    global VERBOSE
    args = sys.argv[1:]
    snap = os.path.join(ROOT, 'build', 'test.z80')
    only = None
    while args:
        a = args.pop(0)
        if a == '-k':
            only = args.pop(0).split(',')
        elif a == '-v':
            VERBOSE = True
        else:
            snap = a
    fails = 0
    t0 = time.time()
    for f in TESTS:
        if only and f.__name__ not in only:
            continue
        s = Session(snap)
        t = time.time()
        try:
            f(s)
            print('PASS %-18s %5.1fs  %6d frames' % (f.__name__, time.time() - t, s.zx.frames))
        except Fail as e:
            fails += 1
            print('FAIL %-18s %s' % (f.__name__, e))
    print('%d failed, %.1fs' % (fails, time.time() - t0))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
