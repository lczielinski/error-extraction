import daisy.lang._
import Real._

object som_setup_w {
  def f(es: Real, ca: Real, rone_es: Real): Real = {
    require(-1.0 <= ca && ca <= 1.0 && 0.0 <= es && es <= 0.1 && 1.0 <= rone_es && rone_es <= 1.05)
    ((((1.0 - (es * (ca * ca))) * rone_es) * ((1.0 - (es * (ca * ca))) * rone_es)) - 1.0)
  }
}
