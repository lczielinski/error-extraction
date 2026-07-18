open Interval
open Opt_func


let start_interval = Array.init 9 (function
| 0 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 1 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 2 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 3 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 4 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 5 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 6 -> {low = -1.00000000000000000000e+00; high = 1.00000000000000000000e+00}
| 7 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| 8 -> {low = 9.99999999999999912396e-06; high = 1.00000000000000000000e+00}
| _ -> failwith "Out of boundaries"
)

let f_X input_array = 
  let var_w0 = input_array.(0) in
  let var_a0 = input_array.(1) in
  let var_m0 = input_array.(2) in
  let var_w1 = input_array.(3) in
  let var_a1 = input_array.(4) in
  let var_m1 = input_array.(5) in
  let var_m2 = input_array.(6) in
  let var_a2 = input_array.(7) in
  let var_w2 = input_array.(8) in
  let ref_0 = (~-$({low = 3.00000000000000000000e+00; high = 3.00000000000000000000e+00})) in
  let ref_1 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w0) in
  let ref_2 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w1) in
  let ref_3 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ var_w2) in
  (((~-$(var_m0)) *$ ((ref_0 *$ ((var_a0 *$ (var_a0 *$ ref_1)) *$ ref_1)) *$ var_w0)) +$ (((~-$(var_m1)) *$ ((ref_0 *$ (((var_a1 *$ ref_2) *$ var_a1) *$ ref_2)) *$ var_w1)) +$ ((~-$(var_m2)) *$ ((ref_0 *$ (((var_a2 *$ ref_3) *$ var_a2) *$ ref_3)) *$ var_w2))))


let _ =
  let x_tol = size_max_X start_interval *. 0.000000e+00 +. 1.000000e-02 in
  let upper_bound, lower_bound, c = Opt0.opt f_X start_interval x_tol (1.000000e-02) (1.000000e-02) (1000000) in
  let () = Printf.printf "iter_max = %d\n" c in
  let () = Printf.printf "max = %0.20e\n" upper_bound in
  let () = Printf.printf "lower_max = %0.20e\n" lower_bound in
  let upper_bound, lower_bound, c = Opt0.opt (fun x -> ~-$ (f_X x)) start_interval x_tol (1.000000e-02) (1.000000e-02) (1000000) in
  let () = Printf.printf "iter_min = %d\n" c in
  let () = Printf.printf "min = %0.20e\n" (-. upper_bound) in
  let () = Printf.printf "lower_min = %0.20e\n" (-. lower_bound) in
  flush stdout
