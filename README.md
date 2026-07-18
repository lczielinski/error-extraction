# Cost-based extraction with a sound relative-error bound

A standalone, minimal implementation of e-graph extraction where the cost of a
term is a **sound upper bound on its worst-case relative rounding error** over
the input box — the idea of NumFuzz (Kellison & Hsu, *Numerical Fuzz: A Type
System for Rounding Error Analysis*, PLDI 2024) used as an extraction
objective. It is the non-LLM counterpart to the `egrammars` repo: same rewrite
rules, same benchmarks, but instead of sampling programs from the e-graph with
a language model, it deterministically picks the provably-most-accurate one.

Everything is in [extract.py](extract.py) (~350 lines, one function per stage).

## Usage

```bash
uv run extract.py nmse_problem_3_3_1     # one benchmark
uv run extract.py all                    # the whole suite (~25s)
uv run extract.py all --rounds 6         # bigger e-graphs (~6 min); this is what
                                         # cancel_sqrt_shift3 needs to find its split
uv run check.py                          # FPTaylor-measure everything extracted
uv run herbie.py                         # score against Herbie's own search
uv run daisy.py                          # score against Daisy's sound rewriting
```

Needs `uv` (the scripts declare their own dependencies) — no GPU, no model.
`check.py` additionally needs `fptaylor` on PATH (`eval $(opam env)`);
`herbie.py` needs `herbie`, or racket with the herbie package installed;
`daisy.py` needs a Daisy checkout built with `sbt compile && sbt script`
(default `~/daisy`, override with `DAISY_DIR`; on a new JDK, Daisy's
`Taylor.scala` needs explicit `override def max/min` in its
`optionAbsOrdering` to compile). Daisy is the closest incumbent — it also
optimizes a sound worst-case bound, but by genetic search with a static
analysis in the loop rather than e-graph extraction against a compositional
cost; `daisy.md` compares both tools' certified bounds and their output
programs measured by FPTaylor as the neutral judge.

Every `extract.py` run merges its records into `results.json` (benchmark,
box, extracted program, predicted bound). `check.py` then bounds each
extracted program *and its reference* with FPTaylor over the same box —
branching programs per arm over their half of the box — writes the
measurements back into `results.json`, and writes the comparison table to
`summary.md` (predicted vs measured vs reference, in ulps, with a verdict
per benchmark).

## How it works

1. **saturate** — egglog grows the e-graph of all terms provably equal to the
   reference over the box ([rules.egglog](rules.egglog), identical to
   egrammars; an interval analysis seeded from the box gates the
   domain-conditional rules). Capped by rounds / time / node count: stopping
   early only removes candidate terms, never soundness.
2. **read_egraph** — each e-class is a set of *spellings* `(op, child classes)`
   that all denote the same real value over the box.
3. **analyze_intervals** — a fixpoint computes an enclosure `[lo, hi]` of each
   class's exact value. Because every spelling of a class has the same value,
   the enclosures each spelling implies are *intersected*. Endpoints are
   rounded outward, so the truth is never shaved off.
4. **cost_table** — a fixpoint computes, per class, the cheapest
   `(relative error bound, term size)` any spelling achieves, where the bound
   `d` guarantees `computed = exact · (1 + e)` with `|e| ≤ d` everywhere in
   the box. Size breaks ties, so among equally-accurate terms the smallest
   wins (and when nothing is bounded, the smallest term overall wins).
5. **build** — emits the cheapest spelling recursively, then recomputes the
   bound on the emitted tree (what you see printed is the bound of the actual
   output, not a table estimate).
6. **split_search** — if no single term is bounded over the whole box (the box
   straddles a cancellation point), try `(if (<= var t) then else)` for
   thresholds `t` at 0 and at the integer literals in the e-graph, extracting
   each arm over its half of the box. First split where both arms are bounded
   wins. This is how `cancel_sqrt_shift3` finds its threshold at `x = 3`.

## The cost model

Two sound bounds are computed per e-class and compared lexicographically —
relative error is the objective, absolute error the fallback where no
relative bound can exist, term size the final tiebreak.

**Relative, in NumFuzz's log metric.** `R` means the term computes
`exact · e^s` with `|s| ≤ R` everywhere in the box. One rounding multiplies
by `(1+e)`, `|e| ≤ u = 2⁻⁵³`, i.e. contributes at most `E = −ln(1−u)` in the
metric — and in this metric the operators compose *additively* (this is why
NumFuzz uses it; it also makes "the bound formula itself cancels" bugs
impossible, since everything is a sum of nonnegative terms):

| term            | log-relative bound `R`                              |
|-----------------|-----------------------------------------------------|
| variable        | `0` (inputs are doubles, taken as exact)            |
| integer literal | `0` (`E` if the integer needs more than 53 bits)    |
| `(- a)`         | `Ra` — negation is exact                            |
| `(* a b)`, `(/ a b)` | `Ra + Rb + E`                                  |
| `(sqrt a)`      | `Ra/2 + E` — sqrt exactly halves the log error      |
| `a ± b`, same sign | `max(Ra, Rb) + E` — no cancellation possible     |
| `a ± b`, general   | `−ln(1 − err/min|a±b|) + E`                      |

with `err = max|a|·(e^Ra − 1) + max|b|·(e^Rb − 1)` the operands' worst
absolute deviation, from the stage-3 intervals. When the result's enclosure
reaches zero (or `err` exceeds it) the bound is infinite — no finite relative
bound exists there. NumFuzz's type system rules that case out (its numeric
type is the *strictly positive* reals); here the spelling simply loses to any
bounded alternative, and the split search or the absolute bound take over.

**Absolute.** `A` means `|computed − exact| ≤ A`. Its hard cases mirror the
relative model's: cancellation is free (absolute errors of `±` just add),
while `* / sqrt` need the interval magnitudes, and division blows up only if
the divisor's computed value can reach zero — a genuine singularity. Each op
adds its final rounding `u·|computed|` plus `ETA = 2⁻¹⁰⁷⁵` for the subnormal
range; a value that may overflow makes the bound infinite.

The two tracks help each other: at a cancelling `±`, the operand deviation
`|x̂ − x|` is bounded by the *better* of `max|x|(e^R − 1)` and `A`, so a
finite absolute bound on a child can rescue the parent's relative bound.

Soundness of the bound arithmetic itself: interval endpoints are
outward-rounded (`math.nextafter`) and every bound formula is nudged up by
`1 + 2⁻⁴⁵` (`up()`), which dwarfs the handful of roundings incurred computing
it. Remaining idealization: round-to-nearest doubles.

## Comparing against the LLM mode and Herbie

The predicted bounds are worst-case and directly comparable to FPTaylor's
relative-error bounds (both in ulps of `2⁻⁵²`); `uv run check.py` does that
comparison for you (see `summary.md`). To score against an egrammars LLM run,
the FPCore programs in `results.json` are exactly the format that repo's
`src/analysis/fptaylor_check.py` consumes.

`uv run herbie.py` scores against Herbie inside Herbie's own harness: each
benchmark becomes one FPCore with our extracted program attached as an `:alt`
target, and a single `herbie report` evaluates reference (`start`), ours
(`target`), and Herbie's rewrite (`end`) on the same sampled points with
Herbie's average-bits metric. It runs on this directory's arithmetic-only
platform ([herbie_platform.rkt](herbie_platform.rkt)) so the comparison is
search-vs-search rather than vocabulary. A second table compares *worst-case*
FPTaylor bounds — our measured bound (from `check.py`) against Herbie's
output program bounded the same way. Writes `herbie.md`; note the two tables
answer different questions: Herbie optimizes the average-case metric, this
repo optimizes (and certifies) the worst case.

Expect three kinds of outcomes:

- **bounded, small** — a well-conditioned whole-box rewrite exists and was
  found (e.g. `nmse_problem_3_3_1` at ~1.5 ulp).
- **bounded after a split** — the box straddles a fragile point but each side
  has a good form (the three `cancel_sqrt_*` benchmarks).
- **unbounded** — the exact result can be 0 somewhere in the box, so *no*
  program has a finite relative-error bound (FPTaylor reports the same);
  the smallest equivalent term is emitted instead.

Because the bound is worst-case over the box and the intervals are one
rectangle per class, the model is conservative: a reported `~200 ulp` often
measures at ~2 ulp. The *ranking* between spellings is what drives extraction,
and mis-rankings only cost accuracy, never soundness.

## Knobs

- `--rounds` (default 4): saturation rounds; more rounds = more rewrites
  reachable but bigger graphs and slower fixpoints.
- `node_cap` / `budget` in `saturate`: hard limits on e-graph growth. The
  20k default keeps the whole suite at ~0.5 s/benchmark; egrammars uses 100k
  for its grammars, which is why its in-repo variant needed subprocess
  babysitting that this version simply avoids.
