# Cost-based extraction vs reference (FPTaylor worst-case bounds)

predicted = this repo's cost bound; measured/reference = FPTaylor on the
extracted program / the original, same box. All in ulps of 2^-52;
`*` = derived from the absolute bound; `-` = value range straddles zero.

- improved: **12/44**
- improved (abs): **14/44**
- no-change (abs): **6/44**
- worse: **2/44**
- worse (abs): **10/44**

| benchmark | predicted | measured | reference | vs reference |
|---|--:|--:|--:|---|
| asymptote_c | 3.7 | 2.2 | 57.7 | improved |
| beta_a | - | - | - | improved (abs) |
| beta_b | - | - | - | improved (abs) |
| cancel_sqrt_2var | 52.3 | 2.2 | 180.0 | improved |
| cancel_sqrt_shift3 | - | 590.2 | 311.9 | worse |
| cancel_sqrt_sum | 26.8 | 1.8 | 179.4 | improved |
| complex_square_real | 1.5 | - | - | improved (abs) |
| conte_near_pole | 2.0 | 61.1 | 25062.1 | improved |
| conte_x_minus_sqrt | - | - | - | no-change (abs) |
| delta4 | - | - | - | improved (abs) |
| excel_x0 | 1.5 | 126.8 | - | improved (abs) |
| expand_square | 1.0 | - | - | improved (abs) |
| fastmath_dist4 | - | - | - | improved (abs) |
| floudas1 | - | - | - | improved (abs) |
| floudas3 | - | - | - | improved (abs) |
| himmilbeau | - | - | - | improved (abs) |
| jetengine | - | - | - | worse (abs) |
| kahan_p9 | 1000002.5 | - | - | no-change (abs) |
| kepler0 | - | 4.2 | 5.4 | improved |
| kepler1 | - | 11.8 | 17.2 | improved |
| kepler2 | - | 37.3 | 75.6 | improved |
| martel_p6 | - | - | - | improved (abs) |
| matrixdeterminant | - | - | - | worse (abs) |
| matrixdeterminant2 | - | - | - | worse (abs) |
| nmse_example_3_1 | 1.8 | 1.6 | 193.8 | improved |
| nmse_example_3_6 | 3.3 | 111585.6 | - | worse (abs) |
| nmse_p42_negative | - | - | - | worse (abs) |
| nmse_p42_positive | - | - | - | worse (abs) |
| nmse_problem_3_2_1_negative | 5002.8 | 509098.5* | - | no-change (abs) |
| nmse_problem_3_2_1_positive | - | - | - | no-change (abs) |
| nmse_problem_3_3_1 | 1.5 | 118862.9* | - | worse (abs) |
| nmse_problem_3_3_3 | - | - | - | worse (abs) |
| nonlin2 | 1.5 | 1.3 | 29958.8 | improved |
| pbrt_cone_z | - | - | - | no-change (abs) |
| rigidbody1 | - | - | - | worse (abs) |
| rigidbody2 | - | - | - | improved (abs) |
| sine | 4.5 | - | - | improved (abs) |
| som_setup_w | - | - | - | improved (abs) |
| sum | 1.0 | 0.8 | 2.3 | improved |
| test03_nonlin2 | 1.5 | - | - | no-change (abs) |
| test04_dqmom9 | - | - | - | worse (abs) |
| test05_nonlin1_r4 | 1.0 | 0.8 | 15597717409.8 | improved |
| triangle | 24.0 | 19.0 | 17.6 | worse |
| triangle1 | 24.3 | 4.0 | 5.2 | improved |
