"""M1: the reproduction gate and every number quoted in docs/milestones/M1_baselines.md.

Reads results/m1 (and the per-subject SNR of M0), writes results/m1/gate.csv and a few summary tables.
Usage: python scripts/m1_summary.py > logs/m1_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import metrics as mt  # noqa: E402

RES = ROOT / "results" / "m1"
GAZE = 0.5
NAMES = ("dry", "wet")
LABEL = {"cca": "CCA", "fbcca_apriori": "FBCCA, a-priori weights", "fbcca_paper": "FBCCA, published weights",
         "trca_apriori": "TRCA, a-priori weights", "etrca_apriori": "ensemble TRCA, a-priori weights",
         "trca_paper": "TRCA, published weights", "etrca_paper": "ensemble TRCA, published weights"}
# Published accuracies, Zhu et al. 2021 (all 102 subjects): (method, window) -> (dry, wet)
PUBLISHED = {("cca", 1.0): (0.497, 0.684),
             ("fbcca_paper", 0.2): (0.12, 0.16), ("fbcca_paper", 1.0): (0.53, 0.73), ("fbcca_paper", 2.0): (0.73, 0.86),
             ("etrca_paper", 0.2): (0.38, 0.66), ("etrca_paper", 1.0): (0.62, 0.88), ("etrca_paper", 2.0): (0.73, 0.93)}
PUBLISHED_CCA_HARMONICS = {"dry": (0.432, 0.483, 0.492, 0.494, 0.497, 0.498),
                           "wet": (0.593, 0.660, 0.677, 0.680, 0.684, 0.683)}
GATE = {"G1": [("cca", 1.0)], "G2": [("fbcca_paper", 1.0), ("fbcca_paper", 2.0)],
        "G3": [("etrca_paper", 1.0), ("etrca_paper", 2.0)]}
TOL = 0.05


def main():
    pd.set_option("display.width", 220)
    acc = pd.read_csv(RES / "wearable_accuracy.csv")
    n_sub = acc.subject.nunique()
    acc["itr"] = mt.itr_bits_per_min(acc.accuracy, 12, acc.window_s + GAZE)
    acc["itr_window_only"] = mt.itr_bits_per_min(acc.accuracy, 12, acc.window_s)
    g = acc.groupby(["variant", "method", "electrode", "window_s"])
    summary = g.agg(mean=("accuracy", "mean"), sem=("accuracy", "sem"), median=("accuracy", "median"),
                    itr=("itr", "mean"), itr_window_only=("itr_window_only", "mean"), n=("accuracy", "size")).reset_index()
    summary.to_csv(RES / "accuracy_summary.csv", index=False, float_format="%.4f")
    mean = summary.set_index(["variant", "method", "electrode", "window_s"])["mean"]
    sem = summary.set_index(["variant", "method", "electrode", "window_s"])["sem"]
    print(f"development subjects: {n_sub}; accuracies: {len(acc)}")

    # ------------------------------------------------------------------ gate
    print("\n== reproduction gate (variant A, development subjects against the published values for 102 subjects)")
    rows = []
    for gate, cases in GATE.items():
        for method, window in cases:
            for e, name in enumerate(NAMES):
                ours, pub = mean["A", method, name, window], PUBLISHED[(method, window)][e]
                rows.append({"gate": gate, "method": LABEL[method], "window_s": window, "electrode": name,
                             "published": pub, "ours": round(ours, 3), "ours_sem": round(sem["A", method, name, window], 3),
                             "difference": round(ours - pub, 3), "passed": bool(abs(ours - pub) <= TOL)})
    for method in ("cca", "fbcca_paper", "etrca_paper"):
        for window in (1.0, 2.0):
            d, w = mean["A", method, "dry", window], mean["A", method, "wet", window]
            rows.append({"gate": "G4", "method": LABEL[method], "window_s": window, "electrode": "wet minus dry",
                         "published": PUBLISHED[(method, window)][1] - PUBLISHED[(method, window)][0]
                         if (method, window) in PUBLISHED else np.nan,
                         "ours": round(w - d, 3), "ours_sem": np.nan, "difference": np.nan, "passed": bool(w > d)})
    rows.append({"gate": "G5", "method": "BETA: CCA, FBCCA, ensemble TRCA", "window_s": np.nan, "electrode": "",
                 "published": np.nan, "ours": np.nan, "ours_sem": np.nan, "difference": np.nan, "passed": "not run"})
    gate = pd.DataFrame(rows)
    gate.to_csv(RES / "gate.csv", index=False)
    print(gate.to_string(index=False))
    for gname in ("G1", "G2", "G3", "G4"):
        d = gate[gate.gate == gname]
        print(f"{gname}: {int((d.passed == True).sum())} of {len(d)} checks pass")          # noqa: E712

    # pre-specified variants A, B, C and the two post hoc diagnostic variants A+ and C-
    diag = pd.read_csv(RES / "wearable_accuracy_diagnostic.csv")
    mean5 = pd.concat([acc, diag]).groupby(["variant", "method", "electrode", "window_s"]).accuracy.mean()
    order5 = ["A", "A+", "B", "C-", "C"]
    print("\n== published values against all filtering variants (A, B, C pre-specified; A+ and C- post hoc)")
    print("   A: cut then filter, mains kept | A+: cut then filter, mains removed | B: past samples, mains removed")
    print("   C-: whole epoch, mains kept    | C: whole epoch, mains removed")
    rows = []
    for (method, window), pub in PUBLISHED.items():
        for e, name in enumerate(NAMES):
            rows.append({"method": LABEL[method], "window_s": window, "electrode": name, "published": pub[e],
                         **{v: round(mean5[v, method, name, window], 3) for v in order5}})
    comp = pd.DataFrame(rows)
    comp.to_csv(RES / "published_comparison.csv", index=False)
    print(comp.to_string(index=False))
    rows = []
    for v in order5:
        d = comp[comp.window_s.isin([1.0, 2.0])]                    # the 10 values of G1-G3
        dev_gate = (d[v] - d.published).abs()
        dev_all = (comp[v] - comp.published).abs()
        rows.append({"variant": v, "G1-G3 values within 0.05": f"{int((dev_gate <= TOL).sum())}/{len(d)}",
                     "largest deviation, G1-G3": dev_gate.max(), "mean deviation, G1-G3": dev_gate.mean(),
                     "all 14 published values within 0.05": f"{int((dev_all <= TOL).sum())}/{len(comp)}",
                     "largest deviation, all 14": dev_all.max()})
    other = pd.DataFrame(rows)
    other.to_csv(RES / "gate_other_variants.csv", index=False, float_format="%.3f")
    print("the same criterion applied to every variant (only A is the pre-registered gate):")
    print(other.round(3).to_string(index=False))
    print("\n== what breaks the reference convention: mains component x context of the filter, 1 s, a-priori weights")
    cells = {"window only": ("A", "A+"), "past samples + window": (None, "B"), "whole epoch": ("C-", "C")}
    rows = []
    for method in ("fbcca_apriori", "etrca_apriori"):
        for name in NAMES:
            for ctx, (kept, removed) in cells.items():
                rows.append({"method": LABEL[method], "electrode": name, "context": ctx,
                             "mains kept": mean5[kept, method, name, 1.0] if kept else np.nan,
                             "mains removed": mean5[removed, method, name, 1.0]})
    fact = pd.DataFrame(rows)
    fact.to_csv(RES / "mains_by_context_1s.csv", index=False, float_format="%.4f")
    print(fact.round(3).to_string(index=False))
    plain = pd.DataFrame([{"window_s": w, "electrode": n, "published FBTRCA": PUBLISHED[("etrca_paper", w)][e],
                           "TRCA (plain), C": round(mean["C", "trca_paper", n, w], 3),
                           "ensemble TRCA, C": round(mean["C", "etrca_paper", n, w], 3),
                           "TRCA (plain), B": round(mean["B", "trca_paper", n, w], 3),
                           "ensemble TRCA, B": round(mean["B", "etrca_paper", n, w], 3)}
                          for w in (0.2, 1.0, 2.0) for e, n in enumerate(NAMES)])
    print("plain against ensemble TRCA, published weights (the paper does not say which form it used):")
    print(plain.to_string(index=False))

    harm = pd.read_csv(RES / "wearable_cca_harmonics.csv").groupby(["electrode", "n_harmonics"]).accuracy.mean().unstack()
    print("\nCCA at 1 s against the number of harmonics (variant A):")
    for name in NAMES:
        print(f"  {name}: ours {harm.loc[name].round(3).tolist()}  published {list(PUBLISHED_CCA_HARMONICS[name])}")

    # ------------------------------------------------------------------ description
    print("\n== mean accuracy (SEM), project pipeline B")
    tab = summary[(summary.variant == "B") & summary.window_s.isin([0.2, 0.6, 1.0, 1.4, 2.0])]
    tab = tab.assign(cell=tab["mean"].map("{:.3f}".format) + " (" + tab["sem"].map("{:.3f}".format) + ")")
    print(tab.pivot(index=["method", "electrode"], columns="window_s", values="cell").to_string())

    print(f"\n== ITR (bits/min), project value T_sel = window + {GAZE} s, variant B: peak and its window")
    for method in ("cca", "fbcca_apriori", "etrca_apriori"):
        for name in NAMES:
            d = summary[(summary.variant == "B") & (summary.method == method) & (summary.electrode == name)]
            i, j = d.itr.idxmax(), d.itr_window_only.idxmax()
            print(f"  {LABEL[method]:34s} {name}: peak {d.itr[i]:6.1f} at {d.window_s[i]} s   "
                  f"(window-only convention of the paper: {d.itr_window_only[j]:6.1f} at {d.window_s[j]} s)")
    print("published peaks (window-only): FBCCA dry 72.25 (1.2 s), wet 125.6 (0.8 s); FBTRCA dry 201.2 (0.2 s), wet 499.5 (0.2 s)")
    for variant in ("A", "C"):
        for method in ("fbcca_paper", "etrca_paper"):
            for name in NAMES:
                d = summary[(summary.variant == variant) & (summary.method == method) & (summary.electrode == name)]
                j = d.itr_window_only.idxmax()
                print(f"  ours, variant {variant}, {LABEL[method]:34s} {name}: {d.itr_window_only[j]:6.1f} at {d.window_s[j]} s")

    print("\n== filtering variants: mean difference in accuracy, same person (a-priori weights)")
    wide = acc.pivot_table(index=["subject", "electrode", "method", "window_s"], columns="variant", values="accuracy")
    diff = pd.DataFrame({"B minus A": wide.B - wide.A, "C minus B": wide.C - wide.B}).reset_index()
    vt = diff[diff.method.isin(["cca", "fbcca_apriori", "etrca_apriori"])].groupby(["method", "electrode", "window_s"])[
        ["B minus A", "C minus B"]].mean().reset_index()
    vt.to_csv(RES / "variant_differences.csv", index=False, float_format="%.4f")
    for col in ("B minus A", "C minus B"):
        print(f"{col}:")
        print(vt.pivot(index=["method", "electrode"], columns="window_s", values=col).round(3).to_string())

    print("\n== optimism of the published weights: published minus a-priori weights, same person, variant B")
    m = acc[acc.variant == "B"].pivot_table(index=["subject", "electrode", "window_s"], columns="method", values="accuracy")
    opt = pd.DataFrame({"FBCCA": m.fbcca_paper - m.fbcca_apriori, "ensemble TRCA": m.etrca_paper - m.etrca_apriori}
                       ).reset_index().groupby(["electrode", "window_s"])[["FBCCA", "ensemble TRCA"]].mean()
    print(opt.unstack("window_s").round(3).to_string())

    # ------------------------------------------------------------------ people
    thr = mt.chance_threshold(120, 12)
    print(f"\n== people not above chance (accuracy below {thr:.3f} = {round(thr * 120)} of 120 trials), variant B")
    b = acc[acc.variant == "B"]
    for method in ("cca", "fbcca_apriori", "etrca_apriori"):
        for window in (1.0, 2.0):
            d = b[(b.method == method) & (b.window_s == window)]
            print(f"  {LABEL[method]:34s} {window} s: " + ", ".join(
                f"{name} {int((d[d.electrode == name].accuracy < thr).sum())}/{n_sub} at chance, "
                f"{int((d[d.electrode == name].accuracy >= 0.9).sum())}/{n_sub} at 0.9 or more" for name in NAMES))
    snr = pd.read_csv(ROOT / "results" / "m0" / "snr_per_subject.csv")[["subject", "electrode", "snr1_trial_oz"]]
    print("Spearman between accuracy (variant B) and the single-trial SNR at Oz of M0:")
    rel = []
    for method in ("fbcca_apriori", "etrca_apriori"):
        for window in (1.0, 2.0):
            for name in NAMES:
                d = b[(b.method == method) & (b.window_s == window) & (b.electrode == name)].merge(snr, on=["subject", "electrode"])
                rho = stats.spearmanr(d.accuracy, d.snr1_trial_oz)[0]
                rel.append({"method": LABEL[method], "window_s": window, "electrode": name, "spearman_rho": rho})
    print(pd.DataFrame(rel).round(3).to_string(index=False))

    # ------------------------------------------------------------------ dry against wet
    print("\n== dry minus wet, same person, variant B (descriptive; H1 is tested later as planned)")
    p = b.pivot_table(index=["subject", "first_headband", "method", "window_s"], columns="electrode", values="accuracy")
    p["d"] = p.dry - p.wet
    p = p.reset_index()
    gap = p.groupby(["method", "window_s"]).d.mean().unstack("window_s")
    gap.loc[["cca", "fbcca_apriori", "etrca_apriori"]].to_csv(RES / "dry_minus_wet_by_window.csv", float_format="%.4f")
    print("mean dry - wet by window:")
    print(gap.loc[["cca", "fbcca_apriori", "etrca_apriori"]].round(3).to_string())
    rows = []
    for method in ("fbcca_apriori", "etrca_apriori"):
        for window in (1.0, 2.0):
            d = p[(p.method == method) & (p.window_s == window)]
            dw, wd_ = d[d.first_headband == "Dry"].d, d[d.first_headband == "Wet"].d
            rows.append({"method": LABEL[method], "window_s": window,
                         "dry lower in": f"{int((d.d < 0).sum())}/{len(d)}",
                         "mean, dry worn first": dw.mean(), "n": len(dw), "mean, wet worn first": wd_.mean(), "n ": len(wd_),
                         "headband effect (mean of the two)": (dw.mean() + wd_.mean()) / 2,
                         "second-headband effect": (wd_.mean() - dw.mean()) / 2})
    cross = pd.DataFrame(rows)
    cross.to_csv(RES / "dry_minus_wet_by_order.csv", index=False, float_format="%.4f")
    print("by order of wearing (crossover view):")
    print(cross.round(3).to_string(index=False))
    print("time cost of dry electrodes: window the dry headband needs to reach the mean accuracy of the wet one")
    for method in ("fbcca_apriori", "etrca_apriori"):
        d = summary[(summary.variant == "B") & (summary.method == method)].pivot(index="window_s", columns="electrode", values="mean")
        cells = []
        for w in (0.4, 0.6, 0.8, 1.0, 1.2):
            target = d.wet[w]
            if d.dry.max() < target:
                cells.append(f"{w} s -> not reached within 2 s")
            else:
                need = np.interp(target, d.dry.to_numpy(), d.index.to_numpy())
                cells.append(f"{w} s -> {need:.2f} s (+{need - w:.2f})")
        print(f"  {LABEL[method]}: " + "; ".join(cells))

    # ------------------------------------------------------------------ confusions and compute
    conf = pd.read_csv(RES / "wearable_confusion_1s.csv")
    freqs = np.array([9.25, 11.25, 13.25, 9.75, 11.75, 13.75, 10.25, 12.25, 14.25, 10.75, 12.75, 14.75])
    conf["df"] = (freqs[conf.predicted_target - 1] - freqs[conf.true_target - 1]).round(2)
    print("\n== errors at 1 s (variant B): share of the errors that go to a target 0.5 Hz away, and to one within 1 Hz")
    for (name, method), d in conf.groupby(["electrode", "method"]):
        err = d[d.df != 0]
        tot = err["count"].sum()
        print(f"  {LABEL[method]:34s} {name}: errors {tot} of {d['count'].sum()}; 0.5 Hz away "
              f"{err[err.df.abs() == 0.5]['count'].sum() / tot:.2f} (chance 0.17), within 1 Hz "
              f"{err[err.df.abs() <= 1.0]['count'].sum() / tot:.2f} (chance 0.32)")
    by_target = conf[conf.df == 0].set_index(["electrode", "method", "true_target"])["count"] / n_sub / 10
    print("accuracy by target frequency (FBCCA a-priori, 1 s):")
    for name in NAMES:
        s = by_target[name, "fbcca_apriori"]
        print(f"  {name}: " + ", ".join(f"{freqs[t - 1]:g} Hz {s[t]:.2f}" for t in np.argsort(freqs) + 1))
    print("\n== compute time of one decision at 1 s (one core of this machine)")
    print(pd.read_csv(RES / "compute_time.csv").to_string(index=False))


if __name__ == "__main__":
    main()
