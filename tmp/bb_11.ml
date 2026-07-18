open Interval
open Opt_func


let start_interval = Array.init 3 (function
| 0 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| 1 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| 2 -> {low = 6.00000000000000000000e+00; high = 8.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_c = input_array.(0) in
  let var_a = input_array.(1) in
  let var_b = input_array.(2) in
  let ref_0 = (var_a +$ var_b) in
  let ref_1 = (ref_0 +$ var_c) in
  let ref_2 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_3 = (var_c *$ ref_2) in
  let ref_4 = (ref_3 -$ var_a) in
  let ref_5 = (ref_4 *$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_6 = (ref_0 +$ ref_5) in
  let ref_7 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 4.00000000000000000000e+00; high = 4.00000000000000000000e+00}) in
  let ref_8 = (ref_6 *$ ref_7) in
  let ref_9 = (ref_1 *$ ref_8) in
  let ref_10 = (ref_3 -$ var_c) in
  let ref_11 = (ref_10 *$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_12 = (ref_11 +$ ref_0) in
  let ref_13 = (ref_12 *$ ref_2) in
  let ref_14 = (ref_3 -$ var_b) in
  let ref_15 = (ref_14 *$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_16 = (ref_15 +$ ref_0) in
  let ref_17 = (ref_16 *$ ref_2) in
  let ref_18 = (ref_17 *$ ref_13) in
  let ref_19 = (ref_18 *$ ref_9) in
  let ref_20 = sqrt_I(ref_19) in
  let ref_21 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ ref_20) in
  let ref_22 = (ref_0 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}) in
  let ref_23 = floor_power2_I(ref_22) in
  let ref_24 = (ref_2 *$ ref_23) in
  ((abs_I(((ref_9 *$ (ref_13 *$ (ref_2 *$ ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ floor_power2_I((ref_14 +$ {low = -2.22507385850720138309e-308; high = 2.22507385850720138309e-308})))))) /$ ref_21)) +$ (abs_I((((ref_18 *$ ((ref_1 *$ (ref_7 *$ ref_23)) +$ (ref_8 *$ ref_23))) +$ (ref_9 *$ ((ref_17 *$ ref_24) +$ (ref_13 *$ ref_24)))) /$ ref_21)) +$ (abs_I(((ref_9 *$ (ref_13 *$ (ref_2 *$ floor_power2_I((ref_16 +$ {low = -1.77635683940025085911e-15; high = 1.77635683940025085911e-15}))))) /$ ref_21)) +$ (abs_I(((ref_9 *$ (ref_17 *$ (ref_2 *$ ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ floor_power2_I((ref_10 +$ {low = -2.22507385850720138309e-308; high = 2.22507385850720138309e-308})))))) /$ ref_21)) +$ (abs_I(((ref_9 *$ (ref_17 *$ (ref_2 *$ floor_power2_I((ref_12 +$ {low = -1.77635683940025085911e-15; high = 1.77635683940025085911e-15}))))) /$ ref_21)) +$ (abs_I(((ref_9 *$ floor_power2_I((ref_18 +$ {low = -1.59872115546022636484e-14; high = 1.59872115546022636484e-14}))) /$ ref_21)) +$ (abs_I(((ref_18 *$ (ref_8 *$ floor_power2_I((ref_1 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16})))) /$ ref_21)) +$ (abs_I(((ref_18 *$ (ref_1 *$ (ref_7 *$ ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ floor_power2_I((ref_4 +$ {low = -2.22507385850720138309e-308; high = 2.22507385850720138309e-308})))))) /$ ref_21)) +$ (abs_I(((ref_18 *$ (ref_1 *$ (ref_7 *$ floor_power2_I((ref_6 +$ {low = -1.77635683940025085911e-15; high = 1.77635683940025085911e-15}))))) /$ ref_21)) +$ (abs_I(((ref_18 *$ floor_power2_I((ref_9 +$ {low = -2.39808173319033875840e-14; high = 2.39808173319033875840e-14}))) /$ ref_21)) +$ (abs_I((floor_power2_I((ref_19 +$ {low = -2.52597942562715777636e-12; high = 2.52597942562715777636e-12})) /$ ref_21)) +$ abs_I(floor_power2_I((ref_20 +$ {low = -4.58892183511766778326e-13; high = 4.58892183511766778326e-13})))))))))))))) /$ abs_I(ref_20))


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
