#!/usr/bin/env python3
"""rvm's Spectrum against the SkoolKit simulator the ZX-UX tests trust.

  python3 tests/rvm_machine.py [--only a,b] [--every N] [-v]

For every scripted session of the C48 corpus (sdk/tests/runs.json, as
tests/ssxrun.py runs them), both machines start from build/test.z80 and
are driven by the same script, frame by frame: log in, type
/dev/cassette/NAME, play the program's records as EAR pulses (so the ROM
loads them bit by bit), type the scripted keys, run until the program
gives the screen back.  The script's decisions are taken from the
SkoolKit machine and applied to both.  Every N frames (default 25) and
at the end, the registers, the T-state count and all of RAM must be
identical; the first difference fails the session with its frame.

This proves zxmachine.py's Z80 timing, interrupts, keyboard matrix and
EAR input on the whole corpus, independently of rvm's own tape trap and
typing (tests/rvm_corpus.py proves those on the same programs).

Two known differences between the two Z80s are taken out first.
rvm's core (z80-python) models two internal registers of the Zilog NMOS
Z80 that SkoolKit 10.1 does not, and they show in the undocumented X/Y
flags (F bits 3 and 5):

  SCF, CCF      X/Y from A alone when the instruction before changed the
                flags, from F OR A when it did not (the "Q" register).
                SkoolKit: always from A (simtables.SCF, CCF).
  BIT b,(HL)    X/Y from the high byte of the internal WZ ("MEMPTR")
                register.  SkoolKit: from the byte tested.

z80-python checks both against the SingleStepTests (SST 37.json,
3f.json, cb 46.json ...) and hardware tests (z80ccf, z80memptr).  In the
corpus they differ in practice (hanoi: LD (HL),A; SCF at DB32h; the ROM's
BIT 7,(HL) at 02C6h), and a flag difference then spreads to RAM through
PUSH AF and the interrupt routine.  So the machine under test runs
SkoolKit's versions of these instructions (use_skoolkit_flags below;
real_flags_kept() shows rvm's own machines still have the Zilog ones);
everything else is compared unchanged.
"""
import functools
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'sdk'), HERE]
import zxrun                       # noqa: E402
import zxmachine                   # noqa: E402
import rtap                        # noqa: E402
from rcc import driver             # noqa: E402
from skoolkit.simutils import A, F, B, C, D, E, H, L, IXh, IXl, IYh, IYl, SP, I, PC, T  # noqa: E402

RUNS = json.load(open(os.path.join(ROOT, 'sdk', 'tests', 'runs.json')))
SCROWN = 0x5B63
FRAME = zxmachine.FRAME


class Diverged(Exception):
    pass


def skoolkit_scf_ccf(cpu, opcode):
    """SCF (37h) / CCF (3Fh) as SkoolKit 10.1's simtables.SCF and CCF: X/Y from A."""
    f = cpu._f
    if opcode == 0x37:
        low = 0x01                                  # C set, H reset
    else:
        low = 0x10 if f & 1 else 0x01              # H = old C, C = not old C
    cpu._f = (f & 0xC4) | (cpu.a & 0x28) | low
    cpu.q = cpu._f
    return 4


def skoolkit_bit_hl(cpu, sub_opcode):
    """BIT b,(HL) (CB 46h + 8b) as SkoolKit 10.1's bit_hl: X/Y from the byte."""
    value = cpu.read_byte((cpu.h << 8) | cpu.l)
    tested = value & (1 << ((sub_opcode >> 3) & 7))
    cpu._f = (cpu._f & 0x01) | 0x10 | (value & 0x28) | (tested & 0x80) | (0 if tested else 0x44)
    cpu.q = cpu._f
    return 12


def use_skoolkit_flags(machine):
    """Make one machine's SCF, CCF (also after a DD/FD prefix) and BIT b,(HL)
    follow SkoolKit.  The dispatch pages are copied first: z80-python
    shares them between all its CPUs."""
    cpu = machine.cpu
    cpu._main_page = list(cpu._main_page)
    cpu._cb_page = list(cpu._cb_page)
    for op in (0x37, 0x3F):
        cpu._main_page[op] = (skoolkit_scf_ccf, op)
        cpu.run_page[op] = functools.partial(skoolkit_scf_ccf, cpu, op)
    for b in range(8):
        op = 0x46 | b << 3
        cpu._cb_page[op] = (skoolkit_bit_hl, op)


def flags_after(code, a, f, wz, skool):
    m = zxmachine.Machine()
    if skool:
        use_skoolkit_flags(m)
    m.mem[0x8000:0x8000 + len(code) + 1] = bytes(code) + b'\x76'      # ...; HALT
    m.mem[0x9000] = 0x80
    c = m.cpu
    c.pc, c.a, c._f, c.h, c.l, c.q, c.wz = 0x8000, a, f, 0x90, 0x00, 0, wz
    c.iff1 = c.iff2 = False
    m.t = 100
    while not c.halted:
        m.run(m.t + 4)
    return c._f


def real_flags_kept():
    """rvm's own machine has the Zilog rules, a changed one SkoolKit's,
    and a machine made after a changed one is not changed."""
    cases = (([0x77, 0x37], 0x40, 0x08, 0, (0x09, 0x01)),      # LD (HL),A; SCF
             ([0x77, 0x3F], 0x40, 0x09, 0, (0x18, 0x10)),      # LD (HL),A; CCF
             ([0xCB, 0x7E], 0x00, 0x00, 0x2800, (0xB8, 0x90)))  # BIT 7,(HL), byte 80h
    for code, a, f, wz, want in cases:
        got = (flags_after(code, a, f, wz, False), flags_after(code, a, f, wz, True),
               flags_after(code, a, f, wz, False))
        if got != (want[0], want[1], want[0]):
            print('FAIL flag rules: %s gives %s, want %s' % (bytes(code).hex(' '), got, want))
            return False
    return True


class Pair:
    def __init__(self, snap):
        self.ref = zxrun.ZX(snap)
        self.me = zxmachine.Machine()
        use_skoolkit_flags(self.me)         # see the module's docstring
        self.me.load_z80(open(snap, 'rb').read())
        self.me.trap_tape = False          # the ROM loads from EAR pulses
        self.frame = 0
        self.every = 25
        self.checks = 0

    def run(self, n, keys=()):
        ref, me = self.ref, self.me
        for _ in range(n):
            ref.tr.pressed = set(keys)
            me.press(keys)
            ref.run(1)
            me.run(me.t + FRAME)
            self.frame += 1
            if self.frame % self.every == 0:
                self.compare()

    def compare(self):
        r = self.ref.sim.registers
        c = self.me.cpu
        mine = (self.me.t, c.a, c._f, c.b, c.c, c.d, c.e, c.h, c.l, c.ix >> 8, c.ix & 255,
                c.iy >> 8, c.iy & 255, c.sp, c.i, (c.pc - c.halted) & 0xFFFF)
        theirs = (r[T], r[A], r[F], r[B], r[C], r[D], r[E], r[H], r[L], r[IXh], r[IXl],
                  r[IYh], r[IYl], r[SP], r[I], r[PC])
        self.checks += 1
        if mine != theirs:
            raise Diverged('frame %d: registers (T A F B C D E H L IXh IXl IYh IYl SP I PC)\n'
                           '  rvm      %s\n  SkoolKit %s' % (self.frame, mine, theirs))
        a = self.ref.mem[0x4000:0x10000]
        b = self.me.mem[0x4000:0x10000]
        if list(a) != list(b):
            first = next(i for i in range(len(a)) if a[i] != b[i]) + 0x4000
            raise Diverged('frame %d: memory differs first at %04X' % (self.frame, first))

    def type(self, text):
        for ch in text:                    # as zxrun.ZX.type: 4 held, 7 apart
            self.run(4, zxrun.keys_for(ch))
            self.run(7)

    def text(self):
        return self.ref.screen()

    def last_line(self):
        rows = [l for l in self.text().splitlines()[:23] if l.strip()]
        return rows[-1] if rows else ''

    def until(self, cond, limit, what):
        for _ in range(limit // 10):
            if cond():
                return
            self.run(10)
        if not cond():
            raise Diverged('timed out waiting for %s (both machines agree so far)' % what)

    def tape(self, blocks):
        t = self.ref.sim.registers[T]
        if t != self.me.t:
            raise Diverged('T-states differ before the tape: %d %d' % (t, self.me.t))
        self.ref.tr.edges = zxrun.tape_pulses(blocks, t + 350000)
        self.me.pulses = zxmachine.tape_pulses(blocks, t + 350000)
        if self.ref.tr.edges != self.me.pulses:
            raise Diverged('the two pulse trains differ')


def session(name, run, every, verbose):
    src = os.path.join(ROOT, 'programs', 'c48', run['dir'], run.get('src', name.split(':')[0]) + '.c')
    out = os.path.join(ROOT, 'build', 'ssx', 'rvm-' + run.get('src', name.split(':')[0]) + '.ssx')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if driver.main([src, '-o', out]):
        return False, 'compile failed', 0
    ssx = open(out, 'rb').read()
    tname = name.split(':')[0][:10]
    p = Pair(os.path.join(ROOT, 'build', 'test.z80'))
    p.every = every
    p.until(lambda: p.last_line().rstrip().endswith('login:'), 3000, 'login:')
    p.type('root\n')
    p.until(lambda: p.last_line() in ('#', '@'), 6000, 'the prompt')
    p.run(10)
    cmd = ' '.join(['/dev/cassette/' + tname] + run.get('args', []))
    p.type(cmd + '\n')
    p.tape(rtap.records(ssx, tname))
    mem = p.ref.mem
    load = (len(ssx) * 20600 + 32000000) // FRAME + 400
    st = {'seen': False, 'gone': False}

    def watch(n):
        for _ in range(n):
            if mem[SCROWN]:
                st['seen'] = True
            elif st['seen']:
                st['gone'] = True
                return
            p.run(1)
    watch(load)
    if not st['seen']:
        return False, 'did not start (both machines agree)', p.frame
    keys = run.get('keys', '').encode().decode('unicode_escape')
    for ch in keys:
        watch(run.get('keygap', 100))
        if st['gone']:
            break
        p.type(ch)
    if not st['gone']:
        watch(run.get('zxux_frames', max(1500, int(run.get('frames', 6000) * 1.5))))
    p.compare()
    return True, 'identical for %d frames (%d checks)%s' % (
        p.frame, p.checks, '' if st['gone'] else ', still running at the end'), p.frame


def main(argv):
    only = None
    every = 25
    verbose = False
    i = 0
    while i < len(argv):
        if argv[i] == '--only':
            only = set(argv[i + 1].split(','))
            i += 2
        elif argv[i] == '--every':
            every = int(argv[i + 1])
            i += 2
        elif argv[i] == '-v':
            verbose = True
            i += 1
        else:
            raise SystemExit('unknown option ' + argv[i])
    if not real_flags_kept():
        return 1
    ok = total = frames = 0
    for name, run in RUNS.items():
        if only and name not in only and name.split(':')[0] not in only:
            continue
        if run.get('ZX-UX') == 'skip':
            continue
        t = time.time()
        try:
            good, why, n = session(name, run, every, verbose)
        except Diverged as e:
            good, why, n = False, 'DIVERGED ' + str(e), 0
        total += 1
        ok += good
        frames += n
        print('%-14s %s %s (%.0fs)' % (name, 'PASS' if good else 'FAIL', why, time.time() - t))
        sys.stdout.flush()
    print('%d/%d sessions identical to SkoolKit, %d frames compared' % (ok, total, frames))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
