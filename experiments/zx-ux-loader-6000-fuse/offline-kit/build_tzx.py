#!/usr/bin/env python3
"""Offline ZX-UX 48K compact 1.5x TZX generator; Python stdlib only.

Preserves the precise bootstrap and tape frame timing validated by Fuse 1.6.0.
Input is a Spectrum TAP with one or more contiguous CODE blocks.  The default
start and final entry is 0x6000. No network or external compiler is required.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

PROJECT_VERSION = "1.0.0-offline"
DEFAULT_ENTRY = 0x6000
DEFAULT_SEGMENTS = 24
ZERO_T = 1140
ONE_T = 2280
PILOT_T = 450
PILOT_EDGES = 1600
SYNC1_T = 250
SYNC2_T = 499
MINISYNC_T = 501
INTER_SEGMENT_MS = 20
BOOTSTRAP_SHA256 = "95a4b505085391fdc6d001c3ced1edd185245c921f8dbc8cadbdcd59d1a24888"
BOOTSTRAP_TAP_BASE64 = (
    "EwAAAHpxbG9hZGVyICCFAQoAhQEQhwH/AAoTAP0wDgAAUF8AOvXAMA4AAOdcAA0AFGoB6s2vDSGWXRFH/wG5AO2w89nV5cUh7/8BEQDZDgomRx5AzW//KETZOvb/uyA37Vv5/9XtW/f/1e1b8/96sygPKvH/7Uvv/zr1/z0oKu2w4dF8PSjAPcpe/z0oFXqzKATr+ev76RFU/81H/xFY/81H/8Hh0dn7yTr9/wjtS/v/3Sr+/34juSgW3b0oCxITEPMIPSi7CBjsvigUfiMYBr4oDTr//8VGEhMQ/MEjGOAjGNsaE8t/IAPXGPfmf9fJQ1JDoEVSUk9SjTEKUBEKUCH6XAGcAO2wwwpQPr/b/g/QzeP/KPUuyAYMzeP/KOx4/gYw5y0g8QYMzeP/KN14/gow2P4GOPB57gNPzbL/yNkeAe1L7/8q8f94sdkoLRZABsjN4//IAC4BQgXI2/6poyj4eaxP0/54/hnLFdK9/33Zd4MHX+2h2eq7/7LJBcjb/qmjKPh5rE/T/skAAAAAAAAAAAAAAAAAAAAAAA2i"
)


class TapeError(ValueError):
    """Bad input tape, memory layout, or builder invariants."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_tap_blocks(tap: bytes) -> list[bytes]:
    blocks: list[bytes] = []
    offset = 0
    while offset < len(tap):
        if offset + 2 > len(tap):
            raise TapeError(f"Truncated TAP block length at offset {offset}")
        length = struct.unpack_from("<H", tap, offset)[0]
        offset += 2
        if length < 2 or offset + length > len(tap):
            raise TapeError(f"Invalid TAP block length {length} at {offset-2}")
        block = tap[offset:offset + length]
        if _xor(block) != 0:
            raise TapeError(f"Bad TAP XOR checksum in block {len(blocks)}")
        blocks.append(block)
        offset += length
    if not blocks:
        raise TapeError("Empty TAP source")
    return blocks


def _xor(blob: bytes) -> int:
    check = 0
    for byte in blob:
        check ^= byte
    return check


def extract_contiguous_code(tap: bytes, entry: int) -> tuple[bytes, list[dict]]:
    """Validate all TAP header/data pairs; combine only CODE blocks in order.

    BASIC and other header/data pairs are checked but not copied to the new TZX;
    the new TZX always supplies its own verified ZQLoader BASIC bootstrap.
    """
    blocks = read_tap_blocks(tap)
    programs: list[dict] = []
    combined = bytearray()
    if entry < 0x6000 or entry >= 0xFF47:
        raise TapeError("Entry must be in safe payload RAM, 0x6000..0xFF46")
    cursor = 0
    while cursor < len(blocks):
        header = blocks[cursor]
        if len(header) != 19 or header[0] != 0:
            raise TapeError(f"Expected 19-byte Spectrum header at TAP block {cursor}")
        block_type = header[1]
        if block_type not in (0, 1, 2, 3):
            raise TapeError(f"Unknown Spectrum header type {block_type} at block {cursor}")
        name = header[2:12].decode("ascii", errors="replace").rstrip()
        length, load_address, parameter_two = struct.unpack_from("<HHH", header, 12)
        if cursor + 1 >= len(blocks):
            raise TapeError(f"No data block following header {name!r}")
        data = blocks[cursor + 1]
        if data[0] != 0xFF or len(data) != length + 2:
            raise TapeError(f"Bad/mismatched data block following header {name!r}")
        if block_type == 3:  # Spectrum CODE header
            required_address = entry + len(combined)
            if load_address != required_address:
                raise TapeError(
                    f"CODE block {name!r} loads at 0x{load_address:04X}, "
                    f"expected contiguous 0x{required_address:04X}"
                )
            combined.extend(data[1:-1])
            programs.append({"name": name, "load_address": load_address,
                             "length": length, "source_tap_header_index": cursor})
        cursor += 2
    if not programs:
        raise TapeError("No Spectrum CODE header/data pairs found")
    # ZQLoader is relocated to the top of 48K RAM at 0xFF47 and must not be
    # overwritten by an expanding source payload.
    if entry + len(combined) > 0xFF47:
        raise TapeError(
            f"CODE payload ends at 0x{entry+len(combined)-1:04X}, "
            "overlapping relocated ZQLoader at 0xFF47"
        )
    return bytes(combined), programs


def bootstrap_blocks() -> tuple[bytes, bytes]:
    tape = base64.b64decode(BOOTSTRAP_TAP_BASE64, validate=True)
    if sha256(tape) != BOOTSTRAP_SHA256:
        raise TapeError("Embedded, Fuse-verified loader bootstrap hash mismatch")
    blocks = read_tap_blocks(tape)
    if len(blocks) != 2 or len(blocks[0]) != 19 or len(blocks[1]) != 391:
        raise TapeError("Embedded ZQLoader bootstrap has unexpected TAP structure")
    # Only the exact runtime-proven 1.5x timing-patched machine-code loader.
    if blocks[1][0x138] != 64 or blocks[1][0x152] != 25:
        raise TapeError("ZQLoader timing patch bytes are not the proven values")
    return blocks[0], blocks[1]


def zq_checksum(payload: bytes) -> int:
    result = 1
    for byte in payload:
        result = (result + byte) & 255
        result = ((result << 1) | (result >> 7)) & 255
    return result


def segment_header(data: bytes, address: int, after: int) -> bytes:
    # ZQLoader's 17-byte struct: length, load_addr, copy_dest, bank, CRC,
    # after_block, reserved words/bytes.  0x0100 = next block; final is JMP.
    header = struct.pack(
        "<HHHBBHHBHBB", len(data), address, 0, 0, zq_checksum(data),
        after, 0, 0, 0, 0, 0,
    )
    assert len(header) == 17
    return header


def generalized_block(raw_data: bytes, symbols: list[tuple[tuple[int, ...], int]]) -> bytes:
    """Write upstream-compatible, compact TZX 0x19 one-toggle-per-bit block."""
    if not raw_data or not symbols:
        raise TapeError("Generalized block requires nonempty data and pilots")
    npp = max(len(pulses) for pulses, _repeat in symbols)
    asp = len(symbols)
    totp = len(symbols)
    npd, asd = 1, 2
    body = bytearray(struct.pack("<HIBBI", 0, totp, npp, asp, len(raw_data) * 8))
    body.extend((npd, asd))
    for pulses, _repetitions in symbols:
        body.append(0)  # Edge::toggle
        for duration in (*pulses, *((0,) * (npp - len(pulses)))):
            body.extend(struct.pack("<H", duration))
    for i, (_pulses, repetitions) in enumerate(symbols):
        body.extend(struct.pack("<BH", i, repetitions))
    body.extend(struct.pack("<BH", 0, ZERO_T))
    body.extend(struct.pack("<BH", 0, ONE_T))
    body.extend(raw_data)
    return bytes((0x19,)) + struct.pack("<I", len(body)) + bytes(body)


def std_block(data: bytes, pause_ms: int) -> bytes:
    return bytes((0x10,)) + struct.pack("<HH", pause_ms, len(data)) + data


def pause_block(ms: int) -> bytes:
    return b"\x20" + struct.pack("<H", ms)


def build_tzx(payload: bytes, *, entry: int, segments: int) -> tuple[bytes, list[dict]]:
    if not (1 <= segments <= 255) or segments > len(payload):
        raise TapeError("Segments must be 1..255 and no more than payload bytes")
    boot_header, boot_data = bootstrap_blocks()
    base, extra = divmod(len(payload), segments)
    sizes = [base + (i < extra) for i in range(segments)]
    tzx = bytearray(b"ZXTape!\x1a\x01\x14")
    tzx.extend(std_block(boot_header, 1000))
    tzx.extend(std_block(boot_data, 1500))
    chunks = []
    offset = 0
    for index, length in enumerate(sizes):
        data = payload[offset:offset + length]
        address = entry + offset
        after = entry if index == segments - 1 else 0x0100
        header = segment_header(data, address, after)
        tzx.extend(generalized_block(header, [
            ((PILOT_T, PILOT_T), PILOT_EDGES // 2),
            ((SYNC1_T, SYNC2_T), 1),
        ]))
        tzx.extend(generalized_block(data, [((MINISYNC_T,), 1)]))
        if index < segments - 1:
            tzx.extend(pause_block(INTER_SEGMENT_MS))
        chunks.append({"index": index + 1, "address": f"0x{address:04X}",
                       "length": length, "checksum": zq_checksum(data),
                       "after": f"0x{after:04X}"})
        offset += length
    assert offset == len(payload)
    return bytes(tzx), chunks


def save_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def deterministic_zip(filename: str, tzx: bytes) -> bytes:
    # Fixed metadata makes the ZIP bit-for-bit reproducible across machines.
    import io
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        record = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
        record.compress_type = zipfile.ZIP_DEFLATED
        record.create_system = 3
        record.external_attr = 0o100644 << 16
        archive.writestr(record, tzx, compress_type=zipfile.ZIP_DEFLATED,
                         compresslevel=9)
    return memory.getvalue()


def parse_int(value: str) -> int:
    return int(value, 0)


def main(argv: list[str] | None = None) -> int:
    cmd = argparse.ArgumentParser(description=__doc__)
    cmd.add_argument("source", type=Path,
                     help="New source ZX Spectrum TAP file (one or more contiguous CODE blocks)")
    cmd.add_argument("--out", type=Path,
                     default=Path("output/zx-ux-new-loader-test.tzx"),
                     help="Output TZX (default: output/zx-ux-new-loader-test.tzx)")
    cmd.add_argument("--entry", type=parse_int, default=DEFAULT_ENTRY,
                     help="Load address and final jump (default: 0x6000; alternatives not Fuse-proven)")
    cmd.add_argument("--segments", type=int, default=DEFAULT_SEGMENTS,
                     help="Number of turbo segments (default: 24)")
    cmd.add_argument("--no-zip", action="store_true", help="Don't write the paired ZIP")
    args = cmd.parse_args(argv)
    try:
        if not args.source.is_file():
            raise TapeError(f"No such source tape: {args.source}")
        source = args.source.read_bytes()
        payload, original_blocks = extract_contiguous_code(source, args.entry)
        tzx, chunks = build_tzx(payload, entry=args.entry, segments=args.segments)
        output = args.out.resolve()
        if output == args.source.resolve():
            raise TapeError("Output TZX would overwrite source TAP")
        save_atomic(output, tzx)
        zip_path = output.with_name(output.name + ".zip")
        zip_data = None if args.no_zip else deterministic_zip(output.name, tzx)
        if zip_data is not None:
            save_atomic(zip_path, zip_data)
        manifest = {
            "builder_version": PROJECT_VERSION,
            "source_file": args.source.name,
            "source_tap_sha256": sha256(source),
            "source_code_blocks": original_blocks,
            "payload_sha256": sha256(payload),
            "payload_size": len(payload),
            "address_start": f"0x{args.entry:04X}",
            "address_end": f"0x{args.entry+len(payload)-1:04X}",
            "final_jump": f"0x{args.entry:04X}",
            "segments": args.segments,
            "bit_tstates": {"zero": ZERO_T, "one": ONE_T},
            "pilot": {"pulse_tstates": PILOT_T, "edges": PILOT_EDGES},
            "sync_tstates": [SYNC1_T, SYNC2_T],
            "minisync_tstates": MINISYNC_T,
            "inter_segment_ms": INTER_SEGMENT_MS,
            "tzx_sha256": sha256(tzx),
            "tzx_size": len(tzx),
            "zip_sha256": None if zip_data is None else sha256(zip_data),
            "verified_embedded_bootstrap_sha256": BOOTSTRAP_SHA256,
            "runtime_verified_configuration": args.entry == 0x6000 and args.segments == 24,
            "note": "The builder is verified; each NEW source TAP requires its own runtime test.",
            "chunks": chunks,
        }
        save_atomic(output.with_name(output.name + ".manifest.json"),
                    (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print(f"Source SHA256:  {manifest['source_tap_sha256']}")
        print(f"Payload:        {len(payload)} bytes from {manifest['address_start']} "
              f"through {manifest['address_end']}")
        print(f"TZX SHA256:     {manifest['tzx_sha256']}")
        print(f"TZX:            {output} ({len(tzx)} bytes)")
        if zip_data is not None:
            print(f"ZIP:            {zip_path} ({len(zip_data)} bytes)")
        print("TZX manifest:   " + str(output) + ".manifest.json")
        return 0
    except (TapeError, OSError, struct.error) as error:
        print(f"BUILD FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())