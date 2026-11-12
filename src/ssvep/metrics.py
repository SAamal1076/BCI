"""Performance measures."""
from __future__ import annotations

import numpy as np
from scipy import stats


def itr_bits_per_min(p, n_classes: int, t_sel: float):
    """Information transfer rate (Wolpaw): 60/T_sel * [log2 N + P log2 P + (1-P) log2((1-P)/(N-1))].

    t_sel is the time of one selection in seconds (window + gaze shift). The rate is set to 0 when the
    accuracy is at or below chance (the formula would otherwise credit systematic errors).
    """
    p = np.asarray(p, dtype=float)
    n = float(n_classes)
    with np.errstate(divide="ignore", invalid="ignore"):
        bits = np.log2(n) + p * np.log2(p) + (1 - p) * np.log2((1 - p) / (n - 1))
    bits = np.where(p >= 1.0, np.log2(n), bits)
    bits = np.where(p <= 1.0 / n, 0.0, bits)
    return 60.0 / t_sel * bits


def chance_threshold(n_trials: int, n_classes: int, alpha: float = 0.05) -> float:
    """Smallest accuracy that is above chance at the one-sided level alpha (binomial)."""
    k = stats.binom.ppf(1 - alpha, n_trials, 1.0 / n_classes)          # P(X <= k) >= 1 - alpha
    return float((k + 1) / n_trials)
