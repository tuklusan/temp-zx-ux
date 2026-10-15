#!/usr/bin/env python3
"""rvm's window, driven through Tk as a user would.

  xvfb-run -a python3 tests/rvm_gui.py      (any Python 3.11+ with Tk)

Checks: every frame the machine makes reaches the window, in order, none
dropped, at no more than 50 a second; a frame is repainted exactly when
it differs from the one before; typed keys reach the program; Shift+Space
is BREAK while the program runs (status 255) and closes the window once
it has ended (with the program's status); the window keeps the program's
last picture at the end; with --keep the window stays live at the ZX-UX
shell; a missing system tape is an error before any window opens; an
8.5 KB program (chess) loads with every frame shown, and --frames ends a
run in the window.
"""
import json
import os
import shutil
import struct
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'sdk'))
CACHE = tempfile.mkdtemp(prefix='rvm-gui-cache-')
os.environ['ZXUX_RVM_CACHE'] = CACHE
import rvm          # noqa: E402
import rvmgui       # noqa: E402
import zxscreen     # noqa: E402
from rcc import driver   # noqa: E402

TMP = tempfile.mkdtemp(prefix='rvm-gui-')
FAILS = []


def check(what, cond, detail=''):
    print('  %s %s%s' % ('ok  ' if cond else 'FAIL', what, '' if cond or not detail else ': ' + detail))
    if not cond:
        FAILS.append(what)


def prog(name):
    out = os.path.join(TMP, name + '.ssx')
    if not os.path.exists(out):
        if driver.main([os.path.join(ROOT, 'sdk', 'tests', 'rvm', name + '.c'), '-o', out]):
            raise SystemExit('rcc failed for ' + name)
    return out


def drive(args, script, timeout=120, mute=True, setup=None):
    """Open the window for rvm ARGS; script(app, t) is called every 50 ms
    with the seconds since the start; returns (status, events, app)."""
    o = rvm.parse(args)
    o.mute = mute
    probe = os.path.join(TMP, 'probe.jsonl')
    app = rvmgui.App(o, probe=probe)
    if setup:
        setup(app)
    t0 = time.monotonic()

    def tick():
        if app.closed:
            return
        t = time.monotonic() - t0
        if t > timeout:
            app.close()
            return
        script(app, t)
        if not app.closed:
            app.root.after(50, tick)
    app.root.after(50, tick)
    status = app.mainloop()
    events = [json.loads(l) for l in open(probe)]
    return status, events, app


def key(app, char=None, keysym=None, shift=False):
    app.root.event_generate('<KeyPress>', keysym=keysym or char, state=1 if shift else 0)


def frames_of(events):
    return [e for e in events if e['event'] == 'frame']


def close_when_ended(app, t):
    if app.ended and not getattr(app, '_closing', False):
        app._closing = True
        app.root.after(200, lambda: key(app, keysym='space', shift=True))


def main():
    print('frames and the end of a program')
    status, ev, app = drive([prog('exit7')], close_when_ended)
    fr = frames_of(ev)
    nums = [e['n'] for e in fr]
    check('the program\'s status comes back when Shift+Space closes the window (7)', status == 7)
    check('every frame reaches the window, in order, none dropped (%d frames)' % len(nums),
          nums == list(range(nums[0], nums[0] + len(nums))) and len(nums) == app.w.sent)
    span = fr[-1]['t'] - fr[0]['t']
    check('about 50 frames a second, not faster (%.1f per second; the timer may be '
          'late and catch up, 5%% allowed)' % ((len(fr) - 1) / span),
          span >= (len(fr) - 1) * 0.020 * 0.95)
    painted = sum(1 for e in fr if e['painted'])
    check('a frame is painted only when it changed (%d of %d)' % (painted, len(fr)),
          0 < painted < len(fr))
    end = [e for e in ev if e['event'] == 'end']
    check('the footer reports the end ("exit7: exit 7")', end and end[0]['text'] == 'exit7: exit 7')
    check('Shift+Space after the end closes the window',
          [e['event'] for e in ev][-2:] == ['close-key', 'close'])

    print('a big program')
    # a block longer than a frame's worth of the tape trap's time once made
    # the machine step over a frame: the window must still get them all
    big = os.path.join(TMP, 'chess.ssx')
    if driver.main([os.path.join(ROOT, 'programs', 'c48', 'games', 'chess.c'), '-o', big]):
        raise SystemExit('rcc failed for chess')
    status, ev, app = drive(['--gui', big, '--frames', '300'], close_when_ended)
    fr = frames_of(ev)
    nums = [e['n'] for e in fr]
    end = [e for e in ev if e['event'] == 'end']
    check('an 8.5 KB program loads and runs; every frame reaches the window (%d)' % len(nums),
          len(nums) > 300 and nums == list(range(nums[0], nums[0] + len(nums)))
          and len(nums) == app.w.sent)
    check('--frames ends the run in the window too ("%s")' % (end[0]['text'] if end else ''),
          bool(end) and 'stopped after 300 frames' in end[0]['text'] and status == 0)

    print('a slow host')
    slow = rvmgui.App.paint_rows

    def paint_slowly(self, rows):
        time.sleep(0.045)                  # a host that paints at ~20 a second
        slow(self, rows)
    rvmgui.App.paint_rows = paint_slowly
    try:
        status, ev, app = drive([prog('spin'), '--keys', '{WAIT 100}{BREAK}'], close_when_ended)
    finally:
        rvmgui.App.paint_rows = slow
    fr = frames_of(ev)
    nums = [e['n'] for e in fr]
    painted = sum(1 for e in fr if e['painted'])
    span = fr[-1]['t'] - fr[0]['t']
    # every changed frame costs 45 ms to paint: the run must take at least
    # that long, with every frame there, in order
    check('painting slower than the Spectrum slows the program, no frame is dropped '
          '(%d frames, %d painted, %.2f s)' % (len(nums), painted, span),
          status == 255 and nums == list(range(nums[0], nums[0] + len(nums)))
          and len(nums) == app.w.sent and painted > 50 and span >= (painted - 1) * 0.045)

    print('sound')
    import rvmsound

    class Speaker:
        """A sound device playing in real time: records what it is given,
        and counts the times it ran out of sound once playing."""
        name = 'test speaker'

        def __init__(self):
            self.data = bytearray()
            self.start = None
            self.before = 0.0
            self.gaps = 0

        def queued(self):
            if self.start is None:
                return 0.0
            q = len(self.data) / 2 / rvmsound.RATE - (self.before + time.monotonic() - self.start)
            if q < 0:
                self.gaps += 1
                self.start = None
                return 0.0
            return q

        def write(self, pcm):
            self.queued()
            if self.start is None:
                self.start = time.monotonic()
                self.before = len(self.data) / 2 / rvmsound.RATE
            self.data += pcm

        def close(self, drain):
            pass
    speaker = Speaker()
    real_open = rvmsound.open_output
    rvmsound.open_output = lambda mute=False: rvmsound.Output(stream=speaker)

    def record(app):
        app.r.pcm = bytearray()            # the exact samples, as --wav keeps them
    try:
        status, ev, app = drive([prog('beeps')], close_when_ended, mute=False, setup=record)
    finally:
        rvmsound.open_output = real_open
    fr = frames_of(ev)
    want = rvmsound.DCBlock().process(bytes(app.r.pcm))
    check('the window streams every frame\'s sound, in order, nothing between frames '
          '(%.2f s of sound, %d frames)' % (len(speaker.data) / 2 / rvmsound.RATE, len(fr)),
          len(want) > 2 * rvmsound.RATE and bytes(speaker.data) == want)
    loud = max(abs(v) for v in struct.unpack('<%dh' % (len(want) // 2), want))
    check('the BEEPs are in it (peak %d)' % loud, loud > rvmsound.AMPLITUDE // 2)
    steady = fr[len(fr) // 5:]
    rate = (len(steady) - 1) / (steady[-1]['t'] - steady[0]['t'])
    check('the sound stream sets the pace: %.2f frames a second (the Spectrum: 50.08)' % rate,
          49.0 < rate < 50.6)
    # (a busy host - another test in parallel - can starve the machine
    # thread for a moment: a few gaps are the host's, not rvm's)
    check('the speaker hardly ran dry while the program played (%d times, 3 allowed)'
          % speaker.gaps, speaker.gaps <= 3)
    check('the program ends normally (exit 0)', status == 0)

    print('the last picture')
    pic = {}

    def grab(app, t):
        if app.ended and 'rgb' not in pic:
            pic['rgb'] = [app.base.get(x, y) for x, y in ((40, 30), (60, 30), (100, 60), (5, 5))]
            pic['want'] = app.r.picture()
            app.root.after(100, lambda: key(app, keysym='space', shift=True))
    status, ev, app = drive([prog('exit7')], grab)
    scr, border = pic['want']
    rows = zxscreen.rgb_rows(scr, [border] * zxscreen.H, 0)
    want = [tuple(rows[y][x * 3:x * 3 + 3]) for x, y in ((40, 30), (60, 30), (100, 60), (5, 5))]
    got = [tuple(int(v) for v in p) if not isinstance(p, str) else tuple(int(v) for v in p.split())
           for p in pic['rgb']]
    check('the window keeps the program\'s own last picture, in its colours', got == want,
          '%s vs %s' % (got, want))

    print('keys')
    sent = []

    def typer(app, t):
        fg = app.r.fg
        # someone at the keyboard may take their time: the window keeps a
        # program that waits for keys (headless runs end as 'input' after
        # 50 frames); type only when it has waited over 100 frames
        if fg and fg.started is not None and not sent and fg.reading_since is not None \
                and app.r.session.m.frame - fg.reading_since > 100:
            sent.append(app.r.why)
            for i, c in enumerate('abq'):
                app.root.after(200 * (i + 1), lambda c=c: key(app, c))
        close_when_ended(app, t)
    status, ev, app = drive([prog('keys')], typer)
    check('a program waiting for keys over 100 frames is not ended by the window',
          sent == [None])
    check('keys typed in the window reach the program (2, then q)', status == 2)

    print('BREAK')
    broke = []

    def breaker(app, t):
        if app.r.fg and app.r.fg.started is not None and not broke and t > 1.0:
            broke.append(1)
            key(app, keysym='space', shift=True)
        close_when_ended(app, t)
    status, ev, app = drive([prog('spin')], breaker)
    check('Shift+Space while the program runs is BREAK: status 255', status == 255)
    check('the footer says so', any(e['event'] == 'end' and 'BREAK' in e['text'] for e in ev))
    check('one BREAK, then one close', [e['event'] for e in ev].count('break') == 1)

    print('--keep')
    done = []

    def keeper(app, t):
        if app.ended and not done:
            done.append(t)
            for i, c in enumerate('echo kept\n'):
                app.root.after(60 * (i + 1), lambda c=c: key(app, keysym='Return') if c == '\n'
                               else key(app, keysym='space') if c == ' ' else key(app, c))
        if done and t > done[0] + 3:
            app.close()
    status, ev, app = drive([prog('exit7'), '--keep'], keeper)
    text = zxscreen.screen_text(app.r.session.m.screen())
    at = [i for i, e in enumerate(ev) if e['event'] == 'end'][0]
    after = [e for e in ev[at:] if e['event'] == 'frame']
    check('with --keep the window stays live at the shell after the program '
          '(%d frames after the end)' % len(after), 'kept' in text and len(after) > 50)

    print('errors')
    r = rvm.main(['--gui', '--system', os.path.join(TMP, 'none.tap'), prog('exit7')])
    check('a missing system tape is an error before any window (status 2)', r == 2)
    print('%d failed' % len(FAILS))
    shutil.rmtree(CACHE, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
