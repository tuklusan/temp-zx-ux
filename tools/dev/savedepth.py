# tools/dev/savedepth.py - run from the repository root
# The stack depth each resident program has when its window image is saved
# (wsave: another resident-text program needs the window).  The SAVE block
# keeps STKRES (or the program's own reserve) of stack; a deeper stack at
# a save kills the program.  Runs every tests/suite.py test (or -k NAMES)
# with the emulator stopping at wsave, and prints the deepest save per
# program name (the status-line name of the slot being saved).
import os, sys, collections
sys.path[:0] = ['tools', 'tests', 'sdk']
import zxrun, suite
from skoolkit.simutils import A, SP, PC, T
WSAVE = suite.ksym('wsave'); CORETOP = suite.ksym('CORETOP')
P_SP = suite.ksym('p_sp'); STLINE = suite.ksym('stline')
deep = collections.defaultdict(int)
where = {}
def run(self, frames):
    regs = self.sim.registers
    for _ in range(frames):
        end = regs[T] + zxrun.FRAME
        while True:
            self.sim.trace(regs[PC], WSAVE, 0, end, 1, None, None, None, None, None)
            if regs[PC] != WSAVE or regs[T] >= end:
                break
            slot = regs[A]
            m = self.mem
            sp = m[P_SP + 2 * slot] | m[P_SP + 2 * slot + 1] << 8
            name = bytes(m[STLINE + 8 * slot:STLINE + 8 * slot + 8]).split(b'\0')[0].decode('latin-1').strip()
            d = CORETOP - sp
            if d > deep[name]:
                deep[name] = d
                where[name] = CURRENT[0]
            self.sim.trace(regs[PC], -1, 1, end, 1, None, None, None, None, None)
        self.frames += 1
zxrun.ZX.run = run
CURRENT = ['']
only = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[1] == '-k' else None
snap = os.path.join('build', 'test.z80')
for f in suite.TESTS:
    if only and f.__name__ not in only:
        continue
    CURRENT[0] = f.__name__
    try:
        f(suite.Session(snap))
        r = 'ok'
    except Exception as e:
        r = 'FAIL %s' % str(e).splitlines()[0][:60]
    print('%-22s %s' % (f.__name__, r), flush=True)
print()
for n, d in sorted(deep.items(), key=lambda x: -x[1]):
    print('%-10s deepest stack at a save: %3d bytes  (%s)' % (n, d, where[n]))
