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
```

Needs `uv` (the scripts declare their own dependencies) — no GPU, no model.
`check.py` additionally needs `fptaylor` on PATH (`eval $(opam env)`).

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

Each floating-point operation rounds once: it multiplies its exact result by
`(1 + e)` with `|e| ≤ u = 2⁻⁵³` (IEEE double, round to nearest). Given bounds
`da`, `db` for the children, the bound for each operator is:

| term            | bound on relative error                              |
|-----------------|------------------------------------------------------|
| variable        | `0` (inputs are doubles, taken as exact)             |
| integer literal | `0` (`u` if the integer needs more than 53 bits)     |
| `(- a)`         | `da` — negation is exact                             |
| `(* a b)`       | `((1+da)(1+db) − 1) ⊕ u`                             |
| `(/ a b)`       | `(da ⊕ db/(1−db)) ⊕ u`, infinite if `db ≥ 1`         |
| `(sqrt a)`      | `≈ da/2 ⊕ u` (two-sided, exact formula in the code)  |
| `a ± b`, same sign | `max(da, db) ⊕ u` — no cancellation possible      |
| `a ± b`, general   | `(max|a|·da + max|b|·db) / min|a±b| ⊕ u`          |

where `x ⊕ y = x + y + x·y` stacks two relative errors (this is exactly
`(1+x)(1+y) − 1`, but written so the formula itself cannot cancel — computing
`1 + 2⁻⁵³ − 1` naively gives `0.0`!).

The last row is the interesting one: additions that can cancel pay a
*condition number* built from the intervals of stage 3. When the enclosure of
the result contains zero the bound is infinite — no finite relative-error
bound exists there. NumFuzz's type system rejects such programs; here the
spelling simply loses to any bounded alternative, and if *nothing* is bounded
the split search takes over.

Soundness of the bound itself: interval endpoints are outward-rounded
(`math.nextafter`), and every error-bound formula is nudged up by a factor
`1 + 2⁻⁴⁵` (`up()`), which dwarfs the handful of roundings incurred computing
the bound. The idealizations, shared with NumFuzz: round-to-nearest doubles,
and no overflow or underflow in intermediate results.

## Comparing against the LLM mode

The predicted bounds are worst-case and directly comparable to FPTaylor's
relative-error bounds (both in ulps of `2⁻⁵²`); `uv run check.py` does that
comparison for you (see `summary.md`). To score against an egrammars LLM run,
the FPCore programs in `results.json` are exactly the format that repo's
`src/analysis/fptaylor_check.py` consumes.

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
