import daisy.lang._
import Real._

object pbrt_cone_z {
  def f(ux: Real, maxCos: Real): Real = {
    require(0.0 <= maxCos && maxCos <= 1.0 && 2.328306437e-10 <= ux && ux <= 1.0)
    ((1.0 - ux) + (ux * maxCos))
  }
}
