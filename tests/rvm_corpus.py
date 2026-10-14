#!/usr/bin/env python3
"""The C48 corpus on rvm: every program, both back ends, on the real ZX-UX.

  python3 tests/rvm_corpus.py [--native|--bytecode] [--only a,b] [--png DIR]

Each scripted session of sdk/tests/runs.json is compiled by rcc and run
by rvm exactly as a user runs it (rvm.Runner, headless): ZX-UX booted
from build/ZX-UX.tap (or rvm's cache of it), the program typed as
/dev/cassette/NAME and loaded through the tape trap, the session's keys
typed once it has started.  A session passes when the program starts
(the loader reaches sys ssxload), shows the text the session expects on
ZX-UX (zxux_text, else expect_text, as tests/ssxrun.py checks it), and,
where the session gives an exit status and the outcome does not depend
on the real clock (no zxux_note), ends with that status.

Negative cases, also checked: security/seckern.c must not compile (a
forged pointer into the kernel's memory), and the LM program (ailmzx48),
which compiles to an SSX1 file bigger than ZX-UX can load, must be
refused by ZX-UX's loader in rvm ("not enough memory", exit status 1)
without starting.

The 58 C48 sources other than LM are all covered: 57 by sessions,
seckern by its compile check.
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, 'sdk')]
import rvm                        # noqa: E402
import zxscreen                   # noqa: E402
from rcc import driver            # noqa: E402

RUNS = json.load(open(os.path.join(ROOT, 'sdk', 'tests', 'runs.json')))
CORPUS = os.path.join(ROOT, 'programs', 'c48')


def compile_c(src, out, flags):
    return driver.main([src, '-o', out] + flags) == 0


def run_session(path, args, keys, keygap, frames):
    o = rvm.Options()
    o.prog, o.args, o.keys, o.keygap, o.frames = path, list(args), keys, keygap, frames
    o.headless = True
    r = rvm.Runner(o)
    r.start()
    while True:
        r.frame()
        why = r.check()
        if why:
            r.why = why
            break
        fg = r.fg
        m = r.session.m
        if fg.started is not None and m.frame - fg.started >= frames:
            r.why = 'frames'
            break
        if fg.started is None and m.frame - r.start_frame >= frames + 3000:
            r.why = 'not started'
            break
    return r


def main(argv):
    flags = []
    only = None
    pngdir = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--native', '--bytecode'):
            if a == '--bytecode':
                flags = ['--bytecode']
            i += 1
        elif a == '--only':
            only = set(argv[i + 1].split(','))
            i += 2
        elif a == '--png':
            pngdir = argv[i + 1]
            i += 2
        else:
            raise SystemExit('unknown option ' + a)
    mode = 'bytecode' if flags else 'native'
    tmp = tempfile.mkdtemp()
    ok = total = 0
    sources = set()
    for name, run in RUNS.items():
        base = name.split(':')[0]
        src = os.path.join(CORPUS, run['dir'], run.get('src', base) + '.c')
        sources.add(os.path.normpath(src))
        if only and name not in only and base not in only:
            continue
        total += 1
        t0 = time.time()
        out = os.path.join(tmp, run.get('src', base)[:10] + '.ssx')
        if not compile_c(src, out, flags):
            print('%-14s FAIL compile' % name)
            continue
        keys = run.get('keys', '')
        frames = run.get('zxux_frames', max(1500, int(run.get('frames', 6000) * 1.5)))
        if flags:
            frames *= 8
        r = run_session(out, run.get('args', []), keys, run.get('keygap', 100), frames)
        fg = r.fg
        pic, border = r.picture()
        final = r.session.m.screen()
        text = zxscreen.screen_text(pic) + '\n' + zxscreen.screen_text(final)
        want = run.get('zxux_text', run.get('expect_text'))
        checks = [('started', fg.started is not None)]
        if want:
            checks.append(('text', want in text))
        if 'expect_status' in run and 'zxux_note' not in run and r.why == 'exit':
            checks.append(('status', fg.status == run['expect_status']))
        good = all(c for _, c in checks)
        ok += good
        print('%-14s %s %-16s %6d frames  [%s] (%.0fs)'
              % (name, 'PASS' if good else 'FAIL', fg.describe() if r.why in ('exit', 'killed')
                 else r.why, (r.session.m.frame - fg.started) if fg.started is not None else 0,
                 ','.join(k + ('' if c else '!') for k, c in checks), time.time() - t0))
        sys.stdout.flush()
        if pngdir:
            os.makedirs(pngdir, exist_ok=True)
            rvm.write_png(pic, os.path.join(pngdir, '%s.%s.png' % (name.replace(':', '_'), mode)),
                          border)
    # the negative cases
    neg = 0
    if not only or 'seckern' in only:
        total += 1
        src = os.path.join(CORPUS, 'security', 'seckern.c')
        sources.add(os.path.normpath(src))
        refused = not compile_c(src, os.path.join(tmp, 'seckern.ssx'), flags)
        print('%-14s %s compile refused (forged pointer into the kernel)'
              % ('seckern', 'PASS' if refused else 'FAIL'))
        ok += refused
        neg += 1
    if not only or 'ailmzx48' in only:
        total += 1
        src = os.path.join(CORPUS, 'ailmzx48', 'ailmzx48.c')
        out = os.path.join(tmp, 'ailmzx48.ssx')
        good = False
        why = 'did not compile'
        if compile_c(src, out, flags):
            import rtap
            need = rtap.need(open(out, 'rb').read())
            r = run_session(out, [], '', 0, 3000)
            text = zxscreen.screen_text(r.session.m.screen())
            good = (need > driver.ZXUX_MAX and r.fg.started is None and r.why == 'exit'
                    and r.fg.status == 1 and 'not enough memory' in text)
            why = 'needs %d bytes; ZX-UX: %s, %s' % (need, 'not enough memory' if
                                                     'not enough memory' in text else '?',
                                                     r.fg.describe())
        print('%-14s %s %s' % ('ailmzx48', 'PASS' if good else 'FAIL', why))
        ok += good
        neg += 1
    if not only:
        allsrc = {os.path.normpath(os.path.join(dp, f)) for dp, _, fs in os.walk(CORPUS)
                  for f in fs if f.endswith('.c') and 'ailmzx48' not in dp}
        missing = allsrc - sources
        total += 1
        print('%-14s %s %d C48 sources besides LM, %d not covered%s'
              % ('coverage', 'PASS' if not missing else 'FAIL', len(allsrc), len(missing),
                 ': ' + ', '.join(sorted(missing)) if missing else ''))
        ok += not missing
    print('%d/%d %s checks pass (rvm on ZX-UX)' % (ok, total, mode))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
