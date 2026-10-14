#!/usr/bin/env python3
"""One-command reproducible ZX-UX release maker (Python standard library only)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from build import ROOT, build, source_tap
from verify import verify


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release(source: Path, text: Path, name: str, output_dir: Path, *, run_tests=True):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', name) or name.endswith('.'):
        raise ValueError('release name must be 1-80 letters, digits, dots, underscores or dashes')
    src_bytes=source.read_bytes()
    normalized=source_tap(source)
    rows=text.read_text('ascii').splitlines()
    data, meta=build(normalized,rows)
    # Safety: do not accidentally overwrite the user's source tape.
    dest=output_dir / (name+'.tzx')
    if dest.resolve()==source.resolve():
        raise ValueError('output would overwrite source tape')
    output_dir.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
    verify(dest, source, text)
    # Run 48K tape generator checks against the release code and source fixture.
    if run_tests:
        subprocess.run([sys.executable,'-m','unittest','-v','test_build'],cwd=ROOT,check=True)
    zip_path=dest.with_suffix('.tzx.zip')
    with zipfile.ZipFile(zip_path,'w') as z:
        zi=zipfile.ZipInfo(dest.name,date_time=(2026,10,14,0,0,0))
        zi.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(zi,data)
    with zipfile.ZipFile(zip_path) as z:
        if z.namelist()!=[dest.name] or z.read(dest.name)!=data or z.testzip() is not None:
            raise AssertionError('TZX ZIP failed round-trip check')
    meta.update({
        'release_name':name,'source_filename':source.name,
        'source_file_sha256':sha256(src_bytes),'normalized_source_tap_sha256':sha256(normalized),
        'text_file_sha256':sha256(text.read_bytes()),
        'build_py_sha256':sha256((ROOT/'build.py').read_bytes()),
        'verify_py_sha256':sha256((ROOT/'verify.py').read_bytes()),
        'zip_sha256':sha256(zip_path.read_bytes()),
        'verification':'static TZX/payload/parity checks + unit tests' if run_tests else 'static TZX/payload/parity checks',
        'runtime_fuse_verified':False,
    })
    manifest=dest.with_suffix('.json')
    manifest.write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    checksums=output_dir / (name+'.SHA256SUMS.txt')
    checksums.write_text(''.join(f'{sha256(p.read_bytes())}  {p.name}\n' for p in
                                 (dest,zip_path,manifest)),encoding='ascii')
    print(json.dumps({'tzx':str(dest),'tzx_zip':str(zip_path),'manifest':str(manifest),
                      'sha256sums':str(checksums),'tzx_sha256':meta['tzx_sha256'],
                      'source_sha256':meta['source_file_sha256'],
                      'bytes':len(data),'kernel_and_fs_bytes':meta['payload_bytes'],
                      'turbo_pauses_ms':meta['turbo_interblock_pause_ms']},indent=2))
    return dest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path,nargs='?',default=ROOT/'ZX-UX.tap',help='new kernel+filesystem .tap or standard-speed .tzx')
    ap.add_argument('--text',type=Path,default=ROOT/'text-lines.txt',help='24 progress lines, each 32 ASCII columns')
    ap.add_argument('--name',default='zx-ux-new-loader-test',help='output filename prefix')
    ap.add_argument('--output-dir',type=Path,default=ROOT/'output')
    ap.add_argument('--skip-unit-tests',action='store_true',help='skip baseline unit tests; static payload verification still runs')
    a=ap.parse_args()
    release(a.source,a.text,a.name,a.output_dir,run_tests=not a.skip_unit_tests)

if __name__=='__main__':main()
