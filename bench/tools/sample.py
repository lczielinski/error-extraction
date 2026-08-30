"""Measured error: a program in the target format against a high-precision
reference, over points of its box.  A lower bound on the worst case, not a
bound on it, so it must never be mixed into a minimum with a sound analyser.
"""

from __future__ import annotations

import hashlib
import math
import random
import struct

import gmpy2
from gmpy2 import mpfr

VERSION = "sample-11"
SAMPLES = 10_000
REF_BITS = 256
ZERO_BITS = 4096             # before believing a reference of exactly zero
MAX_REF_BITS = 16384
SEED = 20250827
DISTRIBUTION = "float"       # or "value", uniform over the reals instead
EQUIV_POINTS = 20
EQUIV_SETTLE = 2.0 ** -200   # equivalence needs far tighter than the error does
EQUIV_TOL = 1e-25

_UNARY = {"neg", "sqrt"}


def _f32(x: float) -> float:
    try:
        return struct.unpack("f", struct.pack("f", x))[0]
    except (OverflowError, ValueError):
        return math.inf if x > 0 else -math.inf


def _ordinal(x: float, width: int) -> int:
    """A monotone index over the representable numbers, adjacent floats one
    apart, so a uniform integer draw is a uniform draw over floats."""
    if width == 32:
        n, sign = struct.unpack("<I", struct.pack("<f", x))[0], 1 << 31
    else:
        n, sign = struct.unpack("<Q", struct.pack("<d", x))[0], 1 << 63
    return -(n & ~sign) if n & sign else n


def _from_ordinal(o: int, width: int) -> float:
    if width == 32:
        n = ((-o) | (1 << 31)) if o < 0 else o
        return struct.unpack("<f", struct.pack("<I", n))[0]
    n = ((-o) | (1 << 63)) if o < 0 else o
    return struct.unpack("<d", struct.pack("<Q", n))[0]


def _span(lo: float, hi: float, width: int) -> tuple:
    """Ordinals of the representable numbers inside [lo, hi].  Narrowing a
    bound can step outside the box, so nudge inward."""
    a, b = _ordinal(_f32(lo) if width == 32 else lo, width), \
        _ordinal(_f32(hi) if width == 32 else hi, width)
    if _from_ordinal(a, width) < lo:
        a += 1
    if _from_ordinal(b, width) > hi:
        b -= 1
    return a, b


def _points(file: str, box: dict, n: int, precision: str) -> list:
    """The same n points for every program of a core."""
    salt = hashlib.sha256(f"{file}|{SEED}|{DISTRIBUTION}".encode()).digest()[:8]
    rng = random.Random(int.from_bytes(salt, "big"))
    width = 32 if precision == "binary32" else 64
    names = sorted(box)
    spans = {}
    for v in names:
        lo, hi = box[v]
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return []              # an unbounded box has no uniform measure
        if DISTRIBUTION == "float":
            a, b = _span(lo, hi, width)
            if a > b:
                return []          # no representable number inside the box
            spans[v] = (a, b)
    out = []
    for _ in range(n):
        p = {}
        for v in names:
            lo, hi = box[v]
            if DISTRIBUTION == "float":
                a, b = spans[v]
                p[v] = _from_ordinal(rng.randint(a, b), width)
            else:
                p[v] = lo if lo == hi else rng.uniform(lo, hi)
        out.append(p)
    return out


def _target(e, env: dict, rnd):
    """As the target format computes it, rounding after every operation."""
    op = e[0]
    if op == "var":
        return env[e[1]]
    if op == "num":
        return rnd(e[1].numerator / e[1].denominator) if e[1].denominator != 1 \
            else rnd(float(e[1].numerator))
    if op == "const":
        return rnd(math.pi if e[1] == "PI" else math.e)
    if op in _UNARY:
        a = _target(e[1], env, rnd)
        if op == "neg":
            return -a
        if a < 0:
            raise ValueError("sqrt of a negative")
        return rnd(math.sqrt(a))
    a, b = _target(e[1], env, rnd), _target(e[2], env, rnd)
    if op == "add":
        return rnd(a + b)
    if op == "sub":
        return rnd(a - b)
    if op == "mul":
        return rnd(a * b)
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return rnd(a / b)


def _ref(e, env: dict):
    """Exactly, at the ambient precision.  A point's coordinates are doubles,
    so they are exact here."""
    op = e[0]
    if op == "var":
        return mpfr(env[e[1]])
    if op == "num":
        return mpfr(e[1].numerator) / mpfr(e[1].denominator)
    if op == "const":
        return gmpy2.const_pi() if e[1] == "PI" else gmpy2.exp(mpfr(1))
    if op in _UNARY:
        a = _ref(e[1], env)
        if op == "neg":
            return -a
        if a < 0:
            raise ValueError("sqrt of a negative")
        return gmpy2.sqrt(a)
    a, b = _ref(e[1], env), _ref(e[2], env)
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def _ulps(got: float, ref, width: int) -> float:
    """Representable numbers between the computed value and the rounded exact
    one, plus one.  Bounded, so no single point dominates a maximum the way an
    unbounded relative error does."""
    exact = float(ref)
    if width == 32:
        exact = _f32(exact)
    if got == exact:
        return 1.0
    if math.isnan(got) or math.isnan(exact):
        return float(1 << width)
    return 1.0 + abs(_ordinal(got, width) - _ordinal(exact, width))


def floor_bits(box: dict) -> int:
    """Adding values whose exponents differ by k needs more than k bits or the
    smaller vanishes: x + 1 at x~1e307 becomes x below ~1020 bits, and the
    reference for sqrt(x+1) - sqrt(x) then collapses to zero."""
    mags = [abs(v) for lo, hi in box.values() for v in (lo, hi)
            if v and math.isfinite(v)] + [1.0]
    span = math.log2(max(mags)) - math.log2(min(mags))
    return min(MAX_REF_BITS, max(REF_BITS, int(2 * span) + 128))


def _stable_ref(body, env: dict, bits: int, settle=None) -> tuple:
    """Doubles the precision until two agree on a nonzero value.  Agreement on
    zero is not believed until ZERO_BITS: two low precisions both losing the
    value to cancellation agree perfectly, and that is the failure."""
    gmpy2.get_context().precision = bits
    lo = _ref(body, env)
    while True:
        gmpy2.get_context().precision = 2 * bits
        hi = _ref(body, env)
        target = mpfr(2) ** -64 if settle is None else mpfr(settle)
        if hi != 0 and lo != 0 and abs((hi - lo) / hi) < target:
            return hi, bits
        if hi == 0 and lo == 0 and bits >= ZERO_BITS:
            return hi, bits          # still zero with room to spare: really zero
        bits *= 2
        lo = hi
        if bits > MAX_REF_BITS:
            raise ArithmeticError(f"reference unstable past {MAX_REF_BITS} bits")


def measure(body, file: str, box: dict, precision: str, n: int = SAMPLES,
            reference=None) -> dict:
    """The worst error observed over n points of the box.

    The reference is the *seed's* exact value, not the candidate's own.  A
    rewrite is supposed to compute the same function, so for an honest one the
    two agree; for a rewrite that quietly changed the function they do not, and
    measuring against its own exact value would score a wrong answer computed
    accurately as perfect.  Daisy's rewriter does exactly that on two cores.
    """
    reference = body if reference is None else reference
    rnd = _f32 if precision == "binary32" else (lambda x: x)
    pts = _points(file, box, n, precision)
    if not pts:
        return {"status": "nopoints", "error": "the box is unbounded"}

    width = 32 if precision == "binary32" else 64
    check = body != reference        # a rewrite: does it agree with its seed?
    abs_errs, rel_errs, ulps, broke, undef = [], [], [], 0, 0
    same, differs = 0, 0
    bits = floor_bits(box)       # never lowered again: what one point needed, others may
    for env in pts:
        try:
            ref, bits = _stable_ref(reference, env, bits)
        except (ZeroDivisionError, ValueError):
            undef += 1               # undefined for the real numbers too
            continue
        except ArithmeticError as ex:
            return {"status": "unstable", "error": str(ex)}
        if not gmpy2.is_finite(ref):
            undef += 1
            continue
        try:
            got = _target(body, env, rnd)
        except (ZeroDivisionError, ValueError, OverflowError):
            broke += 1               # defined over the reals, broken in the format
            continue
        if not math.isfinite(got):
            broke += 1
            continue
        if check and same + differs < EQUIV_POINTS:
            try:
                mine, _ = _stable_ref(body, env, bits, EQUIV_SETTLE)
                theirs, _ = _stable_ref(reference, env, bits, EQUIV_SETTLE)
            except (ZeroDivisionError, ValueError, ArithmeticError):
                differs += 1         # defined for the seed, not for the rewrite
            else:
                near = (mine == theirs or (theirs != 0 and
                                           abs((mine - theirs) / theirs) < EQUIV_TOL))
                same, differs = same + bool(near), differs + (not near)
        d = abs(mpfr(got) - ref)
        abs_errs.append(float(d))
        ulps.append(_ulps(got, ref, width))
        if ref != 0:
            rel_errs.append(float(d / abs(ref)))

    if not abs_errs:
        return {"status": "nopoints", "sampled": len(pts), "broke": broke,
                "undefined": undef,
                "error": "no point was defined in both the format and the reals"}
    worst = max(ulps)
    return {"status": "ok", "sampled": len(abs_errs), "broke": broke,
            "undefined": undef, "ref_bits": bits,
            "ulps": worst, "bits": math.log2(worst),
            "equivalent": (differs == 0) if check else True,
            "equiv_checked": same + differs, "equiv_differs": differs,
            "abs": max(abs_errs), "rel": max(rel_errs) if rel_errs else None}
