import daisy.lang._
import Real._

object nmse_problem_3_3_1 {
  def f(x: Real): Real = {
    require(0.1 <= x && x <= 100.0)
    ((1.0 / (x + 1.0)) - (1.0 / x))
  }
}
