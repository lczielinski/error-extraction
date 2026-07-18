import daisy.lang._
import Real._

object complex_square_real {
  def f(re: Real, im: Real): Real = {
    require(1.0 <= im && im <= 2.0 && 1.0 <= re && re <= 2.0)
    ((re * re) - (im * im))
  }
}
