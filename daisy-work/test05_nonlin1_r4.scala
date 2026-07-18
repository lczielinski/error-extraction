import daisy.lang._
import Real._

object test05_nonlin1_r4 {
  def f(x: Real): Real = {
    require(1.00001 <= x && x <= 2.0)
    ((x - 1.0) / ((x * x) - 1.0))
  }
}
