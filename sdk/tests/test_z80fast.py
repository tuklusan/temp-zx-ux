#!/usr/bin/env python3
"""FastZ80 (sdk/z80fast.py) must behave exactly like the plain z80-python core.

Every opcode that FastZ80 replaces is executed from random CPU states and
random memory on both cores; CPU state (all registers, F, WZ, Q, R, PC, SP),
every memory access in order (address, value, read/write), and the
T-states must be identical.  Exit status 1 on any
difference.

  test_z80fast.py [--cases N]      (default 3000 random states per opcode)
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from z80_python.cpu import Z80CPU   # noqa: E402
import z80fast                       # noqa: E402

REGS8 = ('a', 'b', 'c', 'd', 'e', 'h', 'l', 'i')
REGS16 = ('ix', 'iy', 'sp', 'pc', 'wz', 'af_', 'bc_', 'de_', 'hl_')


def randomize(cpu, rnd, state):
    for k, v in state.items():
        setattr(cpu, k, v)


def make_state(rnd):
    s = {k: rnd.randrange(256) for k in REGS8}
    s.update({k: rnd.randrange(65536) for k in REGS16})
    s['_f'] = rnd.randrange(256)
    s['q'] = rnd.choice((0, rnd.randrange(256)))
    s['r'] = rnd.randrange(256)
    # make memory-addressing registers sometimes hit edges and overlap the code
    if rnd.random() < 0.1:
        s['pc'] = rnd.choice((0xFFFF, 0xFFFE, 0xFFFD, 0x0000))
    if rnd.random() < 0.1:
        s['sp'] = rnd.choice((0x0000, 0x0001, 0xFFFF, (s['pc'] + 1) & 0xFFFF))
    if rnd.random() < 0.1:
        s['h'], s['l'] = s['pc'] >> 8, (s['pc'] + rnd.randrange(4)) & 0xFF
    return s


class Bus:
    """Memory for one test: `mem` (a 256-byte pattern, repeated) overlaid with
    the instruction bytes and with what the instruction writes; every access
    is logged in order (read/write, address, value)."""

    def setup(self, mem, pc, code):
        self.mem = mem
        self.over = {(pc + i) & 0xFFFF: b for i, b in enumerate(code)}
        self.log = []

    def rd(self, a):
        v = self.over.get(a, self.mem[a & 0xFF])
        self.log.append(('r', a, v))
        return v

    def wr(self, a, v):
        self.log.append(('w', a, v))
        self.over[a] = v


def run_one(cpu, bus, mem, state, code):
    bus.setup(mem, state['pc'], code)
    cpu.halted = False
    for k, v in state.items():
        setattr(cpu, k, v)
    t = cpu.step()
    return cpu.capture_state(), bus.log, t


def main(argv):
    cases = 3000
    if argv[:1] == ['--cases']:
        cases = int(argv[1])
    rnd = random.Random(48)
    work = [((op,), 'main %02X' % op) for op in sorted(z80fast.MAIN)]
    work += [((0xED, op), 'ED %02X' % op) for op in sorted(z80fast.ED)]
    bus_a, bus_b = Bus(), Bus()
    ref = Z80CPU(bus_a.rd, bus_a.wr)
    fast = z80fast.FastZ80(bus_b.rd, bus_b.wr)
    bad = 0
    for prefix, name in work:
        for _ in range(cases):
            mem = bytes(rnd.randrange(256) for _ in range(256))
            state = make_state(rnd)
            code = prefix + tuple(rnd.randrange(256) for _ in range(3))
            a = run_one(ref, bus_a, mem, state, code)
            b = run_one(fast, bus_b, mem, state, code)
            if a != b:
                bad += 1
                if bad <= 10:
                    print('DIFF %s state=%r\n  ref=%r t=%d\n fast=%r t=%d' % (name, state, a[0], a[2], b[0], b[2]))
                    if a[1] != b[1]:
                        print('  bus ref ', a[1])
                        print('  bus fast', b[1])
                break
    print('z80fast: %d opcodes x %d random states, %d differ' % (len(work), cases, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
