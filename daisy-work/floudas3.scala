import daisy.lang._
import Real._

object floudas3 {
  def f(x1: Real, x2: Real): Real = {
    require(0.0 <= x1 && x1 <= 2.0 && 0.0 <= x2 && x2 <= 3.0)
    (((-12.0 * x1) - (7.0 * x2)) + (x2 * x2))
  }
}
