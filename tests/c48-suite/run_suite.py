#!/usr/bin/env python3
"""C48 conformance suite: run every test against sdk/rcc, sdk/ras, sdk/rld
and the linked runtime, and resolve every paragraph of the specification.

  python3 tests/c48-suite/run_suite.py [--zxux] [--only GROUP,...] [--out DIR]

Specification: docs/04-C48 Language Specification Rev 0.11.docx (SHA-256
checked below).  Paragraph numbers ("P0123") are the docx body paragraph
indexes, as in tests/c48/traceability.json; empty paragraphs are skipped,
leaving 990.

Groups:
  run    t1..t7 programs, both back ends (--native and --bytecode), run in
         sdk/rvm.py (emulated Z80 + 48K ROM).  Each ck(id, cond) whose id is
         printed as "F<id>" failed; the paragraph tags after it say what it
         tests.
  float  t4's literal bytes against romoracle.py (the ROM's own routines)
  status t8_status.c: run-time traps and exit statuses
  link   t9_main.c + t9_mod.c compiled with -c and linked by sdk/rld
  cases  n1..n4 (must be rejected) and p_accept (must build and run)
  lib    one program per <c48.h> function (Appendix B), linked
  tool   rcc/ras/rld/rtap command line, output files and formats
  zxux   (--zxux) t1..t7 loaded from cassette and run on ZX-UX itself

Outputs (default build/c48-suite/): results.json, resolution.csv and
RESOLUTION.md (every paragraph: how it was resolved and the result).
Exit status 0 when the run itself worked; deviations are reported, not
turned into a failing status, so that the table is always produced.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SDK = os.path.join(ROOT, 'sdk')
sys.path.insert(0, SDK)
sys.path.insert(0, HERE)
SPEC = os.path.join(ROOT, 'docs', '04-C48 Language Specification Rev 0.11.docx')
SPEC_SHA = '577a93270fcd14efc13b4b2b2e6c7c08eaafd24efbd771199ed4a0278ec037ec'
RCC = os.path.join(SDK, 'bin', 'rcc')
RLD = os.path.join(SDK, 'bin', 'rld')
RTAP = os.path.join(SDK, 'bin', 'rtap')
RAS = os.path.join(SDK, 'bin', 'ras')
LIB = os.path.join(SDK, 'lib', 'libc48.ssa')
BACKENDS = ('native', 'bytecode')
PROGRAMS = [('t1_lex.c', []), ('t2_types.c', []), ('t3_expr.c', []), ('t4_float.c', []),
            ('t5_stmt.c', []), ('t6_pp.c', []), ('t7_main.c', ['alpha', 'b'])]
PTAG = re.compile(r'P(\d{4})')


# ---------------------------------------------------------------- spec
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def spec_paragraphs():
    """[(index, style, text)] for the non-empty body paragraphs of the docx"""
    data = open(SPEC, 'rb').read()
    if hashlib.sha256(data).hexdigest() != SPEC_SHA:
        raise SystemExit('specification checksum mismatch: %s' % SPEC)
    z = zipfile.ZipFile(SPEC)
    doc = ET.fromstring(z.read('word/document.xml'))
    styles = {}
    st = ET.fromstring(z.read('word/styles.xml'))
    for s in st.iter(W + 'style'):
        n = s.find(W + 'name')
        styles[s.get(W + 'styleId')] = n.get(W + 'val') if n is not None else s.get(W + 'styleId')
    body = doc.find(W + 'body')
    out = []
    for i, p in enumerate(body.findall(W + 'p')):
        parts = []
        for el in p.iter():
            if el.tag == W + 't':
                parts.append(el.text or '')
            elif el.tag == W + 'tab':
                parts.append('\t')
            elif el.tag in (W + 'br', W + 'cr'):
                parts.append('\n')
        text = ''.join(parts)
        if not text.strip():
            continue
        ps = p.find(W + 'pPr/' + W + 'pStyle')
        style = styles.get(ps.get(W + 'val'), ps.get(W + 'val')) if ps is not None else 'Normal'
        out.append((i, style, text))
    return out


def sections(paras):
    cur = ''
    sec = {}
    for i, style, text in paras:
        if style.startswith('Heading'):
            cur = text.strip()
        sec[i] = cur
    return sec


# ---------------------------------------------------------------- tools
class Run:
    def __init__(self, tmp):
        self.tmp = tmp
        self.results = []          # dicts: id, group, paras, backend, status, detail
        self.n = 0

    def add(self, ident, group, paras, status, detail='', backend=''):
        self.results.append({'id': ident, 'group': group, 'paras': sorted(set(paras)),
                             'backend': backend, 'status': status, 'detail': detail})
        mark = {'PASS': '.', 'FAIL': 'F', 'NOTE': 'n'}.get(status, '?')
        print('%-5s %-40s %-9s %s' % (status, ident, backend, detail[:110]))

    def path(self, name):
        self.n += 1
        d = os.path.join(self.tmp, '%04d' % self.n)
        os.makedirs(d)
        return os.path.join(d, name)


def rcc(args, cwd=None, timeout=120):
    p = subprocess.run([sys.executable, RCC] + args, cwd=cwd, capture_output=True,
                       timeout=timeout, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0'))
    return p.returncode, p.stdout.decode('latin-1'), p.stderr.decode('latin-1')


def tool(script, args, cwd=None):
    p = subprocess.run([sys.executable, script] + args, cwd=cwd, capture_output=True,
                       timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0'))
    return p.returncode, p.stdout.decode('latin-1'), p.stderr.decode('latin-1')


def run_vm(ssx, args=(), frames=4000):
    import rvm
    vm = rvm.VM(ssx, args=list(args), fixed_ticks=1234)
    why = vm.run(max_frames=frames)
    text = ''.join(l.ljust(64) for l in rvm.screen_text(vm.screen()).split('\n'))
    return why, vm.status, ' '.join(text.split())


def build(src, backend, out, extra=()):
    return rcc(['--' + backend, '--max', '0'] + list(extra) + ['-o', out, src],
               cwd=os.path.dirname(src))


def ck_tags(source):
    """{check id: [paragraphs]} from 'ck(id, ...); /* Pnnnn ... */'"""
    tags = {}
    for m in re.finditer(r'\bck\((\d+),', source):
        rest = source[m.end():]
        nxt = re.search(r'\bck\(\d+,', rest)
        seg = rest[:nxt.start()] if nxt else rest
        seg = re.sub(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', '""', seg)
        tags[int(m.group(1))] = []
        for c in re.finditer(r'/\*(.*?)\*/', seg, re.S):
            found = [int(x) for x in PTAG.findall(c.group(1))]
            if found:
                tags[int(m.group(1))] = found
                break
    return tags


def copy_suite(dst):
    for f in os.listdir(HERE):
        if f.endswith(('.h', '.c')):
            shutil.copy(os.path.join(HERE, f), dst)


# ---------------------------------------------------------------- groups
def g_run(R, programs):
    outcome = {}
    for name, args in programs:
        src_text = open(os.path.join(HERE, name)).read()
        tags = ck_tags(src_text)
        for be in BACKENDS:
            d = os.path.dirname(R.path('x'))
            copy_suite(d)
            out = os.path.join(d, name[:-2] + '.ssx')
            rc, _, err = build(os.path.join(d, name), be, out)
            ident = 'run:' + name
            allp = [p for v in tags.values() for p in v]
            if rc:
                R.add(ident + ':compile', 'run', allp, 'FAIL', 'rcc status %d: %s' % (rc, err.strip()), be)
                continue
            why, status, text = run_vm(open(out, 'rb').read(), args)
            failed = {int(x) for x in re.findall(r'F(\d+)', text)}
            m = re.search(r'N(\d+)\.', text)
            if why != 'exit' or not m:
                R.add(ident + ':ran', 'run', allp, 'FAIL', 'did not finish: %s, screen %r' % (why, text[:200]), be)
                continue
            if int(m.group(1)) != len(tags):
                R.add(ident + ':count', 'run', [], 'FAIL',
                      'ran %s checks, source has %d' % (m.group(1), len(tags)), be)
            if (status == 0) != (not failed):
                R.add(ident + ':status', 'run', [], 'FAIL', 'exit status %d with failures %s' % (status, sorted(failed)), be)
            for cid in sorted(tags):
                R.add('%s:ck%d' % (name, cid), 'run', tags[cid],
                      'FAIL' if cid in failed else 'PASS', '', be)
            outcome[(name, be)] = sorted(failed)
            if name == 't4_float.c':
                g_float(R, src_text, text, be)
                outcome[(name, be, 'L')] = re.findall(r'L\d+(?: [0-9a-f]{2}){5}', text)
    # 2, 81, 95: the back end is a representation choice; results agree
    for name, _ in programs:
        a, b = outcome.get((name, 'native')), outcome.get((name, 'bytecode'))
        same = a is not None and a == b and outcome.get((name, 'native', 'L')) == outcome.get((name, 'bytecode', 'L'))
        R.add('equiv:' + name, 'run', [29, 788, 919, 959],
              'PASS' if same else 'FAIL', 'native failed %s, bytecode failed %s' % (a, b))
    return outcome


ORACLES = {}


def oracle_bytes(expr):
    """{engine: five bytes or RomError} for a t4 literal, from the ROM run on
    every available Z80 engine (romoracle.engines())."""
    from romoracle import Oracle, RomError, engines
    out = {}
    neg = expr.startswith('-')
    lit = expr[1:] if neg else expr
    for eng in engines():
        o = ORACLES.setdefault(eng, Oracle(eng))
        try:
            if re.fullmatch(r'0[xX][0-9a-fA-F]+|[0-9]+', lit) and not lit.startswith('0') or lit == '0' \
                    or re.fullmatch(r'0[xX][0-9a-fA-F]+', lit):
                out[eng] = o.integer(-int(lit, 0) if neg else int(lit, 0))
            else:
                w = o.decimal(lit.rstrip('fF'))
                out[eng] = o.negate(w) if neg else w
        except RomError as e:
            out[eng] = e
    return out


def g_float(R, src_text, text, be):
    paras = [int(x) for x in PTAG.findall(src_text[:src_text.index('#include')])]
    got = {int(m.group(1)): bytes.fromhex(m.group(2).replace(' ', ''))
           for m in re.finditer(r'L(\d+)((?: [0-9a-f]{2}){5})', text)}
    for m in re.finditer(r'show\((\d+), (.+?)\);', src_text):
        lid, expr = int(m.group(1)), m.group(2).strip()
        res = oracle_bytes(expr)
        want = res['z80python']
        if any(repr(v) != repr(want) for v in res.values()):
            R.add('t4_float.c:L%d' % lid, 'float', paras, 'FAIL', '%s: the Z80 engines disagree: %s'
                  % (expr, {k: (v.hex(' ') if isinstance(v, bytes) else str(v)) for k, v in res.items()}), be)
            continue
        if not isinstance(want, bytes):
            R.add('t4_float.c:L%d' % lid, 'float', paras, 'FAIL', '%s: ROM rejects it (%s)' % (expr, want), be)
            continue
        have = got.get(lid)
        ok = have == want
        R.add('t4_float.c:L%d' % lid, 'float', paras, 'PASS' if ok else 'FAIL',
              '%s: rcc %s, ROM %s (%s)' % (expr, have.hex(' ') if have else None, want.hex(' '),
                                           '+'.join(res)), be)


T8 = re.compile(r'^ \*\s+(\d+):\s+(\d+)\s+(.*?)\s{2,}((?:P\d{4} ?)+)$', re.M)


def g_status(R):
    src = open(os.path.join(HERE, 't8_status.c')).read()
    cases = [(0, 0, 'no trap (control)', '')] + \
        [(int(a), int(b), c, d) for a, b, c, d in T8.findall(src)]
    for be in BACKENDS:
        d = os.path.dirname(R.path('x'))
        copy_suite(d)
        out = os.path.join(d, 't8.ssx')
        rc, _, err = build(os.path.join(d, 't8_status.c'), be, out)
        if rc:
            R.add('t8_status.c:compile', 'status', [], 'FAIL', err.strip(), be)
            continue
        data = open(out, 'rb').read()
        for n, want, desc, tags in cases:
            why, status, text = run_vm(data, [str(n)])
            want_text = 'BA' if n in (0, 11) else 'B'
            ok = why == 'exit' and status == want and text == want_text
            R.add('t8_status.c:case%d' % n, 'status', [int(x) for x in PTAG.findall(tags)],
                  'PASS' if ok else 'FAIL',
                  '%s: %s status %s (want %d), screen %r (want %r)' % (desc, why, status, want, text, want_text), be)


def g_link(R):
    for be in BACKENDS:
        d = os.path.dirname(R.path('x'))
        copy_suite(d)
        objs = []
        bad = False
        for n in ('t9_main', 't9_mod'):
            rc, _, err = rcc(['--' + be, '-c', '-o', n + '.sso', n + '.c'], cwd=d)
            if rc or open(os.path.join(d, n + '.sso'), 'rb').read()[:4] != b'SSO1':
                R.add('t9:%s:compile' % n, 'link', [763, 764], 'FAIL', err.strip(), be)
                bad = True
            objs.append(n + '.sso')
        if bad:
            continue
        rc, _, err = tool(RLD, ['-o', 't9.ssx'] + objs + [LIB], cwd=d)
        R.add('t9:link', 'link', [288, 763, 764, 768, 1089], 'PASS' if rc == 0 else 'FAIL', err.strip(), be)
        src = open(os.path.join(HERE, 't9_main.c')).read()
        tags = ck_tags(src)
        if rc == 0:
            why, status, text = run_vm(open(os.path.join(d, 't9.ssx'), 'rb').read())
            failed = {int(x) for x in re.findall(r'F(\d+)', text)}
            ran = why == 'exit' and re.search(r'N(\d+)\.', text)
        else:
            ran, failed, text = False, set(), 'not linked'
        for cid in sorted(tags):
            R.add('t9_main.c:ck%d' % cid, 'link', tags[cid],
                  'PASS' if ran and cid not in failed else 'FAIL', '' if ran else text[:100], be)
        # an unresolved external is a link error; so is another unit's static
        rc, _, err = tool(RLD, ['-o', 'u.ssx', 't9_main.sso', LIB], cwd=d)
        R.add('t9:unresolved', 'link', [288], 'PASS' if rc == 1 and 'rld:' in err else 'FAIL',
              'rld status %d: %s' % (rc, err.strip()[:100]), be)
        open(os.path.join(d, 'st.c'), 'w').write(
            'extern int priv;\nint main(void)\n{\n    return priv;\n}\n')
        rcc(['--' + be, '-c', '-o', 'st.sso', 'st.c'], cwd=d)
        rc, _, err = tool(RLD, ['-o', 's.ssx', 'st.sso', 't9_mod.sso', LIB], cwd=d)
        R.add('t9:static_not_exported', 'link', [257, 288, 768], 'PASS' if rc == 1 else 'FAIL',
              'rld status %d: %s' % (rc, err.strip()[:100]), be)
        rc, _, err = tool(RLD, ['-o', 'n.ssx', 't9_mod.sso', LIB], cwd=d)
        R.add('t9:module_without_main', 'link', [371, 769, 1066], 'PASS' if rc == 1 else 'FAIL',
              'linking a module with only a main prototype: rld status %d: %s' % (rc, err.strip()[:100]), be)
        # SSA1: an archive made by rld --archive serves the module's symbols
        rc1, _, e1 = tool(RLD, ['--archive', 'mod.ssa', 't9_mod.sso'], cwd=d)
        rc2, _, e2 = tool(RLD, ['-o', 'a.ssx', 't9_main.sso', 'mod.ssa', LIB], cwd=d)
        ok = rc1 == 0 and rc2 == 0 and open(os.path.join(d, 'mod.ssa'), 'rb').read()[:4] == b'SSA1'
        if ok:
            why, status, text = run_vm(open(os.path.join(d, 'a.ssx'), 'rb').read())
            ok = why == 'exit' and status == 0
        R.add('t9:ssa1_archive', 'link', [288, 764, 768, 989, 1089], 'PASS' if ok else 'FAIL',
              'archive %d, link %d %s' % (rc1, rc2, (e1 + e2).strip()[:100]), be)
        # 23.2: an external function a unit with main never calls is still
        # exported (another unit may call it)
        open(os.path.join(d, 'ex_a.c'), 'w').write(
            'int helper(void)\n{\n    return 0;\n}\nint other(void);\nint main(void)\n{\n    return other();\n}\n')
        open(os.path.join(d, 'ex_b.c'), 'w').write(
            'int helper(void);\nint other(void)\n{\n    return helper();\n}\n')
        rc1, _, e1 = rcc(['--' + be, '-c', '-o', 'ex_a.sso', 'ex_a.c'], cwd=d)
        rc2, _, e2 = rcc(['--' + be, '-c', '-o', 'ex_b.sso', 'ex_b.c'], cwd=d)
        rc3, _, e3 = tool(RLD, ['-o', 'ex.ssx', 'ex_a.sso', 'ex_b.sso', LIB], cwd=d)
        R.add('t9:export_uncalled_function', 'link', [255, 287, 288, 768], 'PASS' if rc1 == rc2 == rc3 == 0 else 'FAIL',
              'compile %d/%d, link %d: %s' % (rc1, rc2, rc3, (e1 + e2 + e3).strip()[:120]), be)
        # 79, B: library services that keep program-wide state (the heap, the
        # UDG bank) work when they are used from several separately compiled
        # units, and the heap when only one unit calls malloc
        open(os.path.join(d, 'rt_a.c'), 'w').write(
            'int udg_define(int slot, unsigned char *bytes);\nvoid *malloc(unsigned int n);\n'
            'unsigned char pat[8] = { 1, 2, 3, 4, 5, 6, 7, 8 };\n'
            'char *mk(void)\n{\n    char *p;\n    p = malloc(10);\n    if (p == 0)\n        return 0;\n'
            '    p[0] = 120;\n    if (udg_define(3, pat) != 0)\n        return 0;\n    return p;\n}\n')
        open(os.path.join(d, 'rt_b.c'), 'w').write(
            'int udg_get(int slot, unsigned char *bytes);\nvoid free(void *p);\nchar *mk(void);\n'
            'int main(void)\n{\n    unsigned char b[8];\n    char *p;\n    p = mk();\n'
            '    if (p == 0 || p[0] != 120)\n        return 2;\n'
            '    if (udg_get(3, b) != 0 || b[0] != 1 || b[7] != 8)\n        return 3;\n'
            '    free(p);\n    return 0;\n}\n')
        rc1, _, e1 = rcc(['--' + be, '-c', '-o', 'rt_a.sso', 'rt_a.c'], cwd=d)
        rc2, _, e2 = rcc(['--' + be, '-c', '-o', 'rt_b.sso', 'rt_b.c'], cwd=d)
        rc3, _, e3 = tool(RLD, ['-o', 'rt.ssx', 'rt_a.sso', 'rt_b.sso', LIB], cwd=d)
        why, status = None, None
        if rc1 == rc2 == rc3 == 0:
            why, status, _ = run_vm(open(os.path.join(d, 'rt.ssx'), 'rb').read())
        R.add('t9:runtime_across_units', 'link', [288, 735, 768, 1042],
              'PASS' if why == 'exit' and status == 0 else 'FAIL',
              'compile %d/%d, link %d, ran %s status %s: %s' % (rc1, rc2, rc3, why, status,
                                                                (e1 + e2 + e3).strip()[:120]), be)


def g_abi(R):
    src = open(os.path.join(HERE, 't10_abi.c')).read()
    tags = ck_tags(src)
    for be in BACKENDS:
        d = os.path.dirname(R.path('x'))
        copy_suite(d)
        shutil.copy(os.path.join(HERE, 't10_abi.s'), d)
        rc1, _, e1 = rcc(['--' + be, '-c', '-o', 'c.sso', 't10_abi.c'], cwd=d)
        rc2, _, e2 = tool(RAS, ['-o', 's.sso', 't10_abi.s'], cwd=d)
        rc3, _, e3 = (1, '', 'not linked') if rc1 or rc2 else tool(RLD, ['-o', 'abi.ssx', 'c.sso', 's.sso', LIB], cwd=d)
        if rc1 or rc2 or rc3:
            R.add('t10:build', 'abi', [p for v in tags.values() for p in v], 'FAIL',
                  (e1 + e2 + e3).strip()[:150], be)
            continue
        why, status, text = run_vm(open(os.path.join(d, 'abi.ssx'), 'rb').read())
        failed = {int(x) for x in re.findall(r'F(\d+)', text)}
        ran = why == 'exit' and re.search(r'N(\d+)\.', text)
        for cid in sorted(tags):
            R.add('t10_abi.c:ck%d' % cid, 'abi', tags[cid],
                  'PASS' if ran and cid not in failed else 'FAIL', '' if ran else text[:100], be)


def parse_cases(path):
    cases = []
    cur = None
    for line in open(path, encoding='ascii').read().split('\n'):
        if line.startswith('//== '):
            words = line[5:].split()
            cur = {'id': words[0], 'paras': [], 'opts': {}, 'lines': []}
            for w in words[1:]:
                if PTAG.fullmatch(w):
                    cur['paras'].append(int(w[1:]))
                elif '=' in w:
                    k, v = w.split('=', 1)
                    cur['opts'][k] = v
                else:
                    cur['opts'][w] = True
            cases.append(cur)
        elif cur is not None:
            cur['lines'].append(line)
    for c in cases:
        while c['lines'] and c['lines'][-1] == '':
            c['lines'].pop()
        text = '\n'.join(c['lines']) + '\n'
        if c['opts'].get('nolf'):
            text = text[:-1]
        if c['opts'].get('crlf'):
            text = text.replace('\n', '\r\n')
        raw = re.sub(r'<<([0-9A-Fa-f]{2})>>', lambda m: chr(int(m.group(1), 16)), text)
        c['bytes'] = raw.encode('latin-1')
    return cases


def g_cases(R):
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.cases'):
            continue
        positive = f.startswith('p_')
        for c in parse_cases(os.path.join(HERE, f)):
            d = os.path.dirname(R.path('x'))
            copy_suite(d)
            src = os.path.join(d, 'case.c')
            open(src, 'wb').write(c['bytes'])
            ident = '%s:%s' % (f, c['id'])
            if not positive:
                out = os.path.join(d, 'case.ssx')
                rc, _, err = rcc(['-o', out, src], cwd=d)
                ok = rc == 1 and err.startswith('rcc:') and not os.path.exists(out)
                why = 'rejected' if ok else 'ACCEPTED (status %d)' % rc if rc == 0 else 'status %d' % rc
                diag = c['opts'].get('diag')
                if ok and diag and not re.search(diag, err, re.I):
                    ok = False
                    why = 'rejected, but the diagnostic does not say %r' % diag
                st = 'PASS' if ok else 'FAIL'
                if not ok and rc == 0 and c['opts'].get('deviation'):
                    # accepted on purpose: a documented maintainer decision
                    st, why = 'DEVIATION', 'ACCEPTED (documented deviation, see README)'
                R.add(ident, 'neg', c['paras'], st,
                      '%s: %s' % (why, err.strip().replace(d + os.sep, '')[:150]))
                continue
            for be in BACKENDS:
                out = os.path.join(d, 'case-%s.ssx' % be)
                rc, _, err = build(src, be, out)
                if rc:
                    st, why = 'FAIL', 'rejected: ' + err.strip().replace(d + os.sep, '')[:150]
                else:
                    w, status, text = run_vm(open(out, 'rb').read())
                    ok = w == 'exit' and status == 0
                    st, why = ('PASS' if ok else 'FAIL'), ('ran: exit status %s' % status if w == 'exit'
                                                          else 'ran: no exit (%s limit reached; hang)' % w)
                if c['opts'].get('may') and st == 'FAIL':
                    st, why = 'NOTE', 'optional or conditional requirement not met: ' + why
                R.add(ident, 'pos', c['paras'], st, why, be)


def header_functions():
    """[(return type, name, [parameter types])] from sdk/include/c48.h"""
    out = []
    for line in open(os.path.join(SDK, 'include', 'c48.h')):
        m = re.match(r'([a-z ]+?)\s*(\**)\s*(\w+)\((.*)\);', line.strip())
        if not m:
            continue
        params = [] if m.group(4) == 'void' else [p.strip() for p in m.group(4).split(',')]
        out.append((m.group(1) + m.group(2), m.group(3), params))
    return out


APPENDIX_B = ('getchar putchar puts cls print_at ink paper bright flash inverse over border plot '
              'point draw circle udg_define udg_get udg_draw udg_clear udg_draw_2x2 ticks yield '
              'sleep beep exit getpid strlen strcmp strcpy strncpy memcpy memmove memchr memset '
              'malloc free sin cos tan asin acos atan sqrt exp log fabs pow open close read seek').split()


def g_lib(R):
    funcs = header_functions()
    names = [f[1] for f in funcs]
    R.add('lib:inventory', 'lib', [1041, 1042, 735],
          'PASS' if sorted(names) == sorted(APPENDIX_B) else 'FAIL',
          'c48.h names vs Appendix B: missing %s, extra %s' % (
              sorted(set(APPENDIX_B) - set(names)), sorted(set(names) - set(APPENDIX_B))))
    hdr = open(os.path.join(SDK, 'include', 'c48.h')).read()
    R.add('lib:beep_prototype', 'lib', [925], 'PASS' if 'int beep(float duration, float pitch);' in hdr else 'FAIL',
          'c48.h declares int beep(float duration, float pitch)')
    arg = {'int': '0', 'unsigned int': '0u', 'float': '0.0', 'char *': '"x"',
           'unsigned char *': 'ub', 'void *': 'vb'}
    for ret, name, params in funcs:
        types = []
        for p in params:
            t = p[:p.rindex('*') + 1] if '*' in p else ' '.join(p.split()[:-1])
            types.append(re.sub(r'\s*\*', ' *', t))
        call = '%s(%s)' % (name, ', '.join(arg[t] for t in types))
        src = ('#include <c48.h>\nint z;\nunsigned char ub[8];\nchar vb[8];\n'
               'int main(void)\n{\n    if (z)\n        %s;\n    return 0;\n}\n' % call)
        d = os.path.dirname(R.path('x'))
        open(os.path.join(d, 'lib.c'), 'w').write(src)
        rc, _, err = rcc(['-o', 'lib.ssx', 'lib.c'], cwd=d)
        R.add('lib:' + name, 'lib', [735, 924, 1042],
              'PASS' if rc == 0 else 'FAIL', '%s: %s' % (call, err.strip()[:120] or 'links'))


def fletcher16(data):
    a = b = 0
    for x in data:
        a = (a + x) % 255
        b = (b + a) % 255
    return b << 8 | a


def g_tool(R):
    d = os.path.dirname(R.path('x'))
    hello = 'int main(void)\n{\n    return 0;\n}\n'
    open(os.path.join(d, 'hello.c'), 'w').write(hello)
    # default output names
    rc, out, err = rcc(['hello.c'], cwd=d)
    ok = rc == 0 and err == '' and os.path.exists(os.path.join(d, 'hello.ssx'))
    R.add('tool:default_ssx', 'tool', [756, 757, 762, 774, 780, 1064, 1082, 1083, 1090],
          'PASS' if ok else 'FAIL', 'status %d, stderr %r' % (rc, err))
    rc, out, err = rcc(['-S', 'hello.c'], cwd=d)
    R.add('tool:asm_s', 'tool', [763, 1082, 1083, 1090],
          'PASS' if rc == 0 and os.path.exists(os.path.join(d, 'hello.s')) else 'FAIL', 'status %d' % rc)
    rc, out, err = rcc(['-c', 'hello.c'], cwd=d)
    sso = os.path.join(d, 'hello.sso')
    ok = rc == 0 and os.path.exists(sso) and open(sso, 'rb').read()[:4] == b'SSO1'
    R.add('tool:object_sso', 'tool', [763, 764, 1082, 1083, 1090], 'PASS' if ok else 'FAIL', 'status %d' % rc)
    rc, out, err = rcc(['-o', 'sub_out.bin', 'hello.c'], cwd=d)
    R.add('tool:output_path', 'tool', [763, 1083], 'PASS' if rc == 0 and
          open(os.path.join(d, 'sub_out.bin'), 'rb').read()[:4] == b'SSX1' else 'FAIL', 'status %d' % rc)
    # SSX1 header and checksum, checked independently of rld
    data = open(os.path.join(d, 'hello.ssx'), 'rb').read()
    magic, flags, hsz, img, bss, stk, heap, ent, nrel, chk = struct.unpack_from('<4sBBHHHHHHH', data)
    body = data[:18] + data[20:]
    ok = magic == b'SSX1' and hsz == 20 and flags == 0 and img + 20 <= len(data) and \
        ent < img and chk == fletcher16(body)
    R.add('tool:ssx1_header', 'tool', [764, 767, 1089, 1090], 'PASS' if ok else 'FAIL',
          'magic %r flags %d header %d image %d bss %d stack %d heap %d entry %d relocs %d checksum %04x (computed %04x)'
          % (magic, flags, hsz, img, bss, stk, heap, ent, nrel, chk, fletcher16(body)))
    # deterministic output
    for mode, ext in (('-c', '.sso'), ('', '.ssx')):
        a = os.path.join(d, 'r1' + ext)
        b = os.path.join(d, 'r2' + ext)
        args = ([mode] if mode else [])
        rcc(args + ['-o', a, 'hello.c'], cwd=d)
        rcc(args + ['-o', b, 'hello.c'], cwd=d)
        same = open(a, 'rb').read() == open(b, 'rb').read()
        R.add('tool:repeatable' + ext, 'tool', [766, 1056, 1065], 'PASS' if same else 'FAIL',
              'two builds %s' % ('identical' if same else 'differ'))
    # status codes, stderr prefix, nothing written on failure
    open(os.path.join(d, 'bad.c'), 'w').write('int main(void) { return x; }\n')
    rc, out, err = rcc(['bad.c'], cwd=d)
    ok = rc == 1 and err.startswith('rcc:') and not os.path.exists(os.path.join(d, 'bad.ssx'))
    R.add('tool:error_status', 'tool', [773, 774, 780, 782, 1064, 1070, 1087],
          'PASS' if ok else 'FAIL', 'status %d, stderr %r' % (rc, err.strip()))
    m = re.search(r'bad\.c:(\d+):', err)
    R.add('tool:error_position', 'tool', [778, 779, 1070], 'PASS' if m and m.group(1) == '1' else 'FAIL',
          'diagnostic names the file and line: %r' % err.strip())
    rc, out, err = rcc(['-c', 'bad.c'], cwd=d)
    R.add('tool:error_no_object', 'tool', [782, 1085, 1087],
          'PASS' if rc == 1 and not os.path.exists(os.path.join(d, 'bad.sso')) else 'FAIL', 'status %d' % rc)
    rc, out, err = rcc([], cwd=d)
    R.add('tool:usage_status', 'tool', [774, 1087], 'PASS' if rc == 2 and err.startswith('usage') or rc == 2 else 'FAIL',
          'no input: status %d %r' % (rc, err.strip()[:80]))
    rc, out, err = rcc(['hello.c', 'bad.c'], cwd=d)
    R.add('tool:usage_two_files', 'tool', [774, 1082, 1087], 'PASS' if rc == 2 else 'FAIL',
          'two inputs: status %d' % rc)
    # the compiler must not overwrite its source
    shutil.copy(os.path.join(d, 'hello.c'), os.path.join(d, 'keep.c'))
    rc, out, err = rcc(['-o', 'keep.c', 'keep.c'], cwd=d)
    kept = open(os.path.join(d, 'keep.c'), 'rb').read() == hello.encode()
    R.add('tool:no_source_overwrite', 'tool', [1085], 'PASS' if kept and rc != 0 and err.startswith('rcc:') else 'FAIL',
          'rcc -o keep.c keep.c: status %d, source %s: %s' % (rc, 'kept' if kept else 'OVERWRITTEN', err.strip()))
    # 81, 82: I/O failures are reported (status 1, "rcc:" message), never a
    # traceback, and no output file claims success
    rc, out, err = rcc(['missing.c'], cwd=d)
    R.add('tool:missing_input', 'tool', [773, 1087], 'PASS' if rc == 1 and err.startswith('rcc:')
          and 'Traceback' not in err else 'FAIL', 'status %d: %s' % (rc, err.strip()[:150]))
    rc, out, err = rcc(['-o', os.path.join('no-such-dir', 'x.ssx'), 'hello.c'], cwd=d)
    R.add('tool:unwritable_output', 'tool', [782, 1085, 1087], 'PASS' if rc == 1 and err.startswith('rcc:')
          and 'Traceback' not in err else 'FAIL', 'status %d: %s' % (rc, err.strip()[:150]))
    # an empty translation unit is valid as -c; linking it without main fails
    open(os.path.join(d, 'empty.c'), 'w').write('/* nothing but a comment */\n')
    rc, out, err = rcc(['-c', 'empty.c'], cwd=d)
    R.add('tool:empty_tu_object', 'tool', [769, 1066], 'PASS' if rc == 0 and
          open(os.path.join(d, 'empty.sso'), 'rb').read()[:4] == b'SSO1' else 'FAIL', 'status %d %s' % (rc, err.strip()))
    rc, out, err = rcc(['empty.c'], cwd=d)
    R.add('tool:empty_tu_link_error', 'tool', [769, 1066], 'PASS' if rc == 1 and 'link' in err else 'FAIL',
          'status %d %s' % (rc, err.strip()))
    open(os.path.join(d, 'zero.c'), 'wb').write(b'')
    rc, out, err = rcc(['-c', 'zero.c'], cwd=d)
    R.add('tool:zero_byte_tu_object', 'tool', [769, 1066], 'PASS' if rc == 0 else 'FAIL',
          'status %d %s' % (rc, err.strip()))
    open(os.path.join(d, 'proto.c'), 'w').write('int main(void);\n')
    rc, out, err = rcc(['-c', 'proto.c'], cwd=d)
    R.add('tool:main_prototype_module', 'tool', [371], 'PASS' if rc == 0 else 'FAIL', 'status %d %s' % (rc, err.strip()))
    # 2, 80: rejection is deterministic; diagnostics name the failing stage
    runs = [rcc(['bad.c'], cwd=d) for _ in range(3)]
    R.add('tool:deterministic_rejection', 'tool', [27, 773], 'PASS' if len(set(runs)) == 1 and runs[0][0] == 1 else 'FAIL',
          'three runs: %s' % sorted(set(r[0] for r in runs)))
    classes = {'lexical': 'int main(void) { return @; }\n',
               'preprocessing': '#if 1\nint main(void) { return 0; }\n',
               'syntax': 'int main(void) { return 0 }\n',
               'type': 'int main(void) { int *p; p = 1.5; return 0; }\n',
               'declaration': 'int x; int x; int main(void) { return 0; }\n',
               'link': 'int f(void);\nint main(void) { return f(); }\n'}
    got = {}
    for k, v in classes.items():
        open(os.path.join(d, 'cls.c'), 'w').write(v)
        got[k] = rcc(['cls.c'], cwd=d)[2].strip()
    ok = all(k in got[k] for k in classes)
    R.add('tool:diagnostic_classes', 'tool', [775, 776, 1070], 'PASS' if ok else 'FAIL',
          '; '.join('%s -> %s' % (k, got[k][:60]) for k in classes))
    # SSB1 bytecode inside the image, same results (checked by the run group)
    rc, out, err = rcc(['--bytecode', '-o', 'bc.ssx', 'hello.c'], cwd=d)
    data = open(os.path.join(d, 'bc.ssx'), 'rb').read() if rc == 0 else b''
    R.add('tool:bytecode_ssx', 'tool', [764, 788, 919], 'PASS' if data[:4] == b'SSX1' else 'FAIL',
          'status %d, %d bytes' % (rc, len(data)))
    # the native/bytecode choice and the memory limit warning
    rc, out, err = rcc(['--native', '--max', '10', '-o', 'lim.ssx', 'hello.c'], cwd=d)
    R.add('tool:memory_limit_report', 'tool', [751, 752, 753, 770, 781, 1088], 'PASS' if 'needs' in err else 'FAIL',
          'status %d %r' % (rc, err.strip()[:100]))
    # rtap: SST1 record
    rc, out, err = tool(RTAP, ['-o', 'hello.tap', 'hello.ssx=hello'], cwd=d)
    ok = False
    detail = 'rtap status %d %s' % (rc, err.strip()[:80])
    tap = os.path.join(d, 'hello.tap')
    if os.path.exists(tap):
        t = open(tap, 'rb').read()
        ssx = open(os.path.join(d, 'hello.ssx'), 'rb').read()
        n1 = t[0] | t[1] << 8
        hdr = t[2:2 + n1]
        n2 = t[2 + n1] | t[3 + n1] << 8
        blk = t[4 + n1:4 + n1 + n2]
        ok = (n1 == 19 and hdr[0] == 0 and hdr[1] == 3 and hdr[12] | hdr[13] << 8 == len(ssx) and
              hdr[16:18] == b'SS' and blk[0] == 0xFF and blk[1:-1] == ssx)
        detail = 'header %s, data block %d bytes, payload %s the SSX1 file' % (
            hdr[:18].hex(' '), n2, 'equals' if blk[1:-1] == ssx else 'differs from')
    R.add('tool:sst1_tape', 'tool', [765, 1089], 'PASS' if ok else 'FAIL', detail)
    rc, out, err = tool(RTAP, ['-o', 'long.tap', 'hello.ssx=elevenchars'], cwd=d)
    R.add('tool:tape_name_rule', 'tool', [1084], 'PASS' if rc != 0 else 'FAIL',
          'an 11-character program tape name: rtap status %d %s' % (rc, err.strip()[:80]))


def g_zxux(R, outcome):
    """load each t-program from cassette on ZX-UX (tests/suite.py machinery)
    and compare the checks that fail with the rvm run of the same file"""
    sys.path.insert(0, os.path.join(ROOT, 'tests'))
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import suite
    import zxrun
    import rtap
    snap = os.path.join(ROOT, 'build', 'test.z80')
    if not os.path.exists(snap):
        R.add('zxux:snapshot', 'zxux', [], 'FAIL', 'build/test.z80 missing: build ZX-UX first')
        return
    for name, args in PROGRAMS:
        d = os.path.dirname(R.path('x'))
        copy_suite(d)
        out = os.path.join(d, name[:-2] + '.ssx')
        rc, _, err = build(os.path.join(d, name), 'native', out)
        tags = ck_tags(open(os.path.join(HERE, name)).read())
        if rc:
            R.add('zxux:' + name, 'zxux', [911, 1088], 'FAIL', err.strip())
            continue
        tname = name[:-2][:10]
        s = suite.Session(snap)
        s.login()
        s.zx.type('/dev/cassette/%s %s\n' % (tname, ' '.join(args)))
        s.zx.tr.edges = zxrun.tape_pulses(rtap.records(open(out, 'rb').read(), tname),
                                          s.zx.sim.registers[25] + 350000)
        # the program's screen is read when its exit gives the screen back
        # (sys screen, A = 39, HL = 0, in sdk/lib/sys.asm _exit)
        import rvm
        sim, r = s.zx.sim, s.zx.sim.registers
        text = ''
        for _ in range(20000):
            end = r[25] + zxrun.FRAME
            while r[25] < end and not text:
                sim.trace(r[24], 0x6003, 0, end, 1, None, None, None, None, None)
                if r[24] == 0x6003:
                    if r[0] == 39 and r[6] == 0 and r[7] == 0:
                        text = ''.join(l.ljust(64) for l in rvm.screen_text(bytes(s.zx.mem[0x4000:0x5B00])).split('\n'))
                    sim.trace(r[24], -1, 1, end, 1, None, None, None, None, None)
            if text:
                break
        failed = {int(x) for x in re.findall(r'F(\d+)', text)}
        m = re.search(r'N(\d+)\.', text)
        ok = bool(m) and int(m.group(1)) == len(tags)
        same = outcome is None or outcome.get((name, 'native')) == sorted(failed)
        R.add('zxux:' + name, 'zxux', [770, 828, 911, 959, 1088],
              'PASS' if ok and same else 'FAIL', 'checks %s, failed %s (rvm: %s)' % (
                  m.group(1) if m else '?', sorted(failed), outcome.get((name, 'native')) if outcome else '-'))
        for cid in sorted(failed):
            R.add('zxux:%s:ck%d' % (name, cid), 'zxux', tags.get(cid, []), 'FAIL', 'failed on ZX-UX')
        if name == 't4_float.c':
            g_float(R, open(os.path.join(HERE, name)).read(), text, 'zxux')


# ---------------------------------------------------------------- report
def resolve(R, paras, outdir):
    sec = sections(paras)
    disp = {}
    for line in open(os.path.join(HERE, 'dispositions.tsv'), encoding='ascii'):
        if not line.strip() or line.startswith('#'):
            continue
        p, kind, why = line.rstrip('\n').split('\t')
        disp[int(p[1:])] = (kind, why)
    by_para = {}
    for r in R.results:
        for p in r['paras']:
            by_para.setdefault(p, []).append(r)
    index = {i for i, _, _ in paras}
    unknown = sorted(set(by_para) - index)
    rows = []
    for i, style, text in paras:
        tests = by_para.get(i, [])
        kind, why = disp.get(i, ('', ''))
        if tests:
            fails = sorted({'%s%s' % (t['id'], ' (%s)' % t['backend'] if t['backend'] else '')
                            for t in tests if t['status'] == 'FAIL'})
            notes = [t for t in tests if t['status'] == 'NOTE']
            devs = [t for t in tests if t['status'] == 'DEVIATION']
            res = 'FAIL' if fails else 'DEVIATION' if devs else 'NOTE' if notes else 'PASS'
            groups = {}
            for t in tests:
                g, _, name = t['id'].partition(':')
                groups.setdefault(g, set()).add(name or g)
            how = 'tested by ' + '; '.join('%s: %s' % (g, ', '.join(sorted(v))) for g, v in sorted(groups.items()))
            if fails:
                how += ' | FAILED: ' + ', '.join(fails)
            if devs:
                how += ' | DEVIATION: ' + ', '.join(sorted({t['id'] for t in devs}))
            if notes:
                how += ' | NOTE: ' + ', '.join(sorted({t['id'] for t in notes}))
            if why:
                how += ' | note: ' + why
        elif kind:
            res = kind
            how = why
        else:
            res = 'UNRESOLVED'
            how = 'no test and no disposition'
        rows.append({'para': 'P%04d' % i, 'section': sec[i], 'style': style,
                     'text': ' '.join(text.split()), 'result': res, 'resolution': how})
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'resolution.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['para', 'section', 'style', 'result', 'resolution', 'text'],
                           lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    counts = {}
    for r in rows:
        counts[r['result']] = counts.get(r['result'], 0) + 1
    write_md(R, rows, counts, outdir)
    return rows, counts, unknown


def write_md(R, rows, counts, outdir):
    def cell(t):
        return t.replace('|', '\\|').replace('\n', ' ')
    fails = [r for r in R.results if r['status'] == 'FAIL']
    out = ['# C48 Rev 0.11 paragraph resolution', '',
           'Generated by `tests/c48-suite/run_suite.py` from %s (SHA-256 %s).' % (
               os.path.relpath(SPEC, ROOT), SPEC_SHA), '',
           'Every non-empty paragraph of the specification has one row.  **PASS**: every test tagged '
           'with the paragraph passed; **FAIL**: at least one tagged test failed (the failing tests are '
           'named); **DEVIATION**: rcc deliberately differs from the paragraph, a documented maintainer '
           'decision (README.md); **NOTE**: only an optional or conditional requirement (MAY, or "once ... '
           'frozen") was not met; other results are the dispositions in `dispositions.tsv` for paragraphs that state '
           'no testable requirement of the compiler, linker or runtime.', '',
           '| Result | Paragraphs |', '|---|---|']
    for k in sorted(counts):
        out.append('| %s | %d |' % (k, counts[k]))
    devs = [r for r in R.results if r['status'] == 'DEVIATION']
    out += ['', 'Test executions: %d (%d failed, %d documented deviations).' % (len(R.results), len(fails), len(devs)),
            '', '## Failed tests and documented deviations', '',
            '| Test | Status | Back end | Paragraphs | Detail |', '|---|---|---|---|---|']
    if not fails + devs:
        out.append('| (none) | | | | |')
    for r in fails + devs:
        out.append('| %s | %s | %s | %s | %s |' % (r['id'], r['status'], r['backend'] or '-',
                   ' '.join('P%04d' % p for p in r['paras']), cell(r['detail'])[:200]))
    out += ['', '## Paragraphs', '', '| Para | Section | Result | Resolution | Text |', '|---|---|---|---|---|']
    for r in rows:
        out.append('| %s | %s | %s | %s | %s |' % (r['para'], cell(r['section'])[:40], r['result'],
                   cell(r['resolution']), cell(r['text'])))
    open(os.path.join(outdir, 'RESOLUTION.md'), 'w').write('\n'.join(out) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', help='groups: run,status,link,cases,lib,tool,zxux')
    ap.add_argument('--zxux', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'c48-suite'))
    a = ap.parse_args()
    groups = set((a.only or 'run,status,link,cases,lib,tool').split(','))
    if a.zxux:
        groups.add('zxux')
    paras = spec_paragraphs()
    tmp = tempfile.mkdtemp(prefix='c48suite-')
    R = Run(tmp)
    try:
        outcome = None
        if 'run' in groups:
            outcome = g_run(R, PROGRAMS)
        if 'status' in groups:
            g_status(R)
        if 'link' in groups:
            g_link(R)
            g_abi(R)
        if 'cases' in groups:
            g_cases(R)
        if 'lib' in groups:
            g_lib(R)
        if 'tool' in groups:
            g_tool(R)
        if 'zxux' in groups:
            g_zxux(R, outcome)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rows, counts, unknown = resolve(R, paras, a.out)
    json.dump({'spec_sha256': SPEC_SHA, 'groups': sorted(groups), 'results': R.results,
               'paragraphs': rows, 'counts': counts}, open(os.path.join(a.out, 'results.json'), 'w'), indent=1)
    st = {}
    for r in R.results:
        st[r['status']] = st.get(r['status'], 0) + 1
    print('tests:', st)
    print('paragraphs:', counts, '(of %d)' % len(rows))
    if unknown:
        print('tags naming no specification paragraph:', unknown)
    return 0


if __name__ == '__main__':
    sys.exit(main())
