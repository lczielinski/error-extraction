# Cost-based extraction vs reference (FPTaylor worst-case bounds)

predicted = this repo's cost bound; measured/reference = FPTaylor on the
extracted program / the original, same box. Relative error in ulps of
2^-52; rows where the value range straddles zero (relative error
undefined) compare absolute error instead, in scientific notation,
and say `(abs)`. `*` = crude bound derived from the absolute one.

- improved: **12/44**
- improved (abs): **19/44**
- no-change (abs): **4/44**
- unmeasurable: **1/44**
- worse: **1/44**
- worse (abs): **7/44**

| benchmark | predicted | measured | reference | vs reference |
|---|--:|--:|--:|---|
| asymptote_c | 2.2 | 1.5 | 57.7 | improved |
| beta_a | 4.0e-16 | 1.7e-16 | 2.2e-16 | improved (abs) |
| beta_b | 4.5e-16 | 2.0e-16 | 2.5e-16 | improved (abs) |
| cancel_sqrt_2var | 52.3 | 2.2 | 180.0 | improved |
| cancel_sqrt_shift3 | 5.0e-14 | - | 2.9e-15 | unmeasurable |
| cancel_sqrt_sum | 26.8 | 1.8 | 179.4 | improved |
| complex_square_real | 1.2e-15 | 6.1e-16 | 6.7e-16 | improved (abs) |
| conte_near_pole | 2.0 | 61.1 | 25062.1 | improved |
| conte_x_minus_sqrt | 9.2e-12 | 7.4e-17 | 1.4e-13 | improved (abs) |
| delta4 | 3.7e-14 | 2.0e-14 | 5.8e-14 | improved (abs) |
| excel_x0 | 1.4e-17 | 8.1e-18 | 4.0e-16 | improved (abs) |
| expand_square | 6.7e-16 | 4.4e-16 | 1.1e-15 | improved (abs) |
| fastmath_dist4 | 6.6e-12 | 4.7e-12 | 6.5e-12 | improved (abs) |
| floudas1 | 3.0e-13 | 1.8e-13 | 2.9e-13 | improved (abs) |
| floudas3 | 1.2e-14 | 7.5e-15 | 1.2e-14 | improved (abs) |
| himmilbeau | 2.0e-12 | 6.1e-13 | 5.9e-13 | worse (abs) |
| jetengine | - | 8.2e-12 | 8.7e-12 | improved (abs) |
| kahan_p9 | 4.4e-04 | 3.7e-12 | 4.0e-12 | improved (abs) |
| kepler0 | 19.7 | 2.8 | 5.4 | improved |
| kepler1 | - | 10.0 | 17.2 | improved |
| kepler2 | - | 30.4 | 75.6 | improved |
| martel_p6 | 1.6e-15 | 7.2e-16 | 5.8e-15 | improved (abs) |
| matrixdeterminant | 3.1e-12 | 1.8e-12 | 1.6e-12 | worse (abs) |
| matrixdeterminant2 | 3.1e-12 | 1.8e-12 | 1.6e-12 | worse (abs) |
| nmse_example_3_1 | 1.8 | 1.6 | 193.8 | improved |
| nmse_example_3_6 | 1.9e-08 | 3.1e-13 | 8.4e-14 | worse (abs) |
| nmse_p42_negative | 3.9e-08 | 3.4e-14 | 2.3e-14 | worse (abs) |
| nmse_p42_positive | 3.9e-08 | 3.4e-14 | 2.3e-14 | worse (abs) |
| nmse_problem_3_2_1_negative | 4.5e-10 | 4.6e-14 | 4.6e-14 | no-change (abs) |
| nmse_problem_3_2_1_positive | 4.5e-10 | 4.6e-14 | 4.6e-14 | no-change (abs) |
| nmse_problem_3_3_1 | 9.5e-14 | 2.6e-15 | 1.9e-15 | worse (abs) |
| nmse_problem_3_3_3 | 2.6e-15 | 1.1e-16 | 4.1e-16 | improved (abs) |
| nonlin2 | 1.5 | 1.3 | 29958.8 | improved |
| pbrt_cone_z | 3.3e-16 | 2.2e-16 | 2.2e-16 | no-change (abs) |
| rigidbody1 | 2.3e-13 | 1.4e-13 | 2.1e-13 | improved (abs) |
| rigidbody2 | 2.7e-11 | 1.6e-11 | 2.3e-11 | improved (abs) |
| sine | 8.6e-16 | 4.2e-16 | 4.4e-16 | improved (abs) |
| som_setup_w | 2.0e-16 | 9.6e-17 | 6.0e-16 | improved (abs) |
| sum | 1.0 | 0.8 | 2.3 | improved |
| test03_nonlin2 | 2.4e-14 | 3.5e-16 | 3.5e-16 | no-change (abs) |
| test04_dqmom9 | 5.7e-10 | 4.0e-10 | 1.7e-05 | improved (abs) |
| test05_nonlin1_r4 | 1.0 | 0.8 | 15597717409.8 | improved |
| triangle | 22.4 | 19.3 | 17.6 | worse |
| triangle1 | 14.2 | 4.2 | 5.2 | improved |
