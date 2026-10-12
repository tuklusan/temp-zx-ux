"""rcc driver: C48 source -> asm -> SSO1 -> SSX1."""
import os
import sys
from .lex import preprocess, CError
from .parse import parse
from . import z80gen, bcgen

SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SDK)


def compile_to_asm(path, opts=None):
    opts = opts or {}
    toks = preprocess(path)
    prog = parse(toks, lib=opts.get('lib', False))
    if opts.get('module'):
        opts = dict(opts, short=None)       # the library's full table has every form
    if opts.get('bytecode') and 'short' not in opts:
        # first pass: which short forms are used often enough to keep
        g = bcgen.BGen(prog, dict(opts))
        g.generate()
        uses = getattr(g, 'short_uses', {})
        opts = dict(opts, short=bcgen.short_allowed(uses))
        prog = parse(preprocess(path), lib=opts.get('lib', False))
    g = bcgen.BGen(prog, opts) if opts.get('bytecode') else z80gen.Gen(prog, opts)
    text = g.generate()
    text = z80gen.peephole(text)
    if not opts.get('lib') and not opts.get('module') and '_udg_' in text:
        # the UDG bank: 32 slots, or --udgs N (slots 0..N-1)
        n = opts.get('udgs') or 32
        text += ('\tsection data\n\tglobal @nudg\n@nudg:\tdb %d\n'
                 '\tsection bss\n\tglobal @udgs\n@udgs:\tds %d\n' % (n, 8 * n))
    return text, prog, g


# memory a program loaded from cassette can have on ZX-UX 2.0 (from a fresh
# login: the arena less init's and sh's images, plus the lent window); a
# program whose native code needs more is built in bytecode (SSB1)
ZXUX_MAX = 14000


def stack_estimate(g):
    """Bytes of stack the program needs: the deepest chain of frames
    (bytecode functions keep their locals on the stack), at least 384;
    a recursive program gets 1024 more."""
    funcs = g.funcs
    memo = {}

    def depth(f, path):
        if f in memo:
            return memo[f]
        if f in path:
            return 0
        F = funcs[f]
        own = 24 + 2 * max(len(f.params) - 1, 0)
        if f in getattr(g, 'bc', ()):
            own += F.frame + 10
        sub = 0
        for c in f.calls:
            if c in funcs:
                sub = max(sub, depth(c, path | {f}))
        memo[f] = own + sub
        return memo[f]
    d = max((depth(f, frozenset()) for f in funcs), default=0) + 160
    rec = any(F.recursive for f, F in funcs.items() if f not in getattr(g, 'bc', ()))
    rec = rec or any(f in f.calls or any(f in c.calls for c in f.calls if c in funcs) for f in funcs)
    if rec or any(g.scc_of.get(f, (f,)) != (f,) for f in funcs):
        return max(1024, d + 512)
    return max(384, (d + 15) & ~15)


def build(src, opts):
    """Compile and link src -> (SSX1 bytes, generator, sizes)."""
    import ras
    import rld
    text, prog, g = compile_to_asm(src, opts)
    base = os.path.splitext(src)[0]
    obj = ras.assemble_text(text, os.path.basename(base) + '.s')
    libp = os.path.join(SDK, 'lib', 'libc48.ssa')
    objs = [rld.Obj(obj, base)]
    arcs = [rld.read_archive(open(libp, 'rb').read(), libp)]
    stack = opts.get('stack')
    if stack is None:
        stack = stack_estimate(g)
    data, bss, ent, gaddr, chosen = rld.link(objs, arcs, 'start', stack, 0)
    h = rld.parse_ssx(data)
    need = max(len(h['image']) + h['bss'] + h['stack'], len(data))
    return data, g, text, obj, need


def main(argv):
    import ras
    import rld
    out = None
    asm_only = False
    obj_only = False
    lib = False
    stack = None
    udgs = None
    heap = 1024
    mode = None
    limit = ZXUX_MAX
    files = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '-o':
            out = argv[i + 1]
            i += 2
            continue
        if a == '-S':
            asm_only = True
        elif a == '-c':
            obj_only = True
        elif a == '--lib':
            lib = True
        elif a == '--bytecode':
            mode = 'all'
        elif a == '--native':
            mode = 'none'
        elif a == '--max':
            limit = int(argv[i + 1], 0)     # 0: no limit
            i += 1
        elif a == '--stack':
            stack = int(argv[i + 1], 0)
            i += 1
        elif a == '--heap':
            heap = int(argv[i + 1], 0)
            i += 1
        elif a == '--udgs':
            udgs = int(argv[i + 1], 0)
            if not 4 <= udgs <= 32:
                print('rcc: --udgs takes 4 to 32', file=sys.stderr)
                return 2
            i += 1
        else:
            files.append(a)
        i += 1
    if len(files) != 1:
        print('usage: rcc [-S|-c] [-o out] [--bytecode|--native] [--max BYTES] [--stack N] [--heap N] [--udgs N] file.c',
              file=sys.stderr)
        return 2
    src = files[0]
    base = os.path.splitext(src)[0]
    target = out or base + ('.s' if asm_only else '.sso' if obj_only else '.ssx')
    if os.path.exists(target) and os.path.exists(src) and os.path.samefile(target, src):
        print('rcc: output %s would overwrite the source' % target, file=sys.stderr)
        return 2
    if not os.path.isfile(src):
        print('rcc: cannot read %s' % src, file=sys.stderr)
        return 1
    opts = {'lib': lib, 'heap': heap, 'stack': stack, 'udgs': udgs, 'module': obj_only}
    if mode == 'all':
        opts['bytecode'] = 'all'
    try:
        if asm_only or obj_only:
            text, prog, g = compile_to_asm(src, opts)
            if asm_only:
                return write_out(target, text.encode())
            obj = ras.assemble_text(text, os.path.basename(base) + '.s')
            return write_out(target, obj)
        data, g, text, obj, need = build(src, opts)
        if mode is None and limit and need > limit:
            # too big for native code: bytecode (SSB1) for what it can
            opts['bytecode'] = 'all'
            data2, g2, text2, obj2, need2 = build(src, opts)
            if need2 < need:
                data, need = data2, need2
    except CError as e:
        print('rcc: %s' % e, file=sys.stderr)
        return 1
    except ras.AsmError as e:
        print('rcc: internal assembler error: %s' % e, file=sys.stderr)
        return 3
    except rld.LinkError as e:
        print('rcc: link: %s' % e, file=sys.stderr)
        return 1
    if limit and need > limit:
        print('rcc: %s needs %d bytes of memory (limit %d)' % (src, need, limit), file=sys.stderr)
    return write_out(target, data)


def write_out(path, data):
    """Write the output file; status 1 (and no partial file) on failure."""
    try:
        with open(path, 'wb') as f:
            f.write(data)
    except OSError as e:
        print('rcc: cannot write %s: %s' % (path, e.strerror or e), file=sys.stderr)
        try:
            os.remove(path)
        except OSError:
            pass
        return 1
    return 0
