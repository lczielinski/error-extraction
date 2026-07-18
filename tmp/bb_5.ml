open Interval
open Opt_func


let start_interval = Array.init 3 (function
| 0 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| 1 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| 2 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_b = input_array.(0) in
  let var_a = input_array.(1) in
  let var_c = input_array.(2) in
  let ref_0 = (var_a +$ var_b) in
  let ref_1 = (ref_0 +$ var_c) in
  let ref_2 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_3 = (ref_1 *$ ref_2) in
  let ref_4 = (ref_3 -$ var_a) in
  let ref_5 = (ref_3 *$ ref_4) in
  let ref_6 = (ref_3 -$ var_b) in
  let ref_7 = (ref_5 *$ ref_6) in
  let ref_8 = (ref_0 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}) in
  let ref_9 = floor_power2_I(ref_8) in
  let ref_10 = (ref_2 *$ ref_9) in
  let ref_11 = (ref_3 -$ var_c) in
  let ref_12 = (ref_7 *$ ref_11) in
  let ref_13 = sqrt_I(ref_12) in
  let ref_14 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ ref_13) in
  let ref_15 = (ref_1 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16}) in
  let ref_16 = floor_power2_I(ref_15) in
  let ref_17 = (ref_2 *$ ref_16) in
  ((abs_I((((ref_7 *$ ref_10) +$ (ref_11 *$ ((ref_5 *$ ref_10) +$ (ref_6 *$ ((ref_3 *$ ref_10) +$ (ref_4 *$ ref_10)))))) /$ ref_14)) +$ (abs_I((((ref_7 *$ ref_17) +$ (ref_11 *$ ((ref_5 *$ ref_17) +$ (ref_6 *$ ((ref_3 *$ ref_17) +$ (ref_4 *$ ref_17)))))) /$ ref_14)) +$ (abs_I(((ref_11 *$ (ref_6 *$ (ref_3 *$ floor_power2_I((ref_4 +$ {low = -1.33226762955018804572e-15; high = 1.33226762955018804572e-15}))))) /$ ref_14)) +$ (abs_I(((ref_11 *$ (ref_6 *$ floor_power2_I((ref_5 +$ {low = -2.93098878501041389781e-14; high = 2.93098878501041389781e-14})))) /$ ref_14)) +$ (abs_I(((ref_11 *$ (ref_5 *$ floor_power2_I((ref_6 +$ {low = -1.33226762955018804572e-15; high = 1.33226762955018804572e-15})))) /$ ref_14)) +$ (abs_I(((ref_11 *$ floor_power2_I((ref_7 +$ {low = -3.46389583683048992073e-13; high = 3.46389583683048992073e-13}))) /$ ref_14)) +$ (abs_I(((ref_7 *$ floor_power2_I((ref_11 +$ {low = -1.33226762955018804572e-15; high = 1.33226762955018804572e-15}))) /$ ref_14)) +$ (abs_I((floor_power2_I((ref_12 +$ {low = -3.01625391330162690461e-12; high = 3.01625391330162690461e-12})) /$ ref_14)) +$ abs_I(floor_power2_I((ref_13 +$ {low = -5.40604598124191931218e-13; high = 5.40604598124191931218e-13}))))))))))) /$ abs_I(ref_13))


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
