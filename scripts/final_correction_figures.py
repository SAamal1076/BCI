"""Figure of the correction of the final evaluation, drawn from results/final/<set> and results/final/<set>_corrected.
Written before the corrected run on the lockbox people.

  03_correction.png   left: accuracy by target with the dry headband, original and corrected template;
                      right: the four tests that use the dry template, original and corrected

Usage: python scripts/final_correction_figures.py --set rehearsal|lockbox     (after final_correction.py evaluate)
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import final_correction as fc  # noqa: E402
import final_evaluation as fe  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

plt = pl.plt
TITLES = {"H2": ("H2  template + 2 blocks minus eTRCA + 6", "hypothesis: above the margin of -0.05", -fe.MARGIN),
          "H5a": ("H5a  slope of accuracy per block", "hypothesis: below 0", 0.0),
          "H5b": ("H5b  correlation of impedance with accuracy", "hypothesis: below 0", 0.0),
          "H6": ("H6  adapted template minus template", "hypothesis: above 0", 0.0)}


def by_target(decisions, column):
    d = decisions[decisions.electrode == "dry"]
    return d.assign(ok=d[column] == d.target).groupby("target").ok.mean()


def figure(name):
    ref, out = fe.folder(name), fc.folder(name)
    dec0, dec1 = pd.read_csv(ref / "decisions_1s.csv"), pd.read_csv(out / "decisions_1s.csv")
    t = fc.comparison(ref, out)
    decided = "supported_original" in t
    n = dec1.subject.nunique()
    dry = pl.COLOR["dry"]

    fig = plt.figure(figsize=(13.5, 6.0))
    outer = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.42], left=0.052, right=0.885 if decided else 0.955, bottom=0.115, top=0.855, wspace=0.2)
    grid = outer[1].subgridspec(2, 2, wspace=1.3 if decided else 0.62, hspace=0.8)

    ax = fig.add_subplot(outer[0])                                     # accuracy by target
    order = np.argsort(wd.TARGET_FREQS)
    x = np.arange(12)
    a0, a1, fb = (by_target(d, col).to_numpy()[order] for d, col in ((dec0, "template"), (dec1, "template"), (dec1, "fbcca")))
    ax.vlines(x, a0, a1, color=pl.INK2, lw=1.2, zorder=2)
    ax.scatter(x, fb, marker="_", s=220, color=pl.INK2, linewidth=1.6, zorder=2, label="FBCCA (uses no template)")
    ax.scatter(x, a0, s=70, color=pl.SURFACE, edgecolor=pl.NEUTRAL, linewidth=1.8, zorder=3, label="template, original")
    ax.scatter(x, a1, s=70, color=dry, edgecolor=pl.SURFACE, linewidth=0.9, zorder=4, label="template, corrected")
    left = fc.saturated_trials()
    for t_ in sorted({tt for _, e, _, tt in left if e == wd.DRY}):
        i = int(np.flatnonzero(order == t_)[0])
        ax.annotate(f"{wd.TARGET_FREQS[t_]} Hz: {a0[i]:.2f} to {a1[i]:.2f}\nthe target of the saturated trial", (i, a0[i]), xytext=(14, -2),
                    textcoords="offset points", va="top", fontsize=9, color=pl.INK)
    ax.set(xticks=x, ylabel="Accuracy at 1 s, no calibration, all ten blocks", xlabel="Target frequency (Hz)",
           ylim=(0, max(0.8, 1.08 * max(a0.max(), a1.max(), fb.max()))), title="Dry headband: accuracy by target")
    ax.set_xticklabels([f"{f:g}" for f in wd.TARGET_FREQS[order]], fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower right", ncol=1)

    for cell, r in zip(((0, 0), (0, 1), (1, 0), (1, 1)), t[t.uses_dry_template].itertuples()):        # the four tests
        ax = fig.add_subplot(grid[cell])
        title, xlabel, line = TITLES[r.hypothesis]
        ax.axvline(line, color=pl.INK, lw=0.9)
        rows = (("original", r.estimate_original, r.ci_low_original, r.ci_high_original, pl.NEUTRAL),
                ("corrected", r.estimate_corrected, r.ci_low_corrected, r.ci_high_corrected, dry))
        lo, hi = min(r.ci_low_original, r.ci_low_corrected, line), max(r.ci_high_original, r.ci_high_corrected, line)
        pad = 0.08 * (hi - lo)
        for y, (label, est, cl, ch, color) in zip((1, 0), rows):
            ax.plot([cl, ch], [y, y], color=color, lw=2)
            ax.scatter([est], [y], s=62, color=color, edgecolor=pl.SURFACE, linewidth=0.9, zorder=3)
            text = f"{est:+.3f}"
            if decided:
                p, ok = getattr(r, f"p_holm_{label}"), getattr(r, f"supported_{label}")
                text += f"\np {p:.2g}, {'supported' if ok else 'not supported'}"
            ax.annotate(text, (1.03, y), xycoords=("axes fraction", "data"), va="center", fontsize=8.5, color=pl.INK, annotation_clip=False)
        ax.set(xlabel=xlabel, yticks=(1, 0), ylim=(-0.6, 1.6), xlim=(lo - pad, hi + pad))
        ax.set_title(title, fontsize=9.5, x=-0.33)
        ax.set_yticklabels(["original", "corrected"])
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.grid(axis="y", visible=False)

    i = int(np.flatnonzero(order == 3)[0])
    if decided:
        flips = int((t.supported_original != t.supported_corrected).sum())
        title = (f"One saturated trial left out of the template: dry accuracy at 9.75 Hz {a0[i]:.2f} to {a1[i]:.2f}; "
                 f"{flips} of the 15 test decisions change")
        note = (f"{n} lockbox people. The corrected analysis was computed after the opening; it is not a second test. Right: the four tests that use the "
                "dry template; dot: estimate, line: 95 % interval, p: after Holm.")
    else:
        title = f"Rehearsal on {n} development people: dry accuracy at 9.75 Hz {a0[i]:.2f} to {a1[i]:.2f} without the saturated trial"
        note = ("Right: the four tests that use the dry template; dot: estimate, line: 95 % bootstrap interval over people. "
                "p-values withheld. The lockbox was not touched.")
    return fig, title, note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="name", choices=["rehearsal", "lockbox"], default="rehearsal")
    args = ap.parse_args()
    out = ROOT / "figures" / "final" / ("rehearsal" if args.name == "rehearsal" else "")
    out.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    fig, title, note = figure(args.name)
    pl.save(fig, out / "03_correction.png", title, note)
    print(f"{(out / '03_correction.png').relative_to(ROOT)}: {title}")


if __name__ == "__main__":
    main()
