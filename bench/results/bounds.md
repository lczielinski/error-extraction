# Bounds: costex vs daisy vs fptaylor vs gappa

- daisy 7544e92-ff4e15a9, `--analysis=dataflow --rangeMethod=interval --errorMethod=affine`
- fptaylor 0.9.4+dev, `-v 0 -abs true -rel true`
- gappa 1.8.2, its defaults

## Summary

Every analyser bounds the same program, the seed.  Above 1x, our bound is tighter.

| Metric | vs | both bounded | we are tighter | looser | tie | only we bound it | only they do | their bound / ours |
|---|---|--:|--:|--:|--:|--:|--:|---|
| mu_abs | daisy | 361 | 357 | 3 | 1 | 4 | 0 | geomean 7.78x, median 2.22x, p10 1.46x, p90 4.38x |
| mu_abs | fptaylor | 362 | 111 | 250 | 1 | 3 | 0 | geomean 0.682x, median 0.839x, p10 0.494x, p90 1x |
| mu_abs | gappa | 364 | 337 | 21 | 6 | 1 | 6 | geomean 6.51x, median 1.49x, p10 1.06x, p90 3.5x |
| mu_rel | daisy | 260 | 260 | 0 | 0 | 20 | 0 | geomean 13.5x, median 7.37x, p10 2.55x, p90 68.3x |
| mu_rel | fptaylor | 277 | 125 | 151 | 1 | 3 | 10 | geomean 0.936x, median 0.979x, p10 0.552x, p90 1.17x |
| mu_rel | gappa | 269 | 262 | 6 | 1 | 11 | 2 | geomean 2.04x, median 1.8x, p10 1.26x, p90 2.45x |

## Coverage

| Analyser | seeds | bounded mu_abs | bounded mu_rel | bounded neither | why not |
|---|--:|--:|--:|--:|---|
| costex | 371 | 365 | 280 | 6 | &mdash; |
| daisy | 371 | 361 | 260 | 10 | 5x daisy.tools.DivisionByZeroException; 2x daisy.tools.OverflowException; 2x no bound in the output |
| fptaylor | 371 | 362 | 287 | 9 | 2x Potential exception detected: Division by zero at: (; 2x Potential exception detected: Overflow at: (rnd64((m; 1x num_of_float: inf |
| gappa | 371 | 370 | 271 | 1 | 1x the Gappa backend does not support PI or E |

## Every core

- sorted by how far our bound trails the tightest tool, worst first

| Core | Seed | mu_abs costex | mu_abs daisy | mu_abs fptaylor | mu_abs gappa | mu_rel costex | mu_rel daisy | mu_rel fptaylor | mu_rel gappa |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Kalman filter per x** | `(+ (+ x0 (+ x1 (* 0.5 (* dt (* dt x2))))) (* (/ (+ (+ (+ (* 1 (+ (+ (…` | 4.62e+03 | 8.41e+03 | 1.38e-05 | 0.00125 | &mdash; | &mdash; | &mdash; | &mdash; |
| **(x - 1) to (x - 20)** | `(* (* (* (* (* (* (* (* (* (* (* (* (* (* (* (* (* (* (* (- x 1) (- x…` | 3.71e+08 | 6.57e+08 | 39.8 | 6.45e+08 | &mdash; | &mdash; | &mdash; | &mdash; |
| **nonlin1** | `(/ z (+ z 1))` | 1.68e-13 | 1.14e-10 | 1.67e-16 | 0.999 | &mdash; | &mdash; | &mdash; | &mdash; |
| **intro-example** | `(/ t (+ t 1))` | 1.68e-13 | 1.14e-10 | 1.67e-16 | 0.999 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Kalman filter per P** | `(+ (+ (* (- 1 (/ (+ (+ (+ (* 1 (+ (+ (* 25 1) (* 0 dt)) (* 0 (* 0.5 (…` | 6.35e-13 | 5.89e-13 | 1.97e-14 | 2.04e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **turbine1** | `(- (- (+ 3 (/ 2 (* r r))) (/ (* (* 0.125 (- 3 (* 2 v))) (* (* (* w w)…` | 3.89e-14 | 8.65e-14 | 1.24e-14 | 8.4e-14 | 2.29e-14 | 5.58e-14 | 7.95e-16 | 4.99e-14 |
| **turbine3** | `(- (- (- 3 (/ 2 (* r r))) (/ (* (* 0.125 (+ 1 (* 2 v))) (* (* (* w w)…` | 3.43e-14 | 6.23e-14 | 6.93e-15 | 39.8 | 5.86e-14 | 1.34e-13 | 2.4e-15 | &mdash; |
| **Kalman filter per K** | `(/ (+ (+ (+ (* 1 (+ (+ (* 25 1) (* 0 dt)) (* 0 (* 0.5 (* dt dt))))) (…` | 6.86e-15 | 6.86e-15 | 2.86e-16 | 2.57e-15 | 3.36e-15 | 2.22e-14 | 3.12e-16 | 2.57e-15 |
| **Statistics.Distribution.Beta:$centropy from math-functions-0.1.5.2** | `(+ (- (- x (* (- y 1) z)) (* (- t 1) a)) (* (- (+ y t) 2) b))` | 1.13e-10 | 1.78e-10 | 1.13e-10 | 1.47e-10 | 1.92e-14 | 7.61e-14 | 1.02e-15 | 2.26e-14 |
| **From Warwick Tucker's Validated Numerics** | `(+ (+ (+ (* 333.75 (* (* (* (* (* 33096 33096) 33096) 33096) 33096) 3…` | 1.5e+22 | n/b | 6.51e+21 | 1.25e+21 | &mdash; | n/b | &mdash; | &mdash; |
| **test03_nonlin2** | `(/ (+ x y) (- x y))` | 3.11e-15 | 4.75e-14 | 3.47e-16 | 1.82 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Jmat.Real.dawson** | `(* (/ (+ (+ (+ (+ (+ 1 (* 0.1049934947 (* x x))) (* 0.0424060604 (* (…` | 6.29e-15 | 4.15e-14 | 7.63e-16 | 9.8e-15 | 2.67e-15 | 6.86e-13 | 1.43e-15 | 3.77e-15 |
| **Kahan p13 Example 1** | `(/ (+ 1 (* (/ (* 2 t) (+ 1 t)) (/ (* 2 t) (+ 1 t)))) (+ 2 (* (/ (* 2 …` | 2.3e-15 | 2.56e-15 | 3.07e-16 | 1.75e-15 | 1.15e-15 | 1.06e-14 | 4.64e-16 | 1.64e-15 |
| **Numeric.Signal.Multichannel:$cget from hsignal-0.2.7.1** | `(+ (* (/ x y) (- z t)) t)` | 2.04e-14 | 5.33e-14 | 1.73e-14 | 4.13e-14 | 1.78e-15 | 6.66e-15 | 2.66e-16 | 4.39e-15 |
| **Rosa's FloatVsDoubleBenchmark** | `(+ x1 (+ (+ (+ (+ (* (+ (* (* (* 2 x1) (/ (- (+ (* (* 3 x1) x1) (* 2 …` | 6.23e-12 | 1.2e-11 | 9.38e-13 | 27 | &mdash; | &mdash; | 2.13e-15 | &mdash; |
| **Numeric.SpecFunctions:logGamma from math-functions-0.1.5.2, C** | `(/ (* (- x 2) (+ (* (+ (* (+ (* (+ (* x 4.16438922228) 78.6994924154)…` | 2.66e-15 | 6.1e-15 | 4.16e-16 | 1.94 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.TwoD.Arc:arcBetween from diagrams-lib-1.3.0.3** | `(/ (- (* x x) (* (* y 4) y)) (+ (* x x) (* (* y 4) y)))` | 1.76e-15 | 7.08e-15 | 2.79e-16 | 9.7e-16 | 5.7e-16 | 3.07e-14 | 3.02e-16 | 9.84e-16 |
| **init-J** | `(/ (- (* E_var E_var) (* L H)) (+ (* E_var E_var) (* L H)))` | 1.76e-15 | 7.08e-15 | 2.8e-16 | 9.7e-16 | 5.7e-16 | 3.07e-14 | 3.01e-16 | 9.84e-16 |
| **Numeric.SpecFunctions:logGamma from math-functions-0.1.5.2, A** | `(+ (- (* x (- y 1)) (* y 0.5)) 0.918938533204673)` | 3.61e-15 | 6.49e-15 | 3.56e-15 | 4.56e-15 | 3.07e-15 | &mdash; | 5.09e-16 | &mdash; |
| **fma_test1** | `(+ (* (+ 1 (* t 2E-16)) (+ 1 (* t 2E-16))) (- -1 (* 2 (* t 2E-16))))` | 4.44e-16 | 4.44e-16 | 4.44e-16 | 8.33e-17 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rendering.Chart.Drawing:drawTextsR from Chart-1.5.3** | `(+ (* x y) (* (- x 1) z))` | 8.88e-15 | 2.31e-14 | 9.77e-15 | 1.33e-14 | 1.44e-15 | 5.77e-15 | 2.81e-16 | 2.2e-15 |
| **sum** | `(+ (+ (- (+ x0 x1) x2) (- (+ x1 x2) x0)) (- (+ x2 x0) x1))` | 3.33e-15 | 4e-15 | 2.22e-15 | 3.66e-15 | 2.55e-15 | &mdash; | 5.05e-16 | &mdash; |
| **test01_sum3** | `(+ (+ (- (+ x0 x1) x2) (- (+ x1 x2) x0)) (- (+ x2 x0) x1))` | 1.79e-06 | 2.15e-06 | 1.19e-06 | 1.97e-06 | 1.37e-06 | &mdash; | 2.71e-07 | &mdash; |
| **Diagrams.Color.HSV:lerp  from diagrams-contrib-1.3.0.5** | `(+ (* (- 1 x) y) (* x z))` | 1.51e-14 | 2.93e-14 | 8.44e-15 | 1.6e-14 | 1.11e-15 | 3.66e-15 | 2.79e-16 | 1.65e-15 |
| **turbine2** | `(- (- (* 6 v) (/ (* (* 0.5 v) (* (* (* w w) r) r)) (- 1 v))) 2.5)` | 4.89e-14 | 1.31e-13 | 1.25e-14 | 1.28e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:incompleteBetaApprox from math-functions-0.1.5.2, A** | `(/ (* x y) (* (* (+ x y) (+ x y)) (+ (+ x y) 1)))` | 8.88e-17 | 6.77e-16 | 2.29e-17 | 1.46e-16 | 8.78e-16 | 1.86e-13 | 8.52e-16 | 1.41e-15 |
| **Linear.Quaternion:$c/ from linear-1.19.1.3, C** | `(- (- (+ (* x y) (* y y)) (* y z)) (* y y))` | 7.99e-14 | 1.38e-13 | 5.06e-14 | 1.16e-13 | 1.28e-15 | &mdash; | 3.44e-16 | 1.67e-15 |
| **Linear.Quaternion:$c/ from linear-1.19.1.3, D** | `(- (+ (- (* x y) (* y y)) (* y y)) (* y z))` | 6.39e-14 | 1.27e-13 | 3.46e-14 | 1.02e-13 | 9.99e-16 | &mdash; | 2.79e-16 | 8.98e-15 |
| **Graphics.Rendering.Chart.Plot.Vectors:renderPlotVectors from Chart-1.5.3** | `(+ x (* (- 1 x) (- 1 y)))` | 1.78e-15 | 4.44e-15 | 2.16e-15 | 2.66e-15 | 9.99e-16 | 4.44e-15 | 2.95e-16 | 1.54e-15 |
| **carbonGas** | `(- (* (+ 35000000 (* (* 0.401 (/ 1000 v)) (/ 1000 v))) (- v (* 1000 0…` | 1.6e-08 | 3.89e-08 | 4.96e-09 | 2.61e-08 | 8.38e-16 | 1.85e-14 | 7.67e-16 | 9.96e-16 |
| **x_by_xy** | `(/ x (+ x y))` | 2.38e-07 | 1.04e-06 | 7.51e-08 | 1.73e-07 | 1.19e-07 | 8.34e-06 | 1.21e-07 | 2.38e-07 |
| **Rosa's Benchmark** | `(- (* 0.954929658551372 x) (* 0.12900613773279798 (* (* x x) x)))` | 7.84e-16 | 9.39e-16 | 4.71e-16 | 7.6e-16 | 1.64e-15 | &mdash; | 5.41e-16 | &mdash; |
| **Kahan p13 Example 2** | `(/ (+ 1 (* (- 2 (/ (/ 2 t) (+ 1 (/ 1 t)))) (- 2 (/ (/ 2 t) (+ 1 (/ 1 …` | 1.12e-15 | 1.31e-15 | 3.77e-16 | 2.61e-15 | 1.49e-15 | 3.86e-15 | 5.71e-16 | 2.84e-15 |
| **Linear.Matrix:det33 from linear-1.19.1.3** | `(+ (- (* x (- (* y z) (* t a))) (* b (- (* c z) (* i a)))) (* j (- (*…` | 5.92e-05 | 0.000119 | 4.77e-05 | 7.97e-05 | 1.1e-14 | 2.95e-14 | 3.7e-15 | 1.43e-14 |
| **Numeric.SpecFunctions:logGamma from math-functions-0.1.5.2, D** | `(+ x (/ (* y (+ (* (+ (* (+ (* (+ (* z 3.13060547623) 11.1667541262) …` | 3.46e-13 | 2.68e-12 | 1.17e-13 | 6.31e-13 | 2.07e-15 | 1.59e-12 | 1.68e-14 | 2.91e-15 |
| **Rectangular parallelepiped of dimension a×b×c** | `(* 2 (+ (+ (* 1 (/ 1 9)) (* (/ 1 9) (/ 1 9))) (* (/ 1 9) 1)))` | 7.42e-17 | n/b | 7.42e-17 | 2.65e-17 | 1.58e-16 | n/b | 1.58e-16 | 5.56e-17 |
| **seraz0-fc-a2** | `(* mult (/ (- (* h xj) (* s s)) (sqrt (+ (* xj xj) (* s s)))))` | 2.5e-13 | 5.99e-13 | 9.26e-14 | 4.86e-13 | 6.81e-16 | 2.06e-14 | 6.5e-16 | 1.15e-15 |
| **himmilbeau** | `(+ (* (- (+ (* x1 x1) x2) 11) (- (+ (* x1 x1) x2) 11)) (* (- (+ x1 (*…` | 1.56e-12 | 2.33e-12 | 5.9e-13 | 1e-12 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Trail:splitAtParam  from diagrams-lib-1.3.0.3, D** | `(- 1 (/ (* (- 1 x) y) (+ y 1)))` | 6.88e-16 | 1.47e-15 | 4.03e-16 | 1.6 | 5.77e-16 | 1.47e-15 | 2.19e-16 | 1.6 |
| **FastMath dist4** | `(- (+ (- (* d1 d2) (* d1 d3)) (* d4 d1)) (* d1 d1))` | 6.97e-14 | 1.47e-13 | 5.08e-14 | 8.86e-14 | 1.52e-15 | &mdash; | 5.79e-16 | 3.71e-15 |
| **Numeric.SpecFunctions:logGamma from math-functions-0.1.5.2, B** | `(+ x (/ (* y (+ (* (+ (* z 0.0692910599291889) 0.4917317610505968) z)…` | 2e-15 | 5.18e-15 | 7.74e-16 | 3.29e-15 | 9.26e-16 | 4.77e-15 | 4.22e-16 | 1.18e-15 |
| **Bouland and Aaronson, Equation (24)** | `(- (+ (* (+ (* a a) (* b b)) (+ (* a a) (* b b))) (* 4 (+ (* (* a a) …` | 3.84e-12 | 6.24e-12 | 3.26e-12 | 4.46e-12 | 1.79e-15 | 1.18e-14 | 7.02e-16 | 2.11e-15 |
| **test04_dqmom9** | `(+ 0 (+ (* (* (* w0 (- 0 m0)) (* -3 (* (* 1 (/ a0 w0)) (/ a0 w0)))) 1…` | 4.24e-05 | 2 | 1.73e-05 | 0.000114 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Colour.RGB:hslsv from colour-2.3.3, C** | `(/ (- x y) (- 2 (+ x y)))` | 1.06e-15 | 2.58e-15 | 4.45e-16 | 1.99e-15 | 5.18e-16 | 1.03e-14 | 4.48e-16 | 8.7e-16 |
| **Linear.Quaternion:$c/ from linear-1.19.1.3, B** | `(+ (- (- (* x y) (* y z)) (* y y)) (* y y))` | 1.01e-13 | 1.59e-13 | 7.19e-14 | 1.38e-13 | 1.07e-15 | &mdash; | 4.74e-16 | 1.38e-15 |
| **Statistics.Math.RootFinding:ridders from math-functions-0.1.5.2** | `(/ (* (* x y) z) (sqrt (- (* z z) (* t a))))` | 7.57e-11 | 2.05e-10 | 3.37e-11 | 1.37e-10 | 5.63e-16 | 2.5e-14 | 6.03e-16 | 1.02e-15 |
| **x / (x^2 + 1)** | `(/ x (+ (* x x) 1))` | 3.11e-16 | 9.55e-16 | 1.39e-16 | 5.44e-16 | 3.11e-16 | 4.77e-15 | 2.81e-16 | 6e-16 |
| **setup-t** | `(* (* es (* sa sa)) (* (- 2 es) (* rone_es rone_es)))` | 7.28e-11 | 1.66e-10 | 3.29e-11 | 8.73e-11 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Trail:splitAtParam  from diagrams-lib-1.3.0.3, B** | `(/ (* x y) (+ y 1))` | 9.33e-16 | 2.01e-15 | 4.32e-16 | 1.93e-15 | 3.33e-16 | 4.52e-15 | 3.36e-16 | 6.44e-16 |
| **From Rump in a 1983 paper** | `(+ (- (* 9 (* (* (* x x) x) x)) (* (* (* y y) y) y)) (* 2 (* y y)))` | 1.9e-12 | 3.72e-12 | 1.64e-12 | 2.14e-12 | 4.04e-15 | &mdash; | 1.9e-15 | &mdash; |
| **doppler2** | `(/ (* (- (+ 331.4 (* 0.6 T))) v) (* (+ (+ 331.4 (* 0.6 T)) u) (+ (+ 3…` | 3.89e-13 | 1.05e-12 | 1.84e-13 | 3.92e-13 | 1.46e-15 | 5.51e-11 | 8.97e-16 | 1.43e-15 |
| **Rosa's DopplerBench** | `(/ (* (- t1) v) (* (+ t1 u) (+ t1 u)))` | 4.49e-16 | 2.13e-15 | 2.14e-16 | 4.33e-16 | 5.55e-16 | 3.85e-14 | 5.61e-16 | 9.99e-16 |
| **Numeric.SpecFunctions:invIncompleteBetaWorker from math-functions-0.1.5.2, E** | `(+ (- 1 x) (* y (sqrt x)))` | 2.66e-15 | 4.59e-15 | 2.72e-15 | 3.85e-15 | 7.03e-16 | 1.53e-15 | 3.36e-16 | 1.1e-15 |
| **seraz0-fc-c1** | `(* mult (/ (* s (+ h xj)) (sqrt (+ (* xj xj) (* s s)))))` | 9.05e-14 | 2.54e-13 | 4.36e-14 | 1.58e-13 | 6.66e-16 | 2.62e-14 | 7.83e-16 | 1.11e-15 |
| **Given's Rotation SVD example** | `(sqrt (* 0.5 (+ 1 (/ x (sqrt (+ (* (* 4 p) p) (* x x)))))))` | 3.03e-16 | 7.28e-16 | 1.47e-16 | 3.89e-16 | 2.73e-16 | 8.56e-16 | 1.51e-16 | 3.46e-16 |
| **Complex division, real part** | `(/ (+ (* a c) (* b d)) (+ (* c c) (* d d)))` | 1.37e-16 | 5.49e-16 | 6.78e-17 | 2.36e-16 | 5.55e-16 | 3.51e-14 | 5.54e-16 | 9.99e-16 |
| **forward-half-diff** | `(* 0.5 (- W (/ 1 W)))` | 1.67e-16 | 3.33e-16 | 8.33e-17 | 1.94e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rasterific.CubicBezier:isSufficientlyFlat from Rasterific-0.6.1** | `(* (* x 16) x)` | 7.11e-15 | 2.13e-14 | 3.55e-15 | 1.07e-14 | 1.11e-16 | 1.33e-15 | 1.11e-16 | 3.33e-16 |
| **Diagrams.Solve.Polynomial:quadForm from diagrams-solve-0.1, C** | `(/ x (* y 2))` | 2.78e-17 | 1.11e-16 | 1.39e-17 | 6.94e-17 | 1.11e-16 | 1.78e-15 | 1.13e-16 | 3.33e-16 |
| **Numeric.Interval.Internal:scale from intervals-0.7.1, B** | `(/ (* x y) 2)` | 8.88e-16 | 3.55e-15 | 4.44e-16 | 3.11e-15 | 1.11e-16 | 1.78e-15 | 1.13e-16 | 4.44e-16 |
| **Numeric.Log:$cexpm1 from log-domain-0.10.2.1, A** | `(* (* x 2) x)` | 8.88e-16 | 2.66e-15 | 4.44e-16 | 1.33e-15 | 1.11e-16 | 1.33e-15 | 1.11e-16 | 3.33e-16 |
| **System.Random.MWC.Distributions:standard from mwc-random-0.13.3.2** | `(* 0.5 (- (* x x) y))` | 6.66e-16 | 1.33e-15 | 3.33e-16 | 7.77e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Linear.Projection:perspective from linear-1.19.1.3, B** | `(/ (* (* x 2) y) (- x y))` | 5.33e-15 | 1.78e-14 | 2.67e-15 | 1.24e-14 | 3.33e-16 | 1.56e-14 | 3.37e-16 | 8.33e-16 |
| **doppler1** | `(/ (* (- (+ 331.4 (* 0.6 T))) v) (* (+ (+ 331.4 (* 0.6 T)) u) (+ (+ 3…` | 1.96e-13 | 4.19e-13 | 9.91e-14 | 2.02e-13 | 1.33e-15 | 1.42e-11 | 9.69e-16 | 1.3e-15 |
| **Data.Number.Erf:$cinvnormcdf from erf-2.0.0.0, B** | `(- x (/ y (+ 1 (/ (* x y) 2))))` | 8.92e-16 | 4.4e-15 | 4.53e-16 | 2.09e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **sine** | `(- (+ (- x (/ (* (* x x) x) 6)) (/ (* (* (* (* x x) x) x) x) 120)) (/…` | 8.51e-16 | 1.13e-15 | 4.38e-16 | 1.46 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.TwoD.Arc:bezierFromSweepQ1 from diagrams-lib-1.3.0.3** | `(/ (* (- 1 x) (- 3 x)) (* y 3))` | 6.94e-17 | 1.5e-16 | 3.63e-17 | 0.167 | &mdash; | &mdash; | &mdash; | &mdash; |
| **sineOrder3** | `(- (* 0.954929658551372 x) (* 0.12900613773279798 (* (* x x) x)))` | 8.95e-16 | 1.45e-15 | 4.71e-16 | 8.89e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **AI.Clustering.Hierarchical.Internal:ward from clustering-0.2.1** | `(/ (- (+ (* (+ x y) z) (* (+ t y) a)) (* y b)) (+ (+ x t) y))` | 6.55e-13 | 1.26e-12 | 3.45e-13 | 7.33e-12 | 4.19e-15 | 1.57e-13 | 3.44e-15 | 7.73e-15 |
| **Diagrams.Trail:splitAtParam  from diagrams-lib-1.3.0.3, C** | `(/ (- x y) (- 1 y))` | 6.29e-16 | 1.35e-15 | 3.33e-16 | 7.5e-16 | 3.33e-16 | 4.74e-15 | 3.35e-16 | 6.48e-16 |
| **subtraction fraction** | `(/ (- (+ f n)) (- f n))` | 1.44e-15 | 4.76e-15 | 7.78e-16 | 2.05e-15 | 3.33e-16 | 6.66e-15 | 3.35e-16 | 7.22e-16 |
| **Linear.Projection:perspective from linear-1.19.1.3, A** | `(/ (+ x y) (- x y))` | 1.44e-15 | 4.76e-15 | 7.78e-16 | 2.05e-15 | 3.33e-16 | 6.66e-15 | 3.35e-16 | 7.22e-16 |
| **Data.Random.Distribution.T:$ccdf from random-fu-0.2.6.2** | `(/ (+ x y) (+ y y))` | 3.61e-16 | 7.49e-16 | 1.95e-16 | 3.89e-16 | 3.33e-16 | 2.4e-15 | 2.91e-16 | 5.43e-16 |
| **doppler3** | `(/ (* (- (+ 331.4 (* 0.6 T))) v) (* (+ (+ 331.4 (* 0.6 T)) u) (+ (+ 3…` | 1.05e-13 | 1.68e-13 | 5.7e-14 | 1.08e-13 | 1.2e-15 | 3.84e-13 | 7.36e-16 | 1.16e-15 |
| **Data.Colour.RGB:hslsv from colour-2.3.3, D** | `(/ (- x y) (+ x y))` | 3.55e-16 | 7.15e-16 | 1.95e-16 | 5.3e-16 | 3.33e-16 | 3.57e-15 | 3.36e-16 | 7.22e-16 |
| **init-p** | `(/ (- L H) (+ L H))` | 3.55e-16 | 7.15e-16 | 1.95e-16 | 5.3e-16 | 3.33e-16 | 3.57e-15 | 3.36e-16 | 7.22e-16 |
| **kepler1** | `(- (- (- (- (+ (+ (* (* x1 x4) (- (+ (+ (- x1) x2) x3) x4)) (* x2 (+ …` | 3.56e-13 | 4.81e-13 | 1.96e-13 | 5.38e-13 | &mdash; | &mdash; | 3.83e-15 | &mdash; |
| **Diagrams.Trail:splitAtParam  from diagrams-lib-1.3.0.3, A** | `(/ (+ x (/ (- (* y z) x) (- (* t z) x))) (+ x 1))` | 4.02e-16 | 6.38e-16 | 2.24e-16 | 5.06e-16 | 4.42e-16 | 1.89e-15 | 4.33e-16 | 6.79e-16 |
| **Octave 3.8, oct_fill_randg** | `(* (- a (/ 1 3)) (+ 1 (* (/ 1 (sqrt (* 9 (- a (/ 1 3))))) rand)))` | 3.84e-15 | 4.89e-15 | 2.15e-15 | 4.73e-15 | 7.31e-16 | 3.61e-15 | 4.82e-16 | 9.88e-16 |
| **Data.Colour.SRGB:invTransferFunction from colour-2.3.3** | `(/ (+ x y) (+ y 1))` | 6.22e-16 | 1.06e-15 | 3.49e-16 | 6.55e-16 | 3.33e-16 | 1.9e-15 | 3.36e-16 | 5.33e-16 |
| **Diagrams.Solve.Tridiagonal:solveTriDiagonal from diagrams-solve-0.1, A** | `(/ (- x (* y z)) (- t (* a z)))` | 3.22e-17 | 1.29e-16 | 1.82e-17 | 6.56e-17 | 5.62e-16 | 3.39e-14 | 7.66e-16 | 1.02e-15 |
| **Numeric.SpecFunctions:invErfc from math-functions-0.1.5.2, B** | `(* 0.70711 (- (/ (+ 2.30753 (* x 0.27061)) (+ 1 (* x (+ 0.99229 (* x …` | 7.74e-16 | 1.13e-15 | 4.41e-16 | 8.21e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Development.Shake.Progress:decay from shake-0.15.5** | `(/ (+ (* x y) (* z (- t a))) (+ y (* z (- b y))))` | 5.17e-16 | 1.76e-15 | 2.95e-16 | 1.19e-15 | 7.8e-16 | 5.68e-14 | 1.25e-15 | 1.4e-15 |
| **UniformSampleCone, z** | `(+ (- 1 ux) (* ux maxCos))` | 2.09e-07 | 3.58e-07 | 1.19e-07 | 2.09e-07 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Linear.Matrix:fromQuaternion from linear-1.19.1.3, A** | `(* 2 (- (* x x) (* x y)))` | 6.22e-15 | 1.24e-14 | 4e-15 | 8.44e-15 | 6.66e-16 | &mdash; | 3.92e-16 | 1.11e-15 |
| **Complex division, imag part** | `(/ (- (* b c) (* a d)) (+ (* c c) (* d d)))` | 2.96e-17 | 1.23e-16 | 1.76e-17 | 0.0882 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:invIncompleteBetaWorker from math-functions-0.1.5.2, H** | `(/ (- (* x x) 3) 6)` | 1.39e-16 | 2.87e-16 | 8.33e-17 | 0.5 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:invIncompleteGamma from math-functions-0.1.5.2, A** | `(- 1 (* x (+ 0.253 (* x 0.12))))` | 2.78e-16 | 4.4e-16 | 1.67e-16 | 2.88e-16 | 1.6e-14 | 3.15e-14 | 1.09e-14 | 1.67e-14 |
| **NMSE problem 3.3.1** | `(- (/ 1 (+ x 1)) (/ 1 x))` | 2.78e-16 | 4.44e-16 | 2.22e-16 | 3.33e-16 | 1.22e-15 | &mdash; | 7.36e-16 | 1.75e-15 |
| **2frac (problem 3.3.1)** | `(- (/ 1 (+ x 1)) (/ 1 x))` | 2.78e-16 | 4.44e-16 | 2.22e-16 | 3.33e-16 | 1.22e-15 | &mdash; | 7.36e-16 | 1.75e-15 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, A** | `(- (+ x y) (* x y))` | 3.55e-15 | 6e-15 | 2.22e-15 | 5e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Codec.Picture.Types:toneMapping from JuicyPixels-3.2.6.1** | `(/ (* x (+ (/ x y) 1)) (+ x 1))` | 5.55e-16 | 8.26e-16 | 3.52e-16 | 9.9e-16 | 4.81e-16 | 2.2e-15 | 4.23e-16 | 6.97e-16 |
| **verhulst** | `(/ (* 4 x) (+ 1 (/ x 1.11)))` | 2.78e-16 | 3.72e-16 | 1.79e-16 | 4.18e-16 | 2.63e-16 | 1.18e-15 | 2.41e-16 | 3.9e-16 |
| **Examples.Basics.BasicTests:f2 from sbv-4.4** | `(- (* x x) (* y y))` | 1.11e-14 | 2.62e-14 | 7.33e-15 | 1.49e-14 | 2.96e-16 | 2.18e-15 | 2.41e-16 | 6.11e-16 |
| **re_sqr** | `(- (* re re) (* im im))` | 1.11e-14 | 2.62e-14 | 7.33e-15 | 1.49e-14 | 2.96e-16 | 2.18e-15 | 2.41e-16 | 6.11e-16 |
| **Difference of squares** | `(- (* a a) (* b b))` | 1.11e-14 | 2.62e-14 | 7.33e-15 | 1.49e-14 | 2.96e-16 | 2.18e-15 | 2.41e-16 | 6.11e-16 |
| **_multiplyComplex, real part** | `(- (* x.re y.re) (* x.im y.im))` | 1.78e-13 | 4.19e-13 | 1.17e-13 | 2.38e-13 | 2.96e-16 | 2.18e-15 | 2.43e-16 | 6.11e-16 |
| **Numeric.SpecFunctions:invIncompleteGamma from math-functions-0.1.5.2, C** | `(- (/ (+ 2.30753 (* x 0.27061)) (+ 1 (* x (+ 0.99229 (* x 0.04481))))…` | 9.22e-16 | 1.43e-15 | 6.12e-16 | 1.05e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:invIncompleteBetaWorker from math-functions-0.1.5.2, D** | `(- x (/ (+ 2.30753 (* x 0.27061)) (+ 1 (* (+ 0.99229 (* x 0.04481)) x…` | 9.22e-16 | 1.43e-15 | 6.12e-16 | 1.05e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Linear.V3:cross from linear-1.19.1.3** | `(- (* x y) (* z t))` | 6.84e-13 | 1.6e-12 | 4.56e-13 | 9.12e-13 | 2.26e-16 | 1.58e-15 | 2.26e-16 | 4.52e-16 |
| **Graphics.Rasterific.QuadraticFormula:discriminant from Rasterific-0.6.1** | `(- (* x x) (* (* y 4) z))` | 1.71e-13 | 3.99e-13 | 1.14e-13 | 2.28e-13 | 2.26e-16 | 1.58e-15 | 2.26e-16 | 4.52e-16 |
| **Data.Random.Distribution.Normal:doubleStdNormalZ from random-fu-0.2.6.2** | `(- (+ x x) 1)` | 6.66e-16 | 1.11e-15 | 4.44e-16 | 4.44e-16 | 3.33e-16 | 1.11e-15 | 3.33e-16 | 4.44e-16 |
| **Diagrams.Solve.Tridiagonal:solveTriDiagonal from diagrams-solve-0.1, C** | `(- x (* y z))` | 4.26e-14 | 9.97e-14 | 2.84e-14 | 5.7e-14 | 2.26e-16 | 1.61e-15 | 2.25e-16 | 4.57e-16 |
| **Diagrams.Solve.Polynomial:quartForm  from diagrams-solve-0.1, D** | `(- (/ (* x y) 2) (/ z 8))` | 1.33e-15 | 4.88e-15 | 8.88e-16 | 4.22e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rasterific.Shading:$sradialGradientWithFocusShader from Rasterific-0.6.1** | `(- x (* y y))` | 1.07e-14 | 2.51e-14 | 7.11e-15 | 1.43e-14 | 2.38e-16 | 1.79e-15 | 2.25e-16 | 5e-16 |
| **Numeric.SpecFunctions:logGammaCorrection from math-functions-0.1.5.2** | `(- (* (* x x) 2) 1)` | 1.33e-15 | 3.11e-15 | 8.88e-16 | 1.78e-15 | 3.33e-16 | 3.11e-15 | 3.33e-16 | 7.77e-16 |
| **Data.Histogram.Bin.LogBinD:$cbinSizeN from histogram-fill-0.8.4.1** | `(- (* x y) x)` | 2.66e-15 | 6e-15 | 1.78e-15 | 3.66e-15 | 3.33e-16 | 3e-15 | 2.25e-16 | 5.92e-16 |
| **Data.Random.Dice:roll from dice-0.1** | `(- (* x x) 1)` | 6.66e-16 | 1.55e-15 | 4.44e-16 | 8.88e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Polynomial:quadForm from diagrams-solve-0.1, A** | `(- x (* (* y 4) z))` | 1.71e-13 | 3.98e-13 | 1.14e-13 | 2.27e-13 | 2.23e-16 | 1.57e-15 | 2.25e-16 | 4.47e-16 |
| **Data.Approximate.Numerics:blog from approximate-0.2.2.1** | `(/ (* 6 (- x 1)) (+ (+ x 1) (* 4 (sqrt x))))` | 4.07e-16 | 6.66e-16 | 2.73e-16 | 1 | &mdash; | &mdash; | &mdash; | &mdash; |
| **bug366, discussion (missed optimization)** | `(sqrt (- (* a a) (* b b)))` | 1.62e-15 | 4.23e-15 | 1.1e-15 | 2.59e-15 | 2.59e-16 | 1.22e-15 | 2.32e-16 | 4.18e-16 |
| **Linear.Matrix:det44 from linear-1.19.1.3** | `(+ (- (+ (+ (- (* (- (* x y) (* z t)) (- (* a b) (* c i))) (* (- (* x…` | 4.18e+13 | 9.46e+13 | 2.86e+13 | 5.5e+13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **(- (/ x0 (- 1 x1)) x0)** | `(- (/ x0 (- 1 x1)) x0)` | 3.52e-16 | 8.7e-16 | 3.33e-16 | 5.61e-16 | 2.24e-16 | 7.61e-16 | 1.58e-16 | 3.26e-16 |
| **Bouland and Aaronson, Equation (25)** | `(- (+ (* (+ (* a a) (* b b)) (+ (* a a) (* b b))) (* 4 (+ (* (* a a) …` | 3.97e-12 | 5.76e-12 | 2.8e-12 | 4.64e-12 | &mdash; | &mdash; | 2.56e-15 | &mdash; |
| **Data.Random.Distribution.Normal:normalTail from random-fu-0.2.6.2** | `(+ (+ (* x x) y) y)` | 3.11e-15 | 5.77e-15 | 2.89e-15 | 4.22e-15 | 2.59e-16 | 6.41e-16 | 1.83e-16 | 3.58e-16 |
| **Linear.Quaternion:$c/ from linear-1.19.1.3, E** | `(+ (+ (+ (* x x) (* y y)) (* y y)) (* y y))` | 5.73e-14 | 1.01e-13 | 4.64e-14 | 6.82e-14 | 4.14e-16 | 2.06e-15 | 2.94e-16 | 5.64e-16 |
| **Linear.Quaternion:$c/ from linear-1.19.1.3, A** | `(+ (+ (+ (* x y) (* z z)) (* z z)) (* z z))` | 9.11e-13 | 1.6e-12 | 7.4e-13 | 1.08e-12 | 4.13e-16 | 2.07e-15 | 2.96e-16 | 5.57e-16 |
| **Main:i from ** | `(+ (+ (+ (+ x x) x) x) x)` | 2.66e-15 | 3.77e-15 | 2.44e-15 | 2.55e-15 | 3.71e-16 | 7.55e-16 | 2.66e-16 | 4.22e-16 |
| **Data.Random.Distribution.Triangular:triangularCDF from random-fu-0.2.6.2, B** | `(/ x (* (- y z) (- t z)))` | 3.47e-18 | 4.73e-17 | 2.49e-18 | 8.24e-18 | 4.44e-16 | 1.48e-13 | 5.76e-16 | 1.11e-15 |
| **Diagrams.TwoD.Apollonian:initialConfig from diagrams-contrib-1.3.0.5, A** | `(/ (- (+ (* x x) (* y y)) (* z z)) (* y 2))` | 3.03e-14 | 8.85e-14 | 2.18e-14 | 1.04e-13 | 4.54e-16 | 7.53e-15 | 3.8e-16 | 8.85e-16 |
| **From Rump in a 1983 paper, rewritten** | `(- (* 9 (* (* (* x x) x) x)) (* (* y y) (- (* y y) 2)))` | 1.64e-12 | 3.49e-12 | 1.18e-12 | 2.1e-12 | 2.2e-15 | 4.37e-14 | 1.79e-15 | 3.61e-15 |
| **Linear.Matrix:fromQuaternion from linear-1.19.1.3, B** | `(* 2 (+ (* x x) (* x y)))` | 7.99e-15 | 1.69e-14 | 5.77e-15 | 1.02e-14 | 2.22e-16 | 1.69e-15 | 2.11e-16 | 4.44e-16 |
| **FastMath dist** | `(+ (* d1 d2) (* d1 d3))` | 1.6e-14 | 3.38e-14 | 1.15e-14 | 2.04e-14 | 2.22e-16 | 1.69e-15 | 2.11e-16 | 4.44e-16 |
| **Diagrams.Solve.Tridiagonal:solveCyclicTriDiagonal from diagrams-solve-0.1, B** | `(/ (+ x (/ (* y z) t)) (+ (+ a 1) (/ (* y b) t)))` | 1.25e-17 | 3.39e-17 | 9.08e-18 | 2.41e-17 | 7.03e-16 | 1.74e-14 | 1.97e-15 | 1.19e-15 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:tickPosition from plot-0.2.3.4** | `(+ x (* (- y x) (/ z t)))` | 1.28e-15 | 3.08e-15 | 1.08e-15 | 2.25e-15 | 3.84e-16 | 2.46e-15 | 2.81e-16 | 7.83e-16 |
| **delta4** | `(+ (- (+ (+ (- (* (- x2) x3) (* x1 x4)) (* x2 x5)) (* x3 x6)) (* x5 x…` | 7.87e-14 | 1.16e-13 | 5.77e-14 | 1.39e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.TwoD.Segment:bezierClip from diagrams-lib-1.3.0.3** | `(+ (* x y) (* z (- 1 y)))` | 4.44e-14 | 9.86e-14 | 4.35e-14 | 5.77e-14 | 5e-16 | 3.08e-15 | 3.68e-16 | 6.22e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, H** | `(+ (- x (/ y (* z 3))) (/ t (* (* z 3) y)))` | 5.69e-16 | 1.67e-15 | 5.03e-16 | 9.39e-16 | 3.83e-16 | 1.83e-15 | 2.83e-16 | 5.89e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisLine from plot-0.2.3.4, A** | `(+ x (* y (/ (- z t) (- z a))))` | 2.03e-15 | 4.39e-15 | 1.5e-15 | 3.76e-15 | 4.81e-16 | 3.49e-15 | 4.93e-16 | 9.07e-16 |
| **Linear.Projection:inverseInfinitePerspective from linear-1.19.1.3** | `(* (- (* x y) (* z y)) t)` | 7.5e-12 | 1.85e-11 | 5.57e-12 | 1.12e-11 | 3.97e-16 | 6.01e-15 | 3.51e-16 | 7.61e-16 |
| **Graphics.Rasterific.Linear:$cquadrance from Rasterific-0.6.1** | `(+ (* x x) (* y y))` | 1.47e-14 | 2.98e-14 | 1.09e-14 | 1.84e-14 | 2.22e-16 | 1.75e-15 | 2.19e-16 | 4.44e-16 |
| **modulus_sqr** | `(+ (* re re) (* im im))` | 1.47e-14 | 2.98e-14 | 1.09e-14 | 1.84e-14 | 2.22e-16 | 1.75e-15 | 2.19e-16 | 4.44e-16 |
| **FastMath test3** | `(+ (+ (* d1 3) (* d1 d2)) (* d1 d3))` | 1.82e-14 | 3.66e-14 | 1.38e-14 | 2.3e-14 | 3.12e-16 | 1.59e-15 | 2.32e-16 | 4.77e-16 |
| **Examples.Basics.ProofTests:f4 from sbv-4.4** | `(+ (+ (* x x) (* (* x 2) y)) (* y y))` | 2.18e-14 | 4.4e-14 | 1.62e-14 | 2.73e-14 | 3.15e-16 | 1.76e-15 | 2.58e-16 | 5.06e-16 |
| **Data.Colour.Matrix:inverse from colour-2.3.3, B** | `(/ (- (* x y) (* z t)) a)` | 3.56e-15 | 1.07e-14 | 2.67e-15 | 9.89e-15 | 3.37e-16 | 5.42e-15 | 3.46e-16 | 6.74e-16 |
| **Linear.V2:$cdot from linear-1.19.1.3, A** | `(+ (* x y) (* z t))` | 9.11e-13 | 1.82e-12 | 6.83e-13 | 1.14e-12 | 2.22e-16 | 1.77e-15 | 2.25e-16 | 4.44e-16 |
| **Diagrams.Solve.Polynomial:quartForm  from diagrams-solve-0.1, C** | `(+ (- (+ (* x y) (/ (* z t) 16)) (/ (* a b) 4)) c)` | 5.83e-11 | 1.47e-10 | 4.37e-11 | 1.32e-10 | 3.67e-16 | 2.57e-15 | 3.64e-16 | 7.58e-16 |
| **Linear.V3:$cdot from linear-1.19.1.3, B** | `(+ (+ (* x y) (* z t)) (* a b))` | 2.34e-10 | 4.67e-10 | 1.75e-10 | 2.92e-10 | 2.24e-16 | 1.78e-15 | 2.25e-16 | 4.46e-16 |
| **Linear.V4:$cdot from linear-1.19.1.3, C** | `(+ (+ (+ (* x y) (* z t)) (* a b)) (* c i))` | 5.98e-08 | 1.2e-07 | 4.49e-08 | 7.48e-08 | 2.24e-16 | 1.78e-15 | 2.25e-16 | 4.46e-16 |
| **Data.Colour.RGBSpace.HSV:hsv from colour-2.3.3, I** | `(* x (- 1 (* y z)))` | 1.14e-13 | 2.84e-13 | 8.53e-14 | 1.7e-13 | 3.35e-16 | 4.51e-15 | 3.37e-16 | 6.71e-16 |
| **_multiplyComplex, imaginary part** | `(+ (* x.re y.im) (* x.im y.re))` | 1.14e-13 | 2.27e-13 | 8.53e-14 | 1.14e-13 | 2.22e-16 | 1.78e-15 | 2.37e-16 | 4.44e-16 |
| **Numeric.SpecFunctions:log1p from math-functions-0.1.5.2, A** | `(* x (- 1 (* x y)))` | 7.11e-15 | 1.75e-14 | 5.33e-15 | 1.05e-14 | 3.7e-16 | 5.85e-15 | 3.38e-16 | 7.77e-16 |
| **Numeric.Integration.TanhSinh:simpson  from integration-0.2.1** | `(* x (+ y y))` | 7.11e-15 | 1.42e-14 | 5.33e-15 | 7.11e-15 | 2.22e-16 | 1.78e-15 | 2.24e-16 | 4.44e-16 |
| **im_sqr** | `(+ (* re im) (* im re))` | 7.11e-15 | 1.42e-14 | 5.33e-15 | 7.11e-15 | 2.22e-16 | 1.78e-15 | 2.25e-16 | 4.44e-16 |
| **Main:bigenough1 from B** | `(+ x (* x x))` | 8.88e-16 | 2e-15 | 6.66e-16 | 1.22e-15 | 2.04e-16 | 9.99e-16 | 1.69e-16 | 3.7e-16 |
| **Graphics.Rasterific.Shading:$sradialGradientWithFocusShader from Rasterific-0.6.1, A** | `(+ (* x x) 1)` | 8.88e-16 | 1.78e-15 | 6.66e-16 | 1.11e-15 | 2e-16 | 8.88e-16 | 1.68e-16 | 3.77e-16 |
| **Expression 2, p15** | `(+ x (* x x))` | 8.88e-16 | 2e-15 | 6.66e-16 | 1.22e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Tridiagonal:solveCyclicTriDiagonal from diagrams-solve-0.1, A** | `(/ (* x y) z)` | 2.22e-16 | 6.66e-16 | 1.67e-16 | 5e-16 | 2.22e-16 | 5.33e-15 | 2.25e-16 | 5.55e-16 |
| **Diagrams.Segment:$catParam from diagrams-lib-1.3.0.3, C** | `(* (* x x) x)` | 1.78e-15 | 4.44e-15 | 1.33e-15 | 2.22e-15 | 2.22e-16 | 4.44e-15 | 2.23e-16 | 5.55e-16 |
| **math.cube on real** | `(* (* x x) x)` | 1.78e-15 | 4.44e-15 | 1.33e-15 | 2.22e-15 | 2.22e-16 | 4.44e-15 | 2.23e-16 | 5.55e-16 |
| **setup-xj** | `(* one_es (* one_es one_es))` | 1.78e-15 | 4.44e-15 | 1.33e-15 | 2.22e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.HyperLogLog.Config:hll from hyperloglog-0.3.4** | `(* (* x y) y)` | 2.84e-14 | 7.11e-14 | 2.13e-14 | 3.55e-14 | 2.22e-16 | 4.44e-15 | 2.24e-16 | 5.55e-16 |
| **semi_latus_rectum** | `(* a (- 1 (* e e)))` | 2.84e-14 | 7.08e-14 | 2.13e-14 | 4.25e-14 | 3.4e-16 | 4.72e-15 | 3.37e-16 | 6.88e-16 |
| **Diagrams.Solve.Polynomial:quartForm  from diagrams-solve-0.1, B** | `(+ (- (* (/ 1 8) x) (/ (* y z) 2)) t)` | 2.84e-14 | 8.53e-14 | 2.13e-14 | 7.11e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.TwoD.Apollonian:initialConfig from diagrams-contrib-1.3.0.5, B** | `(* x (sqrt (- (* y y) (* z z))))` | 6.6e-14 | 1.78e-13 | 4.95e-14 | 1.11e-13 | 3.7e-16 | 3.2e-15 | 3.44e-16 | 6.4e-16 |
| **kepler2** | `(- (- (- (- (+ (+ (* (* x1 x4) (+ (+ (- (+ (+ (- x1) x2) x3) x4) x5) …` | 1.95e-12 | 2.46e-12 | 1.47e-12 | 2.88e-12 | &mdash; | &mdash; | 1.68e-14 | &mdash; |
| **delta** | `(+ (+ (+ (+ (+ (+ (* (* x1 x4) (+ (+ (- (+ (+ (- x1) x2) x3) x4) x5) …` | 1.95e-12 | 2.35e-12 | 1.47e-12 | 2.76e-12 | &mdash; | &mdash; | 1.52e-14 | &mdash; |
| **Diagrams.TwoD.Apollonian:descartes from diagrams-contrib-1.3.0.5** | `(* 2 (sqrt (+ (+ (* x y) (* x z)) (* y z))))` | 9.27e-15 | 1.96e-14 | 7.01e-15 | 1.25e-14 | 2.67e-16 | 1.07e-15 | 2.2e-16 | 3.56e-16 |
| **FastMath dist3** | `(+ (+ (* d1 d2) (* (+ d3 5) d1)) (* d1 32))` | 3.73e-14 | 6.33e-14 | 3.64e-14 | 4.94e-14 | 3.71e-16 | 1.11e-15 | 2.81e-16 | 4.61e-16 |
| **Numeric.Log:$clog1p from log-domain-0.10.2.1, A** | `(+ (+ (* x 2) (* x x)) (* y y))` | 1.55e-14 | 3.11e-14 | 1.18e-14 | 1.91e-14 | 2.57e-16 | 1.64e-15 | 2.13e-16 | 4.44e-16 |
| **Data.Histogram.Bin.BinF:$cfromIndex from histogram-fill-0.8.4.1** | `(+ (+ (/ x 2) (* y x)) z)` | 7.11e-15 | 1.44e-14 | 6.22e-15 | 9.94e-15 | 2.58e-16 | 7.04e-16 | 1.96e-16 | 3.92e-16 |
| **test02_sum8** | `(+ (+ (+ (+ (+ (+ (+ x0 x1) x2) x3) x4) x5) x6) x7)` | 6.22e-15 | 7.99e-15 | 6e-15 | 5.55e-15 | 6.08e-16 | 9.99e-16 | 4.62e-16 | 6.68e-16 |
| **Linear.Quaternion:$clog from linear-1.19.1.3** | `(sqrt (+ (* x x) y))` | 5.2e-16 | 9.17e-16 | 4.23e-16 | 6.69e-16 | 2.04e-16 | 4.1e-16 | 1.55e-16 | 2.68e-16 |
| **Crypto.Random.Test:calculate from crypto-random-0.0.9** | `(+ x (/ (* y y) z))` | 1.33e-15 | 3.33e-15 | 1.11e-15 | 2.55e-15 | 2.96e-16 | 2.22e-15 | 2.25e-16 | 5.77e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Legend:renderLegendOutside from plot-0.2.3.4, C** | `(+ (* x (+ y z)) (* z 5))` | 4.26e-14 | 7.82e-14 | 4.26e-14 | 6.04e-14 | 2.96e-16 | 7.82e-16 | 2.25e-16 | 4.44e-16 |
| **forward-half-sum** | `(* 0.5 (+ W (/ 1 W)))` | 1.67e-16 | 1.67e-16 | 1.39e-16 | 2.5e-16 | 1.85e-16 | 2.22e-16 | 1.41e-16 | 2.78e-16 |
| **test05_nonlin1, test2** | `(/ 1 (+ x 1))` | 8.33e-17 | 1.39e-16 | 8.33e-17 | 1.11e-16 | 2.22e-16 | 4.16e-16 | 1.69e-16 | 2.5e-16 |
| **NMSE example 3.1** | `(- (sqrt (+ x 1)) (sqrt x))` | 4.29e-16 | 1.05e-08 | 3.28e-16 | 1.41 | 1.11e-15 | &mdash; | 9.95e-16 | &mdash; |
| **Statistics.Distribution.Binomial:$cvariance from math-functions-0.1.5.2** | `(* (* x y) (- 1 y))` | 2.66e-14 | 6.57e-14 | 2.04e-14 | 3.29e-14 | 3.33e-16 | 5.48e-15 | 3.36e-16 | 5.92e-16 |
| **Numeric.Log:$cexpm1 from log-domain-0.10.2.1, B** | `(+ (+ (* x y) x) y)` | 5.33e-15 | 9.99e-15 | 4.44e-15 | 6.77e-15 | 2.94e-16 | 1.11e-15 | 2.25e-16 | 4.42e-16 |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, D** | `(+ x (/ (* y (- z x)) t))` | 1.11e-15 | 3.06e-15 | 1.11e-15 | 3.02e-15 | 3.87e-16 | 2.13e-15 | 2.97e-16 | 6.82e-16 |
| **AI.Clustering.Hierarchical.Internal:average from clustering-0.2.1, A** | `(/ x (+ x y))` | 7.22e-17 | 2.05e-16 | 5.56e-17 | 1.39e-16 | 2.22e-16 | 2.05e-15 | 2.24e-16 | 4.44e-16 |
| **AI.Clustering.Hierarchical.Internal:average from clustering-0.2.1, B** | `(/ x (+ y x))` | 7.22e-17 | 2.05e-16 | 5.56e-17 | 1.39e-16 | 2.22e-16 | 2.05e-15 | 2.24e-16 | 4.44e-16 |
| **Numeric.Histogram:binBounds from Chart-1.5.3** | `(+ x (/ (* (- y x) z) t))` | 1.11e-15 | 2.93e-15 | 1.11e-15 | 3.3e-15 | 3.84e-16 | 2.34e-15 | 2.98e-16 | 7.83e-16 |
| **Development.Shake.Progress:message from shake-0.15.5** | `(/ (* x 100) (+ x y))` | 1.08e-14 | 2.42e-14 | 8.47e-15 | 2.13e-14 | 3.33e-16 | 2.42e-15 | 3.36e-16 | 5.55e-16 |
| **Expression 3, p15** | `(+ (* x (* x x)) (* x x))` | 3.11e-15 | 6.66e-15 | 2.44e-15 | 3.77e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Rump's example, from C program** | `(+ (+ (+ (* 333.75 (* (* (* b b) (* b b)) (* b b))) (* (* a a) (- (- …` | 1.75e-07 | 3.14e-07 | 1.38e-07 | 1.85e-07 | &mdash; | &mdash; | 1.01e-15 | &mdash; |
| **Diagrams.Tangent:$catParam from diagrams-lib-1.3.0.3, E** | `(* (* 3 (- 2 (* x 3))) x)` | 8.88e-15 | 1.55e-14 | 8.88e-15 | 9.55e-15 | 6.66e-16 | 5.18e-15 | 5.25e-16 | 9.99e-16 |
| **Language.Haskell.HsColour.ColourHighlight:unbase from hscolour-1.23** | `(+ (* (+ (* x y) z) y) t)` | 1.28e-13 | 2.42e-13 | 1.21e-13 | 1.49e-13 | 3.7e-16 | 1.68e-15 | 2.92e-16 | 6.03e-16 |
| **sqroot** | `(- (+ (- (+ 1 (* 0.5 x)) (* (* 0.125 x) x)) (* (* (* 0.0625 x) x) x))…` | 5.62e-16 | 5.71e-16 | 4.86e-16 | 5.71e-16 | 5.62e-16 | 6.83e-16 | 4.44e-16 | 6.61e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisTick from plot-0.2.3.4, B** | `(- (+ x y) (/ (* (- z t) y) (- a t)))` | 4.77e-15 | 1.24e-14 | 4.77e-15 | 1.07e-14 | 4.57e-16 | 2.35e-15 | 3.61e-16 | 8.51e-16 |
| **Data.Colour.Matrix:determinant from colour-2.3.3, A** | `(+ (- (* x (- (* y z) (* t a))) (* b (- (* c z) (* t i)))) (* j (- (*…` | 0.000159 | 0.00035 | 0.000126 | 0.000222 | 5.36e-16 | 6.7e-15 | 1.2e-15 | 9.59e-16 |
| **kepler0** | `(+ (- (- (+ (* x2 x5) (* x3 x6)) (* x2 x3)) (* x5 x6)) (* x1 (+ (+ (-…` | 7.34e-14 | 1.04e-13 | 5.85e-14 | 1.23e-13 | &mdash; | &mdash; | 1.21e-15 | &mdash; |
| **Kahan p13 Example 3** | `(- 1 (/ 1 (+ 2 (* (- 2 (/ (/ 2 t) (+ 1 (/ 1 t)))) (- 2 (/ (/ 2 t) (+ …` | 2.68e-16 | 6.28e-16 | 2.14e-16 | 5.24e-16 | 4.02e-16 | 1.06e-15 | 3.22e-16 | 8.87e-16 |
| **Rump's example revisited for floating point** | `(+ (+ (+ (* (- 333.75 (* a a)) (* (* (* b b) (* b b)) (* b b))) (* (*…` | 1.81e-07 | 3.21e-07 | 1.45e-07 | 1.91e-07 | &mdash; | &mdash; | 1.07e-15 | &mdash; |
| **clenshaw-final-real** | `(- (* (* sin_arg_r cosh_arg_i) hr) (* (* cos_arg_r sinh_arg_i) hi))` | 2.33e-09 | 5.13e-09 | 1.86e-09 | 2.8e-09 | 3.37e-16 | 4.93e-15 | 4.32e-16 | 6.73e-16 |
| **Graphics.Rasterific.Shading:$sradialGradientWithFocusShader from Rasterific-0.6.1, B** | `(- (* x x) (* (* y 4) (- (* z z) t)))` | 9.1e-12 | 2.02e-11 | 7.28e-12 | 1.28e-11 | 5.56e-16 | 9.9e-15 | 5.6e-16 | 1.17e-15 |
| **Graphics.Rendering.Chart.Plot.Pie:renderPie from Chart-1.5.3** | `(- (+ x y) x)` | 1.78e-15 | 2.66e-15 | 1.78e-15 | 2.44e-15 | 2.78e-16 | 8.88e-16 | 2.24e-16 | 4.81e-16 |
| **Data.Array.Repa.Algorithms.Pixel:doubleRmsOfRGB8 from repa-algorithms-3.4.0.1** | `(sqrt (/ (+ (+ (* x x) (* y y)) (* z z)) 3))` | 5.22e-15 | 1.17e-14 | 4.21e-15 | 7.3e-15 | 2.91e-16 | 1.23e-15 | 2.5e-16 | 4.01e-16 |
| **An eigenvalue calculation from TNG** | `(- (sqrt (+ (* (+ a d) (+ a d)) (* (- b c) (- b c)))) (sqrt (+ (* (- …` | 9.46e-14 | 1.49e-13 | 7.65e-14 | 1.22e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **triangle** | `(sqrt (* (* (* (/ (+ (+ a b) c) 2) (- (/ (+ (+ a b) c) 2) a)) (- (/ (…` | 3.01e-14 | 6.35e-14 | 2.44e-14 | 5.97e-14 | 3.83e-15 | 1.06e-14 | 3.9e-15 | 7.49e-15 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, G** | `(* (/ 1 2) (+ x y))` | 8.88e-16 | 9.99e-16 | 8.88e-16 | 7.22e-16 | 2.22e-16 | 4e-16 | 2.24e-16 | 2.22e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisTicks from plot-0.2.3.4, A** | `(+ x (/ (* y (- z t)) (- z a)))` | 1.84e-15 | 4.21e-15 | 1.5e-15 | 4.2e-15 | 4.81e-16 | 3.35e-15 | 4.91e-16 | 9.07e-16 |
| **bspline3** | `(/ (- (* (* u u) u)) 6)` | 5.09e-17 | 1.06e-16 | 4.16e-17 | 0.167 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.TwoD.Segment.Bernstein:evaluateBernstein from diagrams-lib-1.3.0.3** | `(/ (* x (+ (- y z) 1)) z)` | 7.54e-16 | 2.07e-15 | 6.19e-16 | 3.22e-15 | 4.6e-16 | 9.45e-15 | 4.48e-16 | 9.99e-16 |
| **matrixDeterminant** | `(- (+ (+ (* (* a e) i) (* (* b f) g)) (* (* c d) h)) (+ (+ (* (* c e)…` | 1.9e-12 | 3.5e-12 | 1.56e-12 | 3.5e-12 | &mdash; | &mdash; | &mdash; | &mdash; |
| **matrixDeterminant2** | `(- (+ (* a (* e i)) (+ (* g (* b f)) (* c (* d h)))) (+ (* e (* c g))…` | 1.9e-12 | 3.5e-12 | 1.56e-12 | 3.5e-12 | &mdash; | &mdash; | &mdash; | &mdash; |
| **sqrt_add** | `(/ 1 (+ (sqrt (+ x 1)) (sqrt x)))` | 1.42e-16 | 1.3e-14 | 1.17e-16 | 1.65e-16 | 3.88e-16 | 8.24e-13 | 3.33e-16 | 4.43e-16 |
| **FastMath test2** | `(+ (+ (* d1 10) (* d1 d2)) (* d1 20))` | 1.78e-14 | 2.8e-14 | 1.69e-14 | 2.2e-14 | 3.04e-16 | 8.23e-16 | 2.52e-16 | 4.09e-16 |
| **Numeric.Log:$clog1p from log-domain-0.10.2.1, B** | `(/ x (+ 1 (sqrt (+ x 1))))` | 1.97e-16 | 2.75e-16 | 1.64e-16 | 3.02e-16 | 2.82e-16 | 7.52e-16 | 2.76e-16 | 4.09e-16 |
| **inverse-Up** | `(/ (+ (* Vp cosgam) (* Sp singam)) Tp)` | 1.37e-12 | 3.22e-12 | 1.14e-12 | 2.76e-12 | 3.33e-16 | 6.19e-15 | 3.97e-16 | 6.66e-16 |
| **clenshaw-final-imag** | `(+ (* (* sin_arg_r cosh_arg_i) hi) (* (* cos_arg_r sinh_arg_i) hr))` | 7.06e-10 | 1.42e-09 | 5.88e-10 | 8.24e-10 | 3.33e-16 | 5.32e-15 | 4.13e-16 | 6.66e-16 |
| **Graphics.Rasterific.CubicBezier:cachedBezierAt from Rasterific-0.6.1** | `(+ (+ (+ x (* y z)) (* t a)) (* (* a z) b))` | 1.12e-08 | 2.24e-08 | 9.32e-09 | 1.31e-08 | 3.33e-16 | 5.32e-15 | 4.13e-16 | 6.66e-16 |
| **Quotient of products** | `(/ (* a1 a2) (* b1 b2))` | 5.2e-18 | 2.78e-17 | 4.34e-18 | 1.13e-17 | 3.33e-16 | 2.84e-14 | 4.36e-16 | 7.77e-16 |
| **Numeric.Integration.TanhSinh:everywhere from integration-0.2.1** | `(* x (+ 1 (* y y)))` | 4.26e-14 | 8.55e-14 | 3.55e-14 | 5.7e-14 | 3.31e-16 | 5.03e-15 | 3.29e-16 | 6.61e-16 |
| **ab-angle->ABCF D** | `(- (* (* (* a a) b) b))` | 8.53e-14 | 1.99e-13 | 7.11e-14 | 9.95e-14 | 3.33e-16 | 1.24e-14 | 3.36e-16 | 7.77e-16 |
| **Statistics.Sample:robustSumVarWeighted from math-functions-0.1.5.2** | `(+ x (* (* y z) z))` | 2.73e-12 | 5.46e-12 | 2.27e-12 | 3.18e-12 | 3.33e-16 | 5.32e-15 | 3.36e-16 | 6.66e-16 |
| **FastMath repmul** | `(* (* (* d1 d1) d1) d1)` | 5.33e-15 | 1.24e-14 | 4.44e-15 | 6.22e-15 | 3.33e-16 | 1.24e-14 | 3.36e-16 | 7.77e-16 |
| **angular_momentum** | `(sqrt (* mu p))` | 6.66e-16 | 1.78e-15 | 5.55e-16 | 8.88e-16 | 1.67e-16 | 8.88e-16 | 1.67e-16 | 2.79e-16 |
| **Numeric.Interval.Internal:bisect from intervals-0.7.1, A** | `(+ x (/ (- y x) 2))` | 6.66e-16 | 1.44e-15 | 6.66e-16 | 2.14e-15 | 2.02e-16 | 7.22e-16 | 1.69e-16 | 5.24e-16 |
| **FRP.Yampa.Vector3:vector3Rho from Yampa-0.10.2** | `(sqrt (+ (+ (* x x) (* y y)) (* z z)))` | 7.68e-15 | 1.82e-14 | 6.44e-15 | 1.13e-14 | 2.36e-16 | 1.1e-15 | 2.18e-16 | 3.45e-16 |
| **Data.Array.Repa.Algorithms.ColorRamp:rampColorHotToCold from repa-algorithms-3.4.0.1, B** | `(/ (* 4 (- (- x y) (* z 0.5))) z)` | 7.77e-16 | 2.33e-15 | 7.16e-16 | 2.81e-15 | 2.66e-16 | 1.87e-15 | 2.24e-16 | 5.22e-16 |
| **Bouland and Aaronson, Equation (26)** | `(- (+ (* (+ (* a a) (* b b)) (+ (* a a) (* b b))) (* 4 (* b b))) 1)` | 3.39e-12 | 5.5e-12 | 2.86e-12 | 3.91e-12 | 7.73e-16 | 1.56e-14 | 6.87e-16 | 1.19e-15 |
| **Graphics.Rendering.Chart.Backend.Diagrams:calcFontMetrics from Chart-diagrams-1.5.1, A** | `(/ (+ x y) (- 1 (/ y z)))` | 7.99e-15 | 1.69e-14 | 6.88e-15 | 1.4e-14 | 4.44e-16 | 2.95e-15 | 3.76e-16 | 7.22e-16 |
| **ENA, Section 1.4, Exercise 4b, n=5** | `(- (* (* (* (* (+ x eps) (+ x eps)) (+ x eps)) (+ x eps)) (+ x eps)) …` | 1.03e+30 | 1.62e+30 | 8.74e+29 | 1.62e+30 | &mdash; | &mdash; | &mdash; | &mdash; |
| **floudas1** | `(- (- (- (- (- (* -25 (* (- x1 2) (- x1 2))) (* (- x2 2) (- x2 2))) (…` | 3.35e-13 | 4.49e-13 | 2.85e-13 | 3.75e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **B-delta2** | `(+ (* delta (+ (* delta d2u_ddelta2) du_ddelta)) (* (- (+ (* delta du…` | 3.62e-12 | 5.97e-12 | 3.09e-12 | 4.26e-12 | 7.71e-16 | 1.3e-14 | 9.65e-16 | 1.21e-15 |
| **sqrt A (should all be same)** | `(sqrt (+ (* x x) (* x x)))` | 5.36e-16 | 1.48e-15 | 4.58e-16 | 8.5e-16 | 2.22e-16 | 1.05e-15 | 2.22e-16 | 3.35e-16 |
| **sqrt E (should all be same)** | `(sqrt (+ (* x x) (* x x)))` | 5.36e-16 | 1.48e-15 | 4.58e-16 | 8.5e-16 | 2.22e-16 | 1.05e-15 | 2.22e-16 | 3.35e-16 |
| **Radioactive exchange between two surfaces** | `(- (* (* (* x x) x) x) (* (* (* y y) y) y))` | 1.6e-12 | 3.42e-12 | 1.37e-12 | 1.83e-12 | 4.88e-16 | 1.43e-14 | 4.7e-16 | 9.66e-16 |
| **setup-w** | `(- (* (* (- 1 (* es (* ca ca))) rone_es) (* (- 1 (* es (* ca ca))) ro…` | 1.3e-08 | 2.77e-08 | 1.11e-08 | 1.66e-08 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, C** | `(/ x (* y 3))` | 3.24e-17 | 9.41e-17 | 2.78e-17 | 6.94e-17 | 2.22e-16 | 2.26e-15 | 2.24e-16 | 4.44e-16 |
| **Data.Colour.SRGB:transferFunction from colour-2.3.3** | `(- (* (+ x 1) y) x)` | 5.33e-15 | 9.55e-15 | 5.33e-15 | 7.66e-15 | 4.07e-16 | 1.59e-15 | 3.5e-16 | 6.48e-16 |
| **Expression 1, p15** | `(+ (+ (+ (+ e d) c) b) a)` | 1.42e-14 | 2.11e-14 | 1.42e-14 | 1.77e-14 | 4.24e-16 | 6.8e-16 | 3.66e-16 | 5.34e-16 |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, A** | `(sqrt (+ x y))` | 3.98e-16 | 6.69e-16 | 3.82e-16 | 5.45e-16 | 1.67e-16 | 2.99e-16 | 1.44e-16 | 2.12e-16 |
| **Linear.Projection:inversePerspective from linear-1.19.1.3, B** | `(/ (- x y) (* (* x 2) y))` | 1.25e-16 | 1.28e-15 | 1.08e-16 | 6.87e-16 | 3.33e-16 | 2.04e-14 | 3.36e-16 | 8.33e-16 |
| **Statistics.Sample:$swelfordMean from math-functions-0.1.5.2** | `(+ x (/ (- y x) z))` | 2.78e-16 | 6.45e-16 | 2.78e-16 | 5.79e-16 | 1.63e-16 | 6.07e-16 | 1.41e-16 | 3.74e-16 |
| **B-tau3** | `(+ (* tau (+ (* tau (+ (* tau d3u_dtau3) (* 2 d2u_dtau2))) (* (* 2 (+…` | 4.89e-10 | 7.85e-10 | 4.23e-10 | 5.71e-10 | 1.34e-15 | 6.62e-14 | 7.8e-15 | 2.01e-15 |
| **Data.Array.Repa.Algorithms.ColorRamp:rampColorHotToCold from repa-algorithms-3.4.0.1, C** | `(+ 1 (/ (* 4 (- (+ x (* y 0.25)) z)) y))` | 5.77e-15 | 1.64e-14 | 5.55e-15 | 1.58e-14 | 4.22e-16 | 3.29e-15 | 3.65e-16 | 7.33e-16 |
| **test06_sums4, sum2** | `(+ (+ x0 x1) (+ x2 x3))` | 4.77e-07 | 7.15e-07 | 4.17e-07 | 5.66e-07 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rasterific.Svg.PathConverter:arcToSegments from rasterific-svg-0.2.3.1** | `(+ (/ (* x x) (* y y)) (/ (* z z) (* t t)))` | 2.22e-16 | 9.44e-16 | 1.94e-16 | 3.89e-16 | 4.44e-16 | 3.02e-14 | 6.03e-16 | 8.88e-16 |
| **Graphics.Rendering.Chart.Backend.Diagrams:calcFontMetrics from Chart-diagrams-1.5.1, B** | `(* x (/ (* (/ y z) t) t))` | 4.44e-16 | 2.23e-15 | 3.89e-16 | 8.88e-16 | 4.44e-16 | 3.57e-14 | 5.71e-16 | 9.99e-16 |
| **Data.Octree.Internal:octantDistance  from Octree-0.5.4.2** | `(sqrt (+ (* x x) (* y y)))` | 1.8e-15 | 4.5e-15 | 1.58e-15 | 2.73e-15 | 2.22e-16 | 1.09e-15 | 2.15e-16 | 3.35e-16 |
| **modulus** | `(sqrt (+ (* re re) (* im im)))` | 1.8e-15 | 4.5e-15 | 1.58e-15 | 2.73e-15 | 2.22e-16 | 1.09e-15 | 2.15e-16 | 3.35e-16 |
| **FastMath test1** | `(+ (* d 10) (* d 20))` | 8.88e-15 | 1.55e-14 | 8.88e-15 | 1.22e-14 | 2.22e-16 | 5.18e-16 | 1.95e-16 | 3.33e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Legend:renderLegendInside from plot-0.2.3.4** | `(+ (+ (+ (+ (+ x y) y) x) z) x)` | 1.15e-14 | 1.75e-14 | 1.15e-14 | 1.45e-14 | 3.88e-16 | 6.5e-16 | 3.41e-16 | 4.83e-16 |
| **sqrt B (should all be same)** | `(sqrt (* (* 2 x) x))` | 3.79e-16 | 1.16e-15 | 3.34e-16 | 6.93e-16 | 1.67e-16 | 8.23e-16 | 1.68e-16 | 2.79e-16 |
| **sqrt C (should all be same)** | `(sqrt (* 2 (* x x)))` | 3.79e-16 | 1.16e-15 | 3.34e-16 | 6.93e-16 | 1.67e-16 | 8.23e-16 | 1.68e-16 | 2.79e-16 |
| **sqrt D (should all be same)** | `(sqrt (* 2 (* x x)))` | 3.79e-16 | 1.16e-15 | 3.34e-16 | 6.93e-16 | 1.67e-16 | 8.23e-16 | 1.68e-16 | 2.79e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisTick from plot-0.2.3.4, A** | `(+ x (/ (* (- y z) t) (- a z)))` | 6.47e-15 | 1.56e-14 | 5.71e-15 | 1.56e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **FastMath test5** | `(* (* d1 (* (* (* (* (* d1 (* d1 d1)) d1) d1) (* d1 d1)) d1)) d1)` | 1.02e-12 | 2.16e-12 | 9.09e-13 | 1.08e-12 | 9.99e-16 | 2.16e-12 | 1.03e-15 | 2.11e-15 |
| **Complex square root** | `(* 0.5 (sqrt (* 2 (+ (sqrt (+ (* re re) (* im im))) re))))` | 5.74e-16 | 1.1e-15 | 5.12e-16 | 7.01e-16 | 2.67e-16 | 6.86e-16 | 2.42e-16 | 3.23e-16 |
| **Numeric.Signal:interpolate   from hsignal-0.2.7.1** | `(+ x (* (- y z) (/ (- t x) (- a z))))` | 6.99e-15 | 1.61e-14 | 6.23e-15 | 1.32e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:incompleteGamma from math-functions-0.1.5.2, B** | `(* (* 3 (sqrt x)) (- (+ y (/ 1 (* x 9))) 1))` | 1.3e-14 | 1.91e-14 | 1.31e-14 | 1.43e-14 | 5.98e-16 | 2.09e-15 | 5.34e-16 | 6.91e-16 |
| **mod-dY** | `(+ 0.02515965696 (+ (* 1.193845912E-7 Yr) (+ (* -4.668270147E-7 Xr) (…` | 3.47e-18 | 3.47e-18 | 3.11e-18 | 3.12e-18 | 1.38e-16 | 1.38e-16 | 1.24e-16 | 1.24e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Legend:renderLegendOutside from plot-0.2.3.4, B** | `(+ (* x (+ (+ (+ (+ y z) z) y) t)) (* y 5))` | 1.24e-13 | 2.21e-13 | 1.24e-13 | 1.73e-13 | 4.92e-16 | 1.78e-15 | 4.41e-16 | 6.93e-16 |
| **bug366 (missed optimization)** | `(sqrt (+ (* x x) (+ (* y y) (* z z))))` | 9.05e-15 | 2.14e-14 | 8.12e-15 | 1.28e-14 | 2.78e-16 | 1.3e-15 | 2.67e-16 | 3.89e-16 |
| **Numeric.SpecFunctions:invIncompleteGamma from math-functions-0.1.5.2, D** | `(- (- 1 (/ 1 (* x 9))) (/ y (* 3 (sqrt x))))` | 1e-15 | 1.73e-15 | 9e-16 | 1.46e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Array.Repa.Algorithms.ColorRamp:rampColorHotToCold from repa-algorithms-3.4.0.1, A** | `(+ 1 (/ (* 4 (- (+ x (* y 0.75)) z)) y))` | 6.66e-15 | 1.73e-14 | 6e-15 | 2.07e-14 | 6.29e-16 | 5.77e-15 | 5.92e-16 | 1.07e-15 |
| **Diagrams.ThreeD.Shapes:frustum from diagrams-lib-1.3.0.3, A** | `(* 2 (- (+ (* x y) (* z t)) (* (* (+ a (* b c)) c) i)))` | 5 | 9 | 4.5 | 6.5 | 5.55e-16 | 1.6e-14 | 5.6e-16 | 9.99e-16 |
| **Data.Colour.CIE:cieLABView from colour-2.3.3, C** | `(* 200 (- x y))` | 2.03e-13 | 4.25e-13 | 2.03e-13 | 3.14e-13 | 2.22e-16 | 1.06e-15 | 2e-16 | 5e-16 |
| **Text.Parsec.Token:makeTokenParser from parsec-3.1.9, A** | `(/ (+ x y) 10)` | 2e-16 | 3.11e-16 | 2e-16 | 2.78e-16 | 2.22e-16 | 6.22e-16 | 2e-16 | 3.33e-16 |
| **Data.Colour.CIE:cieLAB from colour-2.3.3, A** | `(* (* (- x (/ 16 116)) 3) y)` | 1.01e-14 | 2.04e-14 | 1.01e-14 | 1.5e-14 | 3.49e-16 | 1.97e-15 | 3.18e-16 | 5.75e-16 |
| **Graphics.Rendering.Chart.Axis.Types:invLinMap from Chart-1.5.3** | `(+ x (/ (* (- y z) (- t x)) (- a z)))` | 6.45e-15 | 1.55e-14 | 5.87e-15 | 1.73e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Tangent:$catParam from diagrams-lib-1.3.0.3, F** | `(* (* x 3) x)` | 1.78e-15 | 4.44e-15 | 1.78e-15 | 3.11e-15 | 2.22e-16 | 1.48e-15 | 2.02e-16 | 4.44e-16 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, G** | `(- x (/ 1 3))` | 1.39e-16 | 3.61e-16 | 1.39e-16 | 2.41e-16 | 1.53e-16 | 5.41e-16 | 1.4e-16 | 3.06e-16 |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, I** | `(+ (+ x y) z)` | 4.44e-15 | 9.1e-15 | 4.44e-15 | 6.77e-15 | 1.53e-16 | 4.34e-16 | 1.4e-16 | 2.64e-16 |
| **Numeric.SpecFunctions:choose from math-functions-0.1.5.2** | `(/ (* x (+ y z)) z)` | 8.88e-16 | 3.05e-15 | 8.14e-16 | 3.22e-15 | 3.33e-16 | 4.88e-15 | 3.25e-16 | 6.66e-16 |
| **2isqrt (example 3.6)** | `(- (/ 1 (sqrt x)) (/ 1 (sqrt (+ x 1))))` | 5.06e-16 | crash | n/b | 4.64e-16 | &mdash; | crash | n/b | &mdash; |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, B** | `(/ (- (+ x y) z) (* t 2))` | 3.47e-17 | 1.18e-16 | 3.47e-17 | 1.74e-16 | 3.7e-16 | 5.03e-15 | 3.4e-16 | 8.7e-16 |
| **Expanding a square** | `(- (* (+ x 1) (+ x 1)) 1)` | 3.11e-15 | 4.44e-15 | 3.11e-15 | 2.89e-15 | 5.55e-16 | 1.48e-15 | 5.19e-16 | 5.92e-16 |
| **Rump's example, with pow** | `(+ (+ (+ (* 333.75 (* (* (* (* (* b b) b) b) b) b)) (* (* a a) (- (- …` | 1.75e-07 | 3.14e-07 | 1.63e-07 | 1.85e-07 | &mdash; | &mdash; | 9.9e-16 | &mdash; |
| **Rump's expression from Stadtherr's award speech** | `(+ (+ (+ (* 333.75 (* (* (* (* (* y y) y) y) y) y)) (* (* x x) (- (- …` | 1.75e-07 | 3.14e-07 | 1.63e-07 | 1.85e-07 | &mdash; | &mdash; | 9.91e-16 | &mdash; |
| **Data.Colour.CIE:lightness from colour-2.3.3** | `(- (* x 116) 16)` | 2.84e-14 | 5.42e-14 | 2.84e-14 | 4.13e-14 | 2.4e-16 | 5.42e-16 | 2.23e-16 | 3.69e-16 |
| **Linear.Projection:inversePerspective from linear-1.19.1.3, C** | `(/ (+ x y) (* (* x 2) y))` | 1.94e-16 | 1.85e-15 | 1.81e-16 | 8.05e-16 | 3.33e-16 | 1.19e-14 | 3.36e-16 | 6.66e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Legend:renderLegendOutside from plot-0.2.3.4, A** | `(+ (+ x y) x)` | 1.78e-15 | 3.11e-15 | 1.78e-15 | 2.44e-15 | 2.13e-16 | 5.18e-16 | 1.99e-16 | 3.22e-16 |
| **predatorPrey** | `(/ (* (* 4 x) x) (+ 1 (* (/ x 1.11) (/ x 1.11))))` | 1.08e-16 | 1.75e-16 | 1.01e-16 | 2.04e-16 | 3.68e-16 | 4.69e-15 | 3.58e-16 | 6.03e-16 |
| **Diagrams.Segment:$catParam from diagrams-lib-1.3.0.3, A** | `(* (* (* x 3) x) y)` | 2.13e-14 | 5.33e-14 | 2.13e-14 | 3.73e-14 | 3.33e-16 | 4.44e-15 | 3.14e-16 | 6.66e-16 |
| **Statistics.Distribution.Beta:$cvariance from math-functions-0.1.5.2** | `(/ (* x y) (* (* z z) (+ z 1)))` | 1.85e-18 | 2.02e-17 | 1.75e-18 | 3.87e-18 | 5.55e-16 | 1.7e-13 | 5.42e-16 | 1.1e-15 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, E** | `(+ x (* (* (- y x) 6) z))` | 4.26e-13 | 7.88e-13 | 4.26e-13 | 6.08e-13 | 4.44e-16 | 4.09e-15 | 4.2e-16 | 8.32e-16 |
| **sqrt sqr** | `(- (/ x x) (* (/ 1 x) (sqrt (* x x))))` | 5e-16 | 1.78e-15 | 4.73e-16 | 8.88e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, F** | `(+ x (/ 1 3))` | 2.5e-16 | 4.72e-16 | 2.5e-16 | 3.52e-16 | 1.32e-16 | 3.54e-16 | 1.26e-16 | 2.08e-16 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, D** | `(+ x (* (* (- y x) 6) (- (/ 2 3) z)))` | 4.99e-13 | 8.57e-13 | 4.99e-13 | 6.77e-13 | 5.64e-16 | 4.71e-15 | 5.38e-16 | 9.61e-16 |
| **carthesianToPolar, radius** | `(sqrt (+ (* x x) (* y y)))` | 2.99e-14 | 2.31e-12 | 2.86e-14 | 4.59e-14 | 2.22e-16 | 1.63e-12 | 2.24e-16 | 3.35e-16 |
| **hypot** | `(sqrt (+ (* x1 x1) (* x2 x2)))` | 2.99e-14 | 2.31e-12 | 2.86e-14 | 4.59e-14 | 2.22e-16 | 1.63e-12 | 2.24e-16 | 3.35e-16 |
| **Diagrams.Backend.Rasterific:rasterificRadialGradient from diagrams-rasterific-1.3.1.3** | `(/ (+ x (* y (- z x))) z)` | 3.08e-15 | 8.62e-15 | 2.95e-15 | 1.16e-14 | 4.43e-16 | 4.84e-15 | 4.33e-16 | 8e-16 |
| **Hakyll.Web.Tags:renderTagCloud from hakyll-4.7.2.3** | `(+ x (* (/ (- y z) (- (+ t 1) z)) (- a x)))` | 2.8e-13 | 7.68e-13 | 2.77e-13 | 5.62e-13 | 9.82e-16 | 4.8e-14 | 9.41e-16 | 1.73e-15 |
| **hypot32** | `(sqrt (+ (* x1 x1) (* x2 x2)))` | 1.61e-05 | 0.00124 | 1.55e-05 | 2.45e-05 | 1.19e-07 | 0.000875 | 2.4e-07 | 1.79e-07 |
| **Data.HashTable.ST.Basic:computeOverhead from hashtables-1.2.0.2** | `(+ (/ x y) (/ (+ 2 (* (* z 2) (- 1 t))) (* t z)))` | 1.16e-15 | 1.31e-14 | 1.17e-15 | 7.21e-15 | 7.9e-16 | &mdash; | 7.67e-16 | &mdash; |
| **Examples.Basics.BasicTests:f1 from sbv-4.4** | `(* (+ x y) (- x y))` | 1.42e-14 | 3.46e-14 | 1.38e-14 | 2.72e-14 | 3.33e-16 | 3.46e-15 | 3.36e-16 | 7.22e-16 |
| **mod-dX** | `(+ 0.02946529277 (+ (* 1.193845912E-7 Xr) (+ (* (- -4.668270147E-7) Y…` | 3.47e-18 | 3.47e-18 | 3.38e-18 | 2.08e-15 | 1.18e-16 | 1.18e-16 | 1.15e-16 | 7.07e-14 |
| **Numeric.SpecFunctions:invIncompleteBetaWorker from math-functions-0.1.5.2, C** | `(* x (- (/ y z) (/ t (- 1 z))))` | 7.33e-15 | 1.57e-14 | 7.16e-15 | 1.05e-14 | 4.43e-16 | 7.19e-15 | 5.22e-16 | 6.73e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, A** | `(+ (- (* x 2) (* (* (* y 9) z) t)) (* (* a 27) b))` | 5.7e-09 | 1.21e-08 | 5.7e-09 | 8.9e-09 | 3.62e-16 | 1.78e-15 | 3.54e-16 | 5.99e-16 |
| **Graphics.Rendering.Chart.SparkLine:renderSparkLine from Chart-1.5.3** | `(- x (/ (- y z) (/ (+ (- t z) 1) a)))` | 2.29e-13 | 1.84e-12 | 2.25e-13 | 5.35e-13 | 6.64e-16 | 9.64e-14 | 7.19e-16 | 1.32e-15 |
| **forward-rot-y** | `(- (* (- u u0) cosrot) (* v sinrot))` | 3.75e-12 | 7.62e-12 | 3.69e-12 | 5.63e-12 | 3.31e-16 | 1.76e-15 | 3.29e-16 | 5.55e-16 |
| **Diagrams.Solve.Polynomial:quadForm from diagrams-solve-0.1, B** | `(* (/ 1 2) (+ x (* y (sqrt z))))` | 7.11e-15 | 9.73e-15 | 7.11e-15 | 7.53e-15 | 4.39e-16 | 1.14e-15 | 4.34e-16 | 4.94e-16 |
| **Henrywood and Agarwal, Equation (9a)** | `(* w0 (sqrt (- 1 (* (* (/ (* M D) (* 2 d)) (/ (* M D) (* 2 d))) (/ h …` | 2.84e-16 | 5.15e-16 | 2.83e-16 | 4e-16 | 1.98e-16 | 5.18e-16 | 2.84e-16 | 3.11e-16 |
| **Data.Colour.CIE:cieLABView from colour-2.3.3, A** | `(+ (* (/ 841 108) x) (/ 4 29))` | 2.68e-15 | 4.41e-15 | 2.68e-15 | 2.97e-15 | 2.78e-16 | 5.56e-16 | 2.77e-16 | 3.52e-16 |
| **Data.Colour.CIE:cieLABView from colour-2.3.3, B** | `(* 500 (- x y))` | 4.49e-13 | 1e-12 | 4.49e-13 | 7.27e-13 | 2.22e-16 | 1e-15 | 2.21e-16 | 5e-16 |
| **forward-rot-x** | `(+ (* v cosrot) (* (- u u0) sinrot))` | 1.09e-11 | 2.56e-11 | 1.09e-11 | 1.82e-11 | 3.38e-16 | 1.6e-15 | 3.39e-16 | 5.66e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, I** | `(/ (- (* x y) (* (* z 9) t)) (* a 2))` | 2.84e-14 | 6.04e-14 | 2.84e-14 | 5.51e-14 | 4.45e-16 | 6.72e-15 | 4.49e-16 | 7.78e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, E** | `(- (- (+ (- (* (* (* (* x 18) y) z) t) (* (* a 4) t)) (* b c)) (* (* …` | 0.000366 | 0.000778 | 0.000366 | 0.000572 | 3.33e-16 | 1.68e-15 | 3.35e-16 | 5.55e-16 |
| **Commute and associate** | `(- (+ (+ x y) z) (+ x (+ y z)))` | 1.15e-14 | 1.15e-14 | 1.17e-14 | 1.62e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.Signal.Multichannel:$cput from hsignal-0.2.7.1** | `(* (/ (- x y) (- z y)) t)` | 3.38e-14 | 1.39e-13 | 3.38e-14 | 1.07e-13 | 4.44e-16 | 3.03e-14 | 4.73e-16 | 1.11e-15 |
| **Statistics.Sample:$skurtosis from math-functions-0.1.5.2** | `(- (/ x (* y y)) 3)` | 2.5e-16 | 4.16e-16 | 2.5e-16 | 2.84e-16 | 8.69e-17 | 1.45e-16 | 8.69e-17 | 9.9e-17 |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, H** | `(* (+ x y) (- 1 z))` | 7.37e-14 | 1.44e-13 | 7.37e-14 | 9.09e-14 | 3.33e-16 | 1.92e-15 | 3.35e-16 | 4.51e-16 |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisLine from plot-0.2.3.4, B** | `(+ x (* y (/ (- z t) (- a t))))` | 2.55e-15 | 9.33e-15 | 2.55e-15 | 7.27e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rendering.Plot.Render.Plot.Axis:renderAxisTicks from plot-0.2.3.4, B** | `(+ x (/ (* y (- z t)) (- a t)))` | 2.55e-15 | 9.33e-15 | 2.55e-15 | 7.99e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, F** | `(* (* x 27) y)` | 5.68e-14 | 1.53e-13 | 5.68e-14 | 1.05e-13 | 2.22e-16 | 1.41e-15 | 2.25e-16 | 4.44e-16 |
| **Text.Parsec.Token:makeTokenParser from parsec-3.1.9, B** | `(* (+ x y) z)` | 5.68e-14 | 1.28e-13 | 5.68e-14 | 9.24e-14 | 2.22e-16 | 1.6e-15 | 2.24e-16 | 4.44e-16 |
| **Main:bigenough2 from A** | `(+ x (* y (+ z x)))` | 8.53e-14 | 1.46e-13 | 8.53e-14 | 1.16e-13 | 3.32e-16 | 2.11e-15 | 3.35e-16 | 5.54e-16 |
| **Diagrams.Segment:$catParam from diagrams-lib-1.3.0.3, B** | `(* (* (* x 3) y) y)` | 8.53e-14 | 2.13e-13 | 8.53e-14 | 1.49e-13 | 3.33e-16 | 4.44e-15 | 3.36e-16 | 6.66e-16 |
| **Data.Colour.CIE:cieLAB from colour-2.3.3, B** | `(/ (+ x 16) 116)` | 2.92e-17 | 3.11e-17 | 2.92e-17 | 3.11e-17 | 1.99e-16 | 2.12e-16 | 1.99e-16 | 2.06e-16 |
| **floudas3** | `(+ (- (* -12 x1) (* 7 x2)) (* x2 x2))` | 1.15e-14 | 1.58e-14 | 1.15e-14 | 1.58e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, G** | `(* (+ x y) (+ z 1))` | 9.33e-14 | 1.65e-13 | 9.33e-14 | 1.29e-13 | 3.33e-16 | 1.95e-15 | 3.36e-16 | 5.49e-16 |
| **Data.Metrics.Snapshot:quantile from metrics-0.3.0.2** | `(+ x (* (- y z) (- t x)))` | 8.79e-13 | 1.85e-12 | 8.79e-13 | 1.36e-12 | 4.45e-16 | 3.74e-15 | 4.48e-16 | 8.41e-16 |
| **test06_sums4, sum1** | `(+ (+ (+ x0 x1) x2) x3)` | 4.77e-07 | 7.15e-07 | 4.77e-07 | 6.26e-07 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Spline.Key:interpolateKeys from smoothie-0.4.0.2** | `(* (* x x) (- 3 (* x 2)))` | 8.88e-16 | 3.55e-15 | 8.88e-16 | 1.78e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, E** | `(+ x (/ (* y (- z t)) a))` | 8.88e-16 | 2.83e-15 | 8.88e-16 | 3.08e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Colour.RGB:hslsv from colour-2.3.3, E** | `(/ (- x y) x)` | 8.88e-16 | 3.55e-15 | 8.88e-16 | 3.94e-15 | 2.22e-16 | 3.55e-15 | 2.24e-16 | 6.11e-16 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, B** | `(* x (+ y 1))` | 3.55e-15 | 7.33e-15 | 3.55e-15 | 5.44e-15 | 2.22e-16 | 1.47e-15 | 2.24e-16 | 4.22e-16 |
| **Data.Colour.RGBSpace.HSV:hsv from colour-2.3.3, H** | `(* x (- 1 y))` | 1.78e-15 | 5.11e-15 | 1.78e-15 | 2.55e-15 | 2.22e-16 | 1.7e-15 | 2.24e-16 | 3.7e-16 |
| **Diagrams.Tangent:$catParam from diagrams-lib-1.3.0.3, D** | `(* 3 (+ (- (* (* x 3) x) (* x 4)) 1))` | 8.88e-15 | 1.78e-14 | 8.88e-15 | 1.29e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rendering.Chart.Plot.AreaSpots:renderAreaSpots4D from Chart-1.5.3** | `(/ (* x (- y z)) (- t z))` | 5.27e-16 | 2.16e-15 | 5.27e-16 | 1.86e-15 | 4.44e-16 | 3.03e-14 | 5.21e-16 | 1.11e-15 |
| **drag_accel_mag** | `(/ (* (* (* (- 0.5) density) (/ (* Cd A) m)) (* (* v 1000) (* v 1000)…` | 6.5e-07 | 1.58e-06 | 6.5e-07 | 1.03e+09 | 8.88e-16 | 9.65e-14 | 2.49e-15 | &mdash; |
| **Diagrams.ThreeD.Shapes:frustum from diagrams-lib-1.3.0.3, B** | `(+ x (* (- y x) z))` | 4.26e-14 | 1.03e-13 | 4.26e-14 | 7.29e-14 | 3.32e-16 | 3.12e-15 | 3.34e-16 | 7.19e-16 |
| **SynthBasics:oscSampleBasedAux from YampaSynth-0.2** | `(+ x (* y (- z x)))` | 4.26e-14 | 1e-13 | 4.26e-14 | 7.16e-14 | 3.32e-16 | 1.76e-15 | 3.34e-16 | 5.77e-16 |
| **Physics.ForceLayout:coulombForce from force-layout-0.4.0.2** | `(/ x (* y y))` | 2.78e-17 | 1.94e-16 | 2.78e-17 | 6.25e-17 | 2.22e-16 | 1.24e-14 | 2.24e-16 | 5.55e-16 |
| **Examples.Basics.BasicTests:f3 from sbv-4.4** | `(* (+ x y) (+ x y))` | 2.49e-14 | 4.71e-14 | 2.49e-14 | 3.6e-14 | 3.33e-16 | 1.88e-15 | 3.36e-16 | 5.55e-16 |
| **floudas** | `(+ x1 x2)` | 4.44e-16 | 8.88e-16 | 4.44e-16 | 7.77e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **floudas2** | `(- (- x1) x2)` | 4.44e-16 | 1.11e-15 | 4.44e-16 | 8.88e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Data.Colour.RGB:hslsv from colour-2.3.3, A** | `(/ (+ x y) 2)` | 4.44e-16 | 1.44e-15 | 4.44e-16 | 1.55e-15 | 1.11e-16 | 5.77e-16 | 1.12e-16 | 3.33e-16 |
| **Data.Colour.RGBSpace.HSL:hsl from colour-2.3.3, C** | `(- (* x 2) y)` | 4.44e-16 | 1.78e-15 | 4.44e-16 | 1.11e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Polynomial:quartForm  from diagrams-solve-0.1, A** | `(- x (* (/ 3 8) y))` | 4.44e-16 | 9.99e-16 | 4.44e-16 | 5e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rendering.Chart.Axis.Types:hBufferRect from Chart-1.5.3** | `(+ x (/ (- x y) 2))` | 4.44e-16 | 1.44e-15 | 4.44e-16 | 1.92e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rendering.Chart.Axis.Types:linMap from Chart-1.5.3** | `(+ x (/ (* (- y x) (- z t)) (- a t)))` | 2.79e-15 | 9.03e-15 | 2.79e-15 | 8.82e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Expression, p14** | `(* a (+ (+ b c) d))` | 2.92e-11 | 4.75e-11 | 2.92e-11 | 4.2e-11 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Backend.Cairo.Internal:setTexture from diagrams-cairo-1.3.0.3** | `(/ (* x (- y z)) y)` | 2.66e-15 | 9.55e-15 | 2.66e-15 | 1.1e-14 | 3.33e-16 | 9.55e-15 | 3.36e-16 | 8.33e-16 |
| **Cancel like terms** | `(- (+ 1 x) x)` | 3.33e-16 | 4.44e-16 | 3.33e-16 | 4.44e-16 | 3.33e-16 | &mdash; | 3.36e-16 | 7.22e-16 |
| **Expression 4, p15** | `(* (+ a b) (+ a b))` | 2.49e-14 | 4.26e-14 | 2.49e-14 | 4.26e-14 | 3.33e-16 | 1.71e-15 | 3.37e-16 | 6.88e-16 |
| **Data.Colour.CIE:cieLAB from colour-2.3.3, C** | `(+ x (/ y 500))` | 2.24e-16 | 4.48e-16 | 2.24e-16 | 3.37e-16 | 1.13e-16 | 4.44e-16 | 1.13e-16 | 2.24e-16 |
| **rigidBody1** | `(- (- (- (- (* x1 x2)) (* (* 2 x2) x3)) x1) x3)` | 2.13e-13 | 2.95e-13 | 2.13e-13 | 2.95e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **rigidBody2** | `(- (+ (- (+ (* (* (* 2 x1) x2) x3) (* (* 3 x3) x3)) (* (* (* x2 x1) x…` | 2.27e-11 | 3.61e-11 | 2.27e-11 | 3.61e-11 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Graphics.Rasterific.Shading:$sgradientColorAt from Rasterific-0.6.1** | `(/ (- x y) (- z y))` | 2.08e-16 | 9.3e-16 | 2.08e-16 | 7.36e-16 | 3.33e-16 | 1.3e-14 | 3.36e-16 | 8.88e-16 |
| **Numeric.SpecFunctions:$slogFactorial from math-functions-0.1.5.2, A** | `(/ 1 (* x x))` | 2.22e-16 | 1.44e-15 | 2.22e-16 | 3.89e-16 | 2.22e-16 | 5.77e-15 | 2.26e-16 | 4.44e-16 |
| **System.Random.MWC.Distributions:blocks from mwc-random-0.13.3.2** | `(* (* x 0.5) x)` | 2.22e-16 | 6.66e-16 | 2.22e-16 | 3.33e-16 | 1.11e-16 | 1.33e-15 | 1.12e-16 | 3.33e-16 |
| **Data.Colour.CIE:cieLAB from colour-2.3.3, D** | `(- x (/ y 200))` | 1.14e-16 | 3.41e-16 | 1.14e-16 | 2.3e-16 | 1.15e-16 | 3.55e-16 | 1.16e-16 | 2.35e-16 |
| **Data.Colour.RGBSpace.HSV:hsv from colour-2.3.3, J** | `(* x (- 1 (* (- 1 y) z)))` | 1.14e-13 | 2.7e-13 | 1.14e-13 | 1.64e-13 | 4.43e-16 | 5.51e-15 | 4.46e-16 | 7.01e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, B** | `(- (* (* x 3) y) z)` | 1.07e-14 | 2.49e-14 | 1.07e-14 | 1.6e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Polynomial:quartForm  from diagrams-solve-0.1, E** | `(- x (/ y 4))` | 1.11e-16 | 6.66e-16 | 1.11e-16 | 4.44e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Optimisation.CirclePacking:place from circle-packing-0.1.0.4, F** | `(- x (/ (* y (- z t)) a))` | 1.11e-15 | 3.05e-15 | 1.11e-15 | 3.3e-15 | 3.84e-16 | 2.44e-15 | 3.92e-16 | 7.83e-16 |
| **Data.Colour.RGB:hslsv from colour-2.3.3, B** | `(+ (/ (* 60 (- x y)) (- z t)) (* a 120))` | 7.28e-12 | 1.41e-11 | 7.28e-12 | 1.07e-11 | 2.22e-16 | 4.59e-16 | 2.23e-16 | 3.33e-16 |
| **Henrywood and Agarwal, Equation (3)** | `(* c0 (sqrt (/ A (* V l))))` | 4.74e-17 | 4.36e-16 | 4.74e-17 | 8.69e-17 | 3.33e-16 | 1.4e-14 | 4.05e-16 | 6.12e-16 |
| **Data.Random.Distribution.Triangular:triangularCDF from random-fu-0.2.6.2, A** | `(- 1 (/ x (* (- y z) (- y t))))` | 5.74e-17 | 7.26e-17 | 5.78e-17 | 5.98e-17 | 5.77e-17 | 7.29e-17 | 5.8e-17 | 6e-17 |
| **ENA, Section 1.4, Exercise 4b, n=2** | `(- (* (+ x eps) (+ x eps)) (* x x))` | 247 | 614 | 249 | 550 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Linear.Projection:infinitePerspective from linear-1.19.1.3, A** | `(/ (* x 2) (- (* y z) (* t z)))` | 1.71e-18 | 1.21e-17 | 1.73e-18 | 3.34e-18 | 3.97e-16 | 2.44e-14 | 4.17e-16 | 7.61e-16 |
| **Main:z from ** | `(+ (+ (+ (- (sqrt (+ x 1)) (sqrt x)) (- (sqrt (+ y 1)) (sqrt y))) (- …` | 4.69e-15 | 5.77e-15 | 4.76e-15 | 6.47e-15 | 7.55e-15 | &mdash; | 9.95e-15 | 1.47e-14 |
| **Main:bigenough3 from C** | `(- (sqrt (+ x 1)) (sqrt x))` | 3.01e-16 | 3.33e-16 | 3.28e-16 | 3.95e-16 | 9.46e-16 | &mdash; | 9.95e-16 | 1.76e-15 |
| **Data.Colour.CIE.Chromaticity:chromaCoords from colour-2.3.3** | `(- (- 1 x) y)` | 8.88e-16 | 2e-15 | 9.44e-16 | 1.44e-15 | 1.11e-16 | 5e-16 | 1.19e-16 | 2.5e-16 |
| **Expression, p6** | `(* (+ a (+ b (+ c d))) 2)` | 5.33e-15 | 1.02e-14 | 5.77e-15 | 9.77e-15 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Backend.Rasterific:$crender from diagrams-rasterific-1.3.1.3** | `(+ (* x y) (* (- 1 x) z))` | 7.11e-15 | 1.87e-14 | 7.99e-15 | 1.15e-14 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Diagrams.Solve.Tridiagonal:solveTriDiagonal from diagrams-solve-0.1, B** | `(/ x (- y (* z t)))` | 6.56e-19 | 3.52e-18 | 1.1e-18 | 1.32e-18 | 3.34e-16 | 1.44e-14 | 3.98e-16 | 6.69e-16 |
| **d2PSI-dDelta2-over-PSI** | `(* (- (* 2 (* Ci (* (- delta 1) (- delta 1)))) 1) (* 2 Ci))` | 8.53e-14 | 2.54e-13 | 1.14e-13 | 1.41e-13 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Numeric.SpecFunctions:logGamma from math-functions-0.1.5.2** | `(/ (+ (* (+ (* (+ (* (+ (* x y) z) y) 27464.7644705) y) 230661.510616…` | 5.95e-14 | 3.44e-13 | 1.48e-13 | 9.33e-14 | 1.28e-15 | 1.25e-13 | 3.89e-14 | 1.74e-15 |
| **Statistics.Correlation.Kendall:numOfTiesBy from math-functions-0.1.5.2** | `(* x (- x 1))` | 2.22e-16 | 8.88e-16 | 3.33e-16 | 4.44e-16 | &mdash; | &mdash; | &mdash; | &mdash; |
| **2sqrt (example 3.1)** | `(- (sqrt (+ x 1)) (sqrt x))` | 2.04e+138 | 4.99e+291 | n/b | 3.55e+138 | 4.09e+292 | &mdash; | n/b | &mdash; |
| **Statistics.Distribution.CauchyLorentz:$cdensity from math-functions-0.1.5.2** | `(/ (/ 1 x) (* y (+ 1 (* z z))))` | 4.86e-19 | 5.54e-18 | 1.4e-18 | 9.18e-19 | 5.55e-16 | 9.09e-14 | &mdash; | 9.99e-16 |
| **Diagrams.Solve.Polynomial:cubForm  from diagrams-solve-0.1, J** | `(/ (+ (- (* (* x 9) y) (* (* (* z 4) t) a)) b) (* z c))` | 3.91e-14 | 2.53e-13 | 7.11e-14 | 1.49e-13 | 6.67e-16 | 6.34e-14 | 3.91e-15 | 1.22e-15 |
| **nonlin2** | `(/ (- (* x y) 1) (- (* (* x y) (* x y)) 1))` | 6.96e-14 | 2.49e-09 | 3.73e-13 | 2.71e-10 | 1.39e-13 | 1.87e-05 | 6.65e-12 | 3.62e-13 |
| **sec4-example** | `(/ (- (* x y) 1) (- (* (* x y) (* x y)) 1))` | 6.96e-14 | 2.49e-09 | 3.73e-13 | 2.71e-10 | 1.39e-13 | 1.87e-05 | 6.65e-12 | 3.62e-13 |
| **test05_nonlin1, r4** | `(/ (- x 1) (- (* x x) 1))` | 2.78e-12 | 3.89e-06 | 2.21e-09 | 1.39e-06 | 5.55e-12 | 1.17 | 3.46e-06 | 2.78e-11 |
| **Development.Shake.Profile:generateTrace from shake-0.15.5** | `(* 1000000 (- x x))` | 0 | 5.82e-11 | 8.88e-13 | 0 | &mdash; | &mdash; | &mdash; | &mdash; |
| **ReportTypes:explainFloat from gipeda-0.1.2.1** | `(* 100 (/ (- x x) x))` | 0 | 4.04e-14 | 1.86e-16 | 0 | &mdash; | &mdash; | &mdash; | &mdash; |
| **Octave 3.8, jcobi/1** | `(/ (+ (/ (- beta alpha) (+ (+ alpha beta) 2)) 1) 2)` | &mdash; | crash | n/b | 2.46e+16 | &mdash; | crash | n/b | &mdash; |
| **Octave 3.8, jcobi/3** | `(/ (/ (/ (+ (+ (+ alpha beta) (* beta alpha)) 1) (+ (+ alpha beta) (*…` | &mdash; | crash | n/b | 3.63e+32 | &mdash; | crash | n/b | &mdash; |
| **a parameter of renormalized beta distribution** | `(* (- (/ (* m (- 1 m)) v) 1) m)` | &mdash; | crash | n/b | inf | &mdash; | crash | n/b | &mdash; |
| **b parameter of renormalized beta distribution** | `(* (- (/ (* m (- 1 m)) v) 1) (- 1 m))` | &mdash; | crash | n/b | inf | &mdash; | crash | n/b | &mdash; |
| **fma_test2** | `(- (* 170000000000000000000000000000000000000000000000000000000000000…` | &mdash; | crash | n/b | 6.47e+292 | &mdash; | crash | n/b | 4.03e-16 |
| **NMSE Section 6.1 mentioned, B** | `(* (* (/ PI 2) (/ 1 (- (* b b) (* a a)))) (- (/ 1 a) (/ 1 b)))` | 8.81e-17 | unsupported | n/b | unsupported | 1.14e-15 | unsupported | n/b | unsupported |
| **xlohi (overflows)** | `(/ (- x lo) (- hi lo))` | &mdash; | crash | n/b | 1.56e-18 | &mdash; | crash | n/b | 3.12e-18 |
| **x (used to be hard to sample)** | `x` | 0 | 2.22e-16 | 0 | 1.11e-16 | 0 | 2.22e-16 | 0 | 1.11e-16 |

&mdash; bounded the other metric but not this one, almost always a range containing zero.  `n/b` bounded nothing; `t/o` timed out; `err` or a bare status, it failed.
