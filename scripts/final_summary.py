"""Descriptive numbers of the final report that are not among the 15 tests.

WRITTEN AFTER THE OPENING of the lockbox. It reads the result files only (results/final/lockbox and the
development results of M2 to M4), decodes nothing and runs no test. Every number is a mean with a 95 %
bootstrap interval over people; none of it changes a method, a setting or a test.

Usage: python scripts/final_summary.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import final_evaluation as fe  # noqa: E402
from ssvep import stats as st  # noqa: E402

NAMES = ("dry", "wet")
PAIRS = [("template", 0, "fbcca", 0, "template minus FBCCA"),
         ("template_adapted", 0, "fbcca", 0, "adapted template minus FBCCA"),
         ("template", 0, "net_A0", 0, "template minus network (A0)"),
         ("template_adapted", 0, "net_A2", 0, "adapted template minus adapted network (A2)"),
         ("template", 2, "own", 2, "template + 2 blocks minus own template, 2 blocks"),
         ("template", 6, "own", 6, "template + 6 blocks minus own template, 6 blocks"),
         ("own", 6, "etrca", 6, "own template minus eTRCA, 6 blocks")]


def ci(v):
    v = np.asarray(v, dtype=float)
    lo, hi = st.bootstrap_ci(v)
    return f"{v.mean():+.3f} [{lo:+.3f}, {hi:+.3f}]"


def person_means(table, design):
    d = table[(table.design == design) & (table.window_s == 1.0)]
    return d.groupby(["method", "k", "electrode", "subject"]).accuracy.mean()


def main():
    acc = pd.read_csv(fe.folder("lockbox") / "accuracy.csv")
    tests = pd.read_csv(fe.folder("lockbox") / "tests.csv")
    dev = fe.earlier()
    print("== descriptive numbers of the final report; written after the opening; result files only; no test")
    print(f"lockbox people: {acc.subject.nunique()}, development people: {dev.subject.nunique()}")

    print("\n== 1. paired differences between methods, blocks 7 to 10, 1 s: mean [95 % interval over people]")
    new, old = person_means(acc, "new_user"), person_means(dev, "new_user")
    rows = []
    for a, ka, b, kb, label in PAIRS:
        row = {"difference": label}
        for el in NAMES:
            row[f"{el}, lockbox"] = ci(new.loc[(a, ka, el)] - new.loc[(b, kb, el)])
            row[f"{el}, development"] = ci(old.loc[(a, ka, el)] - old.loc[(b, kb, el)])
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
    print("development: template and FBCCA from M2 (population of 67), adapted template and networks from M3 (population of 51)")

    print("\n== 2. lockbox mean minus development mean (different people, so not paired), blocks 7 to 10, 1 s")
    rows = []
    for method, k in [("fbcca", 0), ("template", 0), ("template_adapted", 0), ("net_A0", 0), ("net_A2", 0), ("template", 2), ("own", 6), ("etrca", 6)]:
        row = {"method": method, "k": k}
        for el in NAMES:
            a, b = new.loc[(method, k, el)], old.loc[(method, k, el)]
            row[el] = f"{a.mean():.3f} - {b.mean():.3f} = {a.mean() - b.mean():+.3f}"
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== 3. dry minus wet and the headband worn second, ten blocks, 1 s (crossover estimates)")
    first = acc.drop_duplicates("subject").set_index("subject").first_headband.str.lower().str.startswith("dry")
    ten = person_means(acc, "ten_blocks")
    for method in ("fbcca", "etrca_lobo", "template"):
        a = ten.loc[(method, 0)].unstack("electrode")
        d, f = (a.dry - a.wet).to_numpy(), first.loc[a.index].to_numpy()
        lo, hi = st.crossover_ci(d, f)
        period = 0.5 * (d[~f].mean() - d[f].mean())
        print(f"  {method:10s} dry minus wet {st.crossover_effect(d, f):+.3f} [{lo:+.3f}, {hi:+.3f}]; dry worn first ({int(f.sum())} people): "
              f"dry {a.dry[f].mean():.3f}, wet {a.wet[f].mean():.3f}; wet worn first ({int((~f).sum())}): wet {a.wet[~f].mean():.3f}, "
              f"dry {a.dry[~f].mean():.3f}; effect of being the second headband {period:+.3f}")

    print("\n== 4. each person: how many are better with the adapted template, and with 2 blocks of calibration")
    for el in NAMES:
        h6 = new.loc[("template_adapted", 0, el)] - new.loc[("template", 0, el)]
        h2 = new.loc[("template", 2, el)] - new.loc[("etrca", 6, el)]
        print(f"  {el}: adapted template better for {int((h6 > 0).sum())}, equal for {int((h6 == 0).sum())}, worse for {int((h6 < 0).sum())} of {len(h6)}; "
              f"template + 2 blocks at least as good as eTRCA + 6 blocks for {int((h2 >= 0).sum())}, within 0.05 for {int((h2 >= -0.05).sum())}")

    print("\n== 5. expectation written in the plan before the opening, and the outcome")
    expected = {"H1": "supported", "H2 dry": "supported", "H2 wet": "uncertain", "H3": "not supported", "H5a": "not supported",
                "H5b": "not supported", "H6": "supported"}
    for key, exp in expected.items():
        hyp, _, case = key.partition(" ")
        t = tests[(tests.hypothesis == hyp) & ((tests.case == case) if case else True)]
        out = "supported" if t.supported.all() else ("not supported" if not t.supported.any() else "mixed")
        print(f"  {key:7s} expected: {exp:14s} outcome: {out} ({int(t.supported.sum())} of {len(t)} tests)")


if __name__ == "__main__":
    main()
