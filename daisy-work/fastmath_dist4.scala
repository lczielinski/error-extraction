import daisy.lang._
import Real._

object fastmath_dist4 {
  def f(d1: Real, d2: Real, d3: Real, d4: Real): Real = {
    require(1.0 <= d1 && d1 <= 100.0 && 1.0 <= d2 && d2 <= 100.0 && 1.0 <= d3 && d3 <= 100.0 && 1.0 <= d4 && d4 <= 100.0)
    ((((d1 * d2) - (d1 * d3)) + (d4 * d1)) - (d1 * d1))
  }
}
