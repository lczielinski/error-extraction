open Interval
open Opt_func


let start_interval = Array.init 3 (function
| 0 -> {low = 1.00000000000000000000e+00; high = 2.00000000000000000000e+00}
| 1 -> {low = 1.00000000000000000000e+00; high = 2.00000000000000000000e+00}
| 2 -> {low = 1.00000000000000000000e+00; high = 2.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_x2 = input_array.(0) in
  let var_x0 = input_array.(1) in
  let var_x1 = input_array.(2) in
  let ref_0 = (var_x0 -$ var_x2) in
  let ref_1 = (var_x1 +$ ref_0) in
  let ref_2 = (var_x2 -$ var_x0) in
  let ref_3 = (var_x1 +$ ref_2) in
  let ref_4 = (ref_1 +$ ref_3) in
  let ref_5 = (var_x0 -$ var_x1) in
  let ref_6 = (var_x2 +$ ref_5) in
  let ref_7 = (ref_4 +$ ref_6) in
  ((abs_I(floor_power2_I((ref_0 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))) +$ (abs_I(floor_power2_I((ref_1 +$ {low = -5.55111512312578270212e-17; high = 5.55111512312578270212e-17}))) +$ (abs_I(floor_power2_I((ref_2 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))) +$ (abs_I(floor_power2_I((ref_3 +$ {low = -5.55111512312578270212e-17; high = 5.55111512312578270212e-17}))) +$ (abs_I(floor_power2_I((ref_4 +$ {low = -5.55111512312578270212e-16; high = 5.55111512312578270212e-16}))) +$ (abs_I(floor_power2_I((ref_5 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))) +$ (abs_I(floor_power2_I((ref_6 +$ {low = -5.55111512312578270212e-17; high = 5.55111512312578270212e-17}))) +$ abs_I(floor_power2_I((ref_7 +$ {low = -1.27675647831893002149e-15; high = 1.27675647831893002149e-15})))))))))) /$ abs_I(ref_7))


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
