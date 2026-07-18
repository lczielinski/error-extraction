import daisy.lang._
import Real._

object asymptote_c {
  def f(x: Real): Real = {
    require(2.0 <= x && x <= 100.0)
    ((x / (x + 1.0)) - ((x + 1.0) / (x - 1.0)))
  }
}
