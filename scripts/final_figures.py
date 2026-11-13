"""Figures of the final evaluation, drawn from the tables of results/final/<set>. Written before the opening.

  01_tests.png        the 15 estimates with their 95 % intervals, one panel per hypothesis
  02_calibration.png  accuracy of the new people against the number of calibration blocks, next to M2

Usage: python scripts/final_figures.py --set rehearsal|lockbox     (after final_evaluation.py evaluate)
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import final_evaluation as fe  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import stats as st  # noqa: E402

plt = pl.plt
NAMES = ("dry", "wet")
PANELS = (("H1", "H1  dry minus wet accuracy", "hypothesis: below 0", 0.0),
          ("H2", "H2  template + 2 blocks minus eTRCA + 6 blocks", "hypothesis: above the margin of -0.05", -fe.MARGIN),
          ("H3", "H3  network, adaptation minus none", "hypothesis: above 0", 0.0),
          ("H5a", "H5a  slope of accuracy per block", "hypothesis: below 0", 0.0),
          ("H5b", "H5b  correlation of impedance with accuracy", "hypothesis: below 0", 0.0),
          ("H6", "H6  adapted template minus template", "hypothesis: above 0", 0.0))


def fig_tests(tests, n_people, name):
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 6.4))
    decided = "supported" in tests
    for ax, (hyp, title, xlabel, line) in zip(axes.ravel(), PANELS):
        t = tests[tests.hypothesis == hyp].reset_index(drop=True)
        y, labels = np.arange(len(t))[::-1], []
        ax.axvline(line, color=pl.INK, lw=0.9)
        if hyp == "H2":
            ax.axvline(0.0, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
        for yi, r in zip(y, t.itertuples()):
            color = pl.COLOR.get(r.case, pl.NEUTRAL)
            ax.plot([r.ci_low, r.ci_high], [yi, yi], color=color, lw=2)
            filled = not decided or bool(r.supported)
            ax.scatter([r.estimate], [yi], s=62, color=color if filled else pl.SURFACE, edgecolor=color if not filled else pl.SURFACE,
                       linewidth=1.6 if not filled else 0.9, zorder=3)
            text = f"{r.estimate:+.3f}"
            if decided:
                text += f"   p {r.p_holm:.2g}"
            labels.append((yi, text))
        lo, hi = min(t.ci_low.min(), line), max(t.ci_high.max(), line)
        pad = 0.08 * (hi - lo)
        for yi, text in labels:                                        # one column of values, right of every interval
            ax.annotate(text, (hi + pad, yi), va="center", fontsize=8.5, color=pl.INK)
        ax.set(title=title, xlabel=xlabel, yticks=y, ylim=(-0.6, len(t) - 0.4), xlim=(lo - pad, hi + (0.85 if decided else 0.42) * (hi - lo)))
        ax.set_yticklabels(t.case)
        ax.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax.grid(axis="y", visible=False)
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.11, top=0.84, wspace=0.4, hspace=0.62)
    if decided:
        title = f"{int(tests.supported.sum())} of 15 tests supported after the Holm correction ({n_people} lockbox people, opened once)"
        note = ("Dot: estimate; filled: supported, open: not supported. Line: 95 % bootstrap interval over people. "
                "p: one-sided, after the Holm correction (familywise level 0.05).")
    else:
        title = f"Rehearsal on {n_people} development people: the 15 estimates, p-values withheld"
        note = "Dot: estimate. Line: 95 % bootstrap interval over people. The lockbox was not touched."
    return fig, title, note


def fig_calibration(acc, ref, n_people, name):
    mean = lambda d: d.groupby(["method", "k", "electrode", "subject"]).accuracy.mean()       # noqa: E731
    new = mean(acc[(acc.design == "new_user") & (acc.window_s == 1.0)])
    old = mean(ref[(ref.design == "new_user") & (ref.window_s == 1.0)])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.9), sharey=True)
    styles = {"template": ("-", "o"), "etrca": ((0, (4, 2)), "s")}
    for ax, el in zip(axes, NAMES):
        color = pl.COLOR[el]
        f = new.loc[("fbcca", 0, el)]
        ax.axhline(f.mean(), color=pl.NEUTRAL, lw=1.4, ls=(0, (1, 2)))
        ax.annotate("FBCCA, no data from anyone", (-0.25, f.mean()), xytext=(0, -4), textcoords="offset points", ha="left", va="top",
                    fontsize=8.5, color=pl.INK)
        for method, (ls, marker) in styles.items():
            ks = sorted(k for m, k, e in set(new.index.droplevel("subject")) if m == method and e == el)
            v = [new.loc[(method, k, el)] for k in ks]
            lo, hi = zip(*[st.bootstrap_ci(x.to_numpy()) for x in v])
            ax.fill_between(ks, lo, hi, color=color, alpha=0.13, lw=0)
            ax.plot(ks, [x.mean() for x in v], color=color, ls=ls, marker=marker, ms=6.5, mec=pl.SURFACE, mew=1)
            ax.plot(ks, [old.loc[(method, k, el)].mean() for k in ks], ls="none", marker=marker, ms=6.5, mfc="none", mec=pl.INK2, mew=1.2)
        ax.set(title=f"{el.capitalize()} headband", xlabel="Calibration blocks of the new user (one block = 48 s)", xticks=[0, 1, 2, 4, 6],
               xlim=(-0.3, 6.3))
    axes[0].set(ylabel="Accuracy at 1 s, blocks 7 to 10")
    before = "the same people in M2" if name == "rehearsal" else "the 68 development people (M2)"
    handles = [plt.Line2D([], [], color=pl.INK2, ls="-", marker="o", ms=6, mec=pl.SURFACE, label="cross-subject template"),
               plt.Line2D([], [], color=pl.INK2, ls=(0, (4, 2)), marker="s", ms=6, mec=pl.SURFACE, label="ensemble TRCA, own data only"),
               plt.Line2D([], [], color=pl.INK2, ls="none", marker="o", ms=6, mfc="none", mew=1.2, label=before)]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=3)
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.17, top=0.78, wspace=0.06)
    t2, e6 = new.loc[("template", 2)].groupby("electrode").mean(), new.loc[("etrca", 6)].groupby("electrode").mean()
    who = "development people (rehearsal)" if name == "rehearsal" else "lockbox people"
    title = f"{n_people} {who}: template + 2 blocks {t2.dry:.2f} dry, {t2.wet:.2f} wet; eTRCA + 6 blocks {e6.dry:.2f}, {e6.wet:.2f}"
    note = "Lines: mean over the new people, band: 95 % bootstrap interval. Open markers: earlier result on development people."
    return fig, title, note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="name", choices=["rehearsal", "lockbox"], default="rehearsal")
    args = ap.parse_args()
    res = fe.folder(args.name)
    out = ROOT / "figures" / "final" / ("rehearsal" if args.name == "rehearsal" else "")
    out.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    acc, tests = pd.read_csv(res / "accuracy.csv"), pd.read_csv(res / "tests.csv")
    n = acc.subject.nunique()
    ref = fe.earlier()
    if args.name == "rehearsal":
        ref = ref[ref.subject.isin(acc.subject.unique())]
    for stem, (fig, title, note) in (("01_tests", fig_tests(tests, n, args.name)), ("02_calibration", fig_calibration(acc, ref, n, args.name))):
        pl.save(fig, out / f"{stem}.png", title, note)
        print(f"{(out / f'{stem}.png').relative_to(ROOT)}: {title}")


if __name__ == "__main__":
    main()
