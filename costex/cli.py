import argparse

from .analysis import BOUNDS, set_format
from .egraph import build
from .extract import best, extract
from .fpcore import parse, show


def main(argv=None):
    parser = argparse.ArgumentParser(prog="costex", description="Extract the programs with the "
                                     "smallest absolute and relative error bounds.")
    parser.add_argument("file", help="an FPCore file")
    parser.add_argument("--iters", type=int, default=4, help="rewriting iterations; 0 bounds the input")
    parser.add_argument("--no-branch", action="store_true", help="do not introduce conditionals")
    parser.add_argument("--time-limit", type=float, default=120,
                        help="seconds for extraction, after which F_k of the last finished round is reported")
    args = parser.parse_args(argv)
    with open(args.file) as f:
        core = parse(f.read())
    set_format(core.precision)
    g = build(core, args.iters, not args.no_branch)
    F, k, cut = extract(g, args.time_limit)
    I = g.interval[g.root]
    print(f"{core.name}: {sum(map(len, g.nodes.values()))} e-nodes, {len(g.nodes)} e-classes, "
          f"value in {I}, frontier of {len(F[g.root])} at height {k}{' (cut short)' * cut}")
    for name, bound in BOUNDS.items():
        if F[g.root]:
            e, p = best(F[g.root], bound)
            print(f"{name} {float(bound(e)):.3e}  {show(p)}")
        else:
            print(f"{name} none: every program may fail")
