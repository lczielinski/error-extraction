import daisy.lang._
import Real._

object sum {
  def f(x0: Real, x1: Real, x2: Real): Real = {
    require(1.0 <= x0 && x0 <= 2.0 && 1.0 <= x1 && x1 <= 2.0 && 1.0 <= x2 && x2 <= 2.0)
    ((((x0 + x1) - x2) + ((x1 + x2) - x0)) + ((x2 + x0) - x1))
  }
}
