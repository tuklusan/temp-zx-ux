#!/usr/bin/env python3
"""Bare 1.5x TZX control: same TAP+framing, no progress callback. NOT FOR RELEASE."""
import runpy
from pathlib import Path
import hashlib
root=Path(__file__).resolve().parent
ns=runpy.run_path(str(root/'build.py'),run_name='control_import')
payload=ns['payload']
assert len(payload)==24802
tzx=bytearray(b'ZXTape!\x1a\x01\x14')
tzx+=ns['std_block'](ns['loader_header'],1000)
tzx+=ns['std_block'](ns['loader_data'],1500)
seg=ns['SEGMENTS']
base,extra=divmod(len(payload),seg)
off=0
for i in range(seg):
    n=base+(i<extra)
    chunk=payload[off:off+n]
    after=ns['ENTRY'] if i==seg-1 else 0x0100
    header=ns['header_for'](chunk,ns['ENTRY']+off,after)
    tzx+=ns['generalized_data_block'](
        header,[((ns['PILOT_T'],ns['PILOT_T']),ns['PILOT_EDGES']//2),
                ((ns['SYNC_T'],ns['SYNC2_T']),1)])
    tzx+=ns['generalized_data_block'](chunk,[((ns['MINISYNC_T'],),1)])
    if i<seg-1:tzx+=ns['pause_block'](ns['INTER_SEGMENT_MS'])
    off+=n
assert off==len(payload)
out=root/'output'/'bare-control.tzx'
out.write_bytes(tzx)
print('BARE DIAGNOSTIC NOT FOR RELEASE',out,len(tzx),hashlib.sha256(tzx).hexdigest())
