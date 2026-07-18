import daisy.lang._
import Real._

object triangle1 {
  def f(a: Real, b: Real, c: Real): Real = {
    require(6.0 <= a && a <= 8.0 && 6.0 <= b && b <= 8.0 && 6.0 <= c && c <= 8.0)
    sqrt(((((((a + b) + c) / 2.0) * ((((a + b) + c) / 2.0) - a)) * ((((a + b) + c) / 2.0) - b)) * ((((a + b) + c) / 2.0) - c)))
  }
}
