"""romoracle - the 48K ROM as the C48 floating-point oracle (spec 17, 84, 94).

Independent of sdk/rcc: runs the ROM's own DEC-TO-FP (2C9Bh) on a decimal
string, STACK-BC (2D2Bh) on a 16-bit magnitude, and the calculator's negate
(1Bh) on an emulated Z80, and returns the five bytes left on the calculator
stack.  A ROM error report raises RomError.

Two Z80s can run it: 'z80python', the plain z80-python core bundled in sdk/
(not rcc's code, nor the z80fast handlers rvm uses), and 'skoolkit', SkoolKit's
CSimulator when SkoolKit is installed (a second, independent emulator).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'sdk')
ROM48 = os.path.join(SDK, 'rom', '48.rom')


def engines():
    """the Z80 engines available here"""
    out = ['z80python']
    try:
        import skoolkit  # noqa: F401
        out.append('skoolkit')
    except ImportError:
        pass
    return out

STKBOT, STKEND, MEM, ERR_SP, CH_ADD, ERR_NR = 0x5C63, 0x5C65, 0x5C68, 0x5C3D, 0x5C5D, 0x5C3A
FLAGS = 0x5C3B
CALC_STACK = 0xC000
TEXT = 0xB000
STOP = 0x8000            # a HALT; the routine returns or errors to here
SP0 = 0xF000


class RomError(Exception):
    pass


class Oracle:
    def __init__(self, engine='z80python'):
        self.engine = engine
        self.rom = open(ROM48, 'rb').read()

    def _fresh(self):
        mem = [0] * 65536
        mem[:len(self.rom)] = self.rom
        mem[STOP] = 0x76
        for a, v in ((STKBOT, CALC_STACK), (STKEND, CALC_STACK), (MEM, 0x5C92)):
            mem[a], mem[a + 1] = v & 255, v >> 8
        return mem

    def _call(self, mem, pc, regs):
        # stack: return address STOP; ERR_SP -> a slot holding STOP as well,
        # so a ROM error (RST 8) also ends at STOP with ERR_NR set
        sp = SP0
        mem[sp - 2], mem[sp - 1] = STOP & 255, STOP >> 8
        mem[ERR_SP], mem[ERR_SP + 1] = (sp - 2) & 255, (sp - 2) >> 8
        mem[sp - 4], mem[sp - 3] = STOP & 255, STOP >> 8
        mem[ERR_NR] = 0xFF
        r = dict(regs)
        r.update({'SP': sp - 4, 'PC': pc, 'IY': 0x5C3A})
        m, at = (self._skoolkit if self.engine == 'skoolkit' else self._z80python)(mem, r)
        if at != STOP:
            raise RuntimeError('ROM call did not finish')
        if m[ERR_NR] != 0xFF:
            raise RomError('ROM error report %d' % (m[ERR_NR] + 1))
        end = m[STKEND] | m[STKEND + 1] << 8
        if end - CALC_STACK != 5:
            raise RuntimeError('calculator stack holds %d bytes' % (end - CALC_STACK))
        return m, bytes(m[CALC_STACK:CALC_STACK + 5])

    @staticmethod
    def _skoolkit(mem, r):
        from skoolkit import CSimulator
        from skoolkit.simutils import from_memory
        sim = from_memory(CSimulator, mem, r, {'iff': 0})
        sim.run(r['PC'], STOP, False)
        return sim.memory, sim.registers[24]

    @staticmethod
    def _z80python(mem, r):
        if SDK not in sys.path:
            sys.path.insert(0, SDK)
        from z80_python.cpu import Z80CPU
        m = bytearray(mem)

        def wr(a, v):
            if a >= 0x4000:
                m[a] = v
        cpu = Z80CPU(m.__getitem__, wr)
        for k, v in r.items():
            if k in ('A', 'B', 'C', 'D', 'E', 'H', 'L'):
                setattr(cpu, k.lower(), v)
            else:
                setattr(cpu, k.lower(), v)
        for _ in range(5_000_000):
            if cpu.pc == STOP:
                break
            cpu.step()
        return m, cpu.pc

    def decimal(self, text):
        """bytes of the decimal floating literal text (no sign, no suffix)"""
        mem = self._fresh()
        raw = text.encode('ascii') + b'\x0d'
        mem[TEXT:TEXT + len(raw)] = list(raw)
        mem[CH_ADD], mem[CH_ADD + 1] = TEXT & 255, TEXT >> 8
        return self._call(mem, 0x2C9B, {'A': raw[0]})[1]

    def integer(self, value):
        """bytes of a 16-bit integer value converted to float (signed path
        for negative values: magnitude, then negate)"""
        mem = self._fresh()
        mag = -value if value < 0 else value
        _, out = self._call(mem, 0x2D2B, {'B': mag >> 8, 'C': mag & 255})
        return self.negate(out) if value < 0 else out

    def negate(self, five):
        """bytes after the calculator's negate (1Bh) of five bytes"""
        mem = self._fresh()
        mem[CALC_STACK:CALC_STACK + 5] = list(five)
        mem[STKEND], mem[STKEND + 1] = (CALC_STACK + 5) & 255, (CALC_STACK + 5) >> 8
        prog = [0xEF, 0x1B, 0x38, 0xC9]      # RST 28h; negate; end-calc; RET
        mem[0x8100:0x8104] = prog
        return self._call(mem, 0x8100, {})[1]


if __name__ == '__main__':
    o = Oracle()
    for t in sys.argv[1:]:
        try:
            print(t, o.decimal(t).hex(' '))
        except RomError as e:
            print(t, e)
