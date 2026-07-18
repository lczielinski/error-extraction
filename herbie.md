# Cost-based extraction vs Herbie

## Average bits of error (Herbie's metric, same sampled points)

Lower is better. ours 4 / herbie 5 / tie 35 / unscored 0

| benchmark | reference | ours | herbie | winner |
|---|--:|--:|--:|---|
| asymptote_c | 1.59 | 0.28 | 0.28 | tie |
| beta_a | 2.83 | 2.49 | 2.19 | herbie |
| beta_b | 2.87 | 2.52 | 2.23 | herbie |
| cancel_sqrt_2var | 0.01 | 0.05 | 0.01 | tie |
| cancel_sqrt_shift3 | 2.95 | 0.02 | 0.02 | tie |
| cancel_sqrt_sum | 0.01 | 0.02 | 0.01 | tie |
| complex_square_real | 1.11 | 0.24 | 0.25 | tie |
| conte_near_pole | 8.14 | 0.49 | 0.32 | herbie |
| conte_x_minus_sqrt | 59.09 | 0.02 | 0.24 | ours |
| delta4 | 1.04 | 0.37 | 0.34 | tie |
| excel_x0 | 7.21 | 0.27 | 0.31 | tie |
| expand_square | 58.42 | 0.01 | 0.01 | tie |
| fastmath_dist4 | 0.75 | 0.44 | 0.53 | tie |
| floudas1 | 0.24 | 0.18 | 0.08 | herbie |
| floudas3 | 0.14 | 0.14 | 0.14 | tie |
| himmilbeau | 0.04 | 0.02 | 0.03 | tie |
| jetengine | 0.63 | 0.65 | 0.56 | tie |
| kahan_p9 | 0.02 | 0.02 | 0.02 | tie |
| kepler0 | 0.56 | 0.28 | 0.28 | tie |
| kepler1 | 0.77 | 0.58 | 0.60 | tie |
| kepler2 | 1.29 | 0.52 | 0.94 | ours |
| martel_p6 | 3.65 | 0.00 | 0.02 | tie |
| matrixdeterminant | 0.17 | 0.16 | 0.17 | tie |
| matrixdeterminant2 | 0.16 | 0.16 | 0.17 | tie |
| nmse_example_3_1 | 1.36 | 0.45 | 0.26 | herbie |
| nmse_example_3_6 | 1.44 | 0.46 | 0.49 | tie |
| nmse_p42_negative | 0.29 | 0.35 | 0.29 | tie |
| nmse_p42_positive | 0.29 | 0.35 | 0.29 | tie |
| nmse_problem_3_2_1_negative | 0.30 | 0.28 | 0.30 | tie |
| nmse_problem_3_2_1_positive | 0.30 | 0.29 | 0.30 | tie |
| nmse_problem_3_3_1 | 1.61 | 0.33 | 0.32 | tie |
| nmse_problem_3_3_3 | 5.66 | 0.42 | 0.36 | tie |
| nonlin2 | 0.40 | 0.29 | 0.33 | tie |
| pbrt_cone_z | 0.03 | 0.03 | 0.02 | tie |
| rigidbody1 | 0.00 | 0.01 | 0.01 | tie |
| rigidbody2 | 0.07 | 0.07 | 0.07 | tie |
| sine | 0.00 | 0.00 | 0.00 | tie |
| som_setup_w | 3.15 | 0.25 | 0.26 | tie |
| sum | 0.35 | 0.14 | 0.14 | tie |
| test03_nonlin2 | 0.04 | 0.04 | 0.03 | tie |
| test04_dqmom9 | 0.64 | 0.44 | 0.48 | tie |
| test05_nonlin1_r4 | 0.76 | 0.33 | 0.36 | tie |
| triangle | 2.55 | 0.31 | 0.62 | ours |
| triangle1 | 1.13 | 0.31 | 0.45 | ours |

## Worst-case error over the box (FPTaylor)

`-` for Herbie means its output branches or left the subset, so it wasn't bounded. ours 16 / herbie 7 / tie 4 / uncompared 17

| benchmark | ours (measured) | herbie (measured) | winner |
|---|--:|--:|---|
| asymptote_c | 1.5 ulp | 1.3 ulp | herbie |
| beta_a | 1.7e-16 abs | 2.0e-16 abs | ours |
| beta_b | 2.0e-16 abs | - | - |
| cancel_sqrt_2var | 2.2 ulp | 180.0 ulp | ours |
| cancel_sqrt_shift3 | - | - | - |
| cancel_sqrt_sum | 1.8 ulp | 179.4 ulp | ours |
| complex_square_real | 6.1e-16 abs | 7.2e-16 abs | ours |
| conte_near_pole | 61.1 ulp | 125.4 ulp | ours |
| conte_x_minus_sqrt | 7.4e-17 abs | - | - |
| delta4 | 2.0e-14 abs | - | - |
| excel_x0 | 91.4 ulp | 116.1 ulp | ours |
| expand_square | 4.4e-16 abs | 4.4e-16 abs | tie |
| fastmath_dist4 | 4.7e-12 abs | 4.7e-12 abs | tie |
| floudas1 | 1.8e-13 abs | 2.4e-13 abs | ours |
| floudas3 | 7.5e-15 abs | 1.2e-14 abs | ours |
| himmilbeau | 6.1e-13 abs | 4.9e-13 abs | herbie |
| jetengine | 8.2e-12 abs | - | - |
| kahan_p9 | 3.7e-12 abs | 4.0e-12 abs | ours |
| kepler0 | 2.8 ulp | 2.2 ulp | herbie |
| kepler1 | 10.0 ulp | - | - |
| kepler2 | 30.4 ulp | 46.7 ulp | ours |
| martel_p6 | 7.2e-16 abs | 1.3e-15 abs | ours |
| matrixdeterminant | 1.8e-12 abs | - | - |
| matrixdeterminant2 | 1.8e-12 abs | - | - |
| nmse_example_3_1 | 1.6 ulp | 5.1 ulp | ours |
| nmse_example_3_6 | 126.1 ulp | - | - |
| nmse_p42_negative | 13.0 ulp | 3.4e-14 abs | herbie |
| nmse_p42_positive | 454960.6 ulp* | 3.4e-14 abs | herbie |
| nmse_problem_3_2_1_negative | 2.0 ulp | 4.6e-14 abs | tie |
| nmse_problem_3_2_1_positive | 2.0 ulp | 4.6e-14 abs | tie |
| nmse_problem_3_3_1 | 118862.9 ulp* | 83474.9 ulp* | herbie |
| nmse_problem_3_3_3 | 256918.9 ulp* | - | - |
| nonlin2 | 1.3 ulp | 1.4 ulp | ours |
| pbrt_cone_z | 2.2e-16 abs | 1.7e-16 abs | herbie |
| rigidbody1 | 1.4e-13 abs | 2.5e-13 abs | ours |
| rigidbody2 | 1.6e-11 abs | - | - |
| sine | 4.2e-16 abs | 4.2e-16 abs | ours |
| som_setup_w | 9.6e-17 abs | - | - |
| sum | 0.8 ulp | - | - |
| test03_nonlin2 | 3.5e-16 abs | - | - |
| test04_dqmom9 | 4.0e-10 abs | - | - |
| test05_nonlin1_r4 | 0.8 ulp | 601032842.2 ulp | ours |
| triangle | 19.3 ulp | - | - |
| triangle1 | 4.2 ulp | - | - |
