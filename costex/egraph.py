"""The e-graph: built by egglog from the rules in egg/, then read back."""

import os
import subprocess
import tempfile
from collections import namedtuple
from fractions import Fraction
from pathlib import Path

import gmpy2
from gmpy2 import mpfr, mpz

from .fpcore import read
from .interval import DOWN, INF, UP, Iv

EGGLOG = os.environ.get("EGGLOG", os.path.expanduser("~/.cargo/bin/egglog-experimental"))
RULES = os.path.join(os.path.dirname(__file__), "egg")
CONSTRUCTORS = ("Num", "Var", "Add", "Mul", "Div", "Neg", "Sqrt", "If", "Ctx")
TABLES = CONSTRUCTORS + ("lo", "hi", "Bad", "Root")

Node = namedtuple("Node", "op payload children")
EGraph = namedtuple("EGraph", "nodes interval root")


class BadBox(Exception):
    """Some subexpression is undefined on the input box."""


def context(precision, round=gmpy2.RoundToNearest):
    return gmpy2.context(gmpy2.ieee(64 if precision == "binary64" else 32), round=round)


def to_float(q, precision, round=gmpy2.RoundToNearest):
    return context(precision, round).div(mpz(q.numerator), mpz(q.denominator))


def representable(q, precision):
    f = to_float(q, precision)
    return gmpy2.is_finite(f) and Fraction(*f.as_integer_ratio()) == q


def threshold(op, c, precision):
    """The float k with x op fl(c) iff x > k for > and >=, and iff not x > k for < and <=."""
    k = to_float(c, precision)
    return float(context(precision).next_below(k) if op in (">=", "<") else k)


def f64(x):
    return repr(float(x)).replace("e+", "e")


def rational(q):
    return f'(bigrat (from-string "{q.numerator}") (from-string "{q.denominator}"))'


def guarded(e, box, precision):
    """e with each condition as x > k for a float k, keeping only the arm of one the box decides."""
    match e:
        case ("If", (op, x, c), a, b):
            k = threshold(op, c, precision)
            above, below = (a, b) if op in (">", ">=") else (b, a)
            lo, hi = box[x]
            if lo > k or hi <= k:
                return guarded(above if lo > k else below, box, precision)
            return ("If", (">", x, Fraction(k)), guarded(above, box, precision), guarded(below, box, precision))
        case ("Var" | "Num", _):
            return e
        case (op, *args):
            return (op, *(guarded(a, box, precision) for a in args))


def program(core, iters, branch):
    consts = set()

    def term(e, guard):
        """e on a region, where guard maps a variable to the condition on it there."""
        match e:
            case ("Var", x) if x in guard:
                return f'(Ctx "{x}" {guard[x]} (Var "{x}"))'
            case ("Var", x):
                return f'(Var "{x}")'
            case ("Num", q):
                consts.add(q)
                return f"(Num {rational(q)})"
            case ("If", (_, x, k), a, b):
                if x in guard:
                    raise ValueError(f"conditions on {x} are nested, which is not supported")
                arms = (term(a, guard | {x: f"{f64(k)} true"}), term(b, guard | {x: f"{f64(k)} false"}))
                return f'(If "{x}" {f64(k)} {arms[0]} {arms[1]})'
            case (op, *args):
                return f"({op} {' '.join(term(a, guard) for a in args)})"

    files = ["analysis.egg", "rules.egg"] + ["branch.egg"] * branch
    lines = [Path(RULES, f).read_text() for f in files]
    lines.append(f"(Root {term(guarded(core.body, core.box, core.precision), {})})")
    for x, (lo, hi) in core.box.items():
        lines += [f'(set (lo (Var "{x}")) {f64(lo)})', f'(set (hi (Var "{x}")) {f64(hi)})']
    for q in consts:
        lo, hi = to_float(q, "binary64", gmpy2.RoundDown), to_float(q, "binary64", gmpy2.RoundUp)
        lines += [f"(set (lo (Num {rational(q)})) {f64(lo)})", f"(set (hi (Num {rational(q)})) {f64(hi)})"]
    analysis = "(repeat 30 ana)" if iters else "(saturate ana)"
    lines.append(f"(run-schedule (let-scheduler bo (back-off)) (repeat {iters} (saturate dist) (repeat 30 ana)"
                 f" (run-with bo opt) (saturate fold) (saturate branch)) (saturate dist) {analysis})")
    lines += [f"(print-function {t} 1000000000)" for t in TABLES]
    return "\n".join(lines)


def node(op, args, precision):
    """A constant is a Num if the format represents it, and otherwise a Lit, which rounds."""
    match op:
        case "Num":
            _, (_, n), (_, d) = args[0]
            q = Fraction(int(n.strip('"')), int(d.strip('"')))
            return Node("Num" if representable(q, precision) else "Lit", q, ())
        case "Var":
            return Node(op, args[0].strip('"'), ())
        case "If":
            return Node(op, (args[0].strip('"'), Fraction(float(args[1]))), (str(args[2]), str(args[3])))
        case "Ctx":
            return Node(op, (args[0].strip('"'), Fraction(float(args[1])), args[2] == "true"), (str(args[3]),))
        case _:
            return Node(op, None, tuple(map(str, args)))


def read_dump(text, precision):
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
                nodes.setdefault(str(read(rhs)[0]), []).append(node(op, args, precision))
            elif table in ends:
                ends[table][str(args[0])] = float(rhs)
            elif table == "Bad":
                raise BadBox(lhs)
            else:
                root = str(args[0])
    interval = {c: Iv(mpfr(ends["lo"].get(c, -INF)), mpfr(ends["hi"].get(c, INF))) for c in nodes}
    for c, ns in nodes.items():
        for q in {n.payload for n in ns if n.op in ("Num", "Lit")}:
            interval[c] = Iv(DOWN.div(mpz(q.numerator), mpz(q.denominator)),
                             UP.div(mpz(q.numerator), mpz(q.denominator)))
    return EGraph(nodes, interval, root)


def build(core, iters=4, branch=True, timeout=None):
    with tempfile.NamedTemporaryFile("w", suffix=".egg") as f:
        f.write(program(core, iters, branch))
        f.flush()
        run = subprocess.run([EGGLOG, f.name], capture_output=True, text=True, timeout=timeout)
    if run.returncode:
        raise RuntimeError(f"egglog failed: {run.stderr[-1000:]}")
    return read_dump(run.stdout, core.precision)
