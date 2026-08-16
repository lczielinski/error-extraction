"""S-expression reader, FPCore subset parser, and the expression AST.

An expression is a tuple:
    ('var', name) | ('num', Fraction) | ('const', 'PI'|'E')
    ('add'|'sub'|'mul'|'div', a, b) | ('neg', a) | ('sqrt', a)
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

import gmpy2
from gmpy2 import mpfr


class Sym(str):
    """A bare symbol."""


class Str(str):
    """A quoted string."""


_TOKEN = re.compile(r'\s*(?:;[^\n]*|(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()";]+))')


def tokenize(text: str):
    pos, out = 0, []
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            if text[pos:].strip() == "":
                break
            raise SyntaxError(f"cannot tokenize at {text[pos:pos + 30]!r}")
        pos = m.end()
        lparen, rparen, string, atom = m.groups()
        if lparen:
            out.append("(")
        elif rparen:
            out.append(")")
        elif string is not None:
            out.append(Str(string))
        elif atom is not None:
            out.append(Sym(atom))
    return out


def parse_sexps(text: str) -> list:
    """Parse text into a list of top-level s-expressions."""
    toks = tokenize(text)
    pos = 0

    def parse():
        nonlocal pos
        tok = toks[pos]
        pos += 1
        if tok == "(" and type(tok) is str:
            items = []
            while True:
                if pos >= len(toks):
                    raise SyntaxError("unexpected end of input")
                if toks[pos] == ")" and type(toks[pos]) is str:
                    pos += 1
                    return items
                items.append(parse())
        if tok == ")" and type(tok) is str:
            raise SyntaxError("unbalanced )")
        return tok

    out = []
    while pos < len(toks):
        out.append(parse())
    return out


# -- expressions --------------------------------------------------------

_BINOPS = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
_CONSTS = {"PI", "E"}


def _is_number(tok) -> bool:
    if not isinstance(tok, Sym):
        return False
    try:
        Fraction(str(tok))
        return True
    except ValueError:
        return False


def parse_expr(s) -> tuple:
    if isinstance(s, Sym):
        if _is_number(s):
            return ("num", Fraction(str(s)))
        if str(s) in _CONSTS:
            return ("const", str(s))
        return ("var", str(s))
    if not isinstance(s, list) or not s:
        raise SyntaxError(f"bad expression {s!r}")
    head, args = str(s[0]), [parse_expr(a) for a in s[1:]]
    if head == "sqrt":
        if len(args) != 1:
            raise SyntaxError("sqrt takes one argument")
        return ("sqrt", args[0])
    if head == "-" and len(args) == 1:
        return ("neg", args[0])
    if head in _BINOPS:
        if len(args) < 2:
            raise SyntaxError(f"{head} needs at least two arguments")
        if head in ("-", "/") and len(args) > 2:
            raise SyntaxError(f"{head} is binary here")
        out = args[0]
        for a in args[1:]:
            out = (_BINOPS[head], out, a)
        return out
    raise SyntaxError(f"unsupported operation {head!r}")


def to_sexp(e) -> str:
    op = e[0]
    if op == "var":
        return e[1]
    if op == "num":
        f = e[1]
        return str(f.numerator) if f.denominator == 1 else f"(/ {f.numerator} {f.denominator})"
    if op == "const":
        return e[1]
    if op == "neg":
        return f"(- {to_sexp(e[1])})"
    if op == "sqrt":
        return f"(sqrt {to_sexp(e[1])})"
    sym = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[op]
    return f"({sym} {to_sexp(e[1])} {to_sexp(e[2])})"


def variables(e) -> set:
    if e[0] == "var":
        return {e[1]}
    out = set()
    for a in e[1:]:
        if isinstance(a, tuple):
            out |= variables(a)
    return out


# -- evaluation ---------------------------------------------------------


def eval_real(e, env: dict):
    """Exact-arithmetic evaluation at the current MPFR precision."""
    op = e[0]
    if op == "var":
        return mpfr(env[e[1]])
    if op == "num":
        return mpfr(e[1].numerator) / mpfr(e[1].denominator)
    if op == "const":
        return gmpy2.const_pi() if e[1] == "PI" else gmpy2.exp(mpfr(1))
    if op == "neg":
        return -eval_real(e[1], env)
    if op == "sqrt":
        return gmpy2.sqrt(eval_real(e[1], env))
    a, b = eval_real(e[1], env), eval_real(e[2], env)
    return {"add": lambda: a + b, "sub": lambda: a - b,
            "mul": lambda: a * b, "div": lambda: a / b}[op]()


def eval_fp(e, env: dict) -> float:
    """The program: the same tree evaluated in binary64."""
    op = e[0]
    if op == "var":
        return float(env[e[1]])
    if op == "num":
        return e[1].numerator / e[1].denominator
    if op == "const":
        return math.pi if e[1] == "PI" else math.e
    if op == "neg":
        return -eval_fp(e[1], env)
    if op == "sqrt":
        x = eval_fp(e[1], env)
        return math.sqrt(x) if x >= 0 else math.nan
    a, b = eval_fp(e[1], env), eval_fp(e[2], env)
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    return a / b if b != 0 else math.nan


# -- FPCore -------------------------------------------------------------

_NEG_INF, _POS_INF = -math.inf, math.inf


class Core:
    def __init__(self, name, args, box, body):
        self.name = name
        self.args = args
        self.box = box  # var -> (float lo, float hi)
        self.body = body

    def __repr__(self):
        return f"Core({self.name!r}, {self.args}, {self.box}, {to_sexp(self.body)})"


def parse_fpcore(text: str) -> Core:
    forms = parse_sexps(text)
    forms = [f for f in forms if isinstance(f, list) and f and str(f[0]) == "FPCore"]
    if len(forms) != 1:
        raise SyntaxError("expected exactly one (FPCore ...) form")
    form = forms[0]
    i = 1
    name = None
    if not isinstance(form[i], list):
        name = str(form[i])
        i += 1
    if not isinstance(form[i], list):
        raise SyntaxError("expected an argument list")
    args = [str(a) for a in form[i]]
    i += 1
    props = {}
    while i < len(form) - 1:
        key = str(form[i])
        if not key.startswith(":"):
            raise SyntaxError(f"expected a property, got {key!r}")
        props[key] = form[i + 1]
        i += 2
    if i != len(form) - 1:
        raise SyntaxError("expected a single body expression")
    body = parse_expr(form[len(form) - 1])
    if name is None and ":name" in props:
        name = str(props[":name"])

    box = {a: (_NEG_INF, _POS_INF) for a in args}
    if ":pre" in props:
        for var, lo, hi in _parse_pre(props[":pre"], set(args)):
            olo, ohi = box[var]
            box[var] = (max(olo, lo), min(ohi, hi))

    unknown = variables(body) - set(args)
    if unknown:
        raise SyntaxError(f"free variables: {sorted(unknown)}")
    return Core(name, args, box, body)


def _parse_pre(pre, args: set):
    """Yield (var, lo, hi) constraints from a conjunction of interval comparisons."""
    if not isinstance(pre, list) or not pre:
        raise SyntaxError(f"unsupported precondition {pre!r}")
    head = str(pre[0])
    if head == "and":
        for p in pre[1:]:
            yield from _parse_pre(p, args)
        return
    if head not in ("<", "<=", ">", ">="):
        raise SyntaxError(f"unsupported precondition {pre!r}")
    terms = pre[1:]
    if len(terms) < 2:
        raise SyntaxError(f"unsupported precondition {pre!r}")
    if head.startswith(">"):
        terms = list(reversed(terms))
    strict = head in ("<", ">")
    for left, right in zip(terms, terms[1:]):
        lv, rv = str(left), str(right)
        if lv in args and _is_number(right):
            yield lv, _NEG_INF, _bound(Fraction(rv), upper=True, strict=strict)
        elif rv in args and _is_number(left):
            yield rv, _bound(Fraction(lv), upper=False, strict=strict), _POS_INF
        else:
            raise SyntaxError(f"unsupported comparison in precondition: {pre!r}")


def _bound(value: Fraction, upper: bool, strict: bool) -> float:
    """A float bound for the closed box: widened outward, or nudged inward if strict."""
    x = float(value)
    if strict:
        return math.nextafter(x, _NEG_INF) if upper else math.nextafter(x, _POS_INF)
    if upper:
        return x if Fraction(x) >= value else math.nextafter(x, _POS_INF)
    return x if Fraction(x) <= value else math.nextafter(x, _NEG_INF)
