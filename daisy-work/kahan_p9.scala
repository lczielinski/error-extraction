import daisy.lang._
import Real._

object kahan_p9 {
  def f(x: Real, y: Real): Real = {
    require(0.001 <= x && x <= 1.0 && -1.0 <= y && y <= 1.0)
    (((x - y) * (x + y)) / ((x * x) + (y * y)))
  }
}
