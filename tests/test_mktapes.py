#!/usr/bin/env python3
"""The C48 programs and tapes are always a full, reproducible rebuild.

  python3 tests/test_mktapes.py        (after tools/build.py and tools/mktapes.py)

Checks: rcc's output does not depend on what the same process compiled
before or on Python's hash seed (it once did: chess and hanoi-mt came
out different in tools/mktapes.py than alone); tools/mktapes.py --check
finds every kind of stale file (changed, missing, left over from a
removed program) and a rebuild installs exactly the corpus; the check
passes on this tree; tools/mkrelease.py refuses to copy C48 files that
are not a fresh build.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'sdk'), ROOT]
import mktapes                         # noqa: E402
from rcc import driver                 # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix='mktapes-test-')


def check(what, cond, detail=''):
    print('  %s %s%s' % ('ok  ' if cond else 'FAIL', what, '' if cond or not detail else ': ' + detail))
    if not cond:
        FAILS.append(what)


def compile_alone(src, extra, seed):
    """rcc in a fresh process with the given hash seed -> SSX1 bytes"""
    out = os.path.join(TMP, 'alone-%s.ssx' % seed)
    code = ('import sys; sys.path.insert(0, %r); from rcc import driver; '
            'sys.exit(driver.main(sys.argv[1:]))' % os.path.join(ROOT, 'sdk'))
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    subprocess.run([sys.executable, '-c', code, src, '-o', out] + extra, check=True,
                   env=env, stdout=subprocess.DEVNULL, cwd=ROOT)
    return open(out, 'rb').read()


def reproducible():
    print('rcc is reproducible')
    fresh = os.path.join(TMP, 'fresh')
    with contextlib.redirect_stdout(io.StringIO()):
        made, _ = mktapes.build(fresh)
    corpus = os.path.join(ROOT, 'programs', 'c48')
    runs = json.load(open(os.path.join(ROOT, 'sdk', 'tests', 'runs.json')))
    cases = [('chess', os.path.join(corpus, runs['chess']['dir'], 'chess.c'), [], 'c48/chess.ssx'),
             ('hanoi-mt', os.path.join(corpus, 'demos', 'hanoi.c'),
              ['--bytecode', '--stack', '400', '--udgs', '16'], 'c48/hanoi-mt.ssx'),
             ('mobius-mt', os.path.join(corpus, 'demos', 'mobius.c'), ['--bytecode'],
              'c48/mobius-mt.ssx')]
    for name, src, extra, rel in cases:
        inside = open(os.path.join(fresh, rel), 'rb').read()
        alone = [compile_alone(src, extra, seed) for seed in (0, 12345)]
        check('%s: the same bytes compiled alone (two hash seeds) as after the whole corpus'
              % name, alone[0] == alone[1] == inside)
    return fresh, made


def stale_files(fresh, made):
    print('--check finds stale files; a rebuild installs exactly the corpus')
    d = os.path.join(TMP, 'build')
    os.makedirs(os.path.join(d, 'c48'))
    for rel in made:
        shutil.copyfile(os.path.join(fresh, rel), os.path.join(d, rel))
    check('a copy of a fresh build passes', mktapes.compare(fresh, made, d) == [])
    path = os.path.join(d, 'c48', 'mobius.ssx')
    data = bytearray(open(path, 'rb').read())
    data[100] ^= 1
    open(path, 'wb').write(data)
    os.remove(os.path.join(d, 'c48', 'torus.tap'))
    open(os.path.join(d, 'c48', 'oldprog.ssx'), 'wb').write(b'SSX1 stale')
    t = os.path.join(d, 'c48-demos.tzx')
    open(t, 'ab').write(b'\0')
    got = dict(mktapes.compare(fresh, made, d))
    check('a changed program is reported', got.get('c48/mobius.ssx', '').startswith('differs'))
    check('a changed tape is reported', got.get('c48-demos.tzx', '').startswith('differs'))
    check('a missing tape is reported', got.get('c48/torus.tap') == 'missing')
    check('a file no program makes is reported', 'c48/oldprog.ssx' in got)
    check('nothing else is reported (%d)' % len(got), len(got) == 4, str(got))
    mktapes.install(fresh, made, d)
    check('installing the rebuild fixes all four and removes the left-over file',
          mktapes.compare(fresh, made, d) == [] and
          not os.path.exists(os.path.join(d, 'c48', 'oldprog.ssx')))


def this_tree():
    print('this tree')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'mktapes.py'), '--check'],
                       capture_output=True, text=True, cwd=ROOT)
    check('tools/mktapes.py --check passes: build/ is a fresh build', r.returncode == 0,
          r.stdout[-400:])
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'mktapes.py'), '--release'],
                       capture_output=True, text=True, cwd=ROOT)
    check('--release alone is refused (it goes with --check)', r.returncode != 0)


def release_gate():
    print('tools/mkrelease.py refuses stale C48 files')
    import tools.mkrelease as mkrelease
    real = mkrelease.stale_c48
    copied = []
    real_deliver = mkrelease.deliver
    try:
        mkrelease.stale_c48 = lambda: [('c48/chess.ssx', 'differs from a fresh build (stale)')]
        mkrelease.deliver = lambda *a, **k: copied.append(a)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                mkrelease.main([])
            refused = False
        except SystemExit as e:
            refused = 'fresh full build' in str(e)
        check('a stale build is refused before anything is copied', refused and not copied,
              out.getvalue())
        mkrelease.stale_c48 = lambda: []
        try:
            mkrelease.require_fresh_c48()
            passed = True
        except SystemExit:
            passed = False
        check('a fresh build passes the gate', passed)
    finally:
        mkrelease.stale_c48 = real
        mkrelease.deliver = real_deliver


def main():
    fresh, made = reproducible()
    stale_files(fresh, made)
    this_tree()
    release_gate()
    shutil.rmtree(TMP, ignore_errors=True)
    print('%d failed' % len(FAILS))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
