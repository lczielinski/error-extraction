import daisy.lang._
import Real._

object nonlin2 {
  def f(x: Real, y: Real): Real = {
    require(1.001 <= x && x <= 2.0 && 1.001 <= y && y <= 2.0)
    (((x * y) - 1.0) / (((x * y) * (x * y)) - 1.0))
  }
}
