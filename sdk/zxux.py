"""ZX-UX on the rvm machine: boot the real system tape, log in, run SSX1
programs from the cassette, and follow them through the system calls.

Nothing of the kernel is reimplemented here.  The system tape built from
src/ (build/ZX-UX.tap) is loaded by the 48K ROM, exactly as on a
Spectrum, and the kernel, shell and loader do all the work.  rvm only
types on the keyboard, plays the cassette, and observes:

  * system calls at 6003h, their arguments and their results: fork and
    wait give the program's pid and exit status, ssxload (40) its start,
    read(0) a program waiting for the keyboard;
  * a few kernel variables named in build/kernel.json (written by the
    build from the same assembly): the running slot, the pids and the
    screen owners.  They are read, never written.

The state after login is kept in a cache (a .z80 snapshot and the clock),
keyed by the ROM, the system tape, the user name and this file's
MACHINE_VERSION, so later runs start at the shell prompt at once.  A run
from the cache is the same, T-state for T-state, as one that booted.
"""
import hashlib
import json
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import zxmachine                                   # noqa: E402
from zxmachine import FRAME                        # noqa: E402
import zxscreen                                    # noqa: E402

MACHINE_VERSION = 'rvm-machine/1'
DEFAULT_SYSTEM = os.path.normpath(os.path.join(HERE, '..', 'build', 'ZX-UX.tap'))

# system calls rvm follows (src/unix.asm systab)
SYS_EXIT, SYS_FORK, SYS_READ, SYS_WAIT, SYS_SCREEN, SYS_SSXLOAD = 1, 2, 3, 7, 39, 40

INPUT_IDLE = 50            # frames a program waits for keys before 'input'


class RvmError(Exception):
    pass


# ------------------------------------------------------------------ system
def read_tape(path):
    """Blocks (flag + data + parity) of a .tap or standard-speed .tzx."""
    try:
        data = open(path, 'rb').read()
        if data[:8] == b'ZXTape!\x1a':
            import rtap
            return [b for _, b in rtap.tzx_blocks(data)[1]]
        return zxmachine.tap_blocks(data)
    except OSError as e:
        raise RvmError('%s: %s' % (path, e.strerror))
    except (ValueError, IndexError, SystemExit) as e:
        raise RvmError('%s: not a usable tape (%s)' % (path, e))


class SystemImage:
    """The ZX-UX boot tape and its kernel.json, checked against each other."""

    def __init__(self, tape=None, kernel_json=None):
        self.tape = os.path.abspath(tape or DEFAULT_SYSTEM)
        if not os.path.isfile(self.tape):
            raise RvmError('no ZX-UX system tape at %s (build it with tools/build.py, '
                           'or give --system)' % self.tape)
        self.blocks = read_tape(self.tape)
        kj = kernel_json or os.path.join(os.path.dirname(self.tape), 'kernel.json')
        if not os.path.isfile(kj):
            raise RvmError('no kernel.json next to %s (tools/build.py writes it)' % self.tape)
        try:
            info = json.load(open(kj))
        except (OSError, ValueError) as e:
            raise RvmError('%s: cannot be read (%s)' % (kj, e))
        if not isinstance(info, dict) or info.get('format') != 'zx-ux-kernel/1':
            raise RvmError('%s: not a zx-ux-kernel/1 file' % kj)
        kern = self._kernel_block()
        got = hashlib.sha256(kern).hexdigest()
        if got != info.get('kernel_sha256'):
            raise RvmError('%s does not describe the kernel on %s (tape kernel sha256 %s); '
                           'rebuild with tools/build.py' % (kj, self.tape, got[:16]))
        try:
            self.sym = {k: int(info['symbols'][k]) for k in
                        ('NPROC', 'SFREE', 'p_stat', 'p_pid', 'cur', 'scrown')}
            self.syscall = int(info['syscall'])
        except (KeyError, TypeError, ValueError) as e:
            raise RvmError('%s: missing or bad entry %s' % (kj, e))
        self.info = info
        h = hashlib.sha256()
        for b in self.blocks:
            h.update(struct.pack('<H', len(b)) + b)
        self.sha256 = h.hexdigest()

    def _kernel_block(self):
        b = self.blocks
        for i in range(len(b) - 1):
            if b[i][0] == 0 and len(b[i]) == 19 and b[i][1] == 3 \
                    and b[i][2:12].rstrip(b' ') == b'unix' and b[i + 1][0] == 0xFF:
                return b[i + 1][1:-1]
        raise RvmError('%s: no "unix" code block' % self.tape)


# ---------------------------------------------------------------- keyboard
# character -> keys, in ZX-UX's L mode (as the tests type, tools/zxrun.py)
SYM = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '&': '6', "'": '7',
       '(': '8', ')': '9', '_': '0', '<': 'r', '>': 't', ';': 'o', '"': 'p',
       '^': 'h', '-': 'j', '+': 'k', '=': 'l', ':': 'z', '?': 'c', '/': 'v',
       '*': 'b', ',': 'n', '.': 'm', '`': 'x',     # (code 60h: the ROM's pound)
       # keyword tokens the tty maps back to ASCII (src/dev.asm toktab)
       '~': 'a', '|': 's', '\\': 'd', '{': 'f', '}': 'g', '[': 'y', ']': 'u'}
NAMED = {'BREAK': ('CS', 'SPACE'), 'EDIT': ('CS', '1'), 'DELETE': ('CS', '0'),
         'LEFT': ('CS', '5'), 'DOWN': ('CS', '6'), 'UP': ('CS', '7'),
         'RIGHT': ('CS', '8'), 'ENTER': ('ENTER',), 'SPACE': ('SPACE',)}


def char_keys(ch):
    if ch == '\n':
        return ('ENTER',)
    if ch == ' ':
        return ('SPACE',)
    if ch == '\b':
        return ('CS', '0')
    if ch.isascii() and (ch.isdigit() or ch.islower()):
        return (ch,)
    if ch.isascii() and ch.isupper():
        return ('CS', ch.lower())
    if ch in SYM:
        return ('SS', SYM[ch])
    raise RvmError('cannot type %r on a Spectrum' % ch)


def parse_keys(text):
    """--keys text -> actions: ('keys', combo) and ('wait', frames).
    Escapes: \\n ENTER, \\b DELETE; {BREAK} {EDIT} {DELETE} {UP} {DOWN}
    {LEFT} {RIGHT} {ENTER} {SPACE}, {WAIT n} (n frames), {{ for {."""
    try:
        text = text.encode('latin-1', 'backslashreplace').decode('unicode_escape')
    except UnicodeDecodeError as e:
        raise RvmError('bad escape in keys: %s' % e.reason)
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '{':
            if text.startswith('{{', i):
                out.append(('keys', char_keys('{')))
                i += 2
                continue
            j = text.find('}', i)
            if j < 0:
                raise RvmError('unclosed { in keys')
            word = text[i + 1:j].strip()
            if word.upper().startswith('WAIT'):
                try:
                    n = int(word[4:])
                except ValueError:
                    raise RvmError('bad {%s} in keys' % word)
                if not 0 <= n <= 1000000:
                    raise RvmError('bad {%s} in keys' % word)
                out.append(('wait', n))
            elif word.upper() in NAMED:
                out.append(('keys', NAMED[word.upper()]))
            else:
                raise RvmError('unknown key {%s}' % word)
            i = j + 1
            continue
        out.append(('keys', char_keys(c)))
        i += 1
    return out


class Keyboard:
    """Presses key combinations on the matrix, one at a time, on frame
    boundaries.  The ROM's KEYBOARD routine (which ZX-UX calls every
    frame) keeps a released key in one of its two KSTATE sets for five
    more frames, so a key can only be seen again after that, and a third
    key only when a set is free: the schedule obeys both rules.

    hold, gap: frames a combination is held, and the least gap after it.
    compat=True types as tools/zxrun.py (hold 4, gap 7, nothing else)."""
    SETTLE = 6

    def __init__(self, hold=2, gap=3, compat=False):
        if compat:
            hold, gap = 4, 7
        if hold < 1 or gap < 1:
            raise RvmError('key hold and gap must be at least one frame')
        self.hold, self.gap, self.compat = hold, gap, compat
        self.queue = []
        self.current = ()
        self.until = 0             # frame the current press / gap ends
        self.state = 'idle'        # idle, held, gap
        self.released = {}         # main key -> frame it was let go

    def add(self, actions):
        """Actions: ('keys', combo), ('press', combo, frames) to hold it
        longer than usual, ('wait', frames)."""
        self.queue.extend(actions)

    def type(self, text):
        self.queue.extend(('keys', char_keys(c)) for c in text)

    def busy(self):
        return bool(self.queue) or self.state != 'idle'

    @staticmethod
    def _main(combo):
        m = [k for k in combo if k not in ('CS', 'SS')]
        return m[0] if m else combo[0]

    def _can_press(self, combo, frame):
        if self.compat:
            return True
        main = self._main(combo)
        if frame < self.released.get(main, -99) + self.SETTLE:
            return False
        busy = [k for k, f in self.released.items() if k != main and frame < f + self.SETTLE]
        return len(busy) < 2

    def tick(self, frame):
        """The keys to hold during this frame."""
        while True:
            if self.state == 'held':
                if frame < self.until:
                    return self.current
                for k in self.current:
                    if k not in ('CS', 'SS'):
                        self.released[k] = frame
                self.state = 'gap'
                self.until = frame + self.gap
            if self.state == 'gap':
                if frame < self.until:
                    return ()
                self.state = 'idle'
            if not self.queue:
                return ()
            act = self.queue[0]
            kind, arg = act[0], act[1]
            if kind == 'wait':
                self.queue.pop(0)
                self.state = 'gap'
                self.until = frame + arg
                continue
            if not self._can_press(arg, frame):
                return ()
            self.queue.pop(0)
            self.current = tuple(arg)
            self.state = 'held'
            self.until = frame + (act[2] if kind == 'press' else self.hold)


# -------------------------------------------------------------------- jobs
class Job:
    """A program started from the shell: /dev/cassette/NAME args [&]."""

    def __init__(self, name, args, background):
        self.name = name
        self.args = list(args)
        self.background = background
        self.pid = None
        self.loading = None        # frame /etc/ldx called sys ssxload
        self.parent = None         # pid of the shell it was typed to
        self.started = None        # frame of the program's own first system
                                   # call (the load is done, it runs)
        self.ended = None          # frame its parent's wait returned
        self.status = None         # exit status word (FFFF: killed)
        self.picture = None        # (screen, border) as it last owned the screen
        self.exit_picture = None   # the screen as it gave the screen back
                                   # (sys screen 0 or exit, if it owned it)
        self.owned = False
        self.reading_since = None  # frame it began waiting in read(0)

    @property
    def command(self):
        return ' '.join(['/dev/cassette/' + self.name] + self.args) + (' &' if self.background else '')

    def describe(self):
        if self.status is None:
            return 'running' if self.started is not None else 'not started'
        if self.status == 0xFFFF:
            return 'killed (BREAK)'
        return 'exit %d' % self.status


# ----------------------------------------------------------------- session
def cache_dir():
    d = os.environ.get('ZXUX_RVM_CACHE')
    if d:
        return d
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return os.path.join(os.environ['LOCALAPPDATA'], 'zx-ux-rvm')
    return os.path.join(os.path.expanduser('~'), '.cache', 'zx-ux-rvm')


class Session:
    def __init__(self, system=None, kernel_json=None, user='root', cache=True,
                 snapshot=None, keyboard=None, log=None):
        if not 1 <= len(user) <= 8 or not all(c.isascii() and (c.isalnum()) for c in user):
            raise RvmError('user name must be 1 to 8 letters or digits: %r' % user)
        self.system = SystemImage(system, kernel_json)
        self.user = user
        self.use_cache = cache
        self.snapshot = snapshot
        self.m = zxmachine.Machine()
        self.kb = keyboard or Keyboard()
        self.log = log
        s = self.system.sym
        self._p_pid, self._p_stat, self._cur = s['p_pid'], s['p_stat'], s['cur']
        self._scrown, self._nproc, self._sfree = s['scrown'], s['NPROC'], s['SFREE']
        self.m.hooks[self.system.syscall] = self._on_syscall
        self.jobs = []
        self._unforked = []
        self._watch = {}           # return address -> [entries]
        self.syscalls = 0
        self.reader = None         # pid last seen reading the terminal (the
                                   # shell at its prompt)
        self.frame_hooks = []
        self.cache_hit = None

    # ------------------------------------------------------------ helpers
    def say(self, msg):
        if self.log:
            self.log(msg)

    def text(self):
        return zxscreen.screen_text(self.m.screen())

    def last_line(self):
        rows = [l for l in self.text().splitlines()[:23] if l.strip()]
        return rows[-1] if rows else ''

    def word(self, a):
        return self.m.mem[a] | self.m.mem[a + 1] << 8

    def current_pid(self):
        return self.word(self._p_pid + 2 * self.m.mem[self._cur])

    def slot_of(self, pid):
        for i in range(self._nproc):
            if self.m.mem[self._p_stat + i] != self._sfree and self.word(self._p_pid + 2 * i) == pid:
                return i
        return None

    def owns_screen(self, pid):
        slot = self.slot_of(pid)
        return slot is not None and bool(self.m.mem[self._scrown] >> slot & 1)

    # ----------------------------------------------------------- running
    def step(self):
        """Run one frame (with the keys due in it); return its Frame."""
        m = self.m
        m.press(self.kb.tick(m.frame))
        f = m.run_frame()
        if f is None:
            raise RvmError('the machine was stopped inside a frame')
        for job in self.jobs:
            if job.pid is not None and job.started is not None and job.ended is None:
                if self.owns_screen(job.pid):
                    job.picture = (f.screen, f.last_border())
                    job.owned = True
        for h in self.frame_hooks:
            h(f)
        return f

    def run_until(self, cond, frames, what):
        for _ in range(frames):
            if cond():
                return
            self.step()
        if not cond():
            raise RvmError('timed out after %d frames waiting for %s\n%s' % (frames, what, self.text()))

    # -------------------------------------------------------- system calls
    def _on_syscall(self, m):
        cpu = m.cpu
        mem = m.mem
        self.syscalls += 1
        a = cpu.a
        sp = cpu.sp
        ret = mem[sp] | mem[(sp + 1) & 0xFFFF] << 8
        pid = self.current_pid()
        if a == SYS_FORK and self._unforked and self._unforked[0].parent in (None, pid):
            self._expect(ret, sp, 'fork', pid)
        elif a == SYS_WAIT:
            self._expect(ret, sp, 'wait', pid)
        if a != SYS_SSXLOAD:
            job = self._job(pid)
            if job is not None and job.loading is not None and job.started is None:
                job.started = m.frame
                self.say('%s running (pid %d)' % (job.name, pid))
        if a == SYS_SSXLOAD:
            job = self._job(pid)
            if job is not None and job.loading is None:
                job.loading = m.frame
                self.say('%s loading (pid %d)' % (job.name, pid))
        elif a == SYS_EXIT or (a == SYS_SCREEN and (cpu.h << 8 | cpu.l) == 0):
            # the program's last picture: taken before the kernel gives the
            # screen to the console (white on black, the prompt below)
            job = self._job(pid)
            if job is not None and job.started is not None and self.owns_screen(pid):
                job.exit_picture = (m.screen(), m.border)
        elif a == SYS_READ and (cpu.h << 8 | cpu.l) == 0:
            job = self._job(pid)
            if job is None:
                self.reader = pid
            elif job.started is not None:
                job.reading_since = m.frame
                self._expect(ret, sp, 'read', pid)
        return False

    def _job(self, pid):
        for j in self.jobs:
            if j.pid == pid and j.ended is None:
                return j
        return None

    def _expect(self, ret, sp, kind, pid):
        lst = self._watch.setdefault(ret, [])
        lst.append((sp + 2, kind, pid))
        self.m.hooks[ret] = self._on_return

    def _on_return(self, m):
        cpu = m.cpu
        pc = cpu.pc
        lst = self._watch.get(pc, [])
        pid = self.current_pid()
        for i, (sp, kind, who) in enumerate(lst):
            if sp != cpu.sp or who != pid:
                continue
            failed = cpu._f & 1
            hl = cpu.h << 8 | cpu.l
            if kind == 'fork':
                if not failed and hl == 0:
                    continue                 # the child: its parent's return counts
                del lst[i]
                if not failed and self._unforked and self._unforked[0].parent in (None, who):
                    job = self._unforked.pop(0)
                    job.pid = hl
                    self.say('%s forked as pid %d' % (job.name, hl))
            elif kind == 'wait':
                del lst[i]
                if not failed:
                    for job in self.jobs:
                        if job.pid == hl and job.ended is None:
                            job.status = cpu.d << 8 | cpu.e
                            job.ended = m.frame
                            self.say('%s ended: %s' % (job.name, job.describe()))
            elif kind == 'read':
                del lst[i]
                job = self._job(who)
                if job is not None:
                    job.reading_since = None
            break
        if not lst:
            self._watch.pop(pc, None)
            m.hooks.pop(pc, None)
        return False

    # ---------------------------------------------------------------- boot
    def boot(self):
        """Start at the shell prompt: from the cache, a snapshot, or the tape."""
        if self.snapshot:
            try:
                self.m.load_z80(open(self.snapshot, 'rb').read())
            except (OSError, ValueError) as e:
                raise RvmError('%s: %s' % (self.snapshot, getattr(e, 'strerror', None) or e))
            self.cache_hit = False
            self._login()
            self.syscalls = 0
            return
        key = self._cache_key()
        path = os.path.join(cache_dir(), key + '.z80')
        if self.use_cache and os.path.isfile(path) and os.path.isfile(path + '.json'):
            try:
                meta = json.load(open(path + '.json'))
                self.m.load_z80(open(path, 'rb').read())
                if meta.get('key') != key or self.m.t != meta['t'] % FRAME:
                    raise ValueError('cache entry does not match')
                self.m.set_time(meta['t'])
                self.reader = meta.get('reader')
                self.cache_hit = True
                self.syscalls = 0
                self.say('started from the cache (%s)' % path)
                return
            except (ValueError, KeyError, TypeError, OSError) as e:
                self.say('cache entry ignored: %s' % e)
                self.m = self._fresh_machine()
        self.cache_hit = False
        self._cold_boot()
        self._login()
        if self.use_cache:
            self._save_cache(path, key)
        self.syscalls = 0

    def _fresh_machine(self):
        m = zxmachine.Machine()
        m.hooks[self.system.syscall] = self._on_syscall
        return m

    def _cache_key(self):
        h = hashlib.sha256()
        h.update(MACHINE_VERSION.encode())
        h.update(bytes(self.m.mem[:0x4000]))
        h.update(self.system.sha256.encode())
        h.update(self.user.encode())
        h.update(repr((self.kb.hold, self.kb.gap, self.kb.compat)).encode())
        return h.hexdigest()[:32]

    def _save_cache(self, path, key):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = self.m.save_z80()
            for name, blob in ((path, data),
                               (path + '.json', json.dumps({'key': key, 't': self.m.t, 'reader': self.reader,
                                                            'system': self.system.tape}).encode())):
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
                with os.fdopen(fd, 'wb') as f:
                    f.write(blob)
                os.replace(tmp, name)
        except (OSError, ValueError) as e:
            self.say('could not write the cache: %s' % e)

    def _rom_row(self, row):
        mem = self.m.mem
        glyph = {bytes(mem[0x3D00 + i * 8:0x3D08 + i * 8]): chr(32 + i) for i in range(96)}
        s = ''
        for c in range(32):
            a = 0x4000 + ((row & 0x18) << 8) + ((row & 7) << 5) + c
            s += glyph.get(bytes(mem[a + (i << 8)] for i in range(8)), '?')
        return s

    def _cold_boot(self):
        m = self.m
        m.reset()
        self.say('cold boot: ROM, then LOAD "" from %s' % self.system.tape)
        self.run_until(lambda: 'Sinclair' in self._rom_row(23), 400, 'the ROM')
        m.cassette = list(self.system.blocks)
        m.trap_tape = True
        # K mode: J is LOAD; SYMBOL SHIFT + P is "
        self.kb.add([('keys', ('j',)), ('keys', ('SS', 'p')), ('keys', ('SS', 'p')),
                     ('keys', ('ENTER',))])
        self.run_until(lambda: 'login:' in self.text(), 6000, 'the login prompt')
        if m.cassette:
            raise RvmError('the system tape was not read to its end')

    def _login(self):
        self.run_until(lambda: self.last_line().rstrip().endswith('login:'), 6000, 'login:')
        self.kb.type(self.user + '\n')
        self.wait_prompt()

    def wait_prompt(self, frames=6000):
        """Run until the shell prompt is the last line (and stays)."""
        def ready():
            if self.kb.busy() or self.last_line() not in ('#', '@'):
                return False
            for _ in range(10):
                self.step()
            return self.last_line() in ('#', '@')
        self.run_until(ready, frames, 'the shell prompt')

    # ------------------------------------------------------------ programs
    def launch(self, ssx, name, args=(), background=False, extra_blocks=()):
        """Put the program on the cassette and type its command."""
        import rtap
        for a in args:
            if not a or any(c in a for c in ' \n&;<>|') or not all(32 < ord(c) < 127 for c in a):
                raise RvmError('argument %r cannot be typed to the shell' % a)
        blocks = rtap.records(ssx, name)
        job = Job(name, args, background)
        job.parent = self.reader
        self.m.cassette.extend(blocks)
        self.m.cassette.extend(extra_blocks)
        self.jobs.append(job)
        self._unforked.append(job)
        self.kb.type(job.command + '\n')
        return job

    def program_screen(self, job):
        """The program's last picture (screen, border): as it gave the
        screen back (sys screen 0, or exit), else the last frame it owned
        it (BREAK); None if it never owned the screen."""
        return job.exit_picture or job.picture


def program_name(path):
    base = os.path.splitext(os.path.basename(path))[0]
    name = ''.join(c for c in base if c.isascii() and 32 < ord(c) < 127 and c not in '/&;<>|')
    return name[:10] or 'prog'
