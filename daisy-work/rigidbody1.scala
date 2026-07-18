import daisy.lang._
import Real._

object rigidbody1 {
  def f(x1: Real, x2: Real, x3: Real): Real = {
    require(-15.0 <= x1 && x1 <= 15.0 && -15.0 <= x2 && x2 <= 15.0 && -15.0 <= x3 && x3 <= 15.0)
    ((((-((x1 * x2))) - ((2.0 * x2) * x3)) - x1) - x3)
  }
}
