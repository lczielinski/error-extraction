import daisy.lang._
import Real._

object nmse_p42_positive {
  def f(a: Real, b: Real, c: Real): Real = {
    require(1.0 <= a && a <= 100.0 && -100.0 <= b && b <= 100.0 && -100.0 <= c && c <= -1.0)
    (((-(b)) + sqrt(((b * b) - (4.0 * (a * c))))) / (2.0 * a))
  }
}
