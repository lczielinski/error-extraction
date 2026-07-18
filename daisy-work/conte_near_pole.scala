import daisy.lang._
import Real._

object conte_near_pole {
  def f(x: Real): Real = {
    require(1.0001 <= x && x <= 1.001)
    (10.0 / (1.0 - (x * x)))
  }
}
