# Milo

Milo rewrites a floating-point program into the equivalent program with the smallest sound
error bound. It builds an e-graph of real-equivalent programs with [egglog], bounds the rounding
error of every program in it, and extracts the Pareto frontier of absolute and relative error
bounds.

- `milo/`: the tool (e-graph construction, error analysis, extraction)
- `bench/`: the paper's evaluation

## Setup

Needs [uv] and egglog-experimental:

```
cargo install egglog-experimental --version 3.0.0
```

Milo looks for it at `~/.cargo/bin/egglog-experimental`; set `EGGLOG` to use another path.

## Running a program

Write the program in [FPCore] (see [Input programs](#input-programs)):

```
(FPCore (m p)
  :name "E + p"
  :pre (and (<= 0.1 m 1) (<= -10 p 10))
  (+ (sqrt (+ (* m m) (* p p))) p))
```

Then run:

```
uv run milo program.fpcore
```

```
E + p: 1440 e-nodes, 352 e-classes, value in [0.000498756, 20.0499], frontier of 2
fixpoint at height 12: these are optimal among all programs in the e-graph
abs 7.400e-14  (+ (sqrt (+ (* m m) (* p p))) p)
rel 7.225e-13  (if (> p 0) (+ p (sqrt (+ (* m m) (* p p)))) (/ (* m m) (- (sqrt (+ (* m m) (* p p))) p)))
```

Each `abs`/`rel` line is the program with the smallest bound on that error over the whole input
range. Options: `--no-branch` (no conditionals), `--iters N` (rewriting iterations; 0 only bounds
the input), `--time-limit S` (extraction time limit in seconds).

## Input programs

- **Operations:** `+`, `-`, `*`, `/`, `sqrt`, and constants (decimal or rational, e.g. `0.1`,
  `1/3`). No `let`, `pow` or other functions. A conditional `(if (op x c) a b)` is allowed when
  `op` is `<`, `<=`, `>` or `>=`, `x` is an input and `c` is a constant; conditions on the same
  input can't be nested.
- **Ranges:** `:pre` gives every input a lower and an upper bound, as `(<= lo x hi)` combined
  with `and`. Bounds that aren't floats are widened to floats. Other preconditions (strict `<`,
  `or`, constraints between inputs) are rejected, and an input without both bounds usually leaves
  nothing to bound.
- **Definedness:** the program must be defined in real arithmetic on its whole range: no square
  root of a negative number and no division by zero. Milo assumes this without checking it; where
  it fails, the reported bounds don't hold.
- **Format:** `:precision binary64` (the default) or `binary32`. Inputs are floats in that format,
  and each operation is assumed to be correctly rounded to nearest.

## Benchmarks

- `bench/bounding_cores/` and `bench/rewriting_cores/`: Benchmark (1), the 384 straight-line
  programs of [Herbie] 2.3's `bench/` (tag `v2.3`) and [FPBench]'s `benchmarks/` (commit `50b1227`)
  that are in Milo's language once `let`s are inlined and whole powers written as products.
  `:cx-source "suite:file:i"` is the `i`th FPCore of that file, and `:name` is its name. Its box
  keeps every bound of its precondition; the `i`th input gets `[4^i, 2*4^i]` when the precondition
  does not bound it (`:cx-box "default"`), and width `2*4^i` when it bounds it on one side only.
  When the program was undefined on that box, the first box that made it defined was taken instead,
  trying with no range negated, then one, then two, and so on, and for each, `4^i` then `4^-(i+1)`,
  with inputs counted from the first then the last. Every program is proved defined on its box with
  interval arithmetic. Programs equal up to the names of their variables, with the same box, appear
  once (FPBench's copy). The 105 in `rewriting_cores/` are Benchmark (2), whose input has a max
  sampled error above 3 ulps; we only bound the other 279.
- `bench/branching/`: Benchmark (3), 11 programs whose most accurate form branches; `:cx-source`
  gives each one's origin and `:cx-expected` the branch point derived by hand.

## Tool versions

The evaluation (`bench/run.py`) used:

| Tool | Version | Notes |
|---|---|---|
| egglog-experimental | 3.0.0 | Milo's e-graph |
| [Herbie] | 2.3 (tag `v2.3`, `9297b52`) | on Racket 9.3 CS, with the platform `bench/tools/herbie_platform.rkt` |
| [FPBench] | commit `50b1227` | the benchmarks, and the export of each program to Daisy, FPTaylor and Gappa |
| [Daisy] | master `6a6f47a` | a local fix to `Taylor.scala` overrides `max`/`min` so it compiles on newer JDKs. Built with JDK 26.0.2, run with JDK 17.0.20 |
| Daisy, regimes | branch `regimes`, `8e58ff0` | for regime inference (Benchmark (3)), with upstream's rewrite-rule fix `137379b` applied, since the branch predates it, the same `Taylor.scala` fix, and build updates: sbt 1.9.9, scala-smtlib from Maven, mpfr_java 1.4 |
| [PRECiSA] | `2626ba1` (v4.2.0) | built by its Makefile with GHC 9.6.7, Kodiak and filib++ 3.0.2; a local change to `initErrorMark` in `PRECiSA/core/AbsPVSLang.hs` gives an input no initial error, so inputs are exact floats. It analyzes FPCore input in binary64 only, so binary32 programs are skipped |
| [FPTaylor] | `b5a77ca` (`v0.9.3-27`) | OCaml 4.14.2 |
| [Gappa] | 1.8.2 | |
| Python | 3.13.2 | gmpy2 2.3.1 (MPFR), as locked in `uv.lock` |
| C compiler | Apple clang 21.0.0 | run times: `-O2 -ffp-contract=off -fno-vectorize -fno-slp-vectorize` |

Timings were taken on an Apple M3 under macOS 27.0.1.

[egglog]: https://github.com/egraphs-good/egglog
[uv]: https://docs.astral.sh/uv/
[FPCore]: https://fpbench.org/spec/fpcore-2.0.html
[Herbie]: https://github.com/herbie-fp/herbie
[FPBench]: https://github.com/FPBench/FPBench
[Daisy]: https://github.com/malyzajko/daisy
[FPTaylor]: https://github.com/soarlab/FPTaylor
[Gappa]: https://gappa.gitlabpages.inria.fr/
[PRECiSA]: https://github.com/nasa/PRECiSA
