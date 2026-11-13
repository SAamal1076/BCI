"""Graphical abstract of the project, drawn from the result files of the final evaluation (lockbox people).

  figures/graphical_abstract.png   setting | accuracy against calibration time | the hypotheses, tested once

No data file is opened: results/final/lockbox/accuracy.csv and tests.csv only.

Usage: python scripts/m6_graphical_abstract.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import keypad as kp  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

plt = pl.plt
RES = ROOT / "results" / "final" / "lockbox"
BLOCK_S = 48                                                           # one calibration block: 12 trials of 4 s
# back view of the head: rough places of the 8 channels (schematic, not to scale)
PLACES = {"POz": (0.0, 0.34), "PO3": (-0.26, 0.30), "PO4": (0.26, 0.30), "PO5": (-0.50, 0.20), "PO6": (0.50, 0.20),
          "Oz": (0.0, 0.02), "O1": (-0.27, 0.0), "O2": (0.27, 0.0)}


def disc(ax, xy, r, **kw):
    """A disc that looks round on axes whose x and y units differ (r is in x units)."""
    box = ax.get_window_extent()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    ratio = (box.width / (x1 - x0)) / (box.height / (y1 - y0))          # one x unit in y units
    patch = Ellipse(xy, 2 * r, 2 * r * ratio, **kw)
    ax.add_patch(patch)
    return patch


def panel_setting(ax, n_dev, n_box):
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.axis("off")
    ax.text(0, 9.75, "A new user, a wearable headband", fontsize=13.5, fontweight="bold", va="top")
    # the 12 targets
    for i, (char, f) in enumerate(zip(wd.TARGET_CHARS, wd.TARGET_FREQS)):
        x, y = 0.15 + 1.2 * kp.COL[i], 7.75 - 1.12 * kp.ROW[i]
        ax.add_patch(FancyBboxPatch((x, y), 1.0, 0.92, boxstyle="round,pad=0,rounding_size=0.14", fc=pl.SURFACE, ec=pl.INK2, lw=1.1))
        ax.text(x + 0.5, y + 0.60, char, ha="center", va="center", fontsize=12.5, fontweight="bold")
        ax.text(x + 0.5, y + 0.22, f"{f:g}", ha="center", va="center", fontsize=7.6, color=pl.INK2)
    ax.text(0.15, 5.12, "12 flickering targets (Hz)", fontsize=10.5, color=pl.INK2, va="top")
    # the head, seen from behind
    cx, cy, r = 7.75, 7.05, 1.75
    head = disc(ax, (cx, cy), r, fc=pl.SURFACE, ec=pl.INK2, lw=1.3)
    band = Rectangle((cx - r, cy - 0.75), 2 * r, 1.75, fc=pl.GRID, ec="none")
    ax.add_patch(band)
    band.set_clip_path(head)                                           # the headband, inside the outline of the head
    for name, (dx, dy) in PLACES.items():
        disc(ax, (cx + dx * 2.6, cy - 0.35 + dy * 2.6), 0.15, fc=pl.INK, ec=pl.SURFACE, lw=0.9, zorder=3)
    ax.text(cx, 5.12, "8 channels over\nthe visual cortex", fontsize=10.5, color=pl.INK2, va="top", ha="center", linespacing=1.25)
    # facts
    facts = ["102 people, each recorded with a\ndry and a wet headband",
             "Decision from 1 s of signal",
             "The new user gives 0 to 288 s\nof calibration"]
    y = 3.85
    for fact in facts:
        disc(ax, (0.3, y - 0.17), 0.07, fc=pl.INK2, ec="none")
        ax.text(0.65, y, fact, fontsize=10.5, va="top", linespacing=1.3)
        y -= 0.52 + 0.47 * fact.count("\n")
    # development and lockbox
    total = n_dev + n_box
    w_dev = 9.7 * n_dev / total
    ax.add_patch(Rectangle((0.15, 0.62), w_dev - 0.06, 0.5, fc=pl.GRID, ec="none"))
    ax.add_patch(Rectangle((0.15 + w_dev, 0.62), 9.7 - w_dev, 0.5, fc=pl.INK2, ec="none"))
    ax.text(0.15 + w_dev / 2, 0.87, f"{n_dev} people: every choice", ha="center", va="center", fontsize=9.6)
    ax.text(0.15 + w_dev + (9.7 - w_dev) / 2, 0.87, f"{n_box}: tested once", ha="center", va="center", fontsize=9.6, color=pl.SURFACE)
    ax.text(0.15, 0.42, "The numbers shown here are from the people tested once.", fontsize=9.2, color=pl.INK2, va="top")


def panel_calibration(axes, acc):
    new = acc[(acc.design == "new_user") & (acc.window_s == 1.0)].groupby(["method", "k", "electrode", "subject"]).accuracy.mean()
    for ax, el in zip(axes, ("dry", "wet")):
        color = pl.COLOR[el]
        f = new.loc[("fbcca", 0, el)].mean()
        ax.axhline(f, color=pl.NEUTRAL, lw=1.5, ls=(0, (1, 2)))
        ax.annotate(f"FBCCA, no data from anyone: {f:.2f}", (-16, f), xytext=(0, -5), textcoords="offset points", ha="left", va="top",
                    fontsize=9.2, color=pl.INK)
        for method, ls, marker in (("template", "-", "o"), ("etrca", (0, (4, 2)), "s")):
            ks = sorted(k for m, k, e in set(new.index.droplevel("subject")) if m == method and e == el)
            v = [new.loc[(method, k, el)].to_numpy() for k in ks]
            x = [k * BLOCK_S for k in ks]
            lo, hi = zip(*[st.bootstrap_ci(a) for a in v])
            ax.fill_between(x, lo, hi, color=color, alpha=0.13, lw=0)
            ax.plot(x, [a.mean() for a in v], color=color, ls=ls, marker=marker, ms=7.5, mec=pl.SURFACE, mew=1.1, lw=2.4)
        t0, t2, e6 = (new.loc[key].mean() for key in (("template", 0, el), ("template", 2, el), ("etrca", 6, el)))
        ax.annotate(f"{t0:.2f}", (0, t0), xytext=(0, 9), textcoords="offset points", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
        ax.annotate(f"{t2:.2f}", (96, t2), xytext=(0, 9), textcoords="offset points", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
        below = e6 < new.loc[("template", 6, el)].mean()
        ax.annotate(f"{e6:.2f}", (288, e6), xytext=(0, -10 if below else 9), textcoords="offset points", ha="center",
                    va="top" if below else "bottom", fontsize=10.5, fontweight="bold")
        ax.set(title=f"{el.capitalize()} electrodes", xticks=[0, 48, 96, 192, 288], xlim=(-22, 310), ylim=(0.15, 1.0))
        ax.set_xlabel("Calibration of the new user (s)", fontsize=10.5)
        ax.title.set_fontsize(12)
        ax.tick_params(labelsize=9.5)
    axes[0].set_ylabel("Accuracy, 12 targets, 1 s of signal", fontsize=10.5)
    handles = [plt.Line2D([], [], color=pl.INK2, ls="-", marker="o", ms=7, mec=pl.SURFACE, lw=2.2, label="other people's data + own calibration"),
               plt.Line2D([], [], color=pl.INK2, ls=(0, (4, 2)), marker="s", ms=7, mec=pl.SURFACE, lw=2.2, label="own calibration only (ensemble TRCA)")]
    axes[0].legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.02, 1.085), ncol=1, fontsize=10, handlelength=3.2, borderaxespad=0)


def panel_tests(ax, tests):
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.axis("off")
    ax.text(0, 9.75, f"Tested once on {int(tests.n.iloc[0])} unseen people", fontsize=13.5, fontweight="bold", va="top")
    ax.text(0, 9.05, f"{int(tests.supported.sum())} of {len(tests)} pre-specified tests hold (Holm, 0.05)", fontsize=10.5, color=pl.INK2, va="top")
    by = {h: t for h, t in tests.groupby("hypothesis")}
    one = lambda h, case: by[h][by[h].case == case].iloc[0]                          # noqa: E731
    h1 = by["H1"].estimate.abs()
    rows = [
        (by["H1"].supported.all(), "Dry electrodes lower accuracy", f"by {h1.min():.2f} to {h1.max():.2f} ({int(by['H1'].supported.sum())} of 4 tests)"),
        (bool(one("H2", "dry").supported), "Dry: 96 s of calibration are enough",
         f"{one('H2', 'dry').estimate:+.3f} against 288 s of own calibration"),
        (bool(one("H2", "wet").supported), "Wet: 96 s of calibration are enough",
         f"{one('H2', 'wet').estimate:+.3f}, around the margin of -0.05"),
        (by["H6"].supported.all(), "Updating the template without labels helps",
         f"{one('H6', 'dry').estimate:+.3f} dry, {one('H6', 'wet').estimate:+.3f} wet"),
        (by["H3"].supported.any(), "Entropy adaptation helps the small network",
         f"{one('H3', 'dry').estimate:+.3f} dry, {one('H3', 'wet').estimate:+.3f} wet"),
        (by["H5a"].supported.any() or by["H5b"].supported.any(), "Accuracy falls with time or impedance",
         "0 of 4 tests"),
    ]
    y = 8.05
    for supported, statement, detail in rows:
        disc(ax, (0.33, y - 0.3), 0.2, fc=pl.INK if supported else pl.SURFACE, ec=pl.INK, lw=1.7)
        ax.text(0.95, y, statement, fontsize=11, fontweight="bold", va="top")
        ax.text(0.95, y - 0.52, f"{'Holds' if supported else 'Does not hold'}: {detail}", fontsize=9.8, color=pl.INK2, va="top")
        y -= 1.32


def main():
    pl.use_style()
    acc, tests = pd.read_csv(RES / "accuracy.csv"), pd.read_csv(RES / "tests.csv")
    new = acc[(acc.design == "new_user") & (acc.window_s == 1.0)].groupby(["method", "k", "electrode"]).accuracy.mean()
    fig = plt.figure(figsize=(15, 6.9))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.18, 1.0, 1.0, 1.42], left=0.012, right=0.992, bottom=0.115, top=0.80, wspace=0.14)
    ax_setting = fig.add_subplot(grid[0])
    ax_dry = fig.add_subplot(grid[1])
    ax_wet = fig.add_subplot(grid[2], sharey=ax_dry)
    plt.setp(ax_wet.get_yticklabels(), visible=False)
    ax_tests = fig.add_subplot(grid[3])
    # the calibration panels need room for the y label next to the setting panel; positions first, then the
    # drawing, because disc() needs the final shape of the axes
    for ax in (ax_dry, ax_wet):
        box = ax.get_position()
        ax.set_position([box.x0 + 0.03, box.y0, box.width - 0.012, box.height - 0.085])
    box = ax_tests.get_position()
    ax_tests.set_position([box.x0 + 0.022, box.y0, box.width - 0.022, box.height])
    fig.canvas.draw()
    panel_setting(ax_setting, len(wd.DEVELOPMENT), acc.subject.nunique())
    panel_calibration((ax_dry, ax_wet), acc)
    panel_tests(ax_tests, tests)
    title = (f"A new user with dry electrodes: other people's data plus 96 s of calibration reach {new.loc[('template', 2, 'dry')]:.2f}, "
             f"288 s of the user's own reach {new.loc[('etrca', 6, 'dry')]:.2f}")
    fig.text(0.012, 0.975, title, fontsize=15, fontweight="bold", va="top")
    h1 = tests[tests.hypothesis == "H1"].estimate.abs()
    fig.text(0.012, 0.915, f"Wearable SSVEP decoding on open data. Dry electrodes cost {h1.min():.2f} to {h1.max():.2f} of accuracy. With wet "
             f"electrodes, 288 s of the user's own data still do better ({new.loc[('etrca', 6, 'wet')]:.2f}) than 96 s plus other people's "
             f"({new.loc[('template', 2, 'wet')]:.2f}).", fontsize=11, color=pl.INK2, va="top")
    fig.text(0.012, 0.012, "Data: Zhu et al., Sensors 2021 (102 people). Lines: mean over the 34 people set aside before any analysis and decoded once; "
             "bands: 95 % intervals over people. One-sided tests with the Holm correction.", fontsize=8.8, color=pl.INK2, va="bottom")
    out = ROOT / "figures" / "graphical_abstract.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"{out.relative_to(ROOT)}: {title}")


if __name__ == "__main__":
    main()
