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
  let ref_0 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_c) in
  let ref_1 = (ref_0 -$ var_c) in
  let ref_2 = (ref_1 -$ var_b) in
  let ref_3 = (var_a -$ ref_2) in
  let ref_4 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_b) in
  let ref_5 = (ref_4 -$ var_b) in
  let ref_6 = (ref_5 -$ var_a) in
  let ref_7 = (var_c -$ ref_6) in
  let ref_8 = (ref_3 *$ ref_7) in
  let ref_9 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 4.00000000000000000000e+00; high = 4.00000000000000000000e+00}) in
  let ref_10 = (ref_8 *$ ref_9) in
  let ref_11 = (var_c *$ ref_9) in
  let ref_12 = ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ {low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}) in
  let ref_13 = ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ var_a) in
  let ref_14 = (ref_13 -$ var_a) in
  ((ref_10 *$ (var_b *$ (~-$({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00})))) /$ ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ sqrt_I((ref_10 *$ ((var_b *$ (ref_11 -$ (((var_a +$ (var_a *$ ({low = 1.00000000000000000000e+00; high = 1.00000000000000000000e+00} /$ (~-$({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00}))))) -$ (var_b *$ ref_12)) *$ ref_12))) +$ ((((var_c -$ (ref_14 -$ var_b)) *$ var_a) *$ ref_9) -$ (((ref_14 -$ var_c) -$ var_b) *$ ref_11)))))))


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
