import daisy.lang._
import Real._

object cancel_sqrt_sum {
  def f(x: Real): Real = {
    require(-10.0 <= x && x <= 10.0)
    (x + sqrt(((x * x) + 1.0)))
  }
}
