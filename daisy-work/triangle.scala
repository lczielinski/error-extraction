import daisy.lang._
import Real._

object triangle {
  def f(a: Real, b: Real, c: Real): Real = {
    require(9.0 <= a && a <= 9.0 && 4.71 <= b && b <= 4.89 && 4.71 <= c && c <= 4.89)
    sqrt(((((((a + b) + c) / 2.0) * ((((a + b) + c) / 2.0) - a)) * ((((a + b) + c) / 2.0) - b)) * ((((a + b) + c) / 2.0) - c)))
  }
}
