#!/usr/bin/env python3
"""rvm's sound output and clock (sdk/rvmsound.py): unit checks, no device.

  python3 sdk/tests/test_rvmsound.py [-k NAME,...]

The window plays sound as one continuous stream that also keeps the time
(rvmsound.Output).  These checks drive it with simulated devices and a
simulated clock: every frame's samples reach the device in order with
nothing between them, the machine runs at the device's rate (50.08
frames a second), the DC blocker removes the beeper's offset without
touching the pitch, and every failure (no device, a device that stops)
falls back to silence on the wall clock without stopping the program.
The Windows waveOut code runs against a simulated winmm.dll, which
checks the calls, the structure layouts and the buffer lifetimes.  The
exact samples themselves (BEEP to the T-state) are sdk/tests/test_rvm.py.
"""
import ctypes
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(HERE)
sys.path.insert(0, SDK)
import rvmsound                                    # noqa: E402

FAILS = []
TESTS = []
TMP = tempfile.mkdtemp(prefix='rvm-sound-')
A = rvmsound.AMPLITUDE
SPF = rvmsound.FRAME_S * rvmsound.RATE             # samples a frame (880.6)


def test(f):
    TESTS.append(f)


def check(what, cond, detail=''):
    print('  %s %s%s' % ('ok  ' if cond else 'FAIL', what, '' if cond or not detail else ': ' + detail))
    if not cond:
        FAILS.append(what)
    return cond


def samples(pcm):
    return struct.unpack('<%dh' % (len(pcm) // 2), pcm)


def square(freq, seconds, rate=rvmsound.RATE):
    """A beeper tone as the Beeper renders it: 0 / AMPLITUDE."""
    n = int(seconds * rate)
    half = rate / freq / 2
    return struct.pack('<%dh' % n, *[A if int(i / half) % 2 == 0 else 0 for i in range(n)])


def frames_of(pcm, n=None):
    """Split samples into frame-sized pieces (880 or 881, as the Beeper does)."""
    out, pos, k = [], 0, 0
    total = len(pcm) // 2
    while pos < total and (n is None or k < n):
        end = min(total, int(round((k + 1) * SPF)))
        out.append(pcm[pos * 2:end * 2])
        pos, k = end, k + 1
    return out


class Clock:
    """Simulated time: sleep() moves it on."""

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        assert s >= 0
        self.sleeps.append(s)
        self.t += s


class Device:
    """A sound device on the simulated clock: plays RATE samples a second
    from what was written; queued() is what is left.  Records everything
    written, and the times at which the queue ran dry."""

    name = 'test'

    def __init__(self, clock, fail_after=None):
        self.clock = clock
        self.data = bytearray()
        self.start = None
        self.played_before = 0.0          # seconds played before the last gap
        self.gaps = 0
        self.max_queued = 0.0
        self.fail_after = fail_after
        self.writes = 0
        self.closed = None

    def _played(self):
        if self.start is None:
            return 0.0
        return self.played_before + (self.clock.t - self.start)

    def queued(self):
        q = len(self.data) / 2 / rvmsound.RATE - self._played()
        if q < 0:                         # ran dry: playback restarts at the next write
            self.played_before = len(self.data) / 2 / rvmsound.RATE
            self.start = None
            self.gaps += 1
            q = 0.0
        return q

    def write(self, pcm):
        self.writes += 1
        if self.fail_after is not None and self.writes > self.fail_after:
            raise rvmsound.StreamError('device gone')
        self.queued()
        if self.start is None:
            self.start = self.clock.t
            self.played_before = len(self.data) / 2 / rvmsound.RATE
        self.data += pcm
        self.max_queued = max(self.max_queued, self.queued())

    def close(self, drain):
        self.closed = drain


def run_machine(out, clock, pcm_frames, work=0.008):
    """The worker: each frame costs WORK seconds of host time, then goes to
    the output.  Returns the time each frame was handed to the window."""
    times = []
    for pcm in pcm_frames:
        clock.t += work
        out.frame(pcm, True)
        times.append(clock.t)
    return times


@test
def dc_block():
    tone = square(440, 1.0)
    dc = rvmsound.DCBlock()
    y = samples(dc.process(tone))
    tail = y[len(y) // 2:]
    mean = sum(tail) / len(tail)
    check('a beeper tone (0 / +%d) swings around 0 after the DC blocker (mean %.1f)' % (A, mean),
          abs(mean) < 0.01 * A)
    ups = [i for i in range(1, len(tail)) if tail[i - 1] < 0 <= tail[i]]
    f = rvmsound.RATE * (len(ups) - 1) / (ups[-1] - ups[0])
    check('the pitch is untouched (%.2f Hz, tone 440)' % f, abs(f - 440) < 0.5)
    pp = max(tail) - min(tail)
    check('the level is kept (peak to peak %d of %d)' % (pp, A), 0.95 * A < pp < 1.1 * A)
    held = rvmsound.DCBlock()
    z = samples(held.process(b''.join([struct.pack('<h', A)] * 4410)))
    check('the beeper left high settles to silence within 0.1 s (last %d)' % z[-1], abs(z[-1]) < 0.01 * A)
    whole = rvmsound.DCBlock().process(tone)
    parts = rvmsound.DCBlock()
    pieced = b''.join(parts.process(p) for p in frames_of(tone))
    check('frame by frame gives the same samples as all at once (no seam between frames)',
          whole == pieced)
    check('nothing in, nothing out', rvmsound.DCBlock().process(b'') == b'')
    loud = samples(rvmsound.DCBlock().process(square(50, 0.5)))
    check('no 16-bit overflow at the lowest beeper pitches (%d..%d)' % (min(loud), max(loud)),
          -32768 < min(loud) and max(loud) < 32767)


@test
def wall_clock():
    c = Clock()
    w = rvmsound.WallClock(now=c.now, sleep=c.sleep)
    due = []
    for _ in range(500):
        c.t += 0.008                      # the frame's own work
        w.wait()
        due.append(c.t)
    rate = (len(due) - 1) / (due[-1] - due[0])
    check('the wall clock gives the Spectrum\'s rate (%.3f frames a second, 50.080)' % rate,
          abs(rate - 1 / rvmsound.FRAME_S) < 0.001)
    check('a frame period is 69888 T-states (%.4f ms)' % (rvmsound.FRAME_S * 1000),
          abs(rvmsound.FRAME_S - 69888 / 3.5e6) < 1e-12)
    c.t += 2.0                            # the host stalls for 2 s
    stall = c.t
    n0 = len(c.sleeps)
    c.t += 0.008
    w.wait()
    check('after a stall the next frame goes at once (no sleep)', len(c.sleeps) == n0 and c.t == stall + 0.008)
    after = [c.t]
    for _ in range(5):
        c.t += 0.008
        w.wait()
        after.append(c.t)
    gaps = [b - a for a, b in zip(after, after[1:])]
    check('... then the frame rate again, without a burst of frames to catch up (%s ms)'
          % ', '.join('%.3f' % (g * 1000) for g in gaps),
          all(abs(g - rvmsound.FRAME_S) < 1e-9 for g in gaps))
    slow = Clock()
    w = rvmsound.WallClock(now=slow.now, sleep=slow.sleep)
    due = []
    for _ in range(50):
        slow.t += 0.0195                  # nearly a whole frame of work
        w.wait()
        due.append(slow.t)
    rate = (len(due) - 1) / (due[-1] - due[0])
    check('a host that only just keeps up still runs at 50.08 a second (%.3f)' % rate,
          abs(rate - 1 / rvmsound.FRAME_S) < 0.001)
    late = Clock()
    w = rvmsound.WallClock(now=late.now, sleep=late.sleep)
    for _ in range(50):
        late.t += 0.025                   # slower than the Spectrum
        w.wait()
    check('a host that cannot keep up runs as fast as it can, never sleeping', late.sleeps == [])


@test
def stream_is_gapless_and_keeps_time():
    c = Clock()
    dev = Device(c)
    out = rvmsound.Output(stream=dev, sleep=c.sleep)
    tone = square(523.25, 4.0) + bytes(2 * 44100) + square(261.63, 2.0)
    pcm_frames = frames_of(tone)
    times = run_machine(out, c, pcm_frames)
    want = rvmsound.DCBlock().process(b''.join(pcm_frames))
    check('every frame\'s samples reach the device, in order, nothing added or lost (%d frames)'
          % len(pcm_frames), bytes(dev.data) == want)
    steady = times[20:]
    rate = (len(steady) - 1) / (steady[-1] - steady[0])
    check('the device sets the pace: %.3f frames a second (50.080)' % rate,
          abs(rate - 1 / rvmsound.FRAME_S) < 0.05)
    check('the device never ran dry once playing (%d gaps)' % dev.gaps, dev.gaps <= 1)
    check('at most %.0f ms of sound waits ahead of the speaker (%.1f ms)'
          % ((rvmsound.LATENCY + rvmsound.FRAME_S) * 1000, dev.max_queued * 1000),
          dev.max_queued <= rvmsound.LATENCY + rvmsound.FRAME_S + 1e-9)
    check('silent frames are streamed too (the stream never stops)', dev.writes == len(pcm_frames))
    out.close()
    check('closing at the end lets the queued sound play out', dev.closed is True)


@test
def slow_host_underruns_but_never_drops():
    c = Clock()
    dev = Device(c)
    out = rvmsound.Output(stream=dev, sleep=c.sleep)
    pcm_frames = frames_of(square(440, 3.0))
    run_machine(out, c, pcm_frames, work=0.030)            # 30 ms a frame: too slow
    want = rvmsound.DCBlock().process(b''.join(pcm_frames))
    check('a host slower than the Spectrum: the sound has gaps (%d) but every sample is played'
          % dev.gaps, dev.gaps > 10 and bytes(dev.data) == want)
    check('... and the machine is not held back by the sound (no sleeps)', c.sleeps == [])


@test
def failing_device_falls_back():
    c = Clock()
    dev = Device(c, fail_after=30)
    out = rvmsound.Output(stream=dev, clock=rvmsound.WallClock(now=c.now, sleep=c.sleep),
                          sleep=c.sleep)
    pcm_frames = frames_of(square(440, 2.0))
    times = run_machine(out, c, pcm_frames)
    check('a device that stops mid-run: every frame still goes on (%d)' % len(times),
          len(times) == len(pcm_frames))
    rate = (len(times[40:]) - 1) / (times[-1] - times[40])
    check('... on the wall clock at 50.08 a second (%.3f)' % rate, abs(rate - 1 / rvmsound.FRAME_S) < 0.05)
    check('... the device was closed without waiting', dev.closed is False)
    check('... and --verbose says why: "%s"' % out.describe(), 'device gone' in out.describe())
    out.close()


class FakeWinmm:
    """winmm.dll as waveOut uses it, played on a simulated clock.  Checks
    every call's arguments, that a buffer stays prepared, alive and
    unchanged until the device has played it, and that each prepared
    header is unprepared exactly once."""

    def __init__(self, clock, open_rc=0):
        self.clock = clock
        self.open_rc = open_rc
        self.calls = []
        self.queue = []                    # headers written, oldest first
        self.played = bytearray()
        self.prepared = set()
        self.errors = []
        self.start = None
        self.pos = 0.0                     # samples played into the queue head
        self.handle = 0x1234
        self.closed = False
        self.reset = False

        def fn(name):
            def call(*args):
                self.calls.append(name)
                return getattr(self, '_' + name)(*args)
            return call
        for name in ('waveOutOpen', 'waveOutPrepareHeader', 'waveOutWrite',
                     'waveOutUnprepareHeader', 'waveOutReset', 'waveOutClose'):
            setattr(self, name, type('F', (), {'__call__': staticmethod(fn(name))})())

    def _waveOutOpen(self, ph, dev, pfmt, cb, inst, flags):
        fmt = pfmt._obj
        self.fmt = (fmt.wFormatTag, fmt.nChannels, fmt.nSamplesPerSec, fmt.nAvgBytesPerSec,
                    fmt.nBlockAlign, fmt.wBitsPerSample, fmt.cbSize)
        self.open_args = (dev, cb, inst, flags)
        if self.open_rc:
            return self.open_rc
        ph._obj.value = self.handle
        return 0

    def _hdr(self, h, ph, size):
        if h.value != self.handle:
            self.errors.append('wrong handle')
        if size != ctypes.sizeof(ph._obj):
            self.errors.append('wrong header size')
        return ph._obj

    def _waveOutPrepareHeader(self, h, ph, size):
        hdr = self._hdr(h, ph, size)
        self.prepared.add(ctypes.addressof(hdr))
        hdr.dwFlags |= 2                   # WHDR_PREPARED
        return 0

    def _waveOutWrite(self, h, ph, size):
        hdr = self._hdr(h, ph, size)
        if ctypes.addressof(hdr) not in self.prepared:
            self.errors.append('write of an unprepared header')
        hdr.dwFlags &= ~1
        snap = ctypes.string_at(hdr.lpData, hdr.dwBufferLength)
        self.queue.append((hdr, snap))
        self.advance()
        if self.start is None:
            self.start = self.clock.t
        return 0

    def _waveOutUnprepareHeader(self, h, ph, size):
        hdr = self._hdr(h, ph, size)
        a = ctypes.addressof(hdr)
        if a not in self.prepared:
            self.errors.append('unprepare twice or never prepared')
        if not hdr.dwFlags & 1:
            self.errors.append('unprepare before the device was done')
        self.prepared.discard(a)
        return 0

    def _waveOutReset(self, h):
        self.reset = True
        for hdr, snap in self.queue:
            hdr.dwFlags |= 1
        self.queue = []
        return 0

    def _waveOutClose(self, h):
        if self.prepared:
            self.errors.append('close with buffers still prepared')
        self.closed = True
        return 0

    def advance(self):
        """Play what the simulated time allows; a buffer is read when it is
        played, so a buffer freed or changed early would show here."""
        if self.start is None:
            return
        budget = (self.clock.t - self.start) * rvmsound.RATE - self.pos_total()
        while self.queue and budget > 0:
            hdr, snap = self.queue[0]
            now = ctypes.string_at(hdr.lpData, hdr.dwBufferLength)
            if now != snap:
                self.errors.append('a buffer changed before it was played')
            n = len(snap) // 2
            left = n - self.pos
            if budget >= left:
                budget -= left
                self.played += snap
                hdr.dwFlags |= 1
                self.queue.pop(0)
                self.pos = 0.0
                self._done = getattr(self, '_done', 0) + n
            else:
                self.pos += budget
                budget = 0
        if not self.queue:                 # ran dry: the clock restarts at the next write
            self.start = None
            self.pos = 0.0
            self._done = 0

    def pos_total(self):
        return getattr(self, '_done', 0) + self.pos


def fake_waveout(clock, open_rc=0):
    lib = FakeWinmm(clock, open_rc)

    class W(rvmsound.WaveOut):
        def _library(self):
            return lib

        def queued(self):
            lib.advance()
            return rvmsound.WaveOut.queued(self)
    return W, lib


@test
def waveout_layout():
    c = Clock()
    W, lib = fake_waveout(c)
    w = W()
    hdr = w.WAVEHDR()
    p64 = ctypes.sizeof(ctypes.c_void_p) == 8
    check('WAVEHDR is %d bytes, as in the Windows SDK (%d)' % (48 if p64 else 32, ctypes.sizeof(hdr)),
          ctypes.sizeof(hdr) == (48 if p64 else 32))
    check('WAVEHDR.dwFlags at offset %d' % (24 if p64 else 16),
          type(hdr).dwFlags.offset == (24 if p64 else 16))
    check('WAVEFORMATEX is 18 bytes, packed as mmsystem.h packs it (%d)' % ctypes.sizeof(w.WAVEFORMATEX),
          ctypes.sizeof(w.WAVEFORMATEX) == 18)
    check('the format is 16-bit mono PCM at 44100 Hz, 88200 bytes a second',
          lib.fmt == (1, 1, 44100, 88200, 2, 16, 0), str(lib.fmt))
    check('opened on WAVE_MAPPER (the default device), no callback',
          lib.open_args == (0xFFFFFFFF, 0, 0, 0), str(lib.open_args))
    w.close(drain=False)


@test
def waveout_streams():
    c = Clock()
    W, lib = fake_waveout(c)
    out = rvmsound.Output(stream=W(), sleep=c.sleep)
    pcm_frames = frames_of(square(392, 3.0))
    run_machine(out, c, pcm_frames)
    c.t += 1.0                                       # let the last of it play
    out.stream.queued()
    want = rvmsound.DCBlock().process(b''.join(pcm_frames))
    check('waveOut plays every frame\'s samples in order, back to back (%d buffers)' % len(pcm_frames),
          bytes(lib.played) == want)
    check('no buffer was freed, changed or unprepared before it was played: %s' % (lib.errors or 'none'),
          not lib.errors)
    check('every buffer was prepared, written, and unprepared once played',
          lib.calls.count('waveOutPrepareHeader') == len(pcm_frames) ==
          lib.calls.count('waveOutWrite') == lib.calls.count('waveOutUnprepareHeader'))
    check('the speaker never ran dry while playing (%d)' % out.dry, out.dry == 0)
    check('--verbose names the stream: "%s"' % out.describe(), out.describe().startswith('sound: waveOut'))
    out.close(drain=False)
    check('closing resets and closes the device, nothing left prepared',
          lib.reset and lib.closed and not lib.prepared and not lib.errors, str(lib.errors))


@test
def waveout_close_mid_play():
    c = Clock()
    W, lib = fake_waveout(c)
    out = rvmsound.Output(stream=W(), sleep=c.sleep)
    run_machine(out, c, frames_of(square(440, 0.5)))
    queued = len(lib.queue)
    out.close(drain=False)
    check('closing the window with %d buffers queued: reset, all unprepared, closed' % queued,
          queued > 0 and lib.reset and lib.closed and not lib.prepared and not lib.errors,
          str(lib.errors))


@test
def waveout_open_fails():
    c = Clock()
    W, lib = fake_waveout(c, open_rc=2)               # MMSYSERR_BADDEVICEID
    try:
        W()
        ok = False
    except rvmsound.StreamError as e:
        ok = 'waveOutOpen' in str(e)
    check('no sound device: waveOutOpen\'s error is a StreamError', ok)
    real = rvmsound.WaveOut
    rvmsound.WaveOut = W
    try:
        out = rvmsound.open_output(platform='win32')
    finally:
        rvmsound.WaveOut = real
    check('... and the window runs silent on the wall clock: "%s"' % out.describe(),
          out.stream is None and 'waveOutOpen failed' in out.describe())


def recorder(path):
    """A Popen stand-in: a real process that writes its stdin to PATH."""
    def popen(args, **kw):
        recorder.args = args
        code = 'import sys; open(sys.argv[1], "wb").write(sys.stdin.buffer.read())'
        return subprocess.Popen([sys.executable, '-c', code, path], **kw)
    return popen


@test
def pipe_streams():
    path = os.path.join(TMP, 'pipe.raw')
    for prog, want in (('paplay', ['paplay', '--raw', '--format=s16le', '--channels=1',
                                   '--rate=44100', '--latency-msec=80']),
                       ('aplay', ['aplay', '-q', '-t', 'raw', '-f', 'S16_LE', '-c', '1',
                                  '-r', '44100', '-B', '80000'])):
        p = rvmsound.PipeOut(prog, popen=recorder(path))
        check('%s is started for raw 16-bit mono 44100 Hz, 80 ms buffer' % prog,
              recorder.args == want, str(recorder.args))
        out = rvmsound.Output(stream=p)
        pcm_frames = frames_of(square(330, 1.0))
        for f in pcm_frames:
            out.frame(f)
        out.close()
        got = open(path, 'rb').read()
        check('%s gets every frame\'s samples, in order, as one stream' % prog,
              got == rvmsound.DCBlock().process(b''.join(pcm_frames)))


@test
def pipe_player_dies():
    def popen(args, **kw):
        return subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(3)'], **kw)
    p = rvmsound.PipeOut('aplay', popen=popen)
    p.p.wait()
    c = Clock()
    out = rvmsound.Output(stream=p, clock=rvmsound.WallClock(now=c.now, sleep=c.sleep), sleep=c.sleep)
    for f in frames_of(square(330, 0.5)):
        c.t += 0.008
        out.frame(f)
    check('a player that exits (no device): the run goes on silent on the wall clock: "%s"'
          % out.describe(), out.stream is None and 'aplay ended (status 3)' in out.describe())
    missing = rvmsound.open_output(platform='linux', which=lambda p: '/nowhere/' + p if p == 'aplay' else None)
    check('an aplay that cannot be started: silent, with the reason: "%s"' % missing.describe(),
          missing.stream is None and 'aplay' in missing.describe())


@test
def spare_player():
    """paplay with no sound server exits: aplay takes over, mid-run"""
    def dies(args, **kw):
        return subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(1)'], **kw)
    first = rvmsound.PipeOut('paplay', popen=dies)
    first.p.wait()
    path = os.path.join(TMP, 'spare.raw')
    c = Clock()
    out = rvmsound.Output(stream=first, clock=rvmsound.WallClock(now=c.now, sleep=c.sleep),
                          sleep=c.sleep,
                          spare=[lambda: rvmsound.PipeOut('aplay', popen=recorder(path))])
    pcm_frames = frames_of(square(330, 0.5))
    for f in pcm_frames:
        out.frame(f)
    name = out.stream.name if out.stream else None
    out.close()
    got = open(path, 'rb').read()
    check('a player that fails is replaced by the next (%s), and no frame is lost' % name,
          name == 'aplay' and got == rvmsound.DCBlock().process(b''.join(pcm_frames)))
    check('... and only the wall clock is left when no player works',
          rvmsound.Output(stream=None).describe().startswith('sound: none'))


@test
def choice_of_output():
    made = []

    class P:
        def __init__(self, prog):
            made.append(prog)
            self.name = prog
    real = rvmsound.PipeOut
    rvmsound.PipeOut = P
    try:
        both = rvmsound.open_output(platform='linux', which=lambda p: '/usr/bin/' + p)
        only = rvmsound.open_output(platform='linux', which=lambda p: '/usr/bin/aplay' if p == 'aplay' else None)
    finally:
        rvmsound.PipeOut = real
    check('Linux: paplay first (PulseAudio / PipeWire), then aplay', made == ['paplay', 'aplay'],
          str(made))
    check('... as the stream', both.stream.name == 'paplay' and only.stream.name == 'aplay')
    mac = rvmsound.open_output(platform='darwin', which=lambda p: '/usr/bin/afplay' if p == 'afplay' else None)
    check('macOS: afplay, in short files: "%s"' % mac.describe(),
          mac.stream is None and mac.files is not None and 'afplay' in mac.describe())
    mac.close()
    none = rvmsound.open_output(platform='linux', which=lambda p: None)
    check('nothing to play with: silent, on the clock', none.stream is None and none.files is None)
    muted = rvmsound.open_output(mute=True, platform='win32')
    check('--mute: no device is opened', muted.stream is None and muted.files is None)


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
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
