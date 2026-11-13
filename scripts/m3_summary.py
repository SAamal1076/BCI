"""M3: every number quoted in docs/milestones/M3_network.md. Reads results/m3 (and results/m2).

Descriptive statistics on the development people, 95 % bootstrap intervals over people, no p-value.

Usage: python scripts/m3_summary.py > logs/m3_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import metrics as mt  # noqa: E402
from ssvep import stats as st  # noqa: E402

RES, M2 = ROOT / "results" / "m3", ROOT / "results" / "m2"
NAMES = ("dry", "wet")
ORDER = ["fbcca", "template", "template_adapted", "net_A0", "net_A1", "net_A2", "net_online"]
LABEL = {"fbcca": "FBCCA", "template": "cross-subject template", "template_adapted": "template adapted without labels",
         "net_A0": "network, no adaptation", "net_A1": "network, A1 statistics", "net_A2": "network, A2 entropy",
         "net_online": "network, online"}


def ci(v, signed=True):
    lo, hi = st.bootstrap_ci(np.asarray(v))
    f = "+.3f" if signed else ".3f"
    return f"{np.mean(v):{f}} [{lo:{f}}, {hi:{f}}]"


def main():
    d = pd.read_csv(RES / "new_user_accuracy.csv")
    person = d.groupby(["subject", "electrode", "method"]).accuracy.mean().unstack("method")[ORDER]   # mean over seeds
    person.to_csv(RES / "per_person.csv", float_format="%.6f")
    n = person.index.get_level_values("subject").nunique()
    print(f"== 1. new users with no calibration, 1 s window, blocks 7-10: {n} development people, 4 folds of people")
    print("mean accuracy [95 % interval over people]; network: mean of 3 seeds per person")
    rows = [{"method": LABEL[m], **{el: ci(person.xs(el, level="electrode")[m], signed=False) for el in NAMES}} for m in ORDER]
    table = pd.DataFrame(rows)
    table.to_csv(RES / "summary.csv", index=False)
    print(table.to_string(index=False))

    print("\n== 2. differences, same people and trials: mean [95 % interval]; people better / equal / worse")
    pairs = [("template", "fbcca"), ("net_A0", "fbcca"), ("net_A0", "template"), ("net_A1", "net_A0"), ("net_A2", "net_A0"),
             ("net_A2", "net_A1"), ("net_online", "net_A0"), ("template_adapted", "template"), ("net_A2", "template_adapted")]
    rows = []
    for a, b in pairs:
        row = {"difference": f"{LABEL[a]}  minus  {LABEL[b]}"}
        for el in NAMES:
            p = person.xs(el, level="electrode")
            e = p[a] - p[b]
            row[el] = f"{ci(e)}  {int((e > 1e-9).sum())}/{int((e.abs() <= 1e-9).sum())}/{int((e < -1e-9).sum())}"
        rows.append(row)
    diffs = pd.DataFrame(rows)
    diffs.to_csv(RES / "differences.csv", index=False)
    print(diffs.to_string(index=False))

    print("\n== 3. H3 on the development people (descriptive; the tests are run on the lockbox)")
    g = (person["net_A2"] - person["net_A0"]).unstack("electrode")
    g.to_csv(RES / "adaptation_gain.csv", float_format="%.6f")
    for el in NAMES:
        print(f"  H3{'a' if el == 'dry' else 'b'}  g = A2 - A0, {el}: {ci(g[el])}; larger than 0 for {int((g[el] > 1e-9).sum())} people, "
              f"smaller for {int((g[el] < -1e-9).sum())}; largest loss {g[el].min():+.3f}, largest gain {g[el].max():+.3f}")
    print(f"  H3c  g(dry) - g(wet): {ci(g.dry - g.wet)}")
    low = person.xs("dry", level="electrode")["net_A0"] < person.xs("dry", level="electrode")["net_A0"].median()
    print(f"  dry: gain in the lower half of unadapted accuracy {ci(g.dry[low.to_numpy()])}, upper half {ci(g.dry[~low.to_numpy()])}")

    print("\n== 4. spread over the three seeds (mean accuracy over people, for each seed)")
    net = d[d.method.str.startswith("net")]
    by_seed = net.groupby(["method", "electrode", "seed"]).accuracy.mean().unstack("seed")
    by_seed["sd"] = by_seed.std(axis=1, ddof=1)
    print(by_seed.round(3).to_string())
    per = net[net.method == "net_A0"].pivot_table(index=["subject", "electrode"], columns="seed", values="accuracy")
    print(f"  one person, between seeds (no adaptation): mean standard deviation {per.std(axis=1, ddof=1).mean():.3f}")

    print("\n== 5. the template again: population of 51 people (these folds) against 67 (leave-one-subject-out, M2)")
    m2 = pd.read_csv(M2 / "new_user_frozen.csv")
    m2 = m2[(m2.window_s == 1.0) & (m2.k == 0)].pivot_table(index=["subject", "electrode"], columns="method", values="accuracy")
    both = person.join(m2, rsuffix="_m2")
    for el in NAMES:
        b = both.xs(el, level="electrode")
        print(f"  {el}: template 51 people {b.template.mean():.3f}, 67 people {b.cross.mean():.3f}, difference {ci(b.template - b.cross)}; "
              f"FBCCA identical: {bool(np.allclose(b.fbcca, b.fbcca_m2))}")
    pl = d[d.method == "template_adapted"].groupby("electrode").pseudo_label_accuracy.mean()
    print(f"  share of right decisions of the template on the unlabelled blocks 1-6 (its pseudo-labels): dry {pl['dry']:.3f}, wet {pl['wet']:.3f}")

    print("\n== 6. people (threshold for 48 trials)")
    thr = mt.chance_threshold(48, 12)
    for el in NAMES:
        p = person.xs(el, level="electrode")
        print(f"  {el}: not above chance (below {thr:.3f}): " + ", ".join(f"{LABEL[m]} {int((p[m] < thr).sum())}" for m in ("fbcca", "template", "net_A0", "net_A2"))
              + f"; at 0.9 or more: template {int((p.template >= 0.9).sum())}, network A0 {int((p.net_A0 >= 0.9).sum())}")

    log = pd.read_csv(RES / "training_log.csv")
    print(f"\n== 7. training: {len(log)} networks, {log.train_trials.iloc[0]} training trials each; epochs run {log.epochs_run.min()} to {log.epochs_run.max()} "
          f"(best epoch {log.best_epoch.min()} to {log.best_epoch.max()}); time {log.train_seconds.mean():.0f} s on average, {log.train_seconds.max():.0f} s at most")
    print(log.groupby("electrode")[["validation_accuracy", "validation_loss", "best_epoch"]].mean().round(3).to_string())
    print("\n== 8. size and compute")
    print(pd.read_csv(RES / "compute.csv").round(3).to_string(index=False))


if __name__ == "__main__":
    main()
