"""M4: every number quoted in docs/milestones/M4_failures.md. Reads results/m4, m0 and m2.

Descriptive statistics on the development people, 95 % bootstrap intervals over people, no p-value.

Usage: python scripts/m4_summary.py > logs/m4_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import keypad as kp  # noqa: E402
from ssvep import metrics as mt  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

RES, M0, M2 = ROOT / "results" / "m4", ROOT / "results" / "m0", ROOT / "results" / "m2"
NAMES = ("dry", "wet")


def ci(v, f="+.3f"):
    v = np.asarray(v, dtype=float)
    lo, hi = st.bootstrap_ci(v)
    return f"{v.mean():{f}} [{lo:{f}}, {hi:{f}}]"


def rho_ci(x, y, n_boot=2000, seed=0):
    """Spearman correlation with a percentile interval (people resampled)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (n_boot, len(x)))
    boot = [stats.spearmanr(x[i], y[i])[0] for i in idx]
    lo, hi = np.nanquantile(boot, [0.025, 0.975])
    return f"{stats.spearmanr(x, y)[0]:+.2f} [{lo:+.2f}, {hi:+.2f}]"


def main():
    d = pd.read_csv(RES / "decisions_1s.csv")
    d["ok"] = d.template == d.target
    d["ok_fbcca"] = d.fbcca == d.target
    first = d.drop_duplicates("subject").set_index("subject").first_headband.str.lower().str.startswith("dry")
    n = d.subject.nunique()
    blocks = d.groupby(["subject", "electrode", "block"]).ok.mean().unstack("block")          # (person, headband) x 10 blocks
    acc = d.groupby(["subject", "electrode"]).ok.mean().unstack("electrode")
    acc_f = d.groupby(["subject", "electrode"]).ok_fbcca.mean().unstack("electrode")

    print(f"== A. time on task: {n} development people, cross-subject template, no calibration, 1 s")
    by_block = blocks.groupby("electrode").mean()
    by_block.to_csv(RES / "accuracy_by_block.csv", float_format="%.4f")
    print("mean accuracy per block:")
    print(by_block.round(3).to_string())
    slope = pd.DataFrame({"accuracy": st.block_slope(blocks.to_numpy())}, index=blocks.index)
    snr = pd.read_csv(M0 / "snr_per_subject_block.csv").pivot_table(index=["subject", "electrode"], columns="block", values="snr1_trial_oz")
    imp = pd.read_csv(RES / "impedance_blocks.csv").pivot_table(index=["subject", "electrode"], columns="block", values="median_kohm")
    slope["snr_db"] = st.block_slope(snr.loc[blocks.index].to_numpy())
    slope["log10_impedance"] = st.block_slope(np.log10(imp.loc[blocks.index].to_numpy()))
    slope.to_csv(RES / "slopes.csv", float_format="%.6f")
    print("\nslope per block, mean over people [95 % interval]; people with a negative accuracy slope:")
    for el in NAMES:
        s = slope.xs(el, level="electrode")
        print(f"  {el}: accuracy {ci(s.accuracy, '+.4f')} per block (over 9 steps: {9 * s.accuracy.mean():+.3f}); negative for "
              f"{int((s.accuracy < 0).sum())}, positive for {int((s.accuracy > 0).sum())} of {len(s)}")
        print(f"        SNR at Oz {ci(s.snr_db, '+.3f')} dB per block; log10 impedance {ci(s.log10_impedance, '+.4f')} per block "
              f"(x{10 ** (9 * s.log10_impedance.mean()):.2f} over the 10 blocks)")
    print("first half (blocks 1-5) against second half (blocks 6-10), accuracy:")
    for el in NAMES:
        b = blocks.xs(el, level="electrode")
        print(f"  {el}: {b[[1, 2, 3, 4, 5]].mean(axis=1).mean():.3f} then {b[[6, 7, 8, 9, 10]].mean(axis=1).mean():.3f}, "
              f"difference {ci(b[[6, 7, 8, 9, 10]].mean(axis=1) - b[[1, 2, 3, 4, 5]].mean(axis=1))}")
    print("the session as worn (first headband, then second), mean accuracy:")
    for order, lab in ((True, "dry worn first"), (False, "wet worn first")):
        who = first.index[first == order]
        a = acc.loc[who]
        f, s2 = ("dry", "wet") if order else ("wet", "dry")
        print(f"  {lab} ({len(who)} people): first headband ({f}) {a[f].mean():.3f}, second headband ({s2}) {a[s2].mean():.3f}")
    dd = acc.dry - acc.wet
    period = 0.5 * (dd[first[acc.index].to_numpy()].mean() - dd[~first[acc.index].to_numpy()].mean())
    print(f"  effect of being the second headband (crossover estimate): {-period:+.3f}")

    age = pd.read_csv(RES / "ageing_1s.csv")
    print("\nageing of a calibration: template from the person's blocks 1 and 2, tested on blocks 3 to 10")
    print(age.groupby(["electrode", "block"])[["own_blocks_1_2", "template"]].mean().unstack("block").round(3).to_string())
    for el in NAMES:
        a = age[age.electrode == el]
        own = st.block_slope(a.pivot(index="subject", columns="block", values="own_blocks_1_2").to_numpy())
        tem = st.block_slope(a.pivot(index="subject", columns="block", values="template").to_numpy())
        print(f"  {el}: slope over blocks 3-10, own blocks 1-2: {ci(own, '+.4f')}; no calibration: {ci(tem, '+.4f')}; difference {ci(own - tem, '+.4f')}")

    print("\n== B. impedance")
    z = np.log10(imp.median(axis=1)).rename("z").reset_index()
    noise = pd.read_csv(M0 / "noise_per_subject.csv").assign(electrode=lambda t: t.eeg_index.map({1: "dry", 2: "wet"}))
    snr1 = pd.read_csv(M0 / "snr_per_subject.csv")[["subject", "electrode", "snr1_trial_oz"]]
    people = (acc.stack().rename("accuracy").reset_index().merge(z, on=["subject", "electrode"])
              .merge(noise[["subject", "electrode", "line50", "floor_adopted"]], on=["subject", "electrode"])
              .merge(snr1, on=["subject", "electrode"])
              .merge(acc_f.stack().rename("fbcca").reset_index(), on=["subject", "electrode"]))
    people.to_csv(RES / "people.csv", index=False, float_format="%.5f")
    rows = []
    for el in NAMES:
        p = people[people.electrode == el]
        print(f"  {el}: median impedance over people {10 ** p.z.median():.0f} kOhm (range {10 ** p.z.min():.0f} to {10 ** p.z.max():.0f})")
        for col, lab in (("accuracy", "accuracy (H5b)"), ("snr1_trial_oz", "single-trial SNR at Oz"), ("floor_adopted", "noise floor"),
                         ("line50", "mains pick-up")):
            rows.append({"electrode": el, "impedance against": lab, "spearman [95 % interval]": rho_ci(p.z, p[col])})
    print(pd.DataFrame(rows).to_string(index=False))
    within = []
    for (sid, el), a in blocks.iterrows():
        r = stats.spearmanr(np.log10(imp.loc[(sid, el)].to_numpy()), a.to_numpy())[0]
        within.append((sid, el, r))
    within = pd.DataFrame(within, columns=["subject", "electrode", "rho"]).dropna()
    for el in NAMES:
        w = within[within.electrode == el].rho
        print(f"  within a person, impedance of a block against accuracy of that block, {el}: mean Spearman {ci(w, '+.2f')}, "
              f"negative for {int((w < 0).sum())} of {len(w)} people")

    print("\n== C. who fails")
    thr = mt.chance_threshold(120, 12)
    two = pd.read_csv(RES / "accuracy_2s.csv").pivot(index="subject", columns="electrode", values="template")
    m2 = pd.read_csv(M2 / "baseline_accuracy.csv")
    etrca = m2[(m2.method == "etrca") & (m2.window_s == 1.0)].pivot(index="subject", columns="electrode", values="accuracy")
    fail = acc < thr
    print(f"not above chance at 1 s (below {thr:.3f} over 120 trials): dry {int(fail.dry.sum())}, wet {int(fail.wet.sum())} of {n}; "
          f"dry only {int((fail.dry & ~fail.wet).sum())}, wet only {int((~fail.dry & fail.wet).sum())}, both {int((fail.dry & fail.wet).sum())}")
    print(f"with FBCCA: dry {int((acc_f.dry < thr).sum())}, wet {int((acc_f.wet < thr).sum())}")
    pw = people.pivot(index="subject", columns="electrode")
    table = []
    for el in NAMES:
        other = "wet" if el == "dry" else "dry"
        for sid in fail.index[fail[el]]:
            table.append({"subject": sid, "fails with": el, "accuracy 1 s": acc.loc[sid, el], "other headband 1 s": acc.loc[sid, other],
                          "same headband 2 s": two.loc[sid, el], "ensemble TRCA 1 s": etrca.loc[sid, el],
                          "SNR dB": pw["snr1_trial_oz"].loc[sid, el], "noise floor": pw["floor_adopted"].loc[sid, el],
                          "mains uV": pw["line50"].loc[sid, el], "impedance kOhm": 10 ** pw["z"].loc[sid, el],
                          "worn": "first" if (first[sid] == (el == "dry")) else "second"})
    table = pd.DataFrame(table)
    table.to_csv(RES / "failures.csv", index=False, float_format="%.4f")
    print(table.round(3).to_string(index=False))
    for el in NAMES:
        p = people[people.electrode == el].set_index("subject")
        f = fail[el].reindex(p.index)
        if f.sum():
            print(f"  {el}: failing against the others, medians: " + "; ".join(
                f"{lab} {p.loc[f, col].median():.2f} / {p.loc[~f, col].median():.2f}"
                for col, lab in (("snr1_trial_oz", "SNR dB"), ("floor_adopted", "noise floor"), ("line50", "mains uV"))) +
                f"; impedance kOhm {10 ** p.loc[f, 'z'].median():.0f} / {10 ** p.loc[~f, 'z'].median():.0f}")
    low = acc < 0.30
    print(f"below 0.30 at 1 s: dry {int(low.dry.sum())}, wet {int(low.wet.sum())}, both {int((low.dry & low.wet).sum())}; "
          f"Spearman of a person's dry accuracy with their wet accuracy: {rho_ci(acc.dry, acc.wet)}")
    rows = []
    for el in NAMES:
        p = people[people.electrode == el]
        rows.append({"electrode": el, **{lab: rho_ci(p.accuracy, p[col]) for col, lab in (
            ("snr1_trial_oz", "SNR"), ("floor_adopted", "noise floor"), ("line50", "mains pick-up"), ("z", "impedance"))}})
    print("Spearman of accuracy with the label-free measures of M0 [95 % interval]:")
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== D. what is confused (1 s)")
    cls, expected = kp.error_class(), kp.expected_shares()
    rows = []
    for method in ("template", "fbcca"):
        for el in NAMES:
            e = d[(d.electrode == el) & (d[method] != d.target)]
            c = cls[e.target.to_numpy() - 1, e[method].to_numpy() - 1]
            share = np.bincount(c, minlength=4) / len(c)
            rows.append({"decoder": method, "electrode": el, "errors": len(e), **{kp.CLASSES[k]: f"{share[k]:.3f}" for k in range(4)}})
    rows.append({"decoder": "even spread", "electrode": "", "errors": "", **{kp.CLASSES[k]: f"{expected[k]:.3f}" for k in range(4)}})
    conf = pd.DataFrame(rows)
    conf.to_csv(RES / "error_classes.csv", index=False)
    print(conf.to_string(index=False))
    fn = kp.frequency_neighbours()
    for el in NAMES:
        e = d[(d.electrode == el) & ~d.ok]
        m = np.zeros((12, 12))
        np.add.at(m, (e.target.to_numpy() - 1, e.template.to_numpy() - 1), 1)
        per_pair = m / m.sum()
        print(f"  {el}: an error goes to a given frequency neighbour {per_pair[fn].sum() / fn.sum() * 132:.2f} times as often as to an "
              f"average wrong target; to a given keypad neighbour (not a frequency neighbour) "
              f"{per_pair[cls == 2].sum() / (cls == 2).sum() * 132:.2f} times")
        share = d[d.electrode == el].groupby("template").size() / (d.electrode == el).sum()
        top = share.sort_values(ascending=False)
        print(f"       share of the decisions per target: from {top.iloc[-1]:.3f} ({wd.TARGET_FREQS[top.index[-1] - 1]:g} Hz) to "
              f"{top.iloc[0]:.3f} ({wd.TARGET_FREQS[top.index[0] - 1]:g} Hz); 0.083 without bias")
        by_t = d[d.electrode == el].groupby("target").ok.mean()
        print(f"       accuracy per target: lowest {by_t.min():.3f} ({wd.TARGET_FREQS[by_t.idxmin() - 1]:g} Hz), highest {by_t.max():.3f} "
              f"({wd.TARGET_FREQS[by_t.idxmax() - 1]:g} Hz)")


if __name__ == "__main__":
    main()
