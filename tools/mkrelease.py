#!/usr/bin/env python3
"""Copy finished ZX-UX files to release/ without wrapping them in archives.

Run the build and tests first. You may pass a folder containing test logs.
It refuses to copy anything unless build/'s C48 programs and tapes are
exactly what a full rebuild makes (tools/mktapes.py --check).
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build'
RELEASE = ROOT / 'release'


def deliver(source: Path, name: str, required: bool = True) -> bool:
    if not source.is_file():
        if required:
            raise SystemExit(f'Missing build file: {source}')
        return False
    target = RELEASE / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print(f'{target.relative_to(ROOT)}  {target.stat().st_size} bytes')
    return True


def copy_matching(directory: Path, pattern: str, destination: str) -> int:
    count = 0
    for item in sorted(directory.glob(pattern)):
        if item.is_file():
            deliver(item, f'{destination}/{item.name}')
            count += 1
    return count


def copy_logs(directory: Path) -> None:
    """Exclude only empty, optional FUSE stdout/stderr diagnostics.

    Independent FUSE boot proof and JSON are still mandatory. Every
    other log is copied for the driver's nonempty-file validation.
    """
    for item in sorted(directory.glob('*.txt')):
        if not item.is_file():
            continue
        if (item.name in ('fuse-login.stdout.txt', 'fuse-login.stderr.txt')
                and item.stat().st_size == 0):
            continue
        deliver(item, f'logs/{item.name}')


def copy_fresh_proofs() -> None:
    """Deliver the exact reports and native ENV1 captures from this run.

    Release/manifest.txt will hash these files alongside the executable
    images. Avoid copying older build/proofs/ items into a fresh release.
    """
    for name in ('c48-conformance.json', 'ix-abi-proof.json',
                 'native-env1-v1.json'):
        deliver(BUILD / 'logs' / name, f'proofs/{name}')
    for name in ('sequential-1.png', 'sequential-1.scr',
                 'sequential-2.png', 'sequential-2.scr',
                 'concurrent.png', 'concurrent.scr'):
        deliver(BUILD / 'c48-env1' / 'proof' / name,
                f'proofs/native-env1/{name}')


def stale_c48() -> list:
    """[(path, problem)]: build/'s C48 files against a full rebuild."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mktapes
    return mktapes.stale([str(BUILD)])[str(BUILD)]


def require_fresh_c48() -> None:
    problems = stale_c48()
    for rel, problem in problems:
        print(f'build/{rel}: {problem}')
    if problems:
        raise SystemExit('C48 programs in build/ are not a fresh full build: '
                         'run tools/mktapes.py first')


def main(arguments: list[str]) -> None:
    require_fresh_c48()
    RELEASE.mkdir(parents=True, exist_ok=True)
    for name in ('ZX-UX.tzx', 'ZX-UX.tap', 'ZX-UX-c48.tzx',
                 'ZX-UX-multitask.z80', 'ZX-UX-multitask.png'):
        deliver(BUILD / name, name)
    deliver(BUILD / 'test.z80', 'ZX-UX.z80')
    deliver(BUILD / 'README.txt', 'README.txt')
    deliver(ROOT / 'LICENSE', 'LICENSE')
    for name in ('c48-apps.tzx', 'c48-demos.tzx', 'c48-examples.tzx',
                 'c48-games.tzx', 'c48-multitask.tzx'):
        deliver(BUILD / name, name)
    if not copy_matching(BUILD / 'c48', '*.tap', 'c48'):
        raise SystemExit('Missing program tapes')
    if not copy_matching(BUILD / 'c48', '*.ssx', 'c48'):
        raise SystemExit('Missing compiled programs')
    deliver(BUILD / 'gallery.html', 'gallery.html')
    deliver(BUILD / 'sizes.json', 'sizes.json', required=False)
    copy_matching(BUILD / 'shots', '*.png', 'shots')
    copy_matching(BUILD / 'shots-vm', '*.png', 'shots-vm')
    copy_fresh_proofs()
    if arguments:
        logs = Path(arguments[0])
        if not logs.is_dir():
            raise SystemExit(f'Log folder missing: {logs}')
        copy_logs(logs)
        copy_matching(logs, '*.png', 'screens/tests')


if __name__ == '__main__':
    main(sys.argv[1:])
