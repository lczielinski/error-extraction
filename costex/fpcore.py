"""S-expressions, an FPCore subset, and the expression AST:

    ('var', name) | ('num', Fraction) | ('const', 'PI'|'E')
    ('add'|'sub'|'mul'|'div', a, b) | ('neg', a) | ('sqrt', a)
"""

from __future__ import annotations

import decimal
import math
import re
from fractions import Fraction


class Sym(str):
    """A bare symbol."""


class Str(str):
    """A quoted string."""


class _Paren:
    """A delimiter.  Not a str, so no symbol can be one."""

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


OPEN, CLOSE = _Paren("("), _Paren(")")

_TOKEN = re.compile(r'\s*(?:;[^\n]*|([(\[])|([)\]])|"((?:[^"\\]|\\.)*)"|([^\s()\[\]";]+))')


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
        if lparen is not None:
            out.append(OPEN)
        elif rparen is not None:
            out.append(CLOSE)
        elif string is not None:
            out.append(Str(string))
        elif atom is not None:
            out.append(Sym(atom))
    return out


def parse_sexps(text: str) -> list:
    """The top-level s-expressions of text."""
    toks = tokenize(text)
    pos = 0

    def parse():
        nonlocal pos
        tok = toks[pos]
        pos += 1
        if tok is CLOSE:
            raise SyntaxError("unbalanced )")
        if tok is not OPEN:
            return tok
        items = []
        while True:
            if pos >= len(toks):
                raise SyntaxError("unexpected end of input")
            if toks[pos] is CLOSE:
                pos += 1
                return items
            items.append(parse())

    out = []
    while pos < len(toks):
        out.append(parse())
    return out


# -- expressions --------------------------------------------------------

_BINOPS = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
_SYMBOLS = {v: k for k, v in _BINOPS.items()}      # for to_sexp
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
    head = str(s[0])
    if head != "sqrt" and head not in _BINOPS:
        raise SyntaxError(f"unsupported operation {head!r}")
    args = [parse_expr(a) for a in s[1:]]
    if head == "sqrt":
        if len(args) != 1:
            raise SyntaxError("sqrt takes one argument")
        return ("sqrt", args[0])
    if head == "-" and len(args) == 1:
        return ("neg", args[0])
    if len(args) < 2:
        raise SyntaxError(f"{head} needs at least two arguments")
    if head in ("-", "/") and len(args) > 2:
        raise SyntaxError(f"{head} is binary here")
    out = args[0]
    for a in args[1:]:
        out = (_BINOPS[head], out, a)
    return out


def num_str(f: Fraction) -> str:
    """A literal, decimal where that is exact."""
    if f.denominator == 1:
        return str(f.numerator)
    with decimal.localcontext() as ctx:
        ctx.prec = 80
        s = str(decimal.Decimal(f.numerator) / decimal.Decimal(f.denominator))
    return s if Fraction(s) == f else f"(/ {f.numerator} {f.denominator})"


def to_sexp(e) -> str:
    op = e[0]
    if op == "var":
        return e[1]
    if op == "num":
        return num_str(e[1])
    if op == "const":
        return e[1]
    if op == "neg":
        return f"(- {to_sexp(e[1])})"
    if op == "sqrt":
        return f"(sqrt {to_sexp(e[1])})"
    return f"({_SYMBOLS[op]} {to_sexp(e[1])} {to_sexp(e[2])})"


def to_fpcore(name: str, args: list, box: dict, body: str,
              precision: str = "binary64") -> str:
    """One (FPCore ...) form for `body` over `box`."""
    bounds = []
    for v, (lo, hi) in box.items():
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"unbounded box on {v}: [{lo!r}, {hi!r}]")
        bounds.append(f"(<= {lo!r} {v} {hi!r})")
    out = [f'(FPCore ({" ".join(args)})', f'  :name "{name}"']
    if precision != "binary64":
        out.append(f"  :precision {precision}")
    if bounds:
        out.append("  :pre " + (bounds[0] if len(bounds) == 1
                                else f"(and {' '.join(bounds)})"))
    out.append(f"  {body})")
    return "\n".join(out) + "\n"


def variables(e) -> set:
    if e[0] == "var":
        return {e[1]}
    out = set()
    for a in e[1:]:
        if isinstance(a, tuple):
            out |= variables(a)
    return out


# -- FPCore -------------------------------------------------------------


class Core:
    def __init__(self, name, args, box, body, precision="binary64", props=None):
        self.name = name
        self.args = args
        self.box = box             # var -> (float lo, float hi)
        self.body = body
        self.precision = precision
        self.props = props or {}   # raw, keyed with the leading colon

    def __repr__(self):
        return f"Core({self.name!r}, {self.args}, {self.box}, {to_sexp(self.body)})"


def core_from_form(form) -> Core:
    if not (isinstance(form, list) and form and str(form[0]) == "FPCore"):
        raise SyntaxError("not an FPCore form")
    rest = form[1:]
    name = None if not rest or isinstance(rest[0], list) else str(rest.pop(0))
    if len(rest) < 2 or not isinstance(rest[0], list):
        raise SyntaxError("expected an argument list and one body expression")
    if any(isinstance(a, list) for a in rest[0]):
        raise SyntaxError("annotated arguments")
    args = [str(a) for a in rest[0]]
    body, rest = rest[-1], rest[1:-1]
    for key in rest[::2]:
        if not str(key).startswith(":"):
            raise SyntaxError(f"expected a property, got {str(key)!r}")
    if len(rest) % 2 or (not isinstance(body, list) and str(body).startswith(":")):
        raise SyntaxError("property without a value")
    props = {str(k): v for k, v in zip(rest[::2], rest[1::2])}
    precision = str(props.get(":precision", "binary64"))
    if precision not in ("binary64", "binary32"):
        raise SyntaxError(f"precision {precision}")

    body = parse_expr(body)
    if name is None and ":name" in props:
        name = str(props[":name"])
    unknown = variables(body) - set(args)
    if unknown:
        raise SyntaxError(f"free variables: {sorted(unknown)}")

    box = {a: (-math.inf, math.inf) for a in args}
    if ":pre" in props:
        for var, lo, hi in _parse_pre(props[":pre"], set(args)):
            olo, ohi = box[var]
            box[var] = (max(olo, lo), min(ohi, hi))
    return Core(name, args, box, body, precision, props)


def parse_fpcore(text: str) -> Core:
    forms = [f for f in parse_sexps(text)
             if isinstance(f, list) and f and str(f[0]) == "FPCore"]
    if len(forms) != 1:
        raise SyntaxError("expected exactly one (FPCore ...) form")
    return core_from_form(forms[0])


def _parse_pre(pre, args: set):
    """(var, lo, hi) constraints.  An unreadable conjunct is an error: dropping
    it would widen the box past what was asked for."""
    def bail():
        raise SyntaxError(f"unsupported precondition {pre!r}")

    if not isinstance(pre, list) or not pre:
        bail()
    head = str(pre[0])
    if head == "and":
        for p in pre[1:]:
            yield from _parse_pre(p, args)
        return
    if head != "<=" or len(pre) < 3:
        bail()
    for left, right in zip(pre[1:], pre[2:]):
        lv, rv = str(left), str(right)
        if lv in args and _is_number(right):
            yield lv, -math.inf, _bound(Fraction(rv), upper=True)
        elif rv in args and _is_number(left):
            yield rv, _bound(Fraction(lv), upper=False), math.inf
        else:
            bail()


def _bound(value: Fraction, upper: bool) -> float:
    """A float bound, widened outward."""
    x = float(value)
    if upper:
        return x if Fraction(x) >= value else math.nextafter(x, math.inf)
    return x if Fraction(x) <= value else math.nextafter(x, -math.inf)
