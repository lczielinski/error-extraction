import daisy.lang._
import Real._

object test03_nonlin2 {
  def f(x: Real, y: Real): Real = {
    require(0.0 <= x && x <= 1.0 && -1.0 <= y && y <= -0.1)
    ((x + y) / (x - y))
  }
}
