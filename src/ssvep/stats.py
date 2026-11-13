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
