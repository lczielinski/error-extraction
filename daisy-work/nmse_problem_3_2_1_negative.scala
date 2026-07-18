import daisy.lang._
import Real._

object nmse_problem_3_2_1_negative {
  def f(a: Real, b2: Real, c: Real): Real = {
    require(1.0 <= a && a <= 100.0 && -100.0 <= b2 && b2 <= 100.0 && -100.0 <= c && c <= -1.0)
    (((-(b2)) - sqrt(((b2 * b2) - (a * c)))) / a)
  }
}
