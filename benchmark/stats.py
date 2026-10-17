import math
import random


def wilson(k, n, z=1.95996):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, c - m), min(1.0, c + m)


def paired_bootstrap(fn, n, b=10000, seed=7):
    """fn(indices) -> statistic on a resample of task indices. Returns (point, lo, hi): 95% percentile CI."""
    rnd = random.Random(seed)
    point = fn(list(range(n)))
    vals = sorted(fn([rnd.randrange(n) for _ in range(n)]) for _ in range(b))
    return point, vals[int(0.025 * b)], vals[int(0.975 * b) - 1]
