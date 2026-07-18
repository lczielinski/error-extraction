open Interval
open Opt_func


let start_interval = Array.init 9 (function
| 0 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 1 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 2 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 3 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 4 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 5 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 6 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 7 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 8 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_w2 = input_array.(0) in
  let var_a2 = input_array.(1) in
  let var_m2 = input_array.(2) in
  let var_m1 = input_array.(3) in
  let var_a1 = input_array.(4) in
  let var_w1 = input_array.(5) in
  let var_m0 = input_array.(6) in
  let var_a0 = input_array.(7) in
  let var_w0 = input_array.(8) in
  let ref_0 = (~-$(var_m0)) in
  let ref_1 = (~-$({low = 3.00000000000000000000e+00; high = 3.00000000000000000000e+00})) in
  let ref_2 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w0) in
  let ref_3 = (var_a0 *$ ref_2) in
  let ref_4 = (var_a0 *$ ref_3) in
  let ref_5 = (ref_4 *$ ref_2) in
  let ref_6 = (ref_1 *$ ref_5) in
  let ref_7 = (ref_6 *$ var_w0) in
  let ref_8 = (ref_0 *$ ref_7) in
  let ref_9 = (~-$(var_m1)) in
  let ref_10 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w1) in
  let ref_11 = (var_a1 *$ ref_10) in
  let ref_12 = (ref_11 *$ var_a1) in
  let ref_13 = (ref_12 *$ ref_10) in
  let ref_14 = (ref_1 *$ ref_13) in
  let ref_15 = (ref_14 *$ var_w1) in
  let ref_16 = (ref_9 *$ ref_15) in
  let ref_17 = (~-$(var_m2)) in
  let ref_18 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w2) in
  let ref_19 = (var_a2 *$ ref_18) in
  let ref_20 = (ref_19 *$ var_a2) in
  let ref_21 = (ref_20 *$ ref_18) in
  let ref_22 = (ref_1 *$ ref_21) in
  let ref_23 = (ref_22 *$ var_w2) in
  let ref_24 = (ref_17 *$ ref_23) in
  let ref_25 = (ref_16 +$ ref_24) in
  (abs_I((ref_0 *$ (var_w0 *$ (ref_1 *$ (ref_2 *$ (var_a0 *$ floor_power2_I((ref_3 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00})))))))) +$ (abs_I((ref_0 *$ (var_w0 *$ (ref_1 *$ (ref_2 *$ floor_power2_I((ref_4 +$ {low = -7.27595761418342751891e-12; high = 7.27595761418342751891e-12}))))))) +$ (abs_I((ref_0 *$ (var_w0 *$ (ref_1 *$ floor_power2_I((ref_5 +$ {low = -1.45519152283668560418e-06; high = 1.45519152283668560418e-06})))))) +$ (abs_I((ref_0 *$ (var_w0 *$ floor_power2_I((ref_6 +$ {low = -7.22659751772880723606e-06; high = 7.22659751772880723606e-06}))))) +$ (abs_I((ref_0 *$ floor_power2_I((ref_7 +$ {low = -9.13394615054130723606e-06; high = 9.13394615054130723606e-06})))) +$ (abs_I(floor_power2_I((ref_8 +$ {low = -1.10412947833538072361e-05; high = 1.10412947833538072361e-05}))) +$ (abs_I((ref_9 *$ (var_w1 *$ (ref_1 *$ (ref_10 *$ (var_a1 *$ floor_power2_I((ref_11 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00})))))))) +$ (abs_I((ref_9 *$ (var_w1 *$ (ref_1 *$ (ref_10 *$ floor_power2_I((ref_12 +$ {low = -7.27595761418342751891e-12; high = 7.27595761418342751891e-12}))))))) +$ (abs_I((ref_9 *$ (var_w1 *$ (ref_1 *$ floor_power2_I((ref_13 +$ {low = -1.45519152283668560418e-06; high = 1.45519152283668560418e-06})))))) +$ (abs_I((ref_9 *$ (var_w1 *$ floor_power2_I((ref_14 +$ {low = -7.22659751772880723606e-06; high = 7.22659751772880723606e-06}))))) +$ (abs_I((ref_9 *$ floor_power2_I((ref_15 +$ {low = -9.13394615054130723606e-06; high = 9.13394615054130723606e-06})))) +$ (abs_I(floor_power2_I((ref_16 +$ {low = -1.10412947833538072361e-05; high = 1.10412947833538072361e-05}))) +$ (abs_I((ref_17 *$ (var_w2 *$ (ref_1 *$ (ref_18 *$ (var_a2 *$ floor_power2_I((ref_19 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00})))))))) +$ (abs_I((ref_17 *$ (var_w2 *$ (ref_1 *$ (ref_18 *$ floor_power2_I((ref_20 +$ {low = -7.27595761418342751891e-12; high = 7.27595761418342751891e-12}))))))) +$ (abs_I((ref_17 *$ (var_w2 *$ (ref_1 *$ floor_power2_I((ref_21 +$ {low = -1.45519152283668560418e-06; high = 1.45519152283668560418e-06})))))) +$ (abs_I((ref_17 *$ (var_w2 *$ floor_power2_I((ref_22 +$ {low = -7.22659751772880723606e-06; high = 7.22659751772880723606e-06}))))) +$ (abs_I((ref_17 *$ floor_power2_I((ref_23 +$ {low = -9.13394615054130723606e-06; high = 9.13394615054130723606e-06})))) +$ (abs_I(floor_power2_I((ref_24 +$ {low = -1.10412947833538072361e-05; high = 1.10412947833538072361e-05}))) +$ (abs_I(floor_power2_I((ref_25 +$ {low = -2.58972868323326178602e-05; high = 2.58972868323326178602e-05}))) +$ abs_I(floor_power2_I(((ref_8 +$ ref_25) +$ {low = -4.26606275141239301785e-05; high = 4.26606275141239301785e-05}))))))))))))))))))))))


let _ =
  let x_tol = size_max_X start_interval *. 0.000000e+00 +. 1.000000e-02 in
  let upper_bound, lower_bound, c = Opt0.opt f_X start_interval x_tol (1.000000e-02) (1.000000e-02) (1000000) in
  let () = Printf.printf "iter_max = %d\n" c in
  let () = Printf.printf "max = %0.20e\n" upper_bound in
  let () = Printf.printf "lower_max = %0.20e\n" lower_bound in
  let () = Printf.printf "iter_min = 0\n" in
  let () = Printf.printf "min = 0\n" in
  let () = Printf.printf "lower_min = 0\n" in
  flush stdout
