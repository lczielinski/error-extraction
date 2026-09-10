"""Drive egglog: emit the seed program, run it, read the e-graph back."""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import tempfile
from fractions import Fraction

import gmpy2

from . import analysis as A
from .fpcore import Str, parse_sexps
from .interval import INF, NINF, Iv

EGGLOG = os.environ.get("EGGLOG", os.path.expanduser("~/.cargo/bin/egglog-experimental"))
EGG_DIR = os.path.join(os.path.dirname(__file__), "egg")

DEFAULT_ITERS = 4
ANA_ROUNDS = 30

OPS = {"add": "Add", "sub": "Sub", "mul": "Mul", "div": "Div", "neg": "Neg",
       "sqrt": "Sqrt", "ifprop": "IfProp", "ctx": "Ctx"}
OP_NAME = {v: k for k, v in OPS.items()}
LEAVES = ("Num", "Lit", "Var")
CONSTRUCTORS = LEAVES + tuple(OPS.values())

# Guards live in their own sort, so they get their own classes and no interval.
PROP_OPS = {"gt": "Gt", "ge": "Ge", "samesign": "SameSign"}
PROP_NAME = {v: k for k, v in PROP_OPS.items()}
PROP_CONSTRUCTORS = tuple(PROP_OPS.values())

TABLES = CONSTRUCTORS + PROP_CONSTRUCTORS + ("lo", "hi", "Bad")   # dumped in order


class BadBox(Exception):
    """An e-class got an empty interval: the box breaks definedness."""


class ENode:
    __slots__ = ("op", "children", "payload")

    def __init__(self, op, children, payload=None):
        self.op = op
        self.children = children
        self.payload = payload

    def key(self):
        return (self.op, self.payload, self.children)

    def __repr__(self):
        args = self.children if self.payload is None else (str(self.payload),)
        return "(" + " ".join((self.op,) + tuple(args)) + ")"


class EGraph:
    def __init__(self, nodes, interval, lits, root=None, props=None):
        self.nodes = nodes        # class id -> [ENode]
        self.interval = interval  # class id -> Iv
        self.lits = lits          # Lit index -> AST leaf
        self.props = props or {}  # Prop class id -> [ENode]; no interval
        self.root = root
        self.roots = {}           # context suffix -> class id
        self._index = None
        self._pindex = None
        self._where = {}

    def __repr__(self):
        nodes = sum(map(len, self.nodes.values()))
        return f"EGraph({len(self.nodes)} classes, {nodes} nodes)"

    def locate(self, e) -> str:
        """By structure, memoized: a lookup walks the whole tree and callers
        ask for every subterm."""
        if self._index is None:
            self._index = {n.key(): cls for cls, ns in self.nodes.items() for n in ns}
        if e in self._where:
            return self._where[e]
        if e[0] == "var":
            key = ("Var", e[1], ())
        elif is_exact(e):
            key = ("Num", float(e[1]), ())
        elif e[0] in ("num", "const"):
            key = ("Lit", self.lits.index(e), ())
        elif e[0] == "ifprop":
            key = ("IfProp", None, (self.locate_prop(e[1]),
                                    self.locate(e[2]), self.locate(e[3])))
        elif e[0] == "ctx":
            key = ("Ctx", None, (self.locate_prop(e[1]), self.locate(e[2])))
        else:
            key = (OPS[e[0]], None, tuple(self.locate(a) for a in e[1:]))
        if key not in self._index:
            raise RuntimeError(f"term missing from the e-graph: {key}")
        cls = self._index[key]
        self._where[e] = cls
        return cls

    def locate_prop(self, e) -> str:
        """The Prop class of a guard term."""
        if self._pindex is None:
            self._pindex = {n.key(): cls
                            for cls, ns in self.props.items() for n in ns}
        key = (PROP_OPS[e[0]], None, tuple(self.locate(a) for a in e[1:]))
        if key not in self._pindex:
            raise RuntimeError(f"guard missing from the e-graph: {key}")
        return self._pindex[key]


# -- emitting --


def representable(v: Fraction) -> bool:
    try:
        f = float(v)
    except OverflowError:
        return False
    if not math.isfinite(f):
        return False
    if A.mantissa < 53:              # binary32
        try:
            f = struct.unpack("f", struct.pack("f", f))[0]
        except OverflowError:
            return False
        if not math.isfinite(f):
            return False
    return Fraction(f) == v


def _f64(x: float) -> str:
    if x == math.inf:
        return "inf"
    if x == -math.inf:
        return "-inf"
    return repr(float(x)).replace("e+", "e")


def is_exact(e) -> bool:
    return e[0] == "num" and representable(e[1])


def _lit_bounds(leaf) -> tuple:
    if leaf[0] == "const":
        v = gmpy2.const_pi() if leaf[1] == "PI" else gmpy2.exp(gmpy2.mpfr(1))
    else:
        v = gmpy2.mpfr(leaf[1].numerator) / gmpy2.mpfr(leaf[1].denominator)
    f = float(v)
    return math.nextafter(f, -math.inf), math.nextafter(f, math.inf)


class _Emitter:
    def __init__(self):
        self.lines = []
        self.memo = {}
        self.lits = []
        self.n = 0

    def term(self, e) -> str:
        """Bind e to a global, sharing subterms."""
        if e in self.memo:
            return self.memo[e]
        bounds = None
        if e[0] == "var":
            body = f'(Var "{e[1]}")'
        elif is_exact(e):
            body = f"(Num {_f64(float(e[1]))})"
        elif e[0] in ("num", "const"):
            self.lits.append(e)
            body = f"(Lit {len(self.lits) - 1})"
            bounds = _lit_bounds(e)      # an inexact constant needs its own box
        elif e[0] in PROP_OPS:
            kids = [self.term(a) for a in e[1:]]
            body = f"({PROP_OPS[e[0]]} {' '.join(kids)})"
        else:
            kids = [self.term(a) for a in e[1:]]
            body = f"({OPS[e[0]]} {' '.join(kids)})"
        name = f"$t{self.n}"
        self.n += 1
        self.lines.append(f"(let {name} {body})")
        self.memo[e] = name
        if bounds is not None:
            self.bound(name, *bounds)
        return name

    def bound(self, name: str, lo: float, hi: float) -> None:
        self.lines.append(f"(set (lo {name}) {_f64(lo)})")
        self.lines.append(f"(set (hi {name}) {_f64(hi)})")


def _source(name: str) -> str:
    with open(os.path.join(EGG_DIR, name)) as f:
        return f.read()


def program(body, box: dict, iters: int = DEFAULT_ITERS, plans=(), seeds=()) -> tuple:
    """The .egg source, and the Lit table it indexes.

    Each plan is (target, guard, complement): the target under both contexts,
    joined by an IfProp and unioned with it.  The union needs no gate, the node
    being total and equal to both arms, and a context's leaf boxes come from the
    refinement rules in guards.egg rather than from anything emitted here.
    """
    em = _Emitter()
    for name, (lo, hi) in box.items():
        em.bound(em.term(("var", name)), lo, hi)
    root = em.term(body)
    for seed in seeds:
        em.term(seed)

    unions = []
    for i, (target, guard, complement) in enumerate(plans):
        t, p, q = em.term(target), em.term(guard), em.term(complement)
        em.lines.append(f"(let $ifp{i} (IfProp {p} (Ctx {p} {t}) (Ctx {q} {t})))")
        unions.append(f"(union $ifp{i} {t})")

    src = [_source("analysis.egg"),
           _source("rules.egg"),
           _source("guards.egg"),
           "\n".join(em.lines),
           "\n".join(unions),
           f"(let $root {root})",
           f"(run-schedule (repeat {iters} (saturate dist) "
           f"(repeat {ANA_ROUNDS} ana) opt))",
           f"(run-schedule (saturate dist) (repeat {ANA_ROUNDS} ana))"]
    src += [f"(print-function {t} 100000000)" for t in TABLES]
    return "\n".join(src) + "\n", em.lits


# -- reading back --


def _norm(s) -> str:
    if isinstance(s, list):
        return "(" + " ".join(_norm(x) for x in s) + ")"
    if isinstance(s, Str):
        return '"' + str(s) + '"'
    return str(s)


def _blocks(text: str) -> list:
    out, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if s == "(" and cur is None:
            cur = []
        elif s == ")" and cur is not None:
            out.append(cur)
            cur = None
        elif cur is not None and s:
            cur.append(s)
    return out


def _payload(op: str, tok):
    if op == "Num":
        return float(str(tok))
    if op == "Lit":
        return int(str(tok))
    return str(tok)


def parse_dump(text: str) -> tuple:
    blocks = _blocks(text)
    if len(blocks) != len(TABLES):
        raise RuntimeError(f"expected {len(TABLES)} tables in the dump, got {len(blocks)}")

    nodes, props, ends, bad = {}, {}, {"lo": {}, "hi": {}}, []
    for table, rows in zip(TABLES, blocks):
        for row in rows:
            lhs, rhs = row.rsplit(" -> ", 1)
            args = parse_sexps(lhs)[0][1:]
            if table in PROP_CONSTRUCTORS:
                cls = _norm(parse_sexps(rhs)[0])
                props.setdefault(cls, []).append(
                    ENode(table, tuple(_norm(a) for a in args), None))
            elif table in CONSTRUCTORS:
                cls = _norm(parse_sexps(rhs)[0])
                payload = _payload(table, args[0]) if table in LEAVES else None
                children = () if table in LEAVES else tuple(_norm(a) for a in args)
                nodes.setdefault(cls, []).append(ENode(table, children, payload))
            elif table in ends:
                cls, val = _norm(args[0]), float(rhs)
                if math.isnan(val):
                    raise RuntimeError(f"NaN interval endpoint on {cls}")
                ends[table][cls] = val
            else:
                bad.append(_norm(args[0]))
    if bad:
        raise BadBox("empty interval on " + "; ".join(sorted(bad)[:5]))
    # a class the analysis never bounded stays at top
    interval = {cls: Iv(ends["lo"].get(cls, NINF), ends["hi"].get(cls, INF))
                for cls in nodes}
    return nodes, interval, props


def build(body, box: dict, iters: int = DEFAULT_ITERS, out_path: str = None,
          timeout: float = None, plans=(), seeds=()) -> EGraph:
    src, lits = program(body, box, iters, plans, seeds)
    tmp = None if out_path else tempfile.mkdtemp(prefix="costex-")
    path = out_path or os.path.join(tmp, "model.egg")
    with open(path, "w") as f:
        f.write(src)
    try:
        run = subprocess.run([EGGLOG, path], capture_output=True, text=True, timeout=timeout)
        if run.returncode != 0 or "[ERROR]" in run.stderr:
            raise RuntimeError(f"egglog failed ({path}):\n{run.stderr[:2000]}")
        nodes, interval, props = parse_dump(run.stdout)
        g = EGraph(nodes, interval, lits, props=props)
        g.root = g.locate(body)
    except Exception:
        tmp = None             # a failed run keeps its model to look at
        raise
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    return g
