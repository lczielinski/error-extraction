import daisy.lang._
import Real._

object sine {
  def f(x: Real): Real = {
    require(-1.57079632679 <= x && x <= 1.57079632679)
    (((x - (((x * x) * x) / 6.0)) + (((((x * x) * x) * x) * x) / 120.0)) - (((((((x * x) * x) * x) * x) * x) * x) / 5040.0))
  }
}
