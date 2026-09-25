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


def _guards(e):
    """The guards a program branches on, outermost first."""
    if not isinstance(e, tuple):
        return
    if e[0] == "ifprop":
        yield e[1]
    for a in e[1:]:
        yield from _guards(a)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="costex")
    ap.add_argument("file")
    ap.add_argument("--iters", type=int, default=egg.DEFAULT_ITERS,
                    help="interleaved analysis/rewrite passes (default %(default)s)")
    ap.add_argument("--kappa", type=float, default=egg.KAPPA_MIN,
                    help="branch on an addition whose atomic condition number "
                         "exceeds this (default %(default)s)")
    ap.add_argument("--no-branch", action="store_true",
                    help="skip branching, leaving the plain analysis")
    ap.add_argument("--timeout", type=float, default=60.0,
                    help="seconds for the branching build before falling back to the "
                         "plain analysis (default %(default)s)")
    ap.add_argument("--emit", metavar="PATH", help="also write the generated .egg here")
    args = ap.parse_args(argv)
    egg.KAPPA_MIN = args.kappa

    with open(args.file) as f:
        core = parse_fpcore(f.read())
    A.set_target(53 if core.precision == "binary64" else 24)

    t0 = time.monotonic()
    try:
        if args.no_branch:
            g, branched = egg.build(core.body, core.box, iters=args.iters,
                                    out_path=args.emit, branch=False), False
        else:
            g, branched = egg.build_or_plain(core.body, core.box, iters=args.iters,
                                             out_path=args.emit, timeout=args.timeout)
    except egg.BadBox as e:
        print(f"error: {e}\nthe input box does not keep every subexpression defined",
              file=sys.stderr)
        return 1
    front = extract.extract(g)
    elapsed = time.monotonic() - t0
    Ic = g.interval[g.root]

    print(f"{core.name or args.file}   [{core.precision}]")
    for v, (lo, hi) in core.box.items():
        print(f"  {v} in [{lo!r}, {hi!r}]")
    print(f"  I_root  {Ic}")
    print(f"  {g}, {args.iters} iterations, {elapsed:.2f}s"
          + ("" if branched or args.no_branch else
             f"  (branching exceeded {args.timeout:g}s; plain analysis)"))
    print(f"  extraction {front.steps} steps, frontier {len(front.entries.get(g.root, []))}"
          + (", truncated" if front.truncated else ""))

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
        for pred in dict.fromkeys(to_sexp(p) for p in _guards(witness)):
            print(f"               branches on {pred}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
