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
  let ref_0 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 4.00000000000000000000e+00; high = 4.00000000000000000000e+00}) in
  let ref_1 = (var_c *$ ref_0) in
  let ref_2 = (~-$({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00})) in
  let ref_3 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ ref_2) in
  let ref_4 = (var_a *$ ref_3) in
  let ref_5 = (var_a +$ ref_4) in
  let ref_6 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_7 = (var_b *$ ref_6) in
  let ref_8 = (ref_5 -$ ref_7) in
  let ref_9 = (ref_8 *$ ref_6) in
  let ref_10 = (ref_1 -$ ref_9) in
  let ref_11 = (var_b *$ ref_10) in
  let ref_12 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_a) in
  let ref_13 = (ref_12 -$ var_a) in
  let ref_14 = (ref_13 -$ var_b) in
  let ref_15 = (var_c -$ ref_14) in
  let ref_16 = (ref_15 *$ var_a) in
  let ref_17 = (ref_16 *$ ref_0) in
  let ref_18 = (ref_13 -$ var_c) in
  let ref_19 = (ref_18 -$ var_b) in
  let ref_20 = (ref_19 *$ ref_1) in
  let ref_21 = (ref_17 -$ ref_20) in
  let ref_22 = (ref_11 +$ ref_21) in
  let ref_23 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_b) in
  let ref_24 = (ref_23 -$ var_b) in
  let ref_25 = (ref_24 -$ var_a) in
  let ref_26 = (var_c -$ ref_25) in
  let ref_27 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_c) in
  let ref_28 = (ref_27 -$ var_c) in
  let ref_29 = (ref_28 -$ var_b) in
  let ref_30 = (var_a -$ ref_29) in
  let ref_31 = (ref_30 *$ ref_26) in
  let ref_32 = (ref_31 *$ ref_0) in
  let ref_33 = (ref_32 *$ ref_22) in
  let ref_34 = sqrt_I(ref_33) in
  let ref_35 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ ref_34) in
  let ref_36 = (ref_13 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}) in
  let ref_37 = floor_power2_I(ref_36) in
  (abs_I(((ref_22 *$ (ref_0 *$ (ref_26 *$ (~-$(floor_power2_I((ref_28 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ (ref_26 *$ (~-$(floor_power2_I((ref_29 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16}))))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ (ref_26 *$ floor_power2_I((ref_30 +$ {low = -1.33226762955018784851e-15; high = 1.33226762955018784851e-15}))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ (ref_30 *$ (~-$(floor_power2_I((ref_24 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ (ref_30 *$ (~-$(floor_power2_I((ref_25 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16}))))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ (ref_30 *$ floor_power2_I((ref_26 +$ {low = -1.33226762955018784851e-15; high = 1.33226762955018784851e-15}))))) /$ ref_35)) +$ (abs_I(((ref_22 *$ (ref_0 *$ floor_power2_I((ref_31 +$ {low = -5.32907051820075202512e-14; high = 5.32907051820075202512e-14})))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (var_b *$ (~-$((ref_6 *$ floor_power2_I((ref_4 +$ {low = 0.00000000000000000000e+00; high = 0.00000000000000000000e+00}))))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (var_b *$ (~-$((ref_6 *$ floor_power2_I((ref_5 +$ {low = -2.22044604925031357389e-16; high = 2.22044604925031357389e-16}))))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (var_b *$ (~-$((ref_6 *$ floor_power2_I((ref_8 +$ {low = -6.66133814775094022862e-16; high = 6.66133814775094022862e-16}))))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (var_b *$ floor_power2_I((ref_10 +$ {low = -4.44089209850062813385e-16; high = 4.44089209850062813385e-16})))) /$ ref_35)) +$ (abs_I(((ref_32 *$ floor_power2_I((ref_11 +$ {low = -5.32907051820075297176e-15; high = 5.32907051820075297176e-15}))) /$ ref_35)) +$ (abs_I(((ref_32 *$ ((ref_0 *$ (var_a *$ (~-$(ref_37)))) +$ (~-$((ref_1 *$ ref_37))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (ref_0 *$ (var_a *$ (~-$(floor_power2_I((ref_14 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16}))))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (ref_0 *$ (var_a *$ floor_power2_I((ref_15 +$ {low = -1.33226762955018784851e-15; high = 1.33226762955018784851e-15}))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (ref_0 *$ floor_power2_I((ref_16 +$ {low = -1.77635683940025046468e-14; high = 1.77635683940025046468e-14})))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (~-$((ref_1 *$ floor_power2_I((ref_18 +$ {low = -8.88178419700125232339e-16; high = 8.88178419700125232339e-16})))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (~-$((ref_1 *$ floor_power2_I((ref_19 +$ {low = -1.33226762955018784851e-15; high = 1.33226762955018784851e-15})))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ (~-$(floor_power2_I((ref_20 +$ {low = -4.44089209850062695056e-15; high = 4.44089209850062695056e-15}))))) /$ ref_35)) +$ (abs_I(((ref_32 *$ floor_power2_I((ref_21 +$ {low = -1.24344978758017564082e-14; high = 1.24344978758017564082e-14}))) /$ ref_35)) +$ (abs_I(((ref_32 *$ floor_power2_I((ref_22 +$ {low = -2.30926389122032623517e-14; high = 2.30926389122032623517e-14}))) /$ ref_35)) +$ (abs_I((floor_power2_I((ref_33 +$ {low = -2.30215846386272581391e-12; high = 2.30215846386272581391e-12})) /$ ref_35)) +$ abs_I(floor_power2_I((ref_34 +$ {low = -4.21588689884355964987e-13; high = 4.21588689884355964987e-13})))))))))))))))))))))))))


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
