import daisy.lang._
import Real._

object nmse_problem_3_3_3 {
  def f(x: Real): Real = {
    require(2.0 <= x && x <= 100.0)
    (((1.0 / (x + 1.0)) - (2.0 / x)) + (1.0 / (x - 1.0)))
  }
}
