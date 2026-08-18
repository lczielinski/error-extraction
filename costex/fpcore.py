"""S-expression reader, FPCore subset parser, and the expression AST.

An expression is a tuple:
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
    """A delimiter.  Not a str, so it cannot be confused with a symbol."""

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
        if lparen:
            out.append(OPEN)
        elif rparen:
            out.append(CLOSE)
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


MAX_POW = 8


def desugar(s, env: dict = None):
    """Inline let/let*, expand pow with a small rational exponent, drop annotations."""
    env = env or {}
    if isinstance(s, Sym):
        return env.get(str(s), s)
    if not isinstance(s, list) or not s:
        return s
    head = str(s[0])
    if head == "!":
        props = dict(zip((str(p) for p in s[1:-1:2]), s[2:-1:2]))
        if str(props.get(":precision", "binary64")) != "binary64":
            raise SyntaxError("annotation changes precision")
        return desugar(s[-1], env)
    if head in ("let", "let*"):
        if len(s) != 3 or not isinstance(s[1], list):
            raise SyntaxError("malformed let")
        inner = dict(env)
        for b in s[1]:
            if not isinstance(b, list) or len(b) != 2:
                raise SyntaxError("malformed binding")
            inner[str(b[0])] = desugar(b[1], inner if head == "let*" else env)
        return desugar(s[2], inner)
    if head == "pow" and len(s) == 3:
        return _expand_pow(desugar(s[1], env), s[2])
    return [s[0]] + [desugar(a, env) for a in s[1:]]


def _expand_pow(base, exponent):
    if not _is_number(exponent):
        raise SyntaxError("pow with a non-constant exponent")
    n = Fraction(str(exponent))
    if n == Fraction(1, 2):
        return [Sym("sqrt"), base]
    if n.denominator != 1 or abs(n) > MAX_POW:
        raise SyntaxError(f"pow exponent {n}")
    k = abs(int(n))
    out = Sym("1") if k == 0 else base
    for _ in range(k - 1):
        out = [Sym("*"), out, base]
    return out if n >= 0 else [Sym("/"), Sym("1"), out]


def num_str(f: Fraction) -> str:
    """A literal, as a decimal when that is exact."""
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
    sym = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[op]
    return f"({sym} {to_sexp(e[1])} {to_sexp(e[2])})"


def to_fpcore(name: str, args: list, box: dict, body: str) -> str:
    """One (FPCore ...) form for the s-expression `body` over `box`.

    The box written out is the float box the analysis actually used, not the
    source :pre, whose strict inequalities were nudged inward on the way in.
    """
    for v, (lo, hi) in box.items():
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"unbounded box on {v}: [{lo!r}, {hi!r}]")
    bounds = [f"(<= {lo!r} {v} {hi!r})" for v, (lo, hi) in box.items()]
    out = [f'(FPCore ({" ".join(args)})', f'  :name "{name}"']
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

_NEG_INF, _POS_INF = -math.inf, math.inf


class Core:
    def __init__(self, name, args, box, body, precision="binary64", props=None):
        self.name = name
        self.precision = precision
        self.props = props or {}   # raw properties, keyed with the leading colon
        self.args = args
        self.box = box             # var -> (float lo, float hi)
        self.body = body

    def __repr__(self):
        return f"Core({self.name!r}, {self.args}, {self.box}, {to_sexp(self.body)})"


def core_from_form(form) -> Core:
    if not (isinstance(form, list) and form and str(form[0]) == "FPCore"):
        raise SyntaxError("not an FPCore form")
    i = 1
    name = None
    if not isinstance(form[i], list):
        name = str(form[i])
        i += 1
    if not isinstance(form[i], list):
        raise SyntaxError("expected an argument list")
    if any(isinstance(a, list) for a in form[i]):
        raise SyntaxError("annotated arguments")
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
    precision = str(props.get(":precision", "binary64"))
    if precision not in ("binary64", "binary32"):
        raise SyntaxError(f"precision {precision}")

    body = parse_expr(desugar(form[-1]))
    if name is None and ":name" in props:
        name = str(props[":name"])
    unknown = variables(body) - set(args)
    if unknown:
        raise SyntaxError(f"free variables: {sorted(unknown)}")

    box = {a: (_NEG_INF, _POS_INF) for a in args}
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
    """Yield (var, lo, hi) constraints.  A conjunct we cannot read is an error:
    silently dropping it would widen the box past what was asked for."""
    def bail():
        raise SyntaxError(f"unsupported precondition {pre!r}")

    if not isinstance(pre, list) or not pre:
        bail()
    head = str(pre[0])
    if head == "and":
        for p in pre[1:]:
            yield from _parse_pre(p, args)
        return
    if head not in ("<", "<=", ">", ">=") or len(pre) < 3:
        bail()
    terms = list(reversed(pre[1:])) if head.startswith(">") else pre[1:]
    is_strict = head in ("<", ">")
    for left, right in zip(terms, terms[1:]):
        lv, rv = str(left), str(right)
        if lv in args and _is_number(right):
            yield lv, _NEG_INF, _bound(Fraction(rv), upper=True, strict=is_strict)
        elif rv in args and _is_number(left):
            yield rv, _bound(Fraction(lv), upper=False, strict=is_strict), _POS_INF
        else:
            bail()


def _bound(value: Fraction, upper: bool, strict: bool) -> float:
    """A float bound for the closed box: widened outward, nudged inward if strict."""
    x = float(value)
    if strict:
        return math.nextafter(x, _NEG_INF) if upper else math.nextafter(x, _POS_INF)
    if upper:
        return x if Fraction(x) >= value else math.nextafter(x, _POS_INF)
    return x if Fraction(x) <= value else math.nextafter(x, _NEG_INF)
