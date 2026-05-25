"""
Streaming statistics for astroNS BaseNode metrics.

Provides O(1) memory replacements for the raw-list accumulators in BaseNode:
  - StreamingStats: Welford online mean/variance + min/max/sum + P2 quantiles
  - P2Quantile: Jain & Chlamtac (1985) P-squared algorithm for streaming
    quantile estimation with 5 markers, with an exact buffer for small N

Usage:
    stats = StreamingStats()
    for value in observations:
        stats.update(value)
    print(stats.to_dict())
    # {'count': 1000, 'mean': 5.02, 'std': 2.31, 'min': 0.01, 'max': 14.8,
    #  'sum': 5020.0, 'p25': 3.41, 'p75': 6.58, 'p90': 8.12}
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional


class P2Quantile:
    """
    P-squared algorithm for streaming quantile estimation.

    For small sample sizes (< EXACT_THRESHOLD), an exact sorted buffer is
    maintained for precise quantiles. Once the threshold is reached, the
    buffer is freed and the P-squared streaming estimator takes over with
    O(1) memory.

    The P2 markers are trained in parallel from observation 6 onwards, so
    by the time the exact buffer is freed the estimator is well warmed up.

    Reference: Jain, R. and Chlamtac, I. (1985). "The P2 Algorithm for
    Dynamic Calculation of Quantiles and Histograms Without Storing
    Observations." Communications of the ACM, 28(10), pp.1076-1085.
    """

    __slots__ = ("p", "count", "q", "n", "np", "dnp", "_initial", "_buffer")

    # Below this count, return exact quantile from sorted buffer.
    # 500 floats = ~4KB — negligible memory for precise small-N results.
    EXACT_THRESHOLD = 500

    def __init__(self, quantile: float):
        if not 0.0 < quantile < 1.0:
            raise ValueError(f"quantile must be in (0, 1), got {quantile}")
        self.p = quantile
        self.count = 0
        # P2 marker state
        self.q: List[float] = [0.0] * 5
        self.n: List[int] = [0] * 5
        self.np: List[float] = [0.0] * 5
        self.dnp: List[float] = [0.0, quantile / 2, quantile, (1 + quantile) / 2, 1.0]
        self._initial: List[float] = []
        # Exact buffer for small N (freed at EXACT_THRESHOLD)
        self._buffer: Optional[List[float]] = []

    def update(self, x: float) -> None:
        """Add a new observation."""
        self.count += 1

        # Keep exact buffer for small N
        if self._buffer is not None:
            self._buffer.append(x)
            if len(self._buffer) >= self.EXACT_THRESHOLD:
                self._buffer = None  # free memory, switch to P2 only

        # P2 initialization: collect first 5 observations
        if self.count <= 5:
            self._initial.append(x)
            if self.count == 5:
                self._initial.sort()
                self.q = list(self._initial)
                self.n = [1, 2, 3, 4, 5]
                self.np = [
                    1.0,
                    1.0 + 2.0 * self.p,
                    1.0 + 4.0 * self.p,
                    3.0 + 2.0 * self.p,
                    5.0,
                ]
                self._initial = []
            return

        # P2 marker update (observation 6+)
        q = self.q
        if x < q[0]:
            q[0] = x
            k = 0
        elif x < q[1]:
            k = 0
        elif x < q[2]:
            k = 1
        elif x < q[3]:
            k = 2
        elif x <= q[4]:
            k = 3
        else:
            q[4] = x
            k = 3

        n = self.n
        for j in range(k + 1, 5):
            n[j] += 1

        np_ = self.np
        dnp = self.dnp
        for j in range(5):
            np_[j] += dnp[j]

        for j in range(1, 4):
            d = np_[j] - n[j]
            if (d >= 1.0 and n[j + 1] - n[j] > 1) or (
                d <= -1.0 and n[j - 1] - n[j] < -1
            ):
                d_sign = 1 if d > 0 else -1
                qi = self._parabolic(j, d_sign)
                if q[j - 1] < qi < q[j + 1]:
                    q[j] = qi
                else:
                    q[j] = self._linear(j, d_sign)
                n[j] += d_sign

    def _parabolic(self, j: int, d: int) -> float:
        q = self.q
        n = self.n
        nj = n[j]
        return q[j] + (d / (n[j + 1] - n[j - 1])) * (
            (nj - n[j - 1] + d) * (q[j + 1] - q[j]) / (n[j + 1] - nj)
            + (n[j + 1] - nj - d) * (q[j] - q[j - 1]) / (nj - n[j - 1])
        )

    def _linear(self, j: int, d: int) -> float:
        q = self.q
        n = self.n
        neighbor = j + d
        return q[j] + d * (q[neighbor] - q[j]) / (n[neighbor] - n[j])

    @property
    def value(self) -> float:
        """Current quantile estimate (exact for N < EXACT_THRESHOLD)."""
        if self._buffer is not None and len(self._buffer) > 0:
            # Exact quantile from sorted buffer
            s = sorted(self._buffer)
            idx = self.p * (len(s) - 1)
            lo = int(idx)
            hi = min(lo + 1, len(s) - 1)
            frac = idx - lo
            return s[lo] * (1.0 - frac) + s[hi] * frac
        if self.count >= 5:
            return self.q[2]
        return 0.0

    def __repr__(self) -> str:
        mode = "exact" if self._buffer is not None else "P2"
        return f"P2Quantile(p={self.p}, n={self.count}, value={self.value:.4f}, mode={mode})"


class StreamingStats:
    """
    Online streaming statistics with O(1) memory.

    Tracks count, mean, std, min, max, sum, and approximate quantiles
    (p25, p75, p90) using Welford's algorithm and P-squared quantile
    estimation.

    For small sample sizes (< 500), quantiles are computed exactly from
    a sorted buffer. Beyond that threshold, the P-squared streaming
    estimator provides O(1) memory approximate quantiles.

    Replaces the raw-list accumulators in BaseNode (wait_times,
    processing_times, etc.) that previously grew without bound.
    """

    __slots__ = ("n", "_mean", "_M2", "_min", "_max", "_sum", "_p25", "_p75", "_p90")

    def __init__(self):
        self.n: int = 0
        self._mean: float = 0.0
        self._M2: float = 0.0  # sum of squared deviations (Welford)
        self._min: float = float("inf")
        self._max: float = float("-inf")
        self._sum: float = 0.0
        self._p25 = P2Quantile(0.25)
        self._p75 = P2Quantile(0.75)
        self._p90 = P2Quantile(0.90)

    def update(self, x: float) -> None:
        """Add a new observation. O(1) time and memory."""
        self.n += 1
        # Welford online mean and variance
        delta = x - self._mean
        self._mean += delta / self.n
        delta2 = x - self._mean
        self._M2 += delta * delta2
        # Min / max / sum
        if x < self._min:
            self._min = x
        if x > self._max:
            self._max = x
        self._sum += x
        # Quantiles
        self._p25.update(x)
        self._p75.update(x)
        self._p90.update(x)

    @property
    def count(self) -> int:
        return self.n

    @property
    def mean(self) -> float:
        return self._mean if self.n > 0 else 0.0

    @property
    def std(self) -> float:
        """Population standard deviation."""
        return math.sqrt(self._M2 / self.n) if self.n > 1 else 0.0

    @property
    def variance(self) -> float:
        """Population variance."""
        return self._M2 / self.n if self.n > 1 else 0.0

    @property
    def min(self) -> float:
        return self._min if self.n > 0 else 0.0

    @property
    def max(self) -> float:
        return self._max if self.n > 0 else 0.0

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def p25(self) -> float:
        return self._p25.value

    @property
    def p75(self) -> float:
        return self._p75.value

    @property
    def p90(self) -> float:
        return self._p90.value

    def to_dict(self) -> Dict[str, float]:
        """Return all statistics as a dictionary."""
        return {
            "count": self.n,
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "sum": self.sum,
            "p25": self.p25,
            "p75": self.p75,
            "p90": self.p90,
        }

    def __repr__(self) -> str:
        if self.n == 0:
            return "StreamingStats(empty)"
        return (
            f"StreamingStats(n={self.n}, mean={self.mean:.4f}, std={self.std:.4f}, "
            f"min={self.min:.4f}, max={self.max:.4f}, "
            f"p25={self.p25:.4f}, p75={self.p75:.4f}, p90={self.p90:.4f})"
        )


if __name__ == "__main__":
    import random
    import sys
    import numpy as np

    random.seed(42)
    failures = 0

    def check(name, actual, expected, tol, rel=False):
        global failures
        if rel and expected != 0:
            err = abs(actual - expected) / abs(expected)
            ok = err <= tol
            err_str = f"rel_err={err:.2%}"
        else:
            err = abs(actual - expected)
            ok = err <= tol
            err_str = f"abs_err={err:.2e}"
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  {status}  {name:<30s}  got={actual:12.4f}  expected={expected:12.4f}  {err_str}")
        return ok

    # --- Test 1: Uniform(0, 100), 100K samples ---
    print("=== Test 1: Uniform(0, 100), 100K samples ===")
    s = StreamingStats()
    for _ in range(100_000):
        s.update(random.uniform(0, 100))
    check("mean",  s.mean, 50.0,   1.0)
    check("std",   s.std,  28.87,  1.0)
    check("p25",   s.p25,  25.0,   0.02, rel=True)
    check("p75",   s.p75,  75.0,   0.02, rel=True)
    check("p90",   s.p90,  90.0,   0.02, rel=True)

    # --- Test 2: Normal(100, 15), 50K samples ---
    print("\n=== Test 2: Normal(100, 15), 50K samples ===")
    s2 = StreamingStats()
    for _ in range(50_000):
        s2.update(random.gauss(100, 15))
    check("mean",  s2.mean, 100.0,  1.0)
    check("std",   s2.std,  15.0,   1.0)
    check("p25",   s2.p25,  89.9,   0.03, rel=True)
    check("p75",   s2.p75,  110.1,  0.03, rel=True)
    check("p90",   s2.p90,  119.2,  0.03, rel=True)

    # --- Test 3: Small sample, skewed (the sim scenario) ---
    print("\n=== Test 3: Small skewed sample (44 obs, range 68-995225) ===")
    random.seed(99)
    s3 = StreamingStats()
    # Simulate the data_size distribution from the TTL test (lognormal-ish)
    values = [random.lognormvariate(7.5, 2.5) for _ in range(44)]
    for v in values:
        s3.update(v)
    arr3 = np.array(values)
    # numpy uses linear interpolation by default — matches our exact buffer method
    exact_p25 = float(np.percentile(arr3, 25))
    exact_p75 = float(np.percentile(arr3, 75))
    exact_p90 = float(np.percentile(arr3, 90))
    # With exact buffer (N=44 < 500), quantiles should match numpy
    check("p25 (exact buffer)", s3.p25, exact_p25, 0.01, rel=True)
    check("p75 (exact buffer)", s3.p75, exact_p75, 0.01, rel=True)
    check("p90 (exact buffer)", s3.p90, exact_p90, 0.01, rel=True)
    print(f"  (buffer mode: {s3._p25._buffer is not None})")

    # --- Test 4: Transition from exact to P2 ---
    print("\n=== Test 4: Exact→P2 transition at 500 obs ===")
    s4 = StreamingStats()
    vals = []
    for i in range(600):
        v = random.lognormvariate(5, 2)
        vals.append(v)
        s4.update(v)
        if i == 498:
            # Should still be in exact mode
            assert s4._p25._buffer is not None, "Should be exact at N=499"
        if i == 500:
            # Should have switched to P2
            assert s4._p25._buffer is None, "Should be P2 at N=501"

    import numpy as np
    arr = np.array(vals)
    check("mean",  s4.mean,  float(np.mean(arr)), 1e-8)
    check("std",   s4.std,   float(np.std(arr)),   1e-4)
    check("p25 (P2 mode)",  s4.p25, float(np.percentile(arr, 25)), 0.10, rel=True)
    check("p75 (P2 mode)",  s4.p75, float(np.percentile(arr, 75)), 0.10, rel=True)
    check("p90 (P2 mode)",  s4.p90, float(np.percentile(arr, 90)), 0.10, rel=True)
    print(f"  (buffer mode: {s4._p25._buffer is not None})")

    # --- Test 5: Edge cases ---
    print("\n=== Test 5: Edge cases ===")
    s_empty = StreamingStats()
    check("empty mean", s_empty.mean, 0.0, 0.0)
    check("empty std",  s_empty.std,  0.0, 0.0)
    check("empty p90",  s_empty.p90,  0.0, 0.0)

    s_one = StreamingStats()
    s_one.update(42.0)
    check("single mean", s_one.mean, 42.0, 0.0)
    check("single std",  s_one.std,   0.0, 0.0)
    check("single min",  s_one.min,  42.0, 0.0)
    check("single max",  s_one.max,  42.0, 0.0)

    # --- Test 6: Memory footprint ---
    print("\n=== Test 6: Memory footprint after P2 transition ===")
    s6 = StreamingStats()
    for _ in range(1_000_000):
        s6.update(random.random())
    assert s6._p25._buffer is None, "Buffer should be freed after 500 obs"
    print(f"  PASS  Buffer freed, P2 mode active, n={s6.n}")

    # --- Test 7: All-zero values ---
    print("\n=== Test 7: All-zero values (common for wait_times) ===")
    s7 = StreamingStats()
    for _ in range(100):
        s7.update(0.0)
    check("zero mean", s7.mean, 0.0, 0.0)
    check("zero std",  s7.std,  0.0, 0.0)
    check("zero p25",  s7.p25,  0.0, 0.0)
    check("zero p90",  s7.p90,  0.0, 0.0)
    check("zero min",  s7.min,  0.0, 0.0)
    check("zero max",  s7.max,  0.0, 0.0)

    # --- Summary ---
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILURES: {failures}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)
