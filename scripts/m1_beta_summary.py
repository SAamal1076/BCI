"""M1, BETA: gate G5 and the numbers quoted in the report. Reads results/m1/beta_accuracy.csv.

G5 (M1 plan): peak ITR with a gaze shift of 0.55 s, mean over the 70 people, variant A:
CCA 72.5 bits/min at 1.8 s, FBCCA 98.8 at 1.4 s, ensemble TRCA with filter bank 139.6 at 0.6 s (Liu et al. 2020).
Passes if the peak is within 10 % and at the same window +/- 0.2 s.

Usage: python scripts/m1_beta_summary.py > logs/m1_beta_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import metrics as mt  # noqa: E402

RES = ROOT / "results" / "m1"
GAZE = 0.55
PUBLISHED = {"cca": (72.54, 1.8), "fbcca": (98.79, 1.4), "etrca": (139.58, 0.6)}
LABEL = {"cca": "CCA (6-80 Hz)", "fbcca": "FBCCA", "trca": "TRCA with filter bank", "etrca": "ensemble TRCA with filter bank"}
CONTEXT = {"A": "A: cut, then filter (gate)", "C-": "C-: whole trial filtered (uses later samples)"}


def main():
    acc = pd.read_csv(RES / "beta_accuracy.csv")
    acc["itr"] = mt.itr_bits_per_min(acc.accuracy, 40, acc.window_s + GAZE)
    g = acc.groupby(["variant", "method", "window_s"])
    s = g.agg(mean=("accuracy", "mean"), sem=("accuracy", "sem"), itr=("itr", "mean"), itr_sem=("itr", "sem"),
              n=("accuracy", "size")).reset_index()
    s.to_csv(RES / "beta_summary.csv", index=False, float_format="%.4f")
    print(f"BETA: {acc.subject.nunique()} people, 40 targets (chance 0.025), 160 trials per person")

    rows = []
    for variant in ("A", "C-"):
        for method, (pub, pub_win) in PUBLISHED.items():
            d = s[(s.variant == variant) & (s.method == method)].set_index("window_s")
            win = float(d.itr.idxmax())
            peak, sem = float(d.itr.max()), float(d.itr_sem[win])
            ok = bool(abs(peak - pub) <= 0.10 * pub and abs(win - pub_win) <= 0.2 + 1e-9)
            rows.append({"gate": "G5" if variant == "A" else "(same criterion)", "variant": variant, "method": LABEL[method],
                         "published_peak_itr": pub, "published_window_s": pub_win, "our_peak_itr": round(peak, 1),
                         "our_sem": round(sem, 1), "our_window_s": win, "relative_difference": round(peak / pub - 1, 3),
                         "our_itr_at_published_window": round(float(d.itr[pub_win]), 1), "passed": ok})
    gate = pd.DataFrame(rows)
    gate.to_csv(RES / "gate_beta.csv", index=False)
    print("\n== gate G5 (variant A) and the same criterion for whole-trial filtering")
    print(gate.to_string(index=False))
    a = gate[gate.variant == "A"]
    print(f"G5: {int(a.passed.sum())} of {len(a)} checks pass")

    for variant in ("A", "C-"):
        d = s[s.variant == variant]
        print(f"\n== {CONTEXT[variant]}: mean accuracy (SEM over people)")
        t = d.assign(cell=[f"{m:.3f} ({e:.3f})" for m, e in zip(d["mean"], d["sem"])]).pivot(
            index="method", columns="window_s", values="cell")
        print(t[[0.2, 0.6, 1.0, 1.4, 2.0]].to_string())
        print("mean ITR (bits/min, 0.55 s gaze shift):")
        print(d.pivot(index="method", columns="window_s", values="itr").round(1).to_string())

    wide = acc.pivot_table(index=["subject", "method", "window_s"], columns="variant", values="accuracy")
    diff = (wide["C-"] - wide["A"]).groupby(["method", "window_s"]).mean().unstack("window_s")
    print("\n== whole-trial filtering minus cut-then-filter: mean difference in accuracy, same person")
    print(diff.round(3).to_string())

    print("\n== people (variant A)")
    for method, window in (("fbcca", 1.0), ("fbcca", 2.0), ("etrca", 1.0), ("etrca", 2.0)):
        d = acc[(acc.variant == "A") & (acc.method == method) & (acc.window_s == window)].accuracy
        thr = mt.chance_threshold(160, 40)
        print(f"  {LABEL[method]:32s} {window} s: median {d.median():.3f}, range {d.min():.3f} to {d.max():.3f}; "
              f"not above chance (below {thr:.3f}): {(d < thr).sum()} of {len(d)}; at 0.9 or more: {(d >= 0.9).sum()}")
    two = acc[(acc.variant == "A") & (acc.window_s == 1.0)].assign(group=lambda t: np.where(t.subject <= 15, "S1-S15", "S16-S70"))
    print("\naccuracy at 1 s by recording group (variant A):")
    print(two.groupby(["method", "group"]).accuracy.mean().unstack("group").round(3).to_string())


if __name__ == "__main__":
    main()
