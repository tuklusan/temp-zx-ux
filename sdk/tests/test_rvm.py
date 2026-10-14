#!/usr/bin/env python3
"""rvm's machine and its ZX-UX session: unit and system checks.

  python3 sdk/tests/test_rvm.py [-k NAME,...]

Needs only the SDK and the ZX-UX build (build/ZX-UX.tap, kernel.json).
rvm keeps its login cache in a temporary directory for the run.  The
machine's timing against an independent emulator is tests/rvm_machine.py
(it needs SkoolKit); the C48 corpus is tests/rvm_corpus.py; the window
is tests/rvm_gui.py.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(HERE)
ROOT = os.path.dirname(SDK)
sys.path.insert(0, SDK)
CACHE = tempfile.mkdtemp(prefix='rvm-cache-')
os.environ['ZXUX_RVM_CACHE'] = CACHE

import rvm                                         # noqa: E402
import rvmsound                                    # noqa: E402
import rtap                                        # noqa: E402
import zxmachine                                   # noqa: E402
import zxscreen                                    # noqa: E402
import zxux                                        # noqa: E402
from rcc import driver                             # noqa: E402

FAILS = []
TESTS = []
TMP = tempfile.mkdtemp(prefix='rvm-test-')


def test(f):
    TESTS.append(f)
    return f


def check(what, cond, detail=''):
    print('  %s %s%s' % ('ok  ' if cond else 'FAIL', what, '' if cond or not detail else ': ' + detail))
    if not cond:
        FAILS.append(what)
    return cond


def prog(name):
    out = os.path.join(TMP, name + '.ssx')
    if not os.path.exists(out):
        if driver.main([os.path.join(HERE, 'rvm', name + '.c'), '-o', out]):
            raise SystemExit('rcc failed for ' + name)
    return out


def state(m):
    c = m.cpu
    return (m.t, c.a, c._f, c.b, c.c, c.d, c.e, c.h, c.l, c.ix, c.iy, c.sp, c.pc, c.i,
            c.iff1, c.iff2, c.im, c.halted, c.af_, c.bc_, c.de_, c.hl_, bytes(m.mem))


def headless(args):
    return subprocess.run([sys.executable, os.path.join(SDK, 'bin', 'rvm'), '--headless'] + args,
                          capture_output=True, text=True, timeout=600)


# ------------------------------------------------------------------ machine
@test
def z80_coding():
    rnd = random.Random(1)
    cases = [bytes([0xED] * 3), bytes([0xED, 5, 5, 5, 5, 5, 5]), bytes([0xED]) + bytes(10),
             bytes([7]) * 300, bytes([0xED]) * 600, bytes(rnd.randrange(256) for _ in range(4000)),
             bytes(rnd.choice((0, 0xED, 1)) for _ in range(4000))]
    ok = all(zxmachine._z80_unpack(zxmachine._z80_pack(x), len(x)) == x for x in cases)
    check('.z80 run-length coding round-trips (runs, single and double EDh)', ok)
    p = zxmachine._z80_pack(bytes([0xED]) + bytes(10))
    check('the byte after a single EDh is never the start of a run', p[:2] == b'\xed\x00')


@test
def interrupts():
    def taken_after(code):
        m = zxmachine.Machine()
        m.mem[0x8000:0x8000 + len(code)] = bytes(code)
        c = m.cpu
        c.pc, c.im, c.sp = 0x8000, 1, 0xFF00
        c.iff1 = c.iff2 = False
        m.set_time(zxmachine.FRAME - 8)        # INT due 8 T-states later
        m.run(zxmachine.FRAME + 40)
        return m.mem[0xFEFE] | m.mem[0xFEFF] << 8
    check('an interrupt is not taken straight after EI (EI NOP: after the NOP)',
          taken_after([0xFB, 0x00, 0x00]) == 0x8002)
    check('nor after a second EI (EI EI NOP: after the NOP)',
          taken_after([0xFB, 0xFB, 0x00, 0x00]) == 0x8003)


@test
def snapshot_continues():
    s = zxux.Session(cache=False)
    s.boot()
    m1 = s.m
    for _ in range(3):
        s.step()
    halted = m1.cpu.halted
    m2 = zxmachine.Machine()
    m2.load_z80(m1.save_z80())
    m2.t = m1.t
    same = True
    for _ in range(100):
        m1.run_frame()
        m2.run_frame()
        if state(m1) != state(m2):
            same = False
            break
    check('a saved snapshot runs on exactly as the machine it was taken from '
          '(halted at the save: %s)' % halted, same)
    bad = False
    try:
        zxmachine.Machine().load_z80(b'\0' * 10)
    except ValueError:
        bad = True
    check('a truncated .z80 is refused', bad)


@test
def cache_is_exact():
    shutil.rmtree(CACHE, ignore_errors=True)
    s1 = zxux.Session()
    s1.boot()
    s2 = zxux.Session()
    s2.boot()
    check('the first boot reads the tape, the second the cache',
          s1.cache_hit is False and s2.cache_hit is True)
    booted = state(s1.m)
    check('the cached state is the booted state (T-states, registers, memory)',
          booted == state(s2.m))
    ssx = open(prog('exit7'), 'rb').read()
    j1 = s1.launch(ssx, 'exit7')
    j2 = s2.launch(ssx, 'exit7')
    same = True
    for _ in range(600):
        f1, f2 = s1.step(), s2.step()
        if f1.screen != f2.screen or state(s1.m) != state(s2.m):
            same = False
            break
        if j1.ended is not None and j2.ended is not None:
            break
    check('a program runs the same from the cache as after a boot', same and j1.status == 7
          and j2.status == 7 and j1.ended == j2.ended)
    # a cache entry that does not match is ignored, not trusted
    for f in os.listdir(CACHE):
        if f.endswith('.json'):
            open(os.path.join(CACHE, f), 'w').write('{"key": "x", "t": 1}')
    s3 = zxux.Session()
    s3.boot()
    check('a damaged cache entry is ignored and the system boots from the tape',
          s3.cache_hit is False and state(s3.m) == booted)
    # s3 wrote a good entry again: cut its snapshot short
    for f in os.listdir(CACHE):
        if f.endswith('.z80'):
            data = open(os.path.join(CACHE, f), 'rb').read()
            open(os.path.join(CACHE, f), 'wb').write(data[:200])
    s4 = zxux.Session()
    s4.boot()
    check('a truncated cache snapshot is ignored too', s4.cache_hit is False and state(s4.m) == booted)
    check('the system calls counted are the run\'s, not the boot\'s', s4.syscalls == 0)
    check('the shell at the prompt is known (programs are typed to it)', s4.reader is not None)


def rom_ld(block, flag, n, load=True, pulses=False, verify_with=None):
    """Call LD-BYTES (0556h) on a bare machine: by the trap, or by the ROM
    reading the block as EAR pulses -> (carry, IX, DE, memory 8000h..)."""
    m = zxmachine.Machine()
    m.mem[0x5C48] = 0x38                    # BORDCR: border 7
    for i in range(0x8000, 0x8000 + 600):
        m.mem[i] = verify_with[i - 0x8000] if verify_with and i - 0x8000 < len(verify_with) else 0
    c = m.cpu
    c.sp = 0xFF00
    m.mem[0xFF00], m.mem[0xFF01] = 0x00, 0xFE     # return to FE00h
    c.pc = zxmachine.LD_BYTES
    c.ix = 0x8000
    c.d, c.e = n >> 8, n & 255
    c.a = flag
    c._f = 1 if load else 0
    c.iy = 0x5C3A
    done = []

    def ret(mm):
        done.append(1)
        mm.stop_requested = True
        return False
    m.hooks[0xFE00] = ret
    if pulses:
        m.play_pulses([block])
    else:
        m.cassette = [block]
    m.run(m.t + 3500000 * 30)
    if not done:
        return None
    return (c._f & 1, c.ix, c.d << 8 | c.e, bytes(m.mem[0x8000:0x8000 + 600]), m.border, c.iff1)


@test
def tape_trap_is_the_rom():
    data = bytes(range(200))
    good = rtap.tap_block(0xFF, data)
    cases = [('a block that loads', good, 0xFF, 200, True),
             ('a flag that does not match', good, 0x00, 200, True),
             ('a block shorter than asked for', good, 0xFF, 250, True),
             ('a block longer than asked for', good, 0xFF, 150, True),
             ('a parity error', good[:-1] + bytes([good[-1] ^ 1]), 0xFF, 200, True),
             ('VERIFY of matching data', good, 0xFF, 200, False),
             ('VERIFY of different data', good, 0xFF, 200, False)]
    for what, blk, flag, n, load in cases:
        mem = None if load else (data if 'different' not in what else data[:77] + b'?' + data[78:])
        a = rom_ld(blk, flag, n, load, pulses=False, verify_with=mem)
        b = rom_ld(blk, flag, n, load, pulses=True, verify_with=mem)
        # carry, IX, DE, memory, border and interrupts: all as the ROM
        check('trap = ROM: %s (carry %s)' % (what, a and a[0]), a is not None and a == b,
              'trap %s rom %s' % (a and a[:3], b and b[:3]))
    m = zxmachine.Machine()
    c = m.cpu
    c.sp = 0xFF00
    m.mem[0xFF00], m.mem[0xFF01] = 0x00, 0xFE
    c.pc, c.ix, c.d, c.e, c.a = zxmachine.SA_BYTES, 0x8000, 0, 3, 0xFF
    m.mem[0x8000:0x8003] = b'abc'
    m.hooks[0xFE00] = lambda mm: setattr(mm, 'stop_requested', True) or False
    m.run(m.t + 1000000)
    check('SA-BYTES saves flag, data and parity', m.saved == [rtap.tap_block(0xFF, b'abc')])
    m = zxmachine.Machine()
    c = m.cpu
    c.pc = zxmachine.LD_BYTES
    c.sp = 0xFF00
    m.run(m.t + 1000)
    check('an empty cassette is left to the ROM (it waits for the tape)',
          m.tape_requests == 1 and c.pc >= 0x0556)


@test
def keyboard():
    for text, want in (('ab', [('keys', ('a',)), ('keys', ('b',))]),
                       ('A\\n', [('keys', ('CS', 'a')), ('keys', ('ENTER',))]),
                       ('{BREAK}{WAIT 7}', [('keys', ('CS', 'SPACE')), ('wait', 7)]),
                       ('{{x', [('keys', ('SS', 'f')), ('keys', ('x',))])):
        check('keys %r' % text, zxux.parse_keys(text) == want, str(zxux.parse_keys(text)))
    for bad in ('{WAIT -1}', '{NOPE}', '{BREAK', 'é'):
        try:
            zxux.parse_keys(bad)
            check('keys %r refused' % bad, False)
        except zxux.RvmError:
            check('keys %r refused' % bad, True)
    kb = zxux.Keyboard()
    kb.type('aab')
    seen = [kb.tick(f) for f in range(40)]
    downs = [f for f in range(40) if seen[f] and (f == 0 or seen[f - 1] != seen[f])]
    check('the same key again only after the ROM has let it go (6 frames)',
          downs[1] - (downs[0] + kb.hold) >= zxux.Keyboard.SETTLE, str(downs))
    kb = zxux.Keyboard()
    kb.type('abc')
    seen = [kb.tick(f) for f in range(40)]
    downs = [f for f in range(40) if seen[f] and (f == 0 or seen[f - 1] != seen[f])]
    check('a third key waits for a free KSTATE set',
          downs[2] >= downs[0] + kb.hold + zxux.Keyboard.SETTLE, str(downs))


@test
def typing_every_character():
    s = zxux.Session()
    s.boot()
    chars = ''.join(chr(c) for c in range(33, 127))
    lines = [chars[:47], chars[47:]]
    s.kb.type('cat > /tmp/k\n' + lines[0] + '\n' + lines[1] + '\n')
    s.kb.add([('keys', ('CS', '1'))])                       # EDIT: end of input
    s.wait_prompt()
    s.kb.type('cat /tmp/k\n')
    s.wait_prompt()
    rows = s.text().splitlines()
    i = max(n for n, r in enumerate(rows) if r.rstrip() == '# cat /tmp/k')
    got = [rows[i + 1].rstrip(), rows[i + 2].rstrip()]
    check('all 94 printable characters typed reach ZX-UX unchanged', got == lines,
          '%r' % got)


@test
def beeper_exact():
    s = zxux.Session()
    s.boot()
    calls = []

    def hook(m):
        c = m.cpu
        calls.append((c.h << 8 | c.l, m.t))
        return False
    s.m.hooks[0x03B5] = hook
    s.m.take_speaker()
    t0 = s.m.t
    job = s.launch(open(prog('beeps'), 'rb').read(), 'beeps')
    frames = []
    s.frame_hooks.append(lambda f: frames.append(f.number))
    while job.ended is None:
        s.step()
    edges = s.m.take_speaker()
    beeper = rvmsound.Beeper(t0)
    beeper.feed(edges)
    pcm = beeper.render(s.m.t)
    import struct
    samples = struct.unpack('<%dh' % (len(pcm) // 2), pcm)
    check('frames go on while BEEP runs with interrupts off (none skipped)',
          frames == list(range(frames[0], frames[0] + len(frames))))
    for (hl, t1), pitch, nxt in zip(calls, (0, 9, -20, 24.5), calls[1:] + [(0, s.m.t)]):
        seg = [e for e in edges if t1 <= e[0] < nxt[1]]
        per = rvmsound.edge_periods(seg)
        want = rvmsound.beeper_period(hl)
        check('BEEP %g: every period is the ROM\'s 8*HL+236 = %d T-states (%.2f Hz)'
              % (pitch, want, 3.5e6 / want), per and set(per) == {want}, str(sorted(set(per))[:5]))
        check('BEEP %g: HL %d is the ROM formula\'s (%d)' % (pitch, hl, rvmsound.rom_beep_hl(pitch)),
              abs(hl - rvmsound.rom_beep_hl(pitch)) <= 1)
        a = int((t1 - t0) * rvmsound.RATE / 3.5e6) + 50
        b = int((nxt[1] - t0) * rvmsound.RATE / 3.5e6) - 50
        seg = samples[a:b]
        mid = rvmsound.AMPLITUDE / 2
        ups = [i for i in range(1, len(seg)) if seg[i - 1] < mid <= seg[i]]
        if len(ups) > 2:
            f = rvmsound.RATE * (len(ups) - 1) / (ups[-1] - ups[0])
            check('BEEP %g: the WAV sounds at %.2f Hz (ROM %.2f Hz)' % (pitch, f, 3.5e6 / want),
                  abs(f - 3.5e6 / want) / (3.5e6 / want) < 0.005)


# --------------------------------------------------------------- the runner
def runner(path, args=(), keys='', frames=3000, **kw):
    o = rvm.Options()
    o.prog, o.args, o.keys, o.frames, o.headless = path, list(args), keys, frames, True
    for k, v in kw.items():
        setattr(o, k, v)
    r = rvm.Runner(o)
    r.start()
    while True:
        r.frame()
        why = r.check()
        if why:
            r.why = why
            return r
        if r.session.m.frame - r.start_frame >= frames:
            r.why = 'frames'
            return r


@test
def endings():
    r = runner(prog('exit7'))
    check('a program\'s exit status comes back (7)', r.why == 'exit' and r.status_code() == 7
          and 'exit7 here' in zxscreen.screen_text(r.picture()[0]))
    r = runner(prog('keys'), keys='abq')
    check('typed keys reach the program (2 keys, then q)', r.why == 'exit' and r.status_code() == 2)
    r = runner(prog('keys'), keys='ab')
    check('a program left waiting for keys stops the run as "input"', r.why == 'input'
          and r.status_code() == 0)
    r = runner(prog('spin'), keys='{WAIT 50}{BREAK}')
    check('BREAK kills the program: status 255', r.why == 'killed' and r.status_code() == 255
          and r.fg.status == 0xFFFF)
    o = rvm.Options()
    o.prog, o.headless = prog('exit7'), True
    r = rvm.Runner(o)
    r.start()
    r.session.m.cassette = []                     # the record is not on the tape
    for _ in range(3000):
        r.frame()
        r.why = r.check()
        if r.why:
            break
    check('a program not on the cassette ends the run as "tape" (status 1)',
          r.why == 'tape' and r.fg.started is None and r.status_code() == 1)


def big_prog():
    out = os.path.join(TMP, 'chess.ssx')
    if driver.main([os.path.join(ROOT, 'programs', 'c48', 'games', 'chess.c'), '-o', out]):
        raise SystemExit('rcc failed for chess')
    return out


@test
def frames_continuous():
    s = runner(prog('exit7')).session
    nums = []
    s.frame_hooks.append(lambda f: nums.append(f.number))
    for _ in range(300):
        s.step()
    check('every frame is produced, numbered one after another',
          nums == list(range(nums[0], nums[0] + 300)))
    check('FLASH changes phase every 16 frames',
          all(zxmachine.Frame(n, b'', 0, []).flash == (n >> 4) & 1 for n in range(64)))
    # a hook that moves the clock past two frame ends (as a long trapped
    # load once did) must not make a frame number go missing
    m = zxmachine.Machine()
    jumped = []

    def jump(mm):
        if not jumped:
            jumped.append(1)
            mm.t += 2 * zxmachine.FRAME + 100
        return False
    m.hooks[0x0000] = jump
    got = [m.run_frame().number for _ in range(5)]
    check('a clock jump of two frames still gives every frame number (%s)' % got,
          got == [0, 1, 2, 3, 4])
    # the real case: an 8.5 KB program loaded through the tape trap
    s = runner(os.path.join(TMP, 'chess.ssx') if os.path.exists(os.path.join(TMP, 'chess.ssx'))
               else big_prog()).session
    nums = []
    s.frame_hooks.append(lambda f: nums.append(f.number))
    job = s.jobs[-1]
    for _ in range(600):
        s.step()
        if job.started is not None and s.m.frame > job.started + 20:
            break
    check('loading an 8.5 KB program: it starts, every frame numbered one after another',
          job.started is not None and nums == list(range(nums[0], nums[0] + len(nums))))


@test
def tape_out():
    s = zxux.Session()
    s.boot()
    s.m.saved = []
    s.kb.type('tar cf /dev/cassette/x /etc/motd\n')
    s.wait_prompt()
    lines = rtap.list_blocks(s.m.saved)
    check('blocks saved on ZX-UX are captured (tar c to the cassette)',
          len(lines) == 3 and lines[0] == 'archive  /dev/cassette/x:'
          and lines[1].startswith('  - ') and lines[1].endswith(' /etc/motd')
          and lines[2].strip() == 'end of archive', '\n'.join(lines))
    path = os.path.join(TMP, 'out.tap')
    open(path, 'wb').write(zxmachine.tap_file(s.m.saved))
    check('--tape-out writes them as a .tap that reads back', rtap.read_tape(path) == s.m.saved)


def short_z80():
    path = os.path.join(TMP, 'short.z80')
    open(path, 'wb').write(bytes(40))
    return path


@test
def command_line():
    r = headless([prog('exit7')])
    check('rvm exits with the program\'s status (7)', r.returncode == 7, r.stderr)
    r = headless([prog('spin'), '--keys', '{WAIT 50}{BREAK}'])
    check('rvm exits 255 when BREAK killed the program', r.returncode == 255, r.stderr)
    r = headless([prog('exit7'), '--text', '--final'])
    check('--final shows the screen as ZX-UX left it (the prompt)',
          r.returncode == 7 and '\n#' in r.stdout, r.stdout[-200:])
    for args, msg in (([os.path.join(TMP, 'nope.ssx')], 'No such file'),
                      ([os.path.join(SDK, 'rvm.py')], 'not a valid SSX1'),
                      (['--frames', 'x', prog('exit7')], 'needs a number'),
                      (['--bogus', prog('exit7')], 'unknown option'),
                      (['--shell'], 'needs the window'),
                      (['--system', os.path.join(TMP, 'none.tap'), prog('exit7')],
                       'no ZX-UX system tape'),
                      ([prog('exit7'), 'a b'], 'cannot be typed'),
                      (['--snapshot', os.path.join(TMP, 'nope.z80'), prog('exit7')],
                       'No such file'),
                      (['--snapshot', short_z80(), prog('exit7')], 'truncated or damaged'),
                      ([prog('exit7'), '--keys', '\\x'], 'bad escape'),
                      ([prog('exit7'), '--tape', short_z80()], 'not a usable tape'),
                      ([prog('exit7'), '--png', os.path.join(TMP, 'no', 'dir', 'x.png')],
                       'No such file')):
        r = headless(args)
        check('rvm refuses %s (%s)' % (' '.join(os.path.basename(a) for a in args), msg),
              r.returncode == 2 and msg in r.stderr, r.stderr.strip())
    # a kernel.json that does not describe the tape's kernel
    d = os.path.join(TMP, 'sys')
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'build', 'ZX-UX.tap'), d)
    import json
    k = json.load(open(os.path.join(ROOT, 'build', 'kernel.json')))
    k['kernel_sha256'] = '0' * 64
    json.dump(k, open(os.path.join(d, 'kernel.json'), 'w'))
    r = headless(['--system', os.path.join(d, 'ZX-UX.tap'), prog('exit7')])
    check('rvm refuses a kernel.json made for another kernel',
          r.returncode == 2 and 'does not describe' in r.stderr, r.stderr.strip())
    open(os.path.join(d, 'kernel.json'), 'w').write('{"format": "zx-ux-kernel/1", ')
    r = headless(['--system', os.path.join(d, 'ZX-UX.tap'), prog('exit7')])
    check('rvm refuses a kernel.json that is not JSON',
          r.returncode == 2 and 'cannot be read' in r.stderr, r.stderr.strip())
    k = json.load(open(os.path.join(ROOT, 'build', 'kernel.json')))
    del k['symbols']['cur']
    json.dump(k, open(os.path.join(d, 'kernel.json'), 'w'))
    r = headless(['--system', os.path.join(d, 'ZX-UX.tap'), prog('exit7')])
    check('rvm refuses a kernel.json without an address it needs',
          r.returncode == 2 and 'missing or bad entry' in r.stderr, r.stderr.strip())
    r = headless(['--real-tape', prog('exit7')])
    check('--real-tape: the ROM loads the program from EAR pulses (status 7)',
          r.returncode == 7, r.stderr.strip())
    r = subprocess.run([sys.executable, os.path.join(SDK, 'bin', 'rvm'), '--syscall',
                        prog('exit7'), '--text'], capture_output=True, text=True, timeout=300)
    check('rvm --syscall still runs the fast system-call VM', r.returncode == 7
          and 'exit7 here' in r.stdout, r.stderr)


@test
def window_choice():
    o = rvm.parse([prog('exit7'), '--png', 'x.png'])
    check('an output option means no window', not rvm.want_window(o))
    o = rvm.parse([prog('exit7'), '--headless'])
    check('--headless means no window', not rvm.want_window(o))
    if sys.platform.startswith('linux'):
        old = os.environ.pop('DISPLAY', None), os.environ.pop('WAYLAND_DISPLAY', None)
        o = rvm.parse([prog('exit7')])
        check('no display: headless', not rvm.want_window(o))
        if old[0]:
            os.environ['DISPLAY'] = old[0]
        if old[1]:
            os.environ['WAYLAND_DISPLAY'] = old[1]


def main(argv):
    only = None
    if argv[:1] == ['-k']:
        only = set(argv[1].split(','))
    for f in TESTS:
        if only and f.__name__ not in only:
            continue
        print(f.__name__)
        f()
    print('%d failed' % len(FAILS))
    shutil.rmtree(CACHE, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
