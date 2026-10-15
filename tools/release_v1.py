#!/usr/bin/env python3
"""Build, independently validate, and assemble a ZX-UX v1 release.

Start from a clean committed checkout. Checked tools live outside Git.
Nothing is copied to release/ unless mandatory build, C48, integration,
format, source-integrity, and real FUSE boot gates have passed.

Usage:
  python3 tools/release_v1.py --sjasm /tools/sjasmplus \
      --tap2sna /tools/tap2sna.py \
      --fuse-test-command '/path/to/checked-fuse-boot-test'

The private checker is a separate mandatory *pre-GitHub-write* safeguard,
not a local release-building dependency. It must still run before GitHub
pushes/API commits. This driver does not authorize a remote write.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build'
RELEASE = ROOT / 'release'
PYTHON = sys.executable


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def run(cmd, env=None, log=None):
    """Execute a required local command and preserve its actual exit and output."""
    command = shlex.join([str(arg) for arg in cmd])
    result = subprocess.run([str(arg) for arg in cmd], cwd=ROOT,
                            env=env, capture_output=True, text=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('Command: ' + command + '\nExit: ' +
                       str(result.returncode) + '\n\n' +
                       result.stdout + '\n' + result.stderr)
    require(result.returncode == 0,
            'Command failed; inspect ' + str(log if log else command))
    return result.stdout + result.stderr


def validated_file(name):
    """Verify a generated file and return its SHA-256."""
    path = Path(name)
    require(path.is_file() and not path.is_symlink(),
            'Required generated file unavailable: ' + str(path))
    require(path.stat().st_size > 0, 'Generated output has zero length: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_tracked_sources(after_build=False):
    """Check only Git-indexed project files, never .git or untracked caches.

    All tracked paths must exist and have the bytes recorded by the index.
    Generated outputs receive their own validation before delivery.
    """
    records = subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=ROOT)
    require(bool(records), 'No tracked project files')
    for record in records.split(b'\0'):
        if not record:
            continue
        descriptor, raw_path = record.split(b'\t', 1)
        mode, expected, stage = descriptor.split(b' ')
        require(stage == b'0', 'Unmerged Git index')
        relative = Path(os.fsdecode(raw_path))
        require(not relative.is_absolute() and '..' not in relative.parts,
                'Unsafe Git path')
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink(),
                'Tracked file missing or unsupported')
        actual = subprocess.check_output(['git', 'hash-object', '--', str(relative)],
                                         cwd=ROOT).strip()
        if not (after_build and relative.parts[0] == 'build'):
            require(actual == expected, 'Tracked file differs from Git index')



def clear_verified_release():
    """Replace a tracked old release only after the current gates pass.

    Reject symlinks and files not recorded by Git before removing anything.
    Source/index integrity was checked before the build and just before this
    operation; an old release does not authorize skipping either check.
    """
    if not RELEASE.exists():
        require(not RELEASE.is_symlink(), 'Unsafe release link')
        return
    require(RELEASE.is_dir() and not RELEASE.is_symlink(),
            'Unsafe existing release directory')
    records = subprocess.check_output(['git', 'ls-files', '-z', '--', 'release/'],
                                      cwd=ROOT)
    tracked = {ROOT / Path(os.fsdecode(raw)) for raw in records.split(b'\0') if raw}
    for path in RELEASE.rglob('*'):
        require(not path.is_symlink(), 'Release contains an unsupported link')
        if path.is_file():
            require(path in tracked, 'Release contains an untracked file')
        else:
            require(path.is_dir(), 'Release contains an unsupported entry')
    shutil.rmtree(RELEASE)


def version_data(sjasm):
    text = run([sjasm, '--version'])
    return text.strip().splitlines()[0]


def count_log(log):
    """Count executed outcomes; labels in a summary are not observations."""
    text = log.read_text()
    summaries = re.findall(r'^SUMMARY: (\{[^\n]+\})', text, re.MULTILINE)
    if 'SUMMARY:' in text:
        require(len(summaries) == 1, 'Missing or duplicated test summary')
        try:
            data = ast.literal_eval(summaries[0])
        except (ValueError, SyntaxError) as error:
            raise RuntimeError('Malformed test summary') from error
        require(isinstance(data, dict) and all(
            isinstance(data.get(key), int) and not isinstance(data.get(key), bool)
            and data[key] >= 0 for key in ('PASS', 'FAIL', 'ERROR')),
            'Invalid test summary counts')
        return data['PASS'], data['FAIL'] + data['ERROR']
    # For unittest logs, the actual runner reports how many tests ran.
    unit = re.findall(r'^Ran (\d+) tests? in ', text, re.MULTILINE)
    if unit:
        require(len(unit) == 1 and re.search(r'^OK$', text, re.MULTILINE),
                'Unsuccessful unittest summary')
        return int(unit[0]), 0
    # Native ZX-UX and VM sessions report "case PASS ..." rather than
    # "PASS case". Count executed outcomes from either form.
    passed = len(re.findall(r'^(?:PASS\b|\S+\s+PASS\b)', text, re.MULTILINE))
    failed = len(re.findall(r'^(?:FAIL\b|\S+\s+FAIL\b)', text, re.MULTILINE))
    totals = re.findall(r'^(\d+)/(\d+) (?:v1 sessions pass|ran on ZX-UX)$',
                        text, re.MULTILINE)
    if totals:
        require(len(totals) == 1 and
                (passed, passed + failed) == tuple(map(int, totals[0])),
                'Program-session totals disagree with executed outcomes')
    return passed, failed


def screenshot_check():
    config = json.loads((ROOT / 'sdk/tests/runs.json').read_text())
    for name, entry in config.items():
        name = name.replace(':', '_')
        if entry.get('ZX-UX') != 'skip':
            require((BUILD / 'shots' / (name + '.ZX-UX.png')).is_file(),
                    'Missing emulator image for ' + name)
        require((BUILD / 'shots-vm' / (name + '.png')).is_file(),
                'Missing C48 VM image for ' + name)
    require((BUILD / 'ZX-UX-multitask.png').is_file(),
            'Missing Hanoi + Queens8 emulator capture')
    from PIL import Image
    for d in (BUILD / 'shots', BUILD / 'shots-vm'):
        for img in d.glob('*.png'):
            validated_file(img)
            with Image.open(img) as frame:
                require(frame.format == 'PNG' and frame.width > 0 and frame.height > 0,
                        'Invalid emulator PNG capture: ' + str(img))
                frame.verify()
    image = BUILD / 'ZX-UX-multitask.png'
    validated_file(image)
    with Image.open(image) as frame:
        require(frame.format == 'PNG' and frame.width > 0 and frame.height > 0,
                'Invalid multitask PNG capture')
        frame.verify()


def manifest(commit, versions, logs):
    parts = ['ZX-UX v1 release manifest', '', 'Source commit: ' + commit,
             'Assembler: ' + versions['assembler'],
             'SkoolKit: ' + versions['skoolkit'],
             'Tests:']
    for key, log in logs.items():
        p, f = count_log(log)
        require(f == 0, 'Test log reports a failure: ' + key)
        parts.append('  %s: PASS=%d FAIL=%d exit=0' % (key, p, f))
    parts.extend(['', 'Files (SHA-256 and byte size):'])
    for file in sorted(RELEASE.rglob('*')):
        if not file.is_file() or file.name == 'manifest.txt':
            continue
        parts.append('%s  %d  %s' % (hashlib.sha256(file.read_bytes()).hexdigest(),
                                    file.stat().st_size, file.relative_to(RELEASE)))
    (RELEASE / 'manifest.txt').write_text('\n'.join(parts) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sjasm', required=True, type=Path)
    parser.add_argument('--tap2sna', required=True, type=Path)
    parser.add_argument('--fuse-test-command', required=True)
    args = parser.parse_args()
    sjasm = args.sjasm.resolve()
    corpus = ROOT / 'programs' / 'c48'
    tape_tool = args.tap2sna.resolve()
    for tool in (sjasm, tape_tool):
        require(tool.is_file() and not tool.is_symlink(), 'Missing checked tool')
        require(ROOT not in tool.parents, 'Checked tools must stay outside Git')
    require((corpus / 'demos/hanoi.c').is_file() and
            (corpus / 'demos/queens8.c').is_file() and
            (corpus / 'ailmzx48/ailmzx48.c').is_file(),
            'Checked-in v1 C48 sources or LM source are missing')
    require(not RELEASE.is_symlink() and (not RELEASE.exists() or RELEASE.is_dir()),
            'Unsafe release directory')
    require(not run(['git', 'status', '--porcelain']).strip(),
            'Release must start from a clean checkout')
    commit = run(['git', 'rev-parse', 'HEAD']).strip()
    check_tracked_sources()
    validated_file(sjasm)
    validated_file(tape_tool)
    spec = importlib.util.find_spec('skoolkit')
    require(spec is not None and spec.origin is not None,
            'SkoolKit 10.1 is not installed')
    # Verify the exact approved toolbox/ROM/simulator bytes independently.
    import skoolkit
    import skoolkit.csimulator
    require(skoolkit.CSimulator is not None and Path(skoolkit.ROM48).is_file(),
            'SkoolKit emulator and its 48K ROM are unavailable')
    require(skoolkit.VERSION == '10.1', 'Requires SkoolKit 10.1')
    toolbox = sjasm.parent.parent
    require(Path(spec.origin).resolve() ==
            (toolbox / 'runtime/skoolkit/__init__.py').resolve(),
            'SkoolKit was not loaded from the checked toolbox')
    sim_path = Path(skoolkit.csimulator.__file__).resolve()
    require(sim_path.parent == Path(spec.origin).resolve().parent,
            'Compiled simulator does not belong to the checked toolbox')
    for path, expected in (
        (sjasm, '2aafd9bbc62c4ff90b6c69aa71a94a33afda395b587c2936c5fedb970e67adc0'),
        (Path(skoolkit.ROM48), 'd55daa439b673b0e3f5897f99ac37ecb45f974d1862b4dadb85dec34af99cb42'),
        (sim_path, '2116a3d1416bb273be4ef686797a9e055cfbc3217be337ecb878f07f093601b2'),
    ):
        require(path.is_file() and not path.is_symlink() and
                hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                'Checked toolbox file hash does not match')
    from PIL import Image  # Required for real image generation and inspection.
    require(Image is not None, 'Pillow is missing')
    sj_version = version_data(str(sjasm))
    logs = {}

    def step(name, command, env=None):
        log = BUILD / 'logs' / (name + '.txt')
        run(command, env=env, log=log)
        logs[name] = log
        validated_file(log)

    step('release-self-tests', [PYTHON, '-B', '-m', 'unittest', 'discover',
                                '-s', 'tests', '-p', 'release_*checks.py', '-v'])
    step('build', [PYTHON, '-B', 'tools/build.py', str(sjasm)])
    for name in ('unix.bin', 'fs.img', 'ZX-UX.tap', 'ZX-UX.tzx'):
        validated_file(BUILD / name)
    require((BUILD / 'ZX-UX.tzx').read_bytes().startswith(b'ZXTape!\x1a'),
            'Invalid TZX signature')
    step('boot-image-static', [PYTHON, '-B', 'tests/test_boot_v1.py'])
    step('c48-runtime', [PYTHON, '-B', 'sdk/lib/build.py'])
    step('c48-abi-ix', [PYTHON, '-B', 'tests/c48/ix_abi_probe.py',
                        '--report', str(BUILD / 'logs/ix-abi-proof.json')])
    validated_file(BUILD / 'logs/ix-abi-proof.json')
    step('c48-language', [PYTHON, '-B', 'tests/c48/conformance.py',
                          '--backend', 'both', '--report',
                          str(BUILD / 'logs' / 'c48-conformance.json')])
    step('assembler-comparison', [PYTHON, '-B', 'sdk/tests/test_ras.py'],
         {**os.environ, 'SJASMPLUS': str(sjasm)})
    step('rom-tape-boot', [PYTHON, '-B', str(tape_tool),
                           'build/ZX-UX.tzx', 'build/test.z80'])
    # The process-owned ENV1 assertion is an actual linked rcc-native run,
    # not a C48 host-language case or a change to the static ABI matrix.
    step('c48-native-env1', [PYTHON, '-B', 'tests/c48/native_env1_v1.py',
                             '--tap2sna', str(tape_tool), '--report',
                             str(BUILD / 'logs/native-env1-v1.json')])
    validated_file(BUILD / 'logs/native-env1-v1.json')
    step('c48-coverage', [PYTHON, '-B', 'tests/c48/coverage_gate.py',
                          '--report', str(BUILD / 'logs/c48-conformance.json'),
                          '--ix-proof', str(BUILD / 'logs/ix-abi-proof.json'),
                          '--env1-proof', str(BUILD / 'logs/native-env1-v1.json')])
    step('c48-target-units', [PYTHON, '-B', '-m', 'unittest', 'discover',
                              '-s', 'tests/c48', '-p', 'target_gate_tests.py', '-v'])
    step('c48-target', [PYTHON, '-B', 'tests/c48/target_gate.py',
                        '--report', str(BUILD / 'logs/c48-conformance.json'),
                        '--ix-proof', str(BUILD / 'logs/ix-abi-proof.json'),
                        '--env1-proof', str(BUILD / 'logs/native-env1-v1.json')])
    step('system-regression', [PYTHON, '-B', 'tests/suite.py'])
    step('c48-program-tapes', [PYTHON, '-B', 'tools/mktapes.py'])
    step('c48-emulator', [PYTHON, '-B', 'tests/ssxrun.py', '--png',
                          str(BUILD / 'shots')])
    step('c48-v1-native', [PYTHON, '-B', 'sdk/tests/vm_checks.py',
                           '--native', '--png', str(BUILD / 'shots-vm')])
    step('c48-v1-bytecode', [PYTHON, '-B', 'sdk/tests/vm_checks.py',
                             '--bytecode', '--png', str(BUILD / 'shots-vm')])
    step('lm-new-sdk', [PYTHON, '-B', 'tools/lm_v1.py'])
    step('lm-memory-bound', [PYTHON, '-B', 'tests/lm_native_memory.py',
                             '--snapshot', str(BUILD / 'test.z80'),
                             '--image', str(BUILD / 'lm/ailmzx48.ssx'),
                             '--tape', str(BUILD / 'ZX-UX.tzx'),
                             '--output', str(BUILD / 'logs/lm-native')])
    validated_file(BUILD / 'logs/lm-native/lm-native-memory.json')
    step('hanoi-queens8', [PYTHON, '-B', 'tools/mtsnap.py'])
    step('gallery', [PYTHON, '-B', 'tools/gallery.py',
                     str(logs['c48-emulator']), str(logs['c48-v1-bytecode'])])
    from fuse_release_gate import validate_boot_command, validate_boot_proof
    fuse_command, proof_paths = validate_boot_command(
        args.fuse_test_command, ROOT, BUILD, PYTHON)
    step('fuse-independent-boot', fuse_command)
    validate_boot_proof(proof_paths, validated_file)
    screenshot_check()
    check_tracked_sources(after_build=True)
    doc = ['ZX-UX UNIX v1 for the ZX Spectrum 48K',
           'This release was built from Git commit ' + commit + '.',
           'All required emulator and C48 tests completed without errors.',
           'The manifest has the exact checks and SHA-256 sums.',
           'Load ZX-UX.tzx or ZX-UX.tap through the Spectrum tape loader.',
           'Log in with any user name of 1 to 8 characters.',
           'Project, font, and third-party ROM terms are recorded in LICENSE.',
           'FUSE: independent boot checked']
    (BUILD / 'README.txt').write_text('\n'.join(doc) + '\n')
    validated_file(BUILD / 'README.txt')
    clear_verified_release()
    step('release-copy', [PYTHON, '-B', 'tools/mkrelease.py', str(BUILD / 'logs')])
    shutil.copyfile(logs['release-copy'], RELEASE / 'logs/release-copy.txt')
    # every released program and tape is what a full rebuild makes, byte for byte
    step('c48-release-fresh', [PYTHON, '-B', 'tools/mktapes.py', '--check', '--release'])
    for name, source in (
        ('fuse-login.png', proof_paths['screen']),
        ('fuse-login.json', proof_paths['json']),
        ('lm-memory.png', BUILD / 'logs/lm-native/lm-rejected.png'),
        ('lm-memory.scr', BUILD / 'logs/lm-native/lm-rejected.scr'),
        ('lm-memory.json', BUILD / 'logs/lm-native/lm-native-memory.json'),
    ):
        validated_file(source)
        shutil.copyfile(source, RELEASE / name)
    for extra in ('unix.bin', 'fs.img'):
        shutil.copyfile(BUILD / extra, RELEASE / extra)
    for output in RELEASE.rglob('*'):
        if output.is_file():
            validated_file(output)
    manifest(commit, {'assembler': sj_version, 'skoolkit': skoolkit.VERSION}, logs)
    validated_file(RELEASE / 'manifest.txt')
    print('Verified release:', RELEASE)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print('RELEASE STOPPED:', exc, file=sys.stderr)
        sys.exit(1)
