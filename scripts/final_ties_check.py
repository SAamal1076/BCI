"""Robustness check of the Wilcoxon tests of the final evaluation against the treatment of ties.

WRITTEN AFTER THE OPENING, on 14 Nov 2026, while the correction was being checked. It reads the result files
only (results/final/lockbox and results/final/lockbox_corrected), decodes nothing and changes no result.

What it is about: the differences tested by H2, H3 and H6 are differences of accuracies, that is of counts of
correct trials divided by 48. Two differences that are equal as fractions are not always equal as floating
point numbers, so the pre-specified code does not see every tie as a tie, and the Wilcoxon p-value depends a
little on that. Here the same tests are recomputed from the integer counts, where equal differences are
exactly equal, and the Holm procedure is applied again to the 15 p-values.

The reported p-values stay those of the pre-specified code. This check only asks whether a decision depends
on the treatment of ties.

Usage: python scripts/final_ties_check.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import stats as st  # noqa: E402

TRIALS = 48                                                            # blocks 7 to 10
MARGIN_COUNTS = (20, 48)                                               # e + 0.05 > 0  <=>  20 * (difference of counts) + 48 > 0


def counts(acc, method, k, electrode):
    """Correct trials out of 48 per person, summed over the seeds (one row per seed, or one row)."""
    d = acc[(acc.design == "new_user") & (acc.method == method) & (acc.k == k) & (acc.electrode == electrode)]
    c = d.accuracy * TRIALS
    assert np.abs(c - c.round()).max() < 1e-3
    return c.round().astype(int).groupby(d.subject).sum()


def wilcoxon(v, alternative="greater"):
    v = np.asarray(v, dtype=float)
    v = v[v != 0]
    return 1.0 if len(v) == 0 else float(stats.wilcoxon(v, alternative=alternative).pvalue)


def exact_ties(acc):
    """p-values of the 7 Wilcoxon tests of H2, H3 and H6 from integer counts, by row of tests.csv (0-based)."""
    p = {}
    for el, i in (("dry", 4), ("wet", 5)):
        p[i] = wilcoxon(MARGIN_COUNTS[0] * (counts(acc, "template", 2, el) - counts(acc, "etrca", 6, el)) + MARGIN_COUNTS[1])
    g = {el: counts(acc, "net_A2", 0, el) - counts(acc, "net_A0", 0, el) for el in ("dry", "wet")}
    p[6], p[7], p[8] = wilcoxon(g["dry"]), wilcoxon(g["wet"]), wilcoxon(g["dry"] - g["wet"])
    for el, i in (("dry", 13), ("wet", 14)):
        p[i] = wilcoxon(counts(acc, "template_adapted", 0, el) - counts(acc, "template", 0, el))
    return p


def main():
    print("== Wilcoxon tests of the final evaluation: pre-specified code against exact ties (integer counts)")
    print("written after the opening; result files only; the reported p-values stay those of the pre-specified code")
    for label, folder in (("original (the opening)", "lockbox"), ("corrected (after the opening)", "lockbox_corrected")):
        res = ROOT / "results" / "final" / folder
        acc, tests = pd.read_csv(res / "accuracy.csv"), pd.read_csv(res / "tests.csv")
        assert tests.hypothesis.tolist() == ["H1"] * 4 + ["H2"] * 2 + ["H3"] * 3 + ["H5a"] * 2 + ["H5b"] * 2 + ["H6"] * 2
        exact, p = exact_ties(acc), tests.p.to_numpy().copy()
        q = p.copy()
        for i, v in exact.items():
            q[i] = v
        before, after = st.holm(p)[0], st.holm(q)[0]
        assert (before == tests.supported.to_numpy()).all()
        print(f"\n{label}")
        rows = [{"test": i + 1, "hypothesis": tests.hypothesis[i], "case": tests.case[i], "p, pre-specified code": f"{p[i]:.3g}",
                 "p, exact ties": f"{exact[i]:.3g}", "threshold (Holm)": f"{tests.holm_threshold[i]:.3g}",
                 "supported": bool(before[i]), "supported, exact ties": bool(after[i])} for i in sorted(exact)]
        print(pd.DataFrame(rows).to_string(index=False))
        print(f"supported tests, pre-specified code: {(np.flatnonzero(before) + 1).tolist()}; with exact ties: {(np.flatnonzero(after) + 1).tolist()}; "
              f"decisions that differ: {(np.flatnonzero(before != after) + 1).tolist()}")
    print("\nNot recomputed: H1 (crossover rank-sum test), H5a (slopes, not counts) and H5b (permutation test).")


if __name__ == "__main__":
    main()
