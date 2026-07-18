import daisy.lang._
import Real._

object martel_p6 {
  def f(a: Real, b: Real, c: Real, d: Real): Real = {
    require(-14.0 <= a && a <= -13.0 && -3.0 <= b && b <= -2.0 && 3.0 <= c && c <= 3.5 && 12.5 <= d && d <= 13.5)
    ((a + (b + (c + d))) * 2.0)
  }
}
