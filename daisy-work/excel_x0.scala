import daisy.lang._
import Real._

object excel_x0 {
  def f(x0: Real, x1: Real): Real = {
    require(1.0 <= x0 && x0 <= 3.0 && 0.0001 <= x1 && x1 <= 0.02)
    ((x0 / (1.0 - x1)) - x0)
  }
}
