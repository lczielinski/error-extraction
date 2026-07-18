import daisy.lang._
import Real._

object cancel_sqrt_shift3 {
  def f(x: Real): Real = {
    require(-10.0 <= x && x <= 10.0)
    ((x - 3.0) + sqrt((((x - 3.0) * (x - 3.0)) + 1.0)))
  }
}
