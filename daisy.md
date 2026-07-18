# Cost-based extraction vs Daisy (worst-case error over the box)

Daisy rewrites by genetic search against its own sound static bound
(seed 1, default 30x30). `certified` = each tool's own bound;
`measured` = FPTaylor on each tool's output program, same box --
the neutral judge and the basis of `winner` (relative error where
both sides have it, else absolute). `-` for Daisy's measured column
means its output used let-bindings and was not re-measured.

measured winner: ours 16 / daisy 9 / tie 5 / uncompared 14

| benchmark | ours certified | daisy certified | ours measured | daisy measured | winner |
|---|--:|--:|--:|--:|---|
| asymptote_c | 2.2 ulp | 1.5e-12 abs | 1.5 ulp | 57.7 ulp | ours |
| beta_a | 4.0e-16 abs | 5.1e-16 abs | 1.7e-16 abs | 2.2e-16 abs | ours |
| beta_b | 4.5e-16 abs | 5.5e-16 abs | 2.0e-16 abs | 2.5e-16 abs | ours |
| cancel_sqrt_2var | 52.3 ulp | - | 2.2 ulp | - | - |
| cancel_sqrt_shift3 | 214.0 ulp | - | - | - | - |
| cancel_sqrt_sum | 26.8 ulp | - | 1.8 ulp | - | - |
| complex_square_real | 1.5 ulp | 2.9e-15 abs | 6.1e-16 abs | 6.7e-16 abs | ours |
| conte_near_pole | 2.0 ulp | 75083.3 ulp | 61.1 ulp | 25062.1 ulp | ours |
| conte_x_minus_sqrt | 83335.1 ulp | 6.6e-11 abs | 7.4e-17 abs | - | - |
| delta4 | 3.7e-14 abs | 8.7e-14 abs | 2.0e-14 abs | 4.5e-14 abs | ours |
| excel_x0 | 1.1 ulp | 6.3e-16 abs | 91.4 ulp | 4.0e-16 abs | ours |
| expand_square | 1.0 ulp | 7.8e-16 abs | 4.4e-16 abs | 2.8e-16 abs | daisy |
| fastmath_dist4 | 6.6e-12 abs | 8.9e-12 abs | 4.7e-12 abs | 4.7e-12 abs | tie |
| floudas1 | 3.0e-13 abs | 3.4e-13 abs | 1.8e-13 abs | 1.7e-13 abs | daisy |
| floudas3 | 1.2e-14 abs | 1.3e-14 abs | 7.5e-15 abs | 7.5e-15 abs | tie |
| himmilbeau | 2.0e-12 abs | 2.2e-12 abs | 6.1e-13 abs | 5.4e-13 abs | daisy |
| jetengine | - | - | 8.2e-12 abs | - | - |
| kahan_p9 | 1000002.5 ulp | - | 3.7e-12 abs | - | - |
| kepler0 | 19.7 ulp | 6.2e-14 abs | 2.8 ulp | 4.2 ulp | ours |
| kepler1 | 3.0e-13 abs | 3.2e-13 abs | 10.0 ulp | 12.0 ulp | ours |
| kepler2 | 1.5e-12 abs | 1.7e-12 abs | 30.4 ulp | 74.1 ulp | ours |
| martel_p6 | 1.6e-15 abs | 5.3e-15 abs | 7.2e-16 abs | 7.2e-16 abs | tie |
| matrixdeterminant | 3.1e-12 abs | 3.5e-12 abs | 1.8e-12 abs | 1.6e-12 abs | daisy |
| matrixdeterminant2 | 3.1e-12 abs | 3.4e-12 abs | 1.8e-12 abs | 1.7e-12 abs | daisy |
| nmse_example_3_1 | 1.8 ulp | 3.6e-13 abs | 1.6 ulp | - | - |
| nmse_example_3_6 | 2.5 ulp | 3.6e-09 abs | 126.1 ulp | - | - |
| nmse_p42_negative | 5628.8 ulp | - | 13.0 ulp | - | - |
| nmse_p42_positive | 5628.8 ulp | - | 454960.6 ulp | - | - |
| nmse_problem_3_2_1_negative | 5001.8 ulp | - | 2.0 ulp | - | - |
| nmse_problem_3_2_1_positive | 5001.8 ulp | - | 2.0 ulp | - | - |
| nmse_problem_3_3_1 | 1.5 ulp | 7.1e-13 abs | 118862.9 ulp | 1.9e-15 abs | daisy |
| nmse_problem_3_3_3 | 2.2 ulp | 1.3e-14 abs | 256918.9 ulp | 4.1e-16 abs | ours |
| nonlin2 | 1.5 ulp | 84084022538.8 ulp | 1.3 ulp | 29871.5 ulp | ours |
| pbrt_cone_z | 3.3e-16 abs | 5.0e-16 abs | 2.2e-16 abs | 2.2e-16 abs | tie |
| rigidbody1 | 2.3e-13 abs | 2.0e-13 abs | 1.4e-13 abs | 1.2e-13 abs | daisy |
| rigidbody2 | 2.7e-11 abs | 2.9e-11 abs | 1.6e-11 abs | 1.6e-11 abs | daisy |
| sine | 2.9 ulp | 7.4e-16 abs | 4.2e-16 abs | 3.4e-16 abs | daisy |
| som_setup_w | 2.0e-16 abs | 1.0e-15 abs | 9.6e-17 abs | 6.0e-16 abs | ours |
| sum | 1.0 ulp | 2.7e-15 abs | 0.8 ulp | 1.6 ulp | ours |
| test03_nonlin2 | 1.5 ulp | 4.8e-14 abs | 3.5e-16 abs | 3.5e-16 abs | tie |
| test04_dqmom9 | 5.7e-10 abs | 2.0e+00 abs | 4.0e-10 abs | 1.3e-05 abs | ours |
| test05_nonlin1_r4 | 1.0 ulp | 5249952416309750.0 ulp | 0.8 ulp | 15597717409.8 ulp | ours |
| triangle | 22.4 ulp | 46.9 ulp | 19.3 ulp | - | - |
| triangle1 | 14.2 ulp | 1517.2 ulp | 4.2 ulp | - | - |
