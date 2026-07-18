import daisy.lang._
import Real._

object conte_x_minus_sqrt {
  def f(x: Real, eps: Real): Real = {
    require(0.0 <= eps && eps <= 1.0 && 2.0 <= x && x <= 1000.0)
    (x - sqrt(((x * x) - eps)))
  }
}
