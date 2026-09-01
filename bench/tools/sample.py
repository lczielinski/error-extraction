"""Measured error: a program in the target format against a high-precision
reference over points of its box.  A lower bound on the worst case, not a
bound on it, so it must never be mixed into a minimum with a sound analyser.

Uniform points do not find a worst case, which lives on a thin set.  So each
program also climbs from the worst of them, in float-ordinal space, and every
point any climb reaches joins one pool the whole core is scored on.
"""

from __future__ import annotations

import hashlib
import math
import random
import struct

import gmpy2
from gmpy2 import mpfr

VERSION = "sample-13"
SAMPLES = 10_000
SEARCH_SEEDS = 8             # worst uniform points a program climbs from
SEARCH_LEVELS = 64           # step sizes in the ladder, span down to one float
SEARCH_EVALS = 4000          # evaluations per program, over all its climbs
SEARCH_KEEP = 8              # best points a climb contributes to the pool
REF_BITS = 256
ZERO_BITS = 4096             # before believing a reference of exactly zero
MAX_REF_BITS = 16384
SEED = 20250827
DISTRIBUTION = "float"       # or "value", uniform over the reals instead
UNSETTLED_MAX = 0.01         # of the drawn points, before a core is unusable
EQUIV_POINTS = 20
EQUIV_SETTLE = 2.0 ** -200   # equivalence needs far tighter than the error does
# Loose enough for a folded constant -- daisy prints fl(1/3) as 0.3333333333333333,
# whose exact value differs from 1/3 by an ulp -- and many orders tighter than any
# real change of function.  Measured against the input scale, not the result, so a
# point where the two cancel does not read as a disagreement.
EQUIV_TOL = 1e-12

_UNARY = {"neg", "sqrt"}


def _f32(x: float) -> float:
    try:
        return struct.unpack("f", struct.pack("f", x))[0]
    except (OverflowError, ValueError):
        return math.inf if x > 0 else -math.inf


def _ordinal(x: float, width: int) -> int:
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
    """A narrowed bound can step outside the box, so nudge in."""
    a, b = _ordinal(_f32(lo) if width == 32 else lo, width), \
        _ordinal(_f32(hi) if width == 32 else hi, width)
    if _from_ordinal(a, width) < lo:
        a += 1
    if _from_ordinal(b, width) > hi:
        b -= 1
    return a, b


def _spans(box: dict, width: int):
    """None if the box has no uniform measure, or no float inside it."""
    spans = {}
    for v, (lo, hi) in box.items():
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return None
        a, b = _span(lo, hi, width)
        if a > b:
            return None
        spans[v] = (a, b)
    return spans


def _points(file: str, box: dict, n: int, precision: str) -> list:
    """The same n points for every program of a core."""
    salt = hashlib.sha256(f"{file}|{SEED}|{DISTRIBUTION}".encode()).digest()[:8]
    rng = random.Random(int.from_bytes(salt, "big"))
    width = 32 if precision == "binary32" else 64
    names = sorted(box)
    spans = {}
    if DISTRIBUTION == "float":
        spans = _spans(box, width)
        if spans is None:
            return []
    elif any(not (math.isfinite(lo) and math.isfinite(hi))
             for lo, hi in box.values()):
        return []
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
    """The program as the target format runs it."""
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
    """The same program at the current mpfr precision."""
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
    """Never zero, so ratios of scores are safe."""
    exact = float(ref)
    if width == 32:
        exact = _f32(exact)
    if got == exact:
        return 1.0
    if math.isnan(got) or math.isnan(exact):
        return float(1 << width)
    return 1.0 + abs(_ordinal(got, width) - _ordinal(exact, width))


def floor_bits(box: dict) -> int:
    """Adding values whose exponents differ by k needs more than k bits, or
    the smaller vanishes and a cancelling reference collapses to zero."""
    mags = [abs(v) for lo, hi in box.values() for v in (lo, hi)
            if v and math.isfinite(v)] + [1.0]
    span = math.log2(max(mags)) - math.log2(min(mags))
    return min(MAX_REF_BITS, max(REF_BITS, int(2 * span) + 128))


def _noise_floor(env: dict, bits: int):
    """The largest a pure rounding residue can be at this precision: an
    expression over inputs of magnitude M carries noise of order M * 2**-bits."""
    scale = max([abs(v) for v in env.values()] + [1.0])
    return mpfr(scale) * mpfr(2) ** -bits


def _stable_ref(body, env: dict, bits: int, settle=None) -> tuple:
    """Doubles the precision until two agree.  Agreement on zero waits for
    ZERO_BITS: two precisions both losing it to cancellation agree perfectly."""
    gmpy2.get_context().precision = bits
    lo = _ref(body, env)
    while True:
        gmpy2.get_context().precision = 2 * bits
        hi = _ref(body, env)
        target = mpfr(2) ** -64 if settle is None else mpfr(settle)
        if hi != 0 and lo != 0 and abs((hi - lo) / hi) < target:
            return hi, bits
        # Both precisions put the value at or below their own rounding noise,
        # having just failed to agree relatively: that is cancellation residue,
        # which halves as the precision doubles.  A genuinely tiny value would
        # have agreed above instead of tracking the floor down.
        if bits >= ZERO_BITS and abs(hi) <= _noise_floor(env, 2 * bits) \
                and abs(lo) <= _noise_floor(env, bits):
            return mpfr(0), bits
        bits *= 2
        lo = hi
        if bits > MAX_REF_BITS:
            raise ArithmeticError(f"reference unstable past {MAX_REF_BITS} bits")


class _Refs:
    """The seed's exact value, computed once per core and shared by every
    program of it."""

    __slots__ = ("body", "names", "bits", "cache")

    def __init__(self, body, names: list, bits: int):
        self.body = body
        self.names = names
        self.bits = bits
        self.cache = {}

    def at(self, env: dict):
        key = tuple(env[v] for v in self.names)
        if key in self.cache:
            got = self.cache[key]
            if isinstance(got, ArithmeticError):
                raise got
            return got
        try:
            ref, self.bits = _stable_ref(self.body, env, self.bits)
        except (ZeroDivisionError, ValueError):
            ref = None                       # undefined for the reals too
        except ArithmeticError as ex:
            self.cache[key] = ex
            raise
        else:
            if not gmpy2.is_finite(ref):
                ref = None
        self.cache[key] = ref
        return ref

    def soft(self, env: dict):
        """An unsettleable point is unusable rather than fatal: the search
        reaches nastier regions than a uniform draw does."""
        try:
            return self.at(env)
        except ArithmeticError:
            return None


def _scorer(body, refs: _Refs, rnd, width: int):
    def score(env: dict):
        ref = refs.soft(env)
        if ref is None:
            return None
        try:
            got = _target(body, env, rnd)
        except (ZeroDivisionError, ValueError, OverflowError):
            return None
        if not math.isfinite(got):
            return None
        return _ulps(got, ref, width)
    return score


def _neighbours(env: dict, names: list, spans: dict, level: int, width: int):
    """A step is a fraction of that variable's own span, so wide and narrow
    boxes descend together."""
    for v in names:
        a, b = spans[v]
        step = max(1, (b - a) >> level)
        o = _ordinal(env[v], width)
        for moved in (o - step, o + step):
            if a <= moved <= b:
                out = dict(env)
                out[v] = _from_ordinal(moved, width)
                yield out


def _climb(score, env0: dict, names: list, spans: dict, width: int,
           budget: int) -> list:
    """Pattern search for the worst point.  Steps are ordinals, so the finest
    is one float and a cancellation region is reachable."""
    best = score(env0)
    if best is None:
        return []
    cur, used, level = env0, 0, 1
    seen = {}
    while used < budget:
        moved = False
        for env in _neighbours(cur, names, spans, level, width):
            if used >= budget:
                break
            used += 1
            got = score(env)
            if got is None:
                continue
            seen[tuple(env[v] for v in names)] = (got, env)
            if got > best:
                best, cur, moved = got, env, True
        if moved:
            continue                 # this level still pays; stay on it
        level += 1
        if all((b - a) >> level == 0 for a, b in spans.values()):
            break                    # every step is now below one float
    top = sorted(seen.values(), key=lambda pair: -pair[0])[:SEARCH_KEEP]
    return [env for _, env in top]


def _search(programs: dict, base: list, refs: _Refs, rnd, width: int,
            names: list, spans: dict) -> dict:
    """Every program climbs from its own worst uniform points.  A ladder costs
    2 * vars * levels, so many variables buy depth by climbing from fewer."""
    budget = 2 * len(names) * SEARCH_LEVELS
    seeds = max(1, min(SEARCH_SEEDS, SEARCH_EVALS // budget))
    found = {}
    for body in programs.values():
        score = _scorer(body, refs, rnd, width)
        scored = [(score(env), env) for env in base]
        starts = [env for _, env in
                  sorted(((g, e) for g, e in scored if g is not None),
                         key=lambda pair: -pair[0])[:seeds]]
        for env in starts:
            for reached in _climb(score, env, names, spans, width, budget):
                found.setdefault(tuple(reached[v] for v in names), reached)
    return found


def _equivalent(body, refs: _Refs, env: dict, bits: int) -> bool:
    """Does the rewrite agree with its seed on the reals at this point?"""
    try:
        mine, _ = _stable_ref(body, env, bits, EQUIV_SETTLE)
        theirs, _ = _stable_ref(refs.body, env, bits, EQUIV_SETTLE)
    except (ZeroDivisionError, ValueError, ArithmeticError):
        return False                 # defined for the seed, not for the rewrite
    if mine == theirs:
        return True
    scale = max([abs(mine), abs(theirs)]
                + [abs(mpfr(v)) for v in env.values()] + [mpfr(1)])
    return abs(mine - theirs) <= mpfr(EQUIV_TOL) * scale


def _report(body, pool: list, n_uniform: int, refs: _Refs, rnd, width: int,
            drawn: int, reference) -> dict:
    check = body != reference        # a rewrite: does it agree with its seed?
    abs_errs, rel_errs, broke, undef = [], [], 0, 0
    same, differs = 0, 0
    worst, worst_i = 0.0, -1
    # the mean is kept over the uniform points alone: the pool is deliberately
    # enriched with worst cases, so a mean over all of it is not an average
    # over the box
    sum_u, n_u, sum_pool = 0.0, 0, 0.0
    for i, env in enumerate(pool):
        ref = refs.soft(env)
        if ref is None:
            undef += 1               # undefined for the real numbers too
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
            near = _equivalent(body, refs, env, refs.bits)
            same, differs = same + near, differs + (not near)
        d = abs(mpfr(got) - ref)
        abs_errs.append(float(d))
        u = _ulps(got, ref, width)
        sum_pool += u
        if i < n_uniform:
            sum_u, n_u = sum_u + u, n_u + 1
        if u > worst:
            worst, worst_i = u, i
        if ref != 0:
            rel_errs.append(float(d / abs(ref)))

    if not abs_errs:
        return {"status": "nopoints", "sampled": len(pool), "broke": broke,
                "undefined": undef,
                "error": "no point was defined in both the format and the reals"}
    return {"status": "ok", "sampled": len(abs_errs), "broke": broke,
            "undefined": undef, "ref_bits": refs.bits,
            "drawn": drawn, "searched": len(pool) - n_uniform,
            "from_search": worst_i >= n_uniform,
            "ulps": worst, "bits": math.log2(worst),
            "mean_ulps": (sum_u / n_u) if n_u else None,
            "pool_mean_ulps": sum_pool / len(abs_errs),
            "equivalent": (differs == 0) if check else True,
            "equiv_checked": same + differs, "equiv_differs": differs,
            "abs": max(abs_errs), "rel": max(rel_errs) if rel_errs else None}


def measure_group(programs: dict, file: str, box: dict, precision: str,
                  reference, n: int = SAMPLES) -> dict:
    """One core's programs on one pool: the uniform points plus everything any
    climb reached.  Adversarial, and still paired.  The reference is the
    *seed's* exact value, so a rewrite that changed the function scores as
    wrong rather than as accurate."""
    width = 32 if precision == "binary32" else 64
    rnd = _f32 if precision == "binary32" else (lambda x: x)
    names = sorted(box)
    pts = _points(file, box, n, precision)
    if not pts:
        return {name: {"status": "nopoints", "error": "the box is unbounded"}
                for name in programs}

    refs = _Refs(reference, names, floor_bits(box))
    base, unsettled = [], 0
    for env in pts:
        try:
            ref = refs.at(env)
        except ArithmeticError:
            unsettled += 1       # the search already tolerates these; so here
            continue
        if ref is not None:
            base.append(env)
    if unsettled > UNSETTLED_MAX * len(pts):
        return {name: {"status": "unstable", "unsettled": unsettled,
                       "error": f"{unsettled} of {len(pts)} points never settled"}
                for name in programs}

    spans = _spans(box, width)
    found = {}
    if spans and base:               # a core with no variables has one point
        found = _search(programs, base, refs, rnd, width, names, spans)

    extra = [env for env in found.values() if refs.soft(env) is not None]
    pool = base + extra
    # where the exact value is zero, every program is ~2**62 ulps away from it
    # whatever it computes, so the ulp score saturates and carries no signal
    zeros = sum(1 for env in pool if refs.soft(env) == 0)
    return {name: dict(_report(body, pool, len(base), refs, rnd, width,
                               len(pts), reference),
                       unsettled=unsettled, ref_zeros=zeros)
            for name, body in programs.items()}
