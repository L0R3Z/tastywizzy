import math


class Smoother:
    """Lissage exponentiel basé sur le temps. La teinte prend le chemin le plus court."""

    def __init__(self, tau):
        self.tau = tau
        self.h = self.s = self.k = self.v = None

    def update(self, h, s, k, v, dt):
        """h peut être None (aucune teinte) : la teinte lissée est alors conservée."""
        if self.k is None:
            self.h, self.s, self.k, self.v = (0.0 if h is None else h), s, k, v
            return self.h, self.s, self.k, self.v
        a = 1 - math.exp(-dt / self.tau) if self.tau > 0 else 1.0
        if h is not None:
            dh = ((h - self.h + 0.5) % 1.0) - 0.5
            self.h = (self.h + a * dh) % 1.0
            self.s += a * (s - self.s)
        self.k += a * (k - self.k)
        self.v += a * (v - self.v)
        return self.h, self.s, self.k, self.v
