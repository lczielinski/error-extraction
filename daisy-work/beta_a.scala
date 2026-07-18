import daisy.lang._
import Real._

object beta_a {
  def f(m: Real, v: Real): Real = {
    require(0.4 <= m && m <= 0.6 && 0.2 <= v && v <= 0.25)
    ((((m * (1.0 - m)) / v) - 1.0) * m)
  }
}
