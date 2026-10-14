"""The beeper for rvm: speaker edges -> PCM, WAV files, and host playback.

The machine logs every change of the beeper bit (port FEh bit 4) with its
T-state.  Rendering integrates the speaker level over each sample period
(3,500,000 / 44,100 T-states), so a tone's period is exactly the one the
Z80 code made: BEEP's frequency is the ROM's own, to the T-state.

Playback needs nothing outside Python's standard library: winsound on
Windows, otherwise afplay (macOS) or aplay / paplay (Linux) when present.
Sound goes out in short bursts (at most PLAY_CHUNK frames), so it follows
the picture within about a fifth of a second; the pitch never depends on
the host's speed.
"""
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading

CLOCK = 3500000
RATE = 44100
AMPLITUDE = 12000
PLAY_CHUNK = 10            # frames of sound per burst at most
SILENT_FLUSH = 2           # frames of silence that end a burst


class Beeper:
    """Turns (T-state, level) edges into 16-bit mono samples."""

    def __init__(self, t0=0, rate=RATE, level=0):
        self.rate = rate
        self.tps = CLOCK / rate            # T-states per sample
        self.pos = float(t0)               # T-state of the next sample
        self.level = level
        self.pending = []                  # edges at or after pos

    def feed(self, edges):
        self.pending.extend(edges)

    def render(self, t_end):
        """Samples from pos up to t_end (absolute T-states)."""
        out = []
        tps = self.tps
        pos = self.pos
        level = self.level
        edges = self.pending
        i = 0
        n = len(edges)
        while pos + tps <= t_end:
            end = pos + tps
            if i < n and edges[i][0] < end:
                high = 0.0
                t = pos
                while i < n and edges[i][0] < end:
                    te = max(edges[i][0], t)
                    if level:
                        high += te - t
                    t = te
                    level = edges[i][1]
                    i += 1
                if level:
                    high += end - t
                out.append(int(AMPLITUDE * high / tps))
            else:
                out.append(AMPLITUDE if level else 0)
            pos = end
        self.pos = pos
        self.level = level
        self.pending = edges[i:]
        return struct.pack('<%dh' % len(out), *out)


def wav_bytes(pcm, rate=RATE):
    return (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVE' +
            b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) +
            b'data' + struct.pack('<I', len(pcm)) + pcm)


def write_wav(path, pcm, rate=RATE):
    with open(path, 'wb') as f:
        f.write(wav_bytes(pcm, rate))


def edge_periods(edges):
    """Full periods (T-states between rising edges) of a tone."""
    rises = [t for t, lv in edges if lv]
    return [b - a for a, b in zip(rises, rises[1:])]


def rom_beep_hl(pitch):
    """The BEEPER delay BEEP (03F8h) computes for a pitch in semitones
    above middle C: f = 261.63 * 2^(pitch/12), HL = INT(437500/f - 30.125
    + 0.5) (FP-TO-BC rounds).  The ROM works in its own five-byte floats
    from a semitone table, so a pitch whose value lands within a rounding
    error of .5 can differ by one; tests read the ROM's own HL."""
    f = 261.6255653005986 * 2 ** (pitch / 12.0)
    return int(437500 / f - 30.125 + 0.5)


def beeper_period(hl):
    """BEEPER (03B5h) holds each level for 4 * HL + 118 T-states (interrupts
    off), so one period of the tone is 8 * HL + 236 T-states."""
    return 8 * hl + 236


class Player:
    """Plays bursts of samples on the host, in order, from a thread."""

    def __init__(self):
        self.q = queue.Queue(maxsize=64)
        self.method = self._find()
        self.burst = bytearray()
        self.quiet = 0
        self.frames = 0
        self.thread = None
        if self.method:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    @staticmethod
    def _find():
        if sys.platform == 'win32':
            try:
                import winsound    # noqa: F401
                return 'winsound'
            except ImportError:
                return None
        for prog in ('afplay', 'paplay', 'aplay'):
            if shutil.which(prog):
                return prog
        return None

    def frame(self, pcm, sounding):
        """One frame's samples; sounding: the beeper moved in it."""
        if not self.method:
            return
        if sounding:
            self.quiet = 0
        elif self.burst:
            self.quiet += 1
        if sounding or self.burst:
            self.burst += pcm
            self.frames += 1
        if self.burst and (self.quiet >= SILENT_FLUSH or self.frames >= PLAY_CHUNK):
            data = bytes(self.burst)
            self.burst = bytearray()
            self.frames = 0
            self.quiet = 0
            try:
                self.q.put_nowait(data)
            except queue.Full:
                pass                       # far behind: drop sound, never pictures

    def close(self):
        if self.thread:
            self.q.put(None)

    def _loop(self):
        while True:
            data = self.q.get()
            if data is None:
                return
            try:
                self._play(wav_bytes(data))
            except Exception:              # no sound device: carry on silently
                pass

    def _play(self, wav):
        if self.method == 'winsound':
            import winsound
            winsound.PlaySound(wav, winsound.SND_MEMORY)
            return
        fd, path = tempfile.mkstemp(suffix='.wav')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(wav)
            args = [self.method, path]
            if self.method == 'aplay':
                args = ['aplay', '-q', path]
            subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
