"""Benchmark (1): every program of Herbie's and FPBench's suites in our language that is defined
on its box, written to cores/.

    uv run python bench/corpus.py [directory]

A program's box comes from the comparisons of a variable with a number in its precondition. A
variable bounded on one side only gets width 2*4^i, and one bounded on neither [4^i, 2*4^i], for
its position i among the arguments, or its position from the end if the program is undefined
otherwise. A program is defined if it is at each of 1000 sampled points.
"""

import decimal
import glob
import math
import os
import re
import sys
from collections import Counter
from fractions import Fraction
from itertools import pairwise

BENCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BENCH))

import sample  # noqa: E402
from milo import fpcore  # noqa: E402
from milo.fpcore import Core, expr, number, read, show, variables  # noqa: E402

SUITES = {"herbie": os.path.expanduser("~/herbie/bench"), "fpbench": os.path.expanduser("~/fpbench/benchmarks")}
FLIP = {**fpcore.FLIP, "==": "=="}


def inline(e, env):
    """e with its lets substituted, and (pow a n) for a whole n >= 1 as a product."""
    match e:
        case str():
            return env.get(e, e)
        case ["let", bindings, body]:
            return inline(body, env | {x: inline(v, env) for x, v in bindings})
        case ["let*", bindings, body]:
            for x, v in bindings:
                env = env | {x: inline(v, env)}
            return inline(body, env)
        case ["pow", a, str(n)] if number(n) and number(n).denominator == 1 and number(n) >= 1:
            out = a = inline(a, env)
            for _ in range(int(number(n)) - 1):
                out = ["*", out, a]
            return out
        case [op, *args]:
            return [op] + [inline(a, env) for a in args]


def down(q):
    f = float(q)
    return f if Fraction(f) <= q else math.nextafter(f, -math.inf)


def up(q):
    f = float(q)
    return f if Fraction(f) >= q else math.nextafter(f, math.inf)


def comparison(op, q):
    """The floats x with x op q, as an interval widened outward to floats."""
    lo = {">=": down(q), "==": down(q), ">": math.nextafter(down(q), math.inf)}.get(op, -math.inf)
    hi = {"<=": up(q), "==": up(q), "<": math.nextafter(up(q), -math.inf)}.get(op, math.inf)
    return lo, hi


def meet(boxes):
    out = {}
    for box in boxes:
        for x, (lo, hi) in box.items():
            a, b = out.get(x, (-math.inf, math.inf))
            out[x] = (max(a, lo), min(b, hi))
    return out


def join(boxes):
    boxes = list(boxes)
    return {x: (min(b[x][0] for b in boxes), max(b[x][1] for b in boxes))
            for x in set.intersection(*(set(b) for b in boxes))}


def ranges(pre):
    match pre:
        case ["and", *ps]:
            return meet(map(ranges, ps))
        case ["or", *ps]:
            return join(map(ranges, ps))
        case [op, *terms] if op in FLIP:
            facts = []
            for a, b in pairwise(terms):
                if isinstance(a, str) and isinstance(b, str):
                    if number(a) is None and number(b) is not None:
                        facts.append({a: comparison(op, number(b))})
                    elif number(a) is not None and number(b) is None:
                        facts.append({b: comparison(FLIP[op], number(a))})
            return meet(facts)
    return {}


def box(args, pre, reverse=False):
    bounds = ranges(pre)
    out = {}
    for i, x in enumerate(reversed(args) if reverse else args):
        lo, hi = bounds.get(x, (-math.inf, math.inf))
        w = 2 * 4.0 ** i
        if lo == -math.inf and hi == math.inf:
            lo, hi = w / 2, w
        elif lo == -math.inf:
            lo = hi - w
        elif hi == math.inf:
            hi = lo + w
        out[x] = (lo, hi)
    return {x: out[x] for x in args}


def defined(core):
    if any(lo > hi for lo, hi in core.box.values()):
        return False
    return all(sample.exact(core.body, env) is not None for env in sample.points(core, 1000))


def translate(form):
    """The core of an FPCore form, or the reason it is not in our language."""
    rest = form[1:]
    ident = rest.pop(0) if isinstance(rest[0], str) else None
    args, *props, body = rest
    props = dict(zip(props[::2], props[1::2]))
    precision = props.get(":precision", "binary64")
    if precision not in ("binary64", "binary32"):
        return f"precision {precision}"
    if not all(isinstance(a, str) for a in args):
        return "annotated argument"
    try:
        body = expr(inline(body, {}))
    except SyntaxError as e:
        return str(e)
    if variables(body) - set(args):
        return f"constant {' '.join(sorted(variables(body) - set(args)))}"
    name = props.get(":name", ident or "").strip('"')
    return Core(name, args, box(args, props.get(":pre", ["and"])), precision, body, props)


def text(core, source):
    given = set(ranges(core.props.get(":pre", ["and"])))
    pre = " ".join(f"(<= {decimal.Decimal(lo):f} {x} {decimal.Decimal(hi):f})" for x, (lo, hi) in core.box.items())
    lines = [f"(FPCore ({' '.join(core.args)})", f':name "{core.name}"', f':cx-source "{source}"',
             f':cx-box "{"pre" if given >= set(core.args) else "default"}"', f":precision {core.precision}"]
    lines += [f":pre (and {pre})"] * bool(pre) + [f"{show(core.body)})"]
    return "\n  ".join(lines) + "\n"


def main(out):
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*.fpcore")):
        os.remove(old)
    skipped = Counter()
    for suite, root in SUITES.items():
        for path in sorted(glob.glob(f"{root}/**/*.fpcore", recursive=True)):
            rel = os.path.relpath(path, root)
            with open(path) as f:
                forms = [form for form in read(f.read()) if isinstance(form, list) and form[:1] == ["FPCore"]]
            for i, form in enumerate(forms):
                core = translate(form)
                if isinstance(core, str):
                    skipped[re.sub(r" \[.*|, .*", "", core)] += 1
                    continue
                if not defined(core):
                    core = core._replace(box=box(core.args, core.props.get(":pre", ["and"]), True))
                    if not defined(core):
                        skipped["undefined on its box"] += 1
                        continue
                slug = re.sub(r"[^a-z0-9]+", "-", core.name.lower()).strip("-")[:40]
                stem = re.sub(r"[^a-z0-9]+", "-", rel[:-len(".fpcore")].lower())
                with open(os.path.join(out, f"{suite}-{stem}-{i:03d}-{slug}.fpcore"), "w") as f:
                    f.write(text(core, f"{suite}:{rel}:{i}"))
    print(f"{len(glob.glob(os.path.join(out, '*.fpcore')))} cores; skipped:")
    for reason, n in skipped.most_common():
        print(f"  {n:4} {reason}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCH, "cores"))
