"""uv run costex prog.fpcore"""

from __future__ import annotations

import argparse
import sys

from . import analysis as A
from . import egg, extract, interval
from .fpcore import parse_fpcore, to_sexp


def _fmt(x) -> str:
    x = float(x)
    return "inf" if x == float("inf") else f"{x:.4e}"


def _fmt_S(S) -> str:
    """S sits within an ulp or two of 1, so show the deviation in units of u."""
    if S.lo <= 0 or S.hi > 2:
        return f"S = {S}"
    return f"S = 1 + [{float((S.lo - 1) / A.u):+.3f}, {float((S.hi - 1) / A.u):+.3f}]u"


def _mus(pair, Ic) -> str:
    return "  ".join(f"mu_{m} = {_fmt(A.METRICS[m](pair, Ic))}" for m in ("d", "rel", "abs"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="costex")
    ap.add_argument("file")
    ap.add_argument("--iters", type=int, default=egg.DEFAULT_ITERS,
                    help="interleaved analysis/rewrite passes (default %(default)s)")
    ap.add_argument("--prec", type=int, default=interval.DEFAULT_PRECISION,
                    help="MPFR working precision in bits (default %(default)s)")
    ap.add_argument("--format", choices=("binary64", "binary32"), default=None,
                    help="target format (default: the core's :precision)")
    ap.add_argument("--max-steps", type=int, default=extract.DEFAULT_MAX_STEPS)
    ap.add_argument("--max-frontier", type=int, default=None,
                    help="cap entries per class; forfeits optimality")
    ap.add_argument("--emit", metavar="PATH", help="also write the generated .egg here")
    args = ap.parse_args(argv)

    interval.set_precision(args.prec)
    core = parse_fpcore(open(args.file).read())
    A.set_target(53 if (args.format or core.precision) == "binary64" else 24)

    try:
        g = egg.build(core.body, core.box, iters=args.iters, out_path=args.emit)
    except egg.BadBox as e:
        print(f"error: {e}\nthe input box does not keep every subexpression defined", file=sys.stderr)
        return 1

    front = extract.extract(g, max_steps=args.max_steps, max_frontier=args.max_frontier)
    Ic = g.interval[g.root]

    print(f"{core.name or args.file}   [{args.format or core.precision}]")
    for v, (lo, hi) in core.box.items():
        print(f"  {v} in [{lo!r}, {hi!r}]")
    print(f"  I_root  {Ic}")
    print(f"  {g}, {args.iters} iterations; extraction {front.steps} steps"
          + (", truncated" if front.truncated else ""))

    seed = extract.analyze_program(g, core.body)
    print(f"\n  input   {to_sexp(core.body)}")
    print(f"          {_mus(seed, Ic) if seed is not A.BOTTOM else 'may be undefined on B'}")

    entries = front.entries.get(g.root, [])
    if not entries:
        print("\n  no program in the root class has a provable bound")
        return 1

    print()
    for m in ("d", "rel", "abs"):
        value, _, witness = front.best(g.root, Ic, m)
        print(f"  best mu_{m:<3} {_fmt(value)}   {to_sexp(witness)}")

    print(f"\n  frontier of the root class ({len(entries)} entries)")
    for pair, witness in sorted(entries, key=lambda e: float(A.mu_abs(e[0], Ic))):
        print(f"    {_fmt_S(pair.S)}   D = {pair.D}")
        print(f"      {to_sexp(witness)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
