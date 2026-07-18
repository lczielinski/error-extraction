open Interval
open Opt_func


let start_interval = Array.init 3 (function
| 0 -> {low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+02}
| 1 -> {low = -1.00000000000000000000e+02; high = -1.00000000000000000000e+00}
| 2 -> {low = -1.00000000000000000000e+02; high = 0.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_a = input_array.(0) in
  let var_c = input_array.(1) in
  let var_b = input_array.(2) in
  let ref_0 = (var_a +$ var_a) in
  let ref_1 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ ref_0) in
  let ref_2 = (~-$({low = 4.00000000000000000000e+00; high = 4.00000000000000000000e+00})) in
  let ref_3 = (ref_2 *$ var_a) in
  let ref_4 = (var_c *$ ref_3) in
  let ref_5 = (ref_3 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}) in
  let ref_6 = floor_power2_I(ref_5) in
  let ref_7 = (var_c *$ ref_6) in
  let ref_8 = (var_b *$ var_b) in
  let ref_9 = (ref_4 +$ ref_8) in
  let ref_10 = sqrt_I(ref_9) in
  let ref_11 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ ref_10) in
  let ref_12 = (var_b -$ ref_10) in
  let ref_13 = (ref_12 *$ ref_12) in
  let ref_14 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ ref_12) in
  let ref_15 = (ref_4 +$ {low = -2.84217094304040114738e-12; high = 2.84217094304040114738e-12}) in
  let ref_16 = floor_power2_I(ref_15) in
  let ref_17 = (ref_4 *$ ref_14) in
  (abs_I((ref_1 *$ ((ref_4 *$ (~-$(((~-$((ref_7 /$ ref_11))) /$ ref_13)))) +$ (ref_14 *$ ref_7)))) +$ (abs_I((ref_1 *$ ((ref_4 *$ (~-$(((~-$((ref_16 /$ ref_11))) /$ ref_13)))) +$ (ref_14 *$ ref_16)))) +$ (abs_I((ref_1 *$ (ref_4 *$ (~-$(((~-$((floor_power2_I((ref_8 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00})) /$ ref_11))) /$ ref_13)))))) +$ (abs_I((ref_1 *$ (ref_4 *$ (~-$(((~-$((floor_power2_I((ref_9 +$ {low = -7.38964445190504354865e-12; high = 7.38964445190504354865e-12})) /$ ref_11))) /$ ref_13)))))) +$ (abs_I((ref_1 *$ (ref_4 *$ (~-$(((~-$(floor_power2_I((ref_10 +$ {low = -2.75690581475108905555e-12; high = 2.75690581475108905555e-12})))) /$ ref_13)))))) +$ (abs_I((ref_1 *$ (ref_4 *$ (~-$((floor_power2_I((ref_12 +$ {low = -2.77111666946629105926e-12; high = 2.77111666946629105926e-12})) /$ ref_13)))))) +$ (abs_I((ref_1 *$ floor_power2_I((ref_17 +$ {low = -2.79953837876338319539e-08; high = 2.79953837876338319539e-08})))) +$ (abs_I((ref_17 *$ (~-$((floor_power2_I((ref_0 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00})) /$ (ref_0 *$ ref_0)))))) +$ abs_I(floor_power2_I(((ref_17 *$ ref_1) +$ {low = -1.40696556620947981855e-08; high = 1.40696556620947981855e-08})))))))))))


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
