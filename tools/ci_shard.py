#!/usr/bin/env python3
"""Split a test list into shards for CI (.github/workflows/regression.yml).

  ci_shard.py runs I N     programs of sdk/tests/runs.json, shard I of N
  ci_shard.py suite I N    tests of tests/suite.py, shard I of N

Prints the names comma-separated, for --only (runs) or -k (suite).
Shard I takes every Nth name from the I-th, so slow names spread out.
For runs the names are the programs (the part before ':'): the --only of
vm_checks.py, rvm_corpus.py and rvm_machine.py selects a program with all
its sessions (chess also runs chess:play2), so a session name in one
shard would run again in its program's shard.  Together the N shards
select every session exactly once (checked by --check KIND N).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def names(kind):
    if kind == 'runs':
        return list(json.load(open(os.path.join(ROOT, 'sdk', 'tests', 'runs.json'))))
    if kind == 'programs':
        return list(dict.fromkeys(n.split(':')[0] for n in names('runs')))
    if kind == 'suite':
        src = open(os.path.join(ROOT, 'tests', 'suite.py')).read()
        return re.findall(r'^@test\ndef (\w+)\(', src, re.M)
    raise SystemExit('ci_shard: unknown list %r' % kind)


def shard(kind, i, n):
    if not 0 <= i < n:
        raise SystemExit('ci_shard: shard %d of %d' % (i, n))
    return names('programs' if kind == 'runs' else kind)[i::n]


def selected(kind, picked):
    """The names the tests run for the shard's selectors (as their --only / -k)."""
    if kind == 'runs':
        return [x for x in names('runs') if x in picked or x.split(':')[0] in picked]
    return list(picked)


def main(argv):
    if len(argv) == 3 and argv[0] == '--check':
        kind, n = argv[1], int(argv[2])
        parts = [selected(kind, set(shard(kind, i, n))) for i in range(n)]
        flat = [x for p in parts for x in p]
        ok = sorted(flat) == sorted(names(kind)) and len(flat) == len(set(flat)) and all(parts)
        print('%s: %d names in %d shards %s' % (kind, len(flat), n, 'ok' if ok else 'WRONG'))
        return 0 if ok else 1
    if len(argv) != 3:
        print(__doc__)
        return 2
    print(','.join(shard(argv[0], int(argv[1]), int(argv[2]))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
