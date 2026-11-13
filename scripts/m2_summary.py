"""M2: every number quoted in docs/milestones/M2_calibration.md. Reads results/m2 (and results/m0, results/m1).

Descriptive statistics on the development people. No p-value: the tests of H1 and H2 are run on the lockbox.

Usage: python scripts/m2_summary.py > logs/m2_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import metrics as mt  # noqa: E402
from ssvep import stats as st  # noqa: E402

RES, M1, M0 = ROOT / "results" / "m2", ROOT / "results" / "m1", ROOT / "results" / "m0"
GAZE, BLOCK_S, MARGIN = 0.5, 48, 0.05
NAMES = ("dry", "wet")
SHOW = [0.2, 0.6, 1.0, 1.4, 2.0]
LABEL = {"cca": "CCA", "fbcca": "FBCCA", "trca": "TRCA", "etrca": "ensemble TRCA", "cross": "cross-subject template",
         "own": "own template only"}


def ci(v):
    lo, hi = st.bootstrap_ci(np.asarray(v))
    return f"{np.mean(v):+.3f} [{lo:+.3f}, {hi:+.3f}]"


def cell(v):
    lo, hi = st.bootstrap_ci(np.asarray(v))
    return f"{np.mean(v):.3f} [{lo:.3f}, {hi:.3f}]"


def main():
    choice = pd.read_csv(RES / "pipeline_choice.csv")
    name = choice.loc[choice.chosen, "pipeline"].iloc[0]
    print("== 1. step 0: pipeline candidates (1 s, FBCCA and ensemble TRCA, development people)")
    print(choice.round(3).to_string(index=False))
    print(f"chosen and frozen: {name}")

    base = pd.read_csv(RES / "baseline_accuracy.csv")
    base["itr"] = mt.itr_bits_per_min(base.accuracy, 12, base.window_s + GAZE)
    n_people = base.subject.nunique()
    print(f"\n== 2. baselines re-run with pipeline {name}: mean accuracy (SEM), {n_people} development people, leave-one-block-out")
    g = base.groupby(["method", "electrode", "window_s"])
    s = g.agg(mean=("accuracy", "mean"), sem=("accuracy", "sem"), itr=("itr", "mean")).reset_index()
    s.to_csv(RES / "baseline_summary.csv", index=False, float_format="%.4f")
    t = s.assign(c=[f"{m:.3f} ({e:.3f})" for m, e in zip(s["mean"], s["sem"])]).pivot(index=["method", "electrode"], columns="window_s", values="c")
    print(t[SHOW].to_string())
    m1 = pd.read_csv(M1 / "accuracy_summary.csv")
    m1 = m1[m1.variant == "B"].assign(method=lambda d: d.method.str.replace("_apriori", ""))
    both = s.merge(m1[["method", "electrode", "window_s", "mean"]], on=["method", "electrode", "window_s"], suffixes=("", "_m1"))
    both["change"] = both["mean"] - both["mean_m1"]
    print(f"change against the M1 numbers (pipeline B): {name} minus B")
    print(both[both.window_s.isin(SHOW)].pivot(index=["method", "electrode"], columns="window_s", values="change").round(3).to_string())
    print("peak ITR (bits/min, window + 0.5 s):")
    for method in ("cca", "fbcca", "etrca"):
        for el in NAMES:
            d = s[(s.method == method) & (s.electrode == el)].set_index("window_s")
            print(f"  {LABEL[method]:14s} {el}: {d.itr.max():6.1f} at {d.itr.idxmax()} s")
    thr = mt.chance_threshold(120, 12)
    for method, window in (("fbcca", 1.0), ("fbcca", 2.0), ("etrca", 1.0), ("etrca", 2.0)):
        d = base[(base.method == method) & (base.window_s == window)]
        print(f"  {LABEL[method]:14s} {window} s: not above chance (below {thr:.3f}) dry {(d[d.electrode == 'dry'].accuracy < thr).sum()}, "
              f"wet {(d[d.electrode == 'wet'].accuracy < thr).sum()} of {n_people}; at 0.9 or more dry "
              f"{(d[d.electrode == 'dry'].accuracy >= 0.9).sum()}, wet {(d[d.electrode == 'wet'].accuracy >= 0.9).sum()}")
    conf = pd.read_csv(RES / "baseline_confusion_1s.csv")
    for (el, method), d in conf.groupby(["electrode", "method"]):
        m = d.pivot(index="true_target", columns="predicted_target", values="count").to_numpy()
        freqs = np.array([9.25, 11.25, 13.25, 9.75, 11.75, 13.75, 10.25, 12.25, 14.25, 10.75, 12.75, 14.75])
        near = np.isin(freqs, (12.25, 12.75))
        print(f"  share of the decisions on 12.25 or 12.75 Hz, {LABEL[method]}, {el}: {m[:, near].sum() / m.sum():.3f} (0.167 without bias)")

    print(f"\n== 3. dry minus wet, same person, pipeline {name} (descriptive; H1 is tested on the lockbox)")
    wide = base.pivot_table(index=["subject", "first_headband", "method", "window_s"], columns="electrode", values="accuracy").reset_index()
    wide["d"] = wide.dry - wide.wet
    rows = []
    for method in ("fbcca", "etrca"):
        for window in (1.0, 2.0):
            d = wide[(wide.method == method) & (wide.window_s == window)]
            first = d.first_headband.str.lower().str.startswith("dry").to_numpy()
            rows.append({"method": LABEL[method], "window_s": window, "mean d": d.d.mean(), "dry lower in": f"{(d.d < 0).sum()}/{len(d)}",
                         "dry worn first": d.d[first].mean(), "n1": int(first.sum()), "wet worn first": d.d[~first].mean(),
                         "n2": int((~first).sum()), "crossover estimate": st.crossover_effect(d.d, first)})
    dw = pd.DataFrame(rows)
    dw.to_csv(RES / "dry_minus_wet.csv", index=False, float_format="%.4f")
    print(dw.round(3).to_string(index=False))
    gap = wide.groupby(["method", "window_s"]).d.mean().unstack("window_s")
    gap.to_csv(RES / "dry_minus_wet_by_window.csv", float_format="%.4f")
    print("mean dry - wet by window:")
    print(gap.loc[["cca", "fbcca", "etrca"]].round(3).to_string())
    mean = base.groupby(["method", "electrode", "window_s"]).accuracy.mean()
    for method in ("fbcca", "etrca"):
        dry = mean[method]["dry"]
        out = []
        for w in (0.4, 0.6, 0.8, 1.0, 1.2):
            target = mean[method]["wet"][w]
            if dry.max() < target:
                out.append(f"{w} s -> not reached within 2 s")
            else:
                tt = float(np.interp(target, dry.to_numpy(), dry.index.to_numpy()))
                out.append(f"{w} s -> {tt:.2f} s (+{tt - w:.2f})")
        print(f"  time cost of dry electrodes, {LABEL[method]}: " + "; ".join(out))

    new = pd.read_csv(RES / "new_user_accuracy.csv")
    new["itr"] = mt.itr_bits_per_min(new.accuracy, 12, new.window_s + GAZE)
    print(f"\n== 4. new users: {new.subject.nunique()} development people, leave-one-subject-out, test = blocks 7-10 (48 trials)")
    grid = new[(new.method == "cross") & (new.window_s == 1.0) & new.k.isin([1, 2, 4])]
    by_n0 = grid.groupby("n0").accuracy.mean()
    n0 = float(by_n0.idxmax())
    t = grid.groupby(["n0", "electrode", "k"]).accuracy.mean().unstack(["electrode", "k"])
    t["criterion"] = by_n0
    t.to_csv(RES / "n0_choice.csv", float_format="%.4f")
    print("choice of n0 (mean accuracy at 1 s over k = 1, 2, 4 and both headbands):")
    print(t.round(3).to_string())
    print(f"chosen and frozen: n0 = {n0:g}")

    keep = new[(new.method != "cross") | (new.k == 0) | (new.n0 == n0)].copy()
    keep.to_csv(RES / "new_user_frozen.csv", index=False, float_format="%.6f")
    rows = []
    for (method, k, el, w), d in keep.groupby(["method", "k", "electrode", "window_s"]):
        lo, hi = st.bootstrap_ci(d.accuracy.to_numpy())
        rows.append((method, k, el, w, d.accuracy.mean(), lo, hi, d.itr.mean()))
    curve = pd.DataFrame(rows, columns=["method", "k", "electrode", "window_s", "mean", "ci_low", "ci_high", "itr"])
    curve["calibration_s"] = curve.k * BLOCK_S
    curve.to_csv(RES / "calibration_curve.csv", index=False, float_format="%.4f")
    for window in (1.0, 2.0):
        print(f"\ncalibration curve at {window} s: mean accuracy [95 % bootstrap interval over people]; one block = {BLOCK_S} s")
        c = curve[curve.window_s == window]
        t = c.assign(c=[f"{m:.3f} [{a:.3f}, {b:.3f}]" for m, a, b in zip(c["mean"], c.ci_low, c.ci_high)]).pivot(
            index=["electrode", "method"], columns="k", values="c").fillna("")
        print(t.to_string())
    print("\nITR at the best window (bits/min, window + 0.5 s) by number of calibration blocks:")
    best = curve.loc[curve.groupby(["method", "k", "electrode"]).itr.idxmax()]
    print(best.assign(c=[f"{i:.1f} at {w} s" for i, w in zip(best.itr, best.window_s)]).pivot(
        index=["electrode", "method"], columns="k", values="c").fillna("").to_string())

    p = keep.pivot_table(index=["subject", "electrode", "window_s"], columns=["method", "k"], values="accuracy")
    print("\n== 5. no calibration: cross-subject template (k = 0) minus FBCCA, same trials: mean [95 % interval]")
    rows = []
    for el in NAMES:
        for w in SHOW:
            d = p.xs((el, w), level=("electrode", "window_s"))
            e = d[("cross", 0)] - d[("fbcca", 0)]
            rows.append({"electrode": el, "window_s": w, "cross - fbcca": ci(e), "people better": int((e > 0).sum()),
                         "equal": int((e == 0).sum()), "worse": int((e < 0).sum())})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== 6. what the population adds to the person's own blocks: cross (n0 frozen) minus own template, 1 s")
    rows = []
    for el in NAMES:
        d = p.xs((el, 1.0), level=("electrode", "window_s"))
        for k in (1, 2, 4, 6):
            rows.append({"electrode": el, "k": k, "cross - own": ci(d[("cross", k)] - d[("own", k)]),
                         "cross - etrca": ci(d[("cross", k)] - d[("etrca", k)]) if k >= 2 else ""})
    print(pd.DataFrame(rows).to_string(index=False))

    print(f"\n== 7. H2 on the development people (descriptive; the test is run on the lockbox): cross-subject template with 2 blocks "
          f"({2 * BLOCK_S} s)\n   minus ensemble TRCA with 6 blocks ({6 * BLOCK_S} s); H2 says: not more than {MARGIN} lower")
    rows = []
    for el in NAMES:
        for w in (1.0, 2.0):
            d = p.xs((el, w), level=("electrode", "window_s"))
            e = d[("cross", 2)] - d[("etrca", 6)]
            lo, hi = st.bootstrap_ci(e.to_numpy())
            rows.append({"electrode": el, "window_s": w, "cross k=2": d[("cross", 2)].mean(), "etrca k=6": d[("etrca", 6)].mean(),
                         "difference": ci(e), "interval above -0.05": bool(lo > -MARGIN),
                         "people within 0.05 or better": f"{int((e >= -MARGIN).sum())}/{len(e)}"})
    h2 = pd.DataFrame(rows)
    h2.to_csv(RES / "h2_development.csv", index=False, float_format="%.4f")
    print(h2.round(3).to_string(index=False))
    print("blocks the cross-subject template needs to come within 0.05 of ensemble TRCA with 6 blocks (mean accuracy, 1 s):")
    for el in NAMES:
        d = curve[(curve.window_s == 1.0) & (curve.electrode == el)].set_index(["method", "k"])["mean"]
        target = d[("etrca", 6)] - MARGIN
        ks = [k for k in (0, 1, 2, 4, 6) if d[("cross", k)] >= target]
        print(f"  {el}: target {target:.3f}; reached from k = {ks[0] if ks else 'not within 6 blocks'}")

    print("\n== 8. people (1 s, test blocks 7-10)")
    thr = mt.chance_threshold(48, 12)
    snr = pd.read_csv(M0 / "snr_per_subject.csv")[["subject", "electrode", "snr1_trial_oz"]]
    for el in NAMES:
        d = p.xs((el, 1.0), level=("electrode", "window_s"))
        for col, lab in ((("fbcca", 0), "FBCCA"), (("cross", 0), "cross, k = 0"), (("cross", 2), "cross, k = 2"), (("etrca", 6), "ensemble TRCA, k = 6")):
            print(f"  {el} {lab:22s}: not above chance (below {thr:.3f}) {(d[col] < thr).sum()} of {len(d)}; at 0.9 or more {(d[col] >= 0.9).sum()}")
        gain = (d[("cross", 0)] - d[("fbcca", 0)]).rename("gain").reset_index().merge(snr[snr.electrode == el], on="subject")
        low = d[("fbcca", 0)] < d[("fbcca", 0)].median()
        print(f"  {el}: gain of the population template (k = 0) in the lower half of FBCCA accuracy {ci((d[('cross', 0)] - d[('fbcca', 0)])[low])}, "
              f"upper half {ci((d[('cross', 0)] - d[('fbcca', 0)])[~low])}; Spearman of the gain with the SNR of M0: "
              f"{stats.spearmanr(gain.gain, gain.snr1_trial_oz)[0]:+.2f}")


if __name__ == "__main__":
    main()
