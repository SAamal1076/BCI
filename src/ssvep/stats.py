"""Tests fixed in the M2 plan. They are run on the lockbox at the end of the project, not on development data."""
from __future__ import annotations

import numpy as np
from scipy import stats


def crossover_effect(d, treatment_first):
    """Effect of the treatment in a two-period crossover, free of the effect of the period.

    d: treatment minus control for each person. treatment_first: True if the treatment came in the first period.
    Returns 0.5 * [mean(d | treatment first) + mean(d | control first)].
    """
    d, first = np.asarray(d, dtype=float), np.asarray(treatment_first, dtype=bool)
    return 0.5 * (d[first].mean() + d[~first].mean())


def crossover_test(d, treatment_first, alternative="less"):
    """Rank-sum test of the treatment effect (period-adjusted): 'first period minus second period' is compared
    between the two orders. With alternative='less' the hypothesis is that the treatment lowers the outcome."""
    d, first = np.asarray(d, dtype=float), np.asarray(treatment_first, dtype=bool)
    return stats.mannwhitneyu(d[first], -d[~first], alternative=alternative).pvalue


def noninferiority_test(new, reference, margin):
    """One-sided Wilcoxon signed-rank test that `new` is not more than `margin` below `reference` (paired)."""
    e = np.asarray(new, dtype=float) - np.asarray(reference, dtype=float) + margin
    return stats.wilcoxon(e, alternative="greater").pvalue


def bootstrap_ci(values, n_boot=2000, level=0.95, seed=0):
    """Percentile interval of the mean over people (people are resampled)."""
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return tuple(np.quantile(means, [(1 - level) / 2, (1 + level) / 2]))


def block_slope(a):
    """Least-squares slope of a series over its positions 1..n (last axis), per step.
    For accuracy over the 10 blocks of a headband: change of accuracy per block."""
    a = np.asarray(a, dtype=float)
    b = np.arange(1, a.shape[-1] + 1) - (a.shape[-1] + 1) / 2
    return (a * b).sum(axis=-1) / (b * b).sum()


def spearman_permutation_test(x, y, alternative="less", n_perm=10000, seed=0):
    """Spearman correlation and its one-sided permutation p-value (y is shuffled against x).
    alternative='less': the hypothesis is a negative correlation. Returns (rho, p)."""
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rng = np.random.default_rng(seed)
    rxc = (rx - rx.mean()) / rx.std()
    ryc = (ry - ry.mean()) / ry.std()
    perm = np.array([rxc @ ryc[rng.permutation(len(ryc))] for _ in range(n_perm)]) / len(rxc)
    count = (perm <= rho + 1e-12).sum() if alternative == "less" else (perm >= rho - 1e-12).sum()
    return rho, float((count + 1) / (n_perm + 1))
