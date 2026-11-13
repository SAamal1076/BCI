"""M4 figures, drawn from the tables of results/m4 (development people).

Usage: python scripts/m4_figures.py     (after m4_summary.py)
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import keypad as kp  # noqa: E402
from ssvep import metrics as mt  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import stats as st  # noqa: E402

plt = pl.plt
RES, FIG = ROOT / "results" / "m4", ROOT / "figures" / "m4"
NAMES = ("dry", "wet")


def legend(fig, **kw):
    fig.legend(handles=[plt.Line2D([], [], color=pl.COLOR[n], marker="o", ms=6, lw=2, label=f"{n} headband") for n in NAMES], **kw)


def fig_time(d):
    blocks = d.assign(ok=d.template == d.target).groupby(["subject", "electrode", "block"]).ok.mean().unstack("block")
    imp = pd.read_csv(RES / "impedance_blocks.csv").pivot_table(index=["subject", "electrode"], columns="block", values="median_kohm")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    x = np.arange(1, 11)
    for name in NAMES:
        b = blocks.xs(name, level="electrode")
        lo, hi = zip(*[st.bootstrap_ci(b[k].to_numpy()) for k in x])
        axes[0].fill_between(x, lo, hi, color=pl.COLOR[name], alpha=0.13, lw=0)
        axes[0].plot(x, b.mean(), color=pl.COLOR[name], marker="o", ms=6, mec=pl.SURFACE, mew=1)
        rel = imp.xs(name, level="electrode")
        axes[1].plot(x, rel.median(), color=pl.COLOR[name], marker="o", ms=6, mec=pl.SURFACE, mew=1)
    axes[0].set(title="Accuracy of a new user, block by block", xlabel="Block worn with this headband (one block = 48 s)", xticks=x,
                ylim=(0.4, 0.9), ylabel="Accuracy at 1 s, no calibration")
    axes[1].set(title="Electrode impedance, block by block", xlabel="Block worn with this headband", xticks=x, yscale="log",
                ylabel="Median impedance over people (kOhm)")
    axes[1].set_yticks([10, 20, 50, 100, 200])
    axes[1].set_yticklabels(["10", "20", "50", "100", "200"])
    axes[1].minorticks_off()
    legend(fig, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=2)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.15, top=0.78, wspace=0.2)
    return fig


def fig_people(d):
    acc = d.assign(ok=d.template == d.target).groupby(["subject", "electrode"]).ok.mean().unstack("electrode")
    thr = mt.chance_threshold(120, 12)
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    ax.plot([0, 1], [0, 1], color=pl.INK, lw=0.8)
    ax.axhline(thr, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    ax.axvline(thr, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    pl.dots(ax, acc.wet, acc.dry, color=pl.NEUTRAL, size=38)
    for sid in acc.index[acc.dry < thr]:
        ax.annotate(f"S{sid:03d}", (acc.wet[sid], acc.dry[sid]), xytext=(7, 3), textcoords="offset points", fontsize=8.5)
    ax.annotate("not above chance", (0.99, thr), xytext=(0, -4), textcoords="offset points", ha="right", va="top", fontsize=8.5)
    ax.set(xlabel="Accuracy with the wet headband", ylabel="Accuracy with the dry headband", xlim=(0, 1.02), ylim=(0, 1.02), aspect="equal")
    fig.subplots_adjust(left=0.13, right=0.97, bottom=0.11, top=0.84)
    return fig


def fig_errors():
    c = pd.read_csv(RES / "error_classes.csv")
    cols = list(kp.CLASSES)
    short = ["0.5 Hz apart,\ntouching on the keypad", "0.5 Hz apart,\nnot touching", "touching on the keypad,\nnot 0.5 Hz apart", "neither"]
    even = c[c.decoder == "even spread"][cols].astype(float).to_numpy()[0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, method, title in zip(axes, ("template", "fbcca"), ("Template from other people", "FBCCA")):
        for j, name in enumerate(NAMES):
            v = c[(c.decoder == method) & (c.electrode == name)][cols].astype(float).to_numpy()[0] / even
            xs = np.arange(4) + (j - 0.5) * 0.2
            ax.scatter(xs, v, s=70, color=pl.COLOR[name], edgecolor=pl.SURFACE, linewidth=1.2, zorder=3)
            for xx, vv in zip(xs, v):
                ax.annotate(f"{vv:.2f}", (xx, vv), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8.5)
        ax.axhline(1.0, color=pl.INK, lw=0.8)
        ax.set(title=title, xticks=range(4), ylim=(0.6, 1.6), xlim=(-0.5, 3.5))
        ax.set_xticklabels(short, fontsize=8.5)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Share of the errors, relative to an even spread")
    legend(fig, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=2)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.17, top=0.78, wspace=0.05)
    return fig


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    d = pd.read_csv(RES / "decisions_1s.csv")
    pl.save(fig_time(d), FIG / "01_time_on_task.png", "Accuracy hardly changes over the ten blocks, while the impedance does",
            "68 development people as new users, cross-subject template, 1 s window. Band: 95 % interval over people. "
            "Dry impedance rises, wet impedance falls.")
    pl.save(fig_people(d), FIG / "02_people.png", "People who are hard to decode with one headband are hard with the other",
            "Each dot is one development person; cross-subject template, no calibration, 1 s, all 10 blocks. Labelled: not above chance with the dry headband.")
    pl.save(fig_errors(), FIG / "03_errors.png", "The template spreads its errors evenly; FBCCA makes more errors between frequencies 0.5 Hz apart",
            "Errors at 1 s, 68 development people. 1.0 = what an even spread over the 11 wrong targets would give.")
    print("wrote 3 figures to", FIG)


if __name__ == "__main__":
    main()
