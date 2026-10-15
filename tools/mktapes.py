#!/usr/bin/env python3
"""Compile the C48 SDK corpus with the ZX-UX SDK and write cassette tapes.

  python3 tools/mktapes.py                  rebuild every program and tape
  python3 tools/mktapes.py --check          are build/'s copies a fresh rebuild?
  python3 tools/mktapes.py --check --release   ... and release/'s?

For every program in sdk/tests/runs.json (the checked-in programs/c48 sources):
rcc -> build/c48/NAME.ssx (native code, or SSB1 bytecode when native code
would not fit), then rtap writes
  build/c48/NAME.tap              one program
  build/c48-<group>.tzx           the programs of a group (apps, demos, ...)
  build/c48-multitask.tzx         hanoi and queens8, mobius and torus: to run
                                  together (-mt.ssx builds)
  build/ZX-UX-c48.tzx          ZX-UX itself followed by every program
Boot ZX-UX, log in, play a tape and type /dev/cassette/NAME [args].

Every run is a full rebuild: all programs are compiled afresh into an
empty directory, and only then copied into build/; a program or tape in
build/c48 that the rebuild did not make (a program since removed or
renamed) is deleted, so build/c48 is exactly the corpus: it is this
tool's output, not a place for other files.  ZX-UX-c48.tzx starts with
build/ZX-UX.tzx, so run tools/build.py first.

--check rebuilds into a temporary directory, changes nothing, and lists
every C48 file - build/c48/*.ssx and *.tap, build/c48-*.tzx and
build/ZX-UX-c48.tzx (and with --release, the same in release/) - that
differs from the rebuild, is missing, or should not be there; its status
is 1 if there is any.  (The multitask snapshot, build/ZX-UX-multitask.z80,
is tools/mtsnap.py's.)  The CI build job and tools/mkrelease.py run it, so stale
binaries (compiled by an older compiler, library or source) cannot be
committed or released.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'sdk'))
import rld    # noqa: E402
import rtap   # noqa: E402
from rcc import driver   # noqa: E402

GROUPS = (('apps', ('apps',)), ('games', ('games',)), ('demos', ('demos',)),
          ('examples', ('examples', 'sound', 'security')))


def build(dest):
    """Compile every program and write every tape into DEST (c48/ and the
    .tzx files, as in build/).  Returns (relative paths written, the
    report lines)."""
    corpus = os.path.join(ROOT, 'programs', 'c48')
    runs = json.load(open(os.path.join(ROOT, 'sdk', 'tests', 'runs.json')))
    out = os.path.join(dest, 'c48')
    os.makedirs(out, exist_ok=True)
    made = []
    progs = []
    for name, run in runs.items():
        if ':' in name:
            continue
        src = os.path.join(corpus, run['dir'], run.get('src', name) + '.c')
        ssx = os.path.join(out, name + '.ssx')
        if driver.main([src, '-o', ssx]):
            raise SystemExit('rcc failed: %s' % name)
        data = open(ssx, 'rb').read()
        hdr, dat = rtap.records(data, name)
        rtap.write(os.path.join(out, name + '.tap'), b'', [(1000, hdr), (2000, dat)])
        made += ['c48/%s.ssx' % name, 'c48/%s.tap' % name]
        progs.append((run['dir'], name, hdr, dat, len(data), rtap.need(data)))
    head = b'ZXTape!\x1a\x01\x14'
    for g, dirs in GROUPS:
        blocks = []
        t = ('ZX-UX C48 programs: %s' % g).encode()
        for d, name, hdr, dat, n, need in progs:
            if d in dirs:
                blocks += [(1000, hdr), (2000, dat)]
        rtap.write(os.path.join(dest, 'c48-%s.tzx' % g), head + bytes([0x30, len(t)]) + t, blocks)
        made.append('c48-%s.tzx' % g)
    # hanoi and queens8 together: each draws one half of the screen; built
    # small (bytecode, stacks measured: the deepest recursion plus the VM's
    # 170 bytes for the kernel) so that both fit in memory at once
    blocks = []
    # (hanoi uses UDG slots 0-15 only: a 16-slot bank)
    for name, extra in (('hanoi', ['--stack', '400', '--udgs', '16']), ('queens8', ['--stack', '448'])):
        src = os.path.join(corpus, 'demos', name + '.c')
        ssx = os.path.join(out, name + '-mt.ssx')
        if driver.main([src, '-o', ssx, '--bytecode'] + extra):
            raise SystemExit('rcc failed: %s' % name)
        hdr, dat = rtap.records(open(ssx, 'rb').read(), name)
        blocks += [(1000, hdr), (0 if name == 'hanoi' else 2000, dat)]   # pause 0: the tape stops
        made.append('c48/%s-mt.ssx' % name)
    # mobius and torus together, in the background: bytecode (with the
    # stacks rcc measures) makes each about 600 bytes smaller, so that
    # both fit in the arena after login - a background program cannot
    # borrow the window.  They share the whole screen: each draws over
    # the other's picture.
    for name in ('mobius', 'torus'):
        src = os.path.join(corpus, 'demos', name + '.c')
        ssx = os.path.join(out, name + '-mt.ssx')
        if driver.main([src, '-o', ssx, '--bytecode']):
            raise SystemExit('rcc failed: %s' % name)
        hdr, dat = rtap.records(open(ssx, 'rb').read(), name)
        blocks += [(1000, hdr), (0 if name == 'mobius' else 2000, dat)]
        made.append('c48/%s-mt.ssx' % name)
    t = b'ZX-UX C48 programs: hanoi and queens8, then mobius and torus, together'
    rtap.write(os.path.join(dest, 'c48-multitask.tzx'), head + bytes([0x30, len(t)]) + t, blocks)
    made.append('c48-multitask.tzx')
    system = os.path.join(ROOT, 'build', 'ZX-UX.tzx')
    if not os.path.exists(system):
        raise SystemExit('mktapes: %s missing: run tools/build.py first' % system)
    h, blocks = rtap.tzx_blocks(open(system, 'rb').read())
    for d, name, hdr, dat, n, need in progs:
        blocks += [(1000, hdr), (2000, dat)]
    rtap.write(os.path.join(dest, 'ZX-UX-c48.tzx'), h, blocks)
    made.append('ZX-UX-c48.tzx')
    report = ['%-9s %-11s %5d bytes, needs %5d' % (d, name, n, need)
              for d, name, hdr, dat, n, need in progs]
    report.append('%d programs' % len(progs))
    return made, report


def outputs_in(directory):
    """The C48 files a build/ or release/ directory holds now."""
    have = []
    c48 = os.path.join(directory, 'c48')
    if os.path.isdir(c48):
        have += ['c48/' + f for f in os.listdir(c48) if f.endswith(('.ssx', '.tap'))]
    have += [f for f in os.listdir(directory) if f.startswith('c48-') and f.endswith('.tzx')]
    if os.path.exists(os.path.join(directory, 'ZX-UX-c48.tzx')):
        have.append('ZX-UX-c48.tzx')
    return have


def compare(fresh, made, directory):
    """[(path, problem)] for DIRECTORY against a fresh build in FRESH."""
    bad = []
    for rel in sorted(made):
        path = os.path.join(directory, rel)
        if not os.path.exists(path):
            bad.append((rel, 'missing'))
        elif open(path, 'rb').read() != open(os.path.join(fresh, rel), 'rb').read():
            bad.append((rel, 'differs from a fresh build (stale)'))
    for rel in sorted(set(outputs_in(directory)) - set(made)):
        bad.append((rel, 'not made by the build (a removed program?)'))
    return bad


def stale(directories):
    """Rebuild into a temporary directory; {directory: [(path, problem)]}."""
    tmp = tempfile.mkdtemp(prefix='mktapes-')
    try:
        made, _ = build(tmp)
        return {d: compare(tmp, made, d) for d in directories}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install(fresh, made, dest):
    """Copy a fresh build into DEST and delete what it did not make."""
    os.makedirs(os.path.join(dest, 'c48'), exist_ok=True)
    for rel in set(outputs_in(dest)) - set(made):
        os.remove(os.path.join(dest, rel))
    for rel in made:
        shutil.copyfile(os.path.join(fresh, rel), os.path.join(dest, rel))


def main(argv):
    check = '--check' in argv
    release = '--release' in argv
    if [a for a in argv if a not in ('--check', '--release')] or (release and not check):
        raise SystemExit('usage: python3 tools/mktapes.py [--check [--release]]')
    build_dir = os.path.join(ROOT, 'build')
    if check:
        dirs = [build_dir] + ([os.path.join(ROOT, 'release')] if release else [])
        result = stale(dirs)
        bad = 0
        for d in dirs:
            name = os.path.relpath(d, ROOT)
            for rel, problem in result[d]:
                print('%s/%s: %s' % (name, rel, problem))
                bad += 1
            if not result[d]:
                print('%s: every C48 program and tape is a fresh build' % name)
        if bad:
            print('mktapes: %d stale file(s); run tools/mktapes.py%s and commit the result'
                  % (bad, ', then the release (tools/release_v1.py, which empties release/)'
                     if release else ''))
            return 1
        return 0
    tmp = tempfile.mkdtemp(prefix='mktapes-')
    try:
        made, report = build(tmp)
        install(tmp, made, build_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('\n'.join(report))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
