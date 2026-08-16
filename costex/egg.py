"""Drive egglog: emit the seed program, run it, read the e-graph back."""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
from fractions import Fraction

import gmpy2

from .fpcore import Str, parse_sexps
from .interval import TOP, Iv

EGGLOG = os.environ.get("EGGLOG", os.path.expanduser("~/.cargo/bin/egglog-experimental"))
EGG_DIR = os.path.join(os.path.dirname(__file__), "egg")

DEFAULT_ITERS = 4
ANA_ROUNDS = 30

# printed in this order, so the output blocks can be matched up positionally
TABLES = ("Num", "Lit", "Var", "Add", "Sub", "Mul", "Div", "Neg", "Sqrt", "lo", "hi", "Bad")
CONSTRUCTORS = {"Num", "Lit", "Var", "Add", "Sub", "Mul", "Div", "Neg", "Sqrt"}
OPS = {"add": "Add", "sub": "Sub", "mul": "Mul", "div": "Div", "neg": "Neg", "sqrt": "Sqrt"}


class BadBox(Exception):
    """An e-class got an empty interval: the input box breaks definedness."""


class ENode:
    __slots__ = ("op", "children", "payload")

    def __init__(self, op, children, payload=None):
        self.op = op
        self.children = children
        self.payload = payload

    def key(self):
        return (self.op, self.payload, self.children)

    def __repr__(self):
        inner = " ".join([self.op] + [str(p) for p in (self.payload,) if p is not None]
                         + list(self.children))
        return f"({inner})"


class EGraph:
    def __init__(self, nodes, interval, lits, root):
        self.nodes = nodes        # class id -> [ENode]
        self.interval = interval  # class id -> Iv
        self.lits = lits          # Lit index -> AST leaf
        self.root = root

    def __repr__(self):
        return f"EGraph({len(self.nodes)} classes, {sum(map(len, self.nodes.values()))} nodes)"


# -- emitting -----------------------------------------------------------


def representable(v: Fraction) -> bool:
    """Is this exact value a binary64 number?"""
    try:
        f = float(v)
    except OverflowError:
        return False
    return math.isfinite(f) and Fraction(f) == v


def _f64(x: float) -> str:
    if x == math.inf:
        return "inf"
    if x == -math.inf:
        return "-inf"
    return repr(float(x)).replace("e+", "e")


def _lit_bounds(leaf) -> tuple:
    """A float interval enclosing an inexact constant, widened by an ulp."""
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
        """Bind e to a global and return its name, sharing subterms."""
        if e in self.memo:
            return self.memo[e]
        if e[0] == "var":
            body = f'(Var "{e[1]}")'
        elif e[0] == "num" and representable(e[1]):
            body = f"(Num {_f64(float(e[1]))})"
        elif e[0] in ("num", "const"):
            self.lits.append(e)
            body = f"(Lit {len(self.lits) - 1})"
        else:
            kids = [self.term(a) for a in e[1:]]
            body = f"({OPS[e[0]]} {' '.join(kids)})"
        name = f"$t{self.n}"
        self.n += 1
        self.lines.append(f"(let {name} {body})")
        self.memo[e] = name
        if e[0] in ("num", "const") and not (e[0] == "num" and representable(e[1])):
            lo, hi = _lit_bounds(e)
            self.lines.append(f"(set (lo {name}) {_f64(lo)})")
            self.lines.append(f"(set (hi {name}) {_f64(hi)})")
        return name


def program(body, box: dict, iters: int = DEFAULT_ITERS) -> tuple:
    """The full .egg source, plus the Lit table and the emitter's memo."""
    em = _Emitter()
    for name, (lo, hi) in box.items():
        var = em.term(("var", name))
        em.lines.append(f"(set (lo {var}) {_f64(lo)})")
        em.lines.append(f"(set (hi {var}) {_f64(hi)})")
    root = em.term(body)

    src = [open(os.path.join(EGG_DIR, "analysis.egg")).read(),
           open(os.path.join(EGG_DIR, "rules.egg")).read(),
           "\n".join(em.lines),
           f"(let $root {root})",
           f"(run-schedule (repeat {iters} (repeat {ANA_ROUNDS} ana) opt))",
           f"(run-schedule (repeat {ANA_ROUNDS} ana))"]
    src += [f"(print-function {t} 100000000)" for t in TABLES]
    return "\n".join(src) + "\n", em.lits


# -- reading back -------------------------------------------------------


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


def parse_dump(text: str, lits: list) -> tuple:
    blocks = _blocks(text)
    if len(blocks) != len(TABLES):
        raise RuntimeError(f"expected {len(TABLES)} tables in the dump, got {len(blocks)}")

    nodes, interval, bad = {}, {}, []
    for table, rows in zip(TABLES, blocks):
        for row in rows:
            lhs, rhs = row.rsplit(" -> ", 1)
            args = parse_sexps(lhs)[0][1:]
            if table in CONSTRUCTORS:
                cls = _norm(parse_sexps(rhs)[0])
                if table in ("Num", "Lit", "Var"):
                    node = ENode(table, (), _payload(table, args[0]))
                else:
                    node = ENode(table, tuple(_norm(a) for a in args))
                nodes.setdefault(cls, []).append(node)
            elif table in ("lo", "hi"):
                cls, val = _norm(args[0]), float(rhs)
                if math.isnan(val):
                    raise RuntimeError(f"NaN interval endpoint on {cls}")
                old = interval.get(cls, TOP)
                interval[cls] = (Iv(val, old.hi) if table == "lo" else Iv(old.lo, val))
            else:
                bad.append(_norm(args[0]))
    if bad:
        raise BadBox("empty interval on " + "; ".join(sorted(bad)[:5]))
    for cls in nodes:
        interval.setdefault(cls, TOP)
    return nodes, interval


def _find_root(body, nodes: dict, lits: list) -> str:
    """Locate the seed expression's class by structure."""
    index = {}
    for cls, ns in nodes.items():
        for n in ns:
            index[n.key()] = cls

    def look(e) -> str:
        if e[0] == "var":
            key = ("Var", e[1], ())
        elif e[0] == "num" and representable(e[1]):
            key = ("Num", float(e[1]), ())
        elif e[0] in ("num", "const"):
            key = ("Lit", lits.index(e), ())
        else:
            key = (OPS[e[0]], None, tuple(look(a) for a in e[1:]))
        if key not in index:
            raise RuntimeError(f"seed subterm missing from the e-graph: {key}")
        return index[key]

    return look(body)


def build(body, box: dict, iters: int = DEFAULT_ITERS, out_path: str = None) -> EGraph:
    src, lits = program(body, box, iters)
    path = out_path or os.path.join(tempfile.mkdtemp(prefix="costex-"), "model.egg")
    with open(path, "w") as f:
        f.write(src)
    run = subprocess.run([EGGLOG, path], capture_output=True, text=True)
    if run.returncode != 0 or "[ERROR]" in run.stderr:
        raise RuntimeError(f"egglog failed ({path}):\n{run.stderr[:2000]}")
    nodes, interval = parse_dump(run.stdout, lits)
    return EGraph(nodes, interval, lits, _find_root(body, nodes, lits))
