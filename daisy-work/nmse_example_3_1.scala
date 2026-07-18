import daisy.lang._
import Real._

object nmse_example_3_1 {
  def f(x: Real): Real = {
    require(0.0001 <= x && x <= 100.0)
    (sqrt((x + 1.0)) - sqrt(x))
  }
}
