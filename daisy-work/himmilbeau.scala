import daisy.lang._
import Real._

object himmilbeau {
  def f(x1: Real, x2: Real): Real = {
    require(-5.0 <= x1 && x1 <= 5.0 && -5.0 <= x2 && x2 <= 5.0)
    (((((x1 * x1) + x2) - 11.0) * (((x1 * x1) + x2) - 11.0)) + (((x1 + (x2 * x2)) - 7.0) * ((x1 + (x2 * x2)) - 7.0)))
  }
}
