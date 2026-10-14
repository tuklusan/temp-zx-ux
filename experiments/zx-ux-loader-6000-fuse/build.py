#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, struct, zipfile

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "ZX-UX.tap"
OUT = ROOT / "output"
TZX = OUT / "zx-ux-new-loader-test.tzx"
ZIP = OUT / "zx-ux-new-loader-test.tzx.zip"

ZQ_B64 = "EwAAAHpxbG9hZGVyICCFAQoAhQEQhwH/AAoTAP0wDgAAUF8AOvXAMA4AAOdcAA0AFGoB6s2vDSGWXRFH/wG5AO2w89nV5cUh7/8BEQDZDgomRx5AzW//KETZOvb/uyA37Vv5/9XtW/f/1e1b8/96sygPKvH/7Uvv/zr1/z0oKu2w4dF8PSjAPcpe/z0oFXqzKATr+ev76RFU/81H/xFY/81H/8Hh0dn7yTr9/wjtS/v/3Sr+/34juSgW3b0oCxITEPMIPSi7CBjsvigUfiMYBr4oDTr//8VGEhMQ/MEjGOAjGNsaE8t/IAPXGPfmf9fJQ1JDoEVSUk9SjTEKUBEKUCH6XAGcAO2wwwpQPr/b/g/QzeP/KPUuyAYMzeP/KOx4/gYw5y0g8QYMzeP/KN14/gow2P4GOPB57gNPzbL/yNkeAe1L7/8q8f94sdkoLRYMBsjN4//IAC4BQgXI2/6poyj4eaxP0/54/gnLFdK9/33Zd4MHX+2h2eq7/7LJBcjb/qmjKPh5rE/T/skAAAAAAAAAAAAAAAAAAAAAAA3+"

ENTRY = 0x6000
SEGMENTS = 24
ZERO_T = 1140
ONE_T = 2280
PILOT_T = 450
# The upstream proven leader lasts about 200 ms at 500 T-state pulses.
# Keep the requested approximately 400-T-state pulse, with 450 T and
# 1,600 edges (~206 ms) for robust acquisition at the new data rate.
# The payload bit timing remains exactly 1140/2280 T-states.
PILOT_EDGES = 1600
SYNC_T = 250
SYNC2_T = 499
MINISYNC_T = 501
INTER_SEGMENT_MS = 20

TOTAL_START = 0x5CCB
ASM_UPPER_START = 0xFF47
ASM_UPPER_START_OFFSET = 0x5D96
BIT_LOOP_MAX = 0xFFB3
BIT_ONE_THESHLD = 0xFFCD

def tap_blocks(data):
    p = 0
    out = []
    while p < len(data):
        if p + 2 > len(data):
            raise ValueError("truncated TAP length")
        n = struct.unpack_from("<H", data, p)[0]
        p += 2
        block = data[p:p+n]
        p += n
        if len(block) != n:
            raise ValueError("truncated TAP block")
        out.append(block)
    if p != len(data):
        raise ValueError("TAP trailing bytes")
    return out

def xor_checksum(data):
    x = 0
    for b in data:
        x ^= b
    return x

def patch_symbol_byte(block, symbol, value):
    adr = 1 + symbol
    if adr >= ASM_UPPER_START:
        adr -= ASM_UPPER_START
        adr += ASM_UPPER_START_OFFSET
    adr -= TOTAL_START
    block[adr] = value
    return adr

def zq_crc(payload):
    v = 1
    for b in payload:
        v = (v + b) & 0xff
        v = ((v << 1) | (v >> 7)) & 0xff
    return v

def header_for(chunk, address, after):
    h = struct.pack(
        "<HHHBBHHBHBB",
        len(chunk), address, 0, 0, zq_crc(chunk),
        after, 0, 0, 0, 0, 0
    )
    assert len(h) == 17
    return h

def generalized_data_block(data, pilot_symbols):
    """Compact standard TZX 0x19 block for ZQLoader one-edge-per-bit data.

    pilot_symbols is a list of (pulse_lengths, repetitions).  Every symbol
    toggles the EAR edge.  Data alphabet is exactly two symbols: zero and one,
    one pulse per bit, so the byte stream can be stored verbatim in the TZX.
    """
    if not data:
        raise ValueError("generalized data block needs data")

    npp = max(len(pulses) for pulses, _ in pilot_symbols) if pilot_symbols else 0
    asp = len(pilot_symbols)
    totp = len(pilot_symbols)
    totd = len(data) * 8
    npd = 1
    asd = 2

    body = bytearray()
    body += struct.pack("<H", 0)              # pause after block: 0 ms
    body += struct.pack("<I", totp)
    body += bytes([npp, asp])
    body += struct.pack("<I", totd)
    body += bytes([npd, asd])

    # Pilot/sync alphabet and sequence.
    for pulses, _ in pilot_symbols:
        body.append(0)                        # Edge::toggle
        padded = list(pulses) + [0] * (npp - len(pulses))
        body += struct.pack("<" + "H" * npp, *padded)
    for sym, (_, reps) in enumerate(pilot_symbols):
        body += struct.pack("<BH", sym, reps)

    # Data alphabet: symbol 0 = ZERO_T, symbol 1 = ONE_T.
    body += struct.pack("<BH", 0, ZERO_T)     # Edge::toggle + pulse
    body += struct.pack("<BH", 0, ONE_T)
    body += data

    return b"\x19" + struct.pack("<I", len(body)) + body

def std_block(data, pause_ms):
    return b"\x10" + struct.pack("<HH", pause_ms, len(data)) + data

def pause_block(ms):
    return b"\x20" + struct.pack("<H", ms)

zblocks = tap_blocks(base64.b64decode(ZQ_B64))
assert len(zblocks) == 2
loader_header = zblocks[0]
loader_data = bytearray(zblocks[1])
assert len(loader_header) == 19 and len(loader_data) == 391
assert xor_checksum(loader_header) == 0 and xor_checksum(loader_data) == 0

# 64 polling counts comfortably spans a 2280-T "1".  The compare byte is
# ONE_MAX-ZERO_MAX.  With a decision boundary of 39 polling cycles this is 25.
off_max = patch_symbol_byte(loader_data, BIT_LOOP_MAX, 64)
off_thr = patch_symbol_byte(loader_data, BIT_ONE_THESHLD, 25)
loader_data[-1] = 0
loader_data[-1] = xor_checksum(loader_data[:-1])
assert xor_checksum(loader_data) == 0
assert off_max == 0x138 and off_thr == 0x152

src = tap_blocks(SRC.read_bytes())
assert len(src) == 6
for b in src:
    assert xor_checksum(b) == 0

h1, d1, h2, d2 = src[2], src[3], src[4], src[5]
assert h1[0] == 0 and h1[1] == 3
assert h2[0] == 0 and h2[1] == 3
len1, addr1 = struct.unpack_from("<HH", h1, 12)
len2, addr2 = struct.unpack_from("<HH", h2, 12)
p1, p2 = d1[1:-1], d2[1:-1]
assert len(p1) == len1 and len(p2) == len2
assert addr1 == ENTRY
assert addr2 == addr1 + len1
payload = p1 + p2
assert len(payload) == 24670
assert PILOT_EDGES % 2 == 0 and PILOT_EDGES >= 600
assert ENTRY + len(payload) - 1 == 0xC05D

base, rem = divmod(len(payload), SEGMENTS)
sizes = [base + (1 if i < rem else 0) for i in range(SEGMENTS)]
assert sum(sizes) == len(payload)

tzx = bytearray(b"ZXTape!\x1a\x01\x14")
tzx += std_block(loader_header, 1000)
tzx += std_block(loader_data, 1500)

pos = 0
addr = ENTRY
for i, n in enumerate(sizes):
    chunk = payload[pos:pos+n]
    after = ENTRY if i == SEGMENTS - 1 else 0x0100
    header = header_for(chunk, addr, after)

    # Standard compact TZX representation used by ZQLoader itself:
    #   0x19: leader + sync/minisync + 17-byte turbo header
    #   0x19: minisync + payload bytes
    # This represents the same physical edge stream without expanding every
    # edge into a separate TZX pulse record.
    tzx += generalized_data_block(
        header,
        [
            ((PILOT_T, PILOT_T), PILOT_EDGES // 2),
            ((SYNC_T, SYNC2_T), 1),
        ],
    )
    tzx += generalized_data_block(
        chunk,
        [
            ((MINISYNC_T,), 1),
        ],
    )

    if i != SEGMENTS - 1:
        tzx += pause_block(INTER_SEGMENT_MS)

    pos += n
    addr += n

assert pos == len(payload)
assert addr == 0xC05E

OUT.mkdir(parents=True, exist_ok=True)
TZX.write_bytes(tzx)
with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.write(TZX, arcname=TZX.name)

print("input_sha256", hashlib.sha256(SRC.read_bytes()).hexdigest())
print("payload_sha256", hashlib.sha256(payload).hexdigest())
print("tzx_sha256", hashlib.sha256(tzx).hexdigest())
print("zip_sha256", hashlib.sha256(ZIP.read_bytes()).hexdigest())
print("payload", hex(ENTRY), hex(ENTRY + len(payload) - 1), len(payload))
print("segments", len(sizes), sizes)
print("timing", ZERO_T, ONE_T, PILOT_T, SYNC_T, SYNC2_T, MINISYNC_T)
print("tzx_size", len(tzx))
assert 24000 < len(tzx) < 32000
