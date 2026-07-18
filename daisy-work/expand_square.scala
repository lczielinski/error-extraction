import daisy.lang._
import Real._

object expand_square {
  def f(x: Real): Real = {
    require(-1.0 <= x && x <= 1.0)
    (((x + 1.0) * (x + 1.0)) - 1.0)
  }
}
