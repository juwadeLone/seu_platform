"""Tabulated spectrum with log-log interpolation and trapezoid integrals.

A Spectrum is a 1-D table y(x) with x strictly increasing. Units are carried
by the caller; the code only integrates. Typical uses:
  - differential LET flux   x: MeV*cm^2/mg, y: cm^-2 s^-1 (MeV*cm^2/mg)^-1
  - differential proton flux x: MeV,        y: cm^-2 s^-1 MeV^-1
"""
import math


class Spectrum:
    def __init__(self, xs, ys):
        self.xs = [float(v) for v in xs]
        self.ys = [float(v) for v in ys]
        if len(self.xs) != len(self.ys) or len(self.xs) < 2:
            raise ValueError("spectrum needs >=2 aligned points")
        if any(self.xs[k+1] <= self.xs[k] for k in range(len(self.xs)-1)):
            raise ValueError("x must be strictly increasing")
        if any(y < 0 for y in self.ys):
            raise ValueError("flux values must be >= 0")

    def __call__(self, x):
        if x <= self.xs[0] or x >= self.xs[-1]:
            return 0.0
        lo, hi = 0, len(self.xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        x0, x1 = self.xs[lo], self.xs[lo+1]
        y0, y1 = self.ys[lo], self.ys[lo+1]
        f = (x - x0) / (x1 - x0)
        # log-log interpolation keeps power laws exact
        lx0, lx1 = math.log(x0), math.log(x1)
        g = (math.log(x) - lx0) / (lx1 - lx0)
        if y0 > 0 and y1 > 0:
            return math.exp(math.log(y0) + g * (math.log(y1) - math.log(y0)))
        return y0 + f * (y1 - y0)

    def integrate_against(self, weight_fn):
        """Integral of y(x)*weight_fn(x) dx by trapezoid over table points."""
        total = 0.0
        for k in range(len(self.xs) - 1):
            x0, x1 = self.xs[k], self.xs[k+1]
            w0 = self.ys[k] * weight_fn(x0)
            w1 = self.ys[k+1] * weight_fn(x1)
            total += 0.5 * (w0 + w1) * (x1 - x0)
        return total

    def total_flux(self):
        return self.integrate_against(lambda x: 1.0)

    def scale(self, factor):
        return Spectrum(self.xs, [factor * y for y in self.ys])

    def as_rows(self):
        return list(zip(self.xs, self.ys))
