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
  ({low = 1.51200000000000000000e+03; high = 1.51200000000000000000e+03} /$ ({low = 2.00000000000000000000e+00; high = 2.00000000000000000000e+00} *$ sqrt_I((((ref_3 *$ (ref_3 -$ var_a)) *$ (ref_3 -$ var_b)) *$ (ref_3 -$ var_c)))))


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
