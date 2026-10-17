"""The e-graph: built by egglog from the rules in egg/, then read back."""

import math
import os
import struct
import subprocess
import tempfile
from collections import namedtuple
from fractions import Fraction

from gmpy2 import mpfr

from .fpcore import read
from .interval import INF, Iv

EGGLOG = os.environ.get("EGGLOG", os.path.expanduser("~/.cargo/bin/egglog-experimental"))
RULES = os.path.join(os.path.dirname(__file__), "egg")
CONSTRUCTORS = ("Num", "Lit", "Var", "Add", "Mul", "Div", "Neg", "Sqrt", "If", "Ctx")
TABLES = CONSTRUCTORS + ("lo", "hi", "Bad", "Root")

Node = namedtuple("Node", "op payload children")
EGraph = namedtuple("EGraph", "nodes interval root")


class BadBox(Exception):
    """Some subexpression is undefined somewhere on the input box."""


def single(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def representable(q, precision):
    try:
        f = float(q)
        if precision == "binary32":
            f = single(f)
    except OverflowError:
        return False
    return math.isfinite(f) and Fraction(f) == q


def threshold(op, c, precision):
    """The float k of the format with: x op c iff x > k (> and >=) or iff not x > k (< and <=),
    for every float x, the literal c being rounded to the format as the program does."""
    k = float(c) if precision == "binary64" else single(float(c))
    if op in (">=", "<") and precision == "binary64":
        k = math.nextafter(k, -math.inf)
    elif op in (">=", "<"):
        n = struct.unpack("<I", struct.pack("<f", k))[0]
        n = n - 1 if k > 0 else 0x80000001 if k == 0 else n + 1
        k = struct.unpack("<f", struct.pack("<I", n))[0]
    return k


def f64(x):
    return repr(float(x)).replace("e+", "e")


def program(core, iters, branch):
    lits = set()

    def term(e, box, guard):
        """e on the region box, where guard maps a variable to the innermost condition on it."""
        match e:
            case ("Var", x) if x in guard:
                return f'(Ctx "{x}" {guard[x]} (Var "{x}"))'
            case ("Var", x):
                return f'(Var "{x}")'
            case ("Num", q) if representable(q, core.precision):
                return f"(Num {f64(q)})"
            case ("Num", q):
                lits.add(q)
                return f'(Lit "{q}")'
            case ("If", (op, x, c), a, b):
                k = threshold(op, c, core.precision)
                above, below = (a, b) if op in (">", ">=") else (b, a)
                (lo, hi), arms = box[x], []
                if hi > k:
                    arms.append(term(above, {**box, x: (k, hi)}, {**guard, x: f"{f64(k)} true"}))
                if lo <= k:
                    arms.append(term(below, {**box, x: (lo, k)}, {**guard, x: f"{f64(k)} false"}))
                return f'(If "{x}" {f64(k)} {" ".join(arms)})' if len(arms) == 2 else arms[0]
            case (op, *args):
                return f"({op} {' '.join(term(a, box, guard) for a in args)})"

    files = ["analysis.egg", "rules.egg"] + ["branch.egg"] * branch
    lines = [open(os.path.join(RULES, f)).read() for f in files]
    lines.append(f"(Root {term(core.body, core.box, {})})")
    for x, (lo, hi) in core.box.items():
        lines += [f'(set (lo (Var "{x}")) {f64(lo)})', f'(set (hi (Var "{x}")) {f64(hi)})']
    for q in lits:
        lo, hi = math.nextafter(float(q), -math.inf), math.nextafter(float(q), math.inf)
        lines += [f'(set (lo (Lit "{q}")) {f64(lo)})', f'(set (hi (Lit "{q}")) {f64(hi)})']
    analysis = "(repeat 30 ana)" if iters else "(saturate ana)"
    lines.append(f"(run-schedule (repeat {iters} (saturate dist) (repeat 30 ana) opt (saturate branch))"
                 f" (saturate dist) {analysis})")
    lines += [f"(print-function {t} 1000000000)" for t in TABLES]
    return "\n".join(lines)


def node(op, args):
    match op:
        case "Num":
            return Node(op, Fraction(float(args[0])), ())
        case "Lit":
            return Node(op, Fraction(args[0].strip('"')), ())
        case "Var":
            return Node(op, args[0].strip('"'), ())
        case "If":
            return Node(op, (args[0].strip('"'), Fraction(float(args[1]))), (str(args[2]), str(args[3])))
        case "Ctx":
            return Node(op, (args[0].strip('"'), Fraction(float(args[1])), args[2] == "true"), (str(args[3]),))
        case _:
            return Node(op, None, tuple(map(str, args)))


def read_dump(text):
    tables = []
    for line in text.splitlines():
        if line == "(":
            tables.append([])
        elif line != ")":
            tables[-1].append(line.split(" -> "))
    nodes, ends, root = {}, {"lo": {}, "hi": {}}, None
    for table, rows in zip(TABLES, tables):
        for lhs, rhs in rows:
            op, *args = read(lhs)[0]
            if table in CONSTRUCTORS:
                nodes.setdefault(str(read(rhs)[0]), []).append(node(op, args))
            elif table in ends:
                ends[table][str(args[0])] = float(rhs)
            elif table == "Bad":
                raise BadBox(lhs)
            else:
                root = str(args[0])
    interval = {c: Iv(mpfr(ends["lo"].get(c, -INF)), mpfr(ends["hi"].get(c, INF))) for c in nodes}
    return EGraph(nodes, interval, root)


def build(core, iters=4, branch=True, timeout=None):
    with tempfile.NamedTemporaryFile("w", suffix=".egg") as f:
        f.write(program(core, iters, branch))
        f.flush()
        run = subprocess.run([EGGLOG, f.name], capture_output=True, text=True, timeout=timeout)
    if run.returncode:
        raise RuntimeError(f"egglog failed: {run.stderr[-1000:]}")
    return read_dump(run.stdout)
