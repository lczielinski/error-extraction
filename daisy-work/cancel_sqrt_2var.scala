import daisy.lang._
import Real._

object cancel_sqrt_2var {
  def f(y: Real, x: Real): Real = {
    require(1.0 <= x && x <= 10.0 && -10.0 <= y && y <= 10.0)
    (y + sqrt(((y * y) + (x * x))))
  }
}
