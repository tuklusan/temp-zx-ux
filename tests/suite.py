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
    """an unpack that runs out of blocks packs other files meanwhile"""
    s.login()
    s.sh('cp /usr/doc/zxpack /tmp/a')          # raw 11 blocks, packable
    s.expect('zxpack /usr/doc/zxpack', '1293 -> 584 bytes', frames=60000)
    sum_a = s.sh('sum /tmp/a', frames=20000)
    def free():
        out = s.sh('df')
        return int(re.search(r'(\d+) bytes free', '\n'.join(out)).group(1))
    # fill the arena until the 1293 raw bytes of the doc no longer fit
    n = 0
    while free() > 1300 and n < 5:
        s.sh('cp /tmp/a /tmp/f%d' % n, frames=20000)
        n += 1
    if free() > 1300:
        s.sh('cp /usr/doc/tar /tmp/g', frames=20000)
    s.expect('wc /usr/doc/zxpack', re.compile(r'38 +213 +1293 /usr/doc/zxpack'),
             frames=200000)
    s.sh('rm /tmp/g')
    s.expect('ls -l /usr/doc/zxpack', re.compile(r's.rw.. 1 +1293 '))
    # the blocks came from packing closed files during the unpack
    s.expect('ls -l /tmp', re.compile(r'^z', re.M))
    s.expect('sum /tmp/a', *sum_a, frames=60000)
    for i in range(n):
        s.expect('cmp /tmp/a /tmp/f%d' % i, absent=('differ', 'EOF'),
                 frames=60000)


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
