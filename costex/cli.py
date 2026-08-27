"""uv run costex prog.fpcore"""

from __future__ import annotations

import argparse
import sys
import time

from . import analysis as A
from . import egg, extract
from .fpcore import parse_fpcore, to_sexp


def _fmt(x) -> str:
    x = float(x)
    return "inf" if x == float("inf") else f"{x:.4e}"


def _mus(pair, Ic) -> str:
    return "  ".join(f"mu_{m} = {_fmt(A.METRICS[m](pair, Ic))}" for m in A.METRICS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="costex")
    ap.add_argument("file")
    ap.add_argument("--iters", type=int, default=egg.DEFAULT_ITERS,
                    help="interleaved analysis/rewrite passes (default %(default)s)")
    ap.add_argument("--emit", metavar="PATH", help="also write the generated .egg here")
    args = ap.parse_args(argv)

    with open(args.file) as f:
        core = parse_fpcore(f.read())
    A.set_target(53 if core.precision == "binary64" else 24)

    t0 = time.monotonic()
    try:
        g = egg.build(core.body, core.box, iters=args.iters, out_path=args.emit)
    except egg.BadBox as e:
        print(f"error: {e}\nthe input box does not keep every subexpression defined",
              file=sys.stderr)
        return 1
    t1 = time.monotonic()
    front = extract.extract(g)
    t2 = time.monotonic()
    Ic = g.interval[g.root]

    print(f"{core.name or args.file}   [{core.precision}]")
    for v, (lo, hi) in core.box.items():
        print(f"  {v} in [{lo!r}, {hi!r}]")
    print(f"  I_root  {Ic}")
    print(f"  {g}, {args.iters} iterations, {t1 - t0:.2f}s")
    print(f"  extraction {front.steps} steps, frontier {len(front.entries.get(g.root, []))}"
          f", {t2 - t1:.2f}s" + (", truncated" if front.truncated else ""))

    seed = extract.analyze_program(g, core.body)
    print(f"\n  input   {to_sexp(core.body)}")
    print("          " + (_mus(seed, Ic) if seed is not A.BOTTOM
                          else "may be undefined on B"))

    if not front.entries.get(g.root):
        print("\n  no program in the root class has a provable bound")
        return 1

    print()
    for m in A.METRICS:
        value, _, witness = front.best(g.root, Ic, m)
        print(f"  best mu_{m:<3} {_fmt(value)}   {to_sexp(witness)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
