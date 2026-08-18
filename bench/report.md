# costex vs FPTaylor

- 10 cores, costex at 4 iterations
- FPTaylor 0.9.4+dev, `-v 0 -abs true -rel true --fail-on-exception true`
- FPTaylor data for 10 of them
- sorted by file name

| Core | Program | costex mu_abs | FPTaylor abs | costex mu_rel | FPTaylor rel |
|---|---|---:|---:|---:|---:|
| **carthesianToPolar, radius** | seed, abs, rel: `(sqrt (+ (* x x) (* y y)))` | 2.99e-14 | 2.86e-14 | 2.22e-16 | 2.24e-16 |
| **matrixDeterminant** | seed: `(- (+ (+ (* (* a e) i) (* (* b f) g)) (* (* c d) h)) (+ (+ (* (* c e)…`<br>abs, rel: `(- (+ (+ (* f (* b g)) (* d (* c h))) (+ (* e (* a i)) (* (* (- a) f)…` | 1.9e-12<br>1.79e-12 | 1.56e-12<br>1.73e-12 | &mdash;<br>&mdash; | &mdash;<br>&mdash; |
| **matrixDeterminant2** | seed: `(- (+ (* a (* e i)) (+ (* g (* b f)) (* c (* d h)))) (+ (* e (* c g))…`<br>abs, rel: `(- (+ (+ (* (* g b) f) (* d (* h c))) (+ (* e (* i a)) (* (* (- c) e)…` | 1.9e-12<br>1.79e-12 | 1.56e-12<br>1.73e-12 | &mdash;<br>&mdash; | &mdash;<br>&mdash; |
| **delta4** | seed: `(+ (- (+ (+ (- (* (- x2) x3) (* x1 x4)) (* x2 x5)) (* x3 x6)) (* x5 x…`<br>abs, rel: `(+ (+ (* x1 (- x2 x1)) (* x1 (- x3 x4))) (+ (+ (* x1 (- x5 x4)) (* x1…` | 8.01e-14<br>3.64e-14 | 5.77e-14<br>2.55e-14 | &mdash;<br>&mdash; | &mdash;<br>&mdash; |
| **delta** | seed: `(+ (+ (+ (+ (+ (+ (* (* x1 x4) (+ (+ (- (+ (+ (- x1) x2) x3) x4) x5) …`<br>abs, rel: `(+ (+ (* x6 (+ (+ (+ (* x3 (- x2 x3)) (* x1 x3)) (+ (* x3 x5) (* x3 (…` | 1.96e-12<br>1.06e-12 | 1.47e-12<br>7.42e-13 | &mdash;<br>&mdash; | 1.52e-14<br>7.83e-15 |
| **sqrt_add** | seed: `(/ 1 (+ (sqrt (+ x 1)) (sqrt x)))`<br>abs, rel: `(/ 1 (+ (sqrt x) (sqrt (+ x 1))))` | 1.43e-16<br>1.42e-16 | 1.17e-16<br>1.17e-16 | 3.89e-16<br>3.88e-16 | 3.33e-16<br>3.33e-16 |
| **floudas** | seed, abs, rel: `(+ x1 x2)` | 4.44e-16 | 4.44e-16 | &mdash; | &mdash; |
| **x_by_xy** | seed, abs, rel: `(/ x (+ x y))` | 2.38e-07 | 7.51e-08 | 1.19e-07 | 1.21e-07 |
| **hypot** | seed, abs, rel: `(sqrt (+ (* x1 x1) (* x2 x2)))` | 2.99e-14 | 2.86e-14 | 2.22e-16 | 2.24e-16 |
| **hypot32** | seed, abs, rel: `(sqrt (+ (* x1 x1) (* x2 x2)))` | 1.61e-05 | 1.55e-05 | 1.19e-07 | 2.4e-07 |
