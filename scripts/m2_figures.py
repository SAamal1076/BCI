"""M2 figures, drawn from the tables of results/m2 (development people).

Usage: python scripts/m2_figures.py     (after m2_summary.py)
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import plotting as pl  # noqa: E402

plt = pl.plt
RES, FIG = ROOT / "results" / "m2", ROOT / "figures" / "m2"
NAMES = ("dry", "wet")
CHANCE = 1 / 12
STYLE = {"cross": "solid", "own": (0, (5, 2)), "etrca": (0, (1, 1.5))}
TEXT = {"cross": "cross-subject template", "own": "own template only", "etrca": "ensemble TRCA"}


def headband_legend(fig, **kw):
    handles = [plt.Line2D([], [], color=pl.COLOR[n], lw=2, label=f"{n} headband") for n in NAMES]
    fig.legend(handles=handles, **kw)


def fig_pipeline():
    c = pd.read_csv(RES / "pipeline_choice.csv").set_index("pipeline").loc[["B", "B1", "B2"]]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1, 1]})
    for ax, method, title in zip(axes[:2], ("fbcca", "etrca"), ("FBCCA (no calibration)", "Ensemble TRCA (per-person calibration)")):
        for name in NAMES:
            v = c[f"{method}_{name}"]
            ax.plot(range(3), v, color=pl.COLOR[name], marker="o", ms=8, mec=pl.SURFACE, mew=1)
            for i, y in enumerate(v):
                ax.annotate(f"{y:.2f}", (i, y), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8.5)
        ax.set(title=title, ylim=(0.3, 1.0), xlim=(-0.4, 2.4), xticks=range(3))
        ax.set_xticklabels(["B", "B1", "B2"])
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Accuracy at 1 s (12 targets)")
    ax = axes[2]
    for method, ls in (("fbcca", "solid"), ("etrca", (0, (1, 1.5)))):
        v = c[f"{method}_share_12.25_12.75"]
        ax.plot(range(3), v, color=pl.NEUTRAL, ls=ls, marker="o", ms=8, mec=pl.SURFACE, mew=1,
                label="FBCCA" if method == "fbcca" else "ensemble TRCA")
    ax.axhline(2 / 12, color=pl.INK, lw=0.8)
    ax.annotate("no bias", (2.35, 2 / 12), xytext=(0, -4), textcoords="offset points", ha="right", va="top", fontsize=8.5)
    ax.set(title="Decisions on 12.25 or 12.75 Hz", ylim=(0.1, 0.35), xlim=(-0.4, 2.4), xticks=range(3), ylabel="Share of all decisions")
    ax.set_xticklabels(["B", "B1", "B2"])
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    headband_legend(fig, loc="upper right", bbox_to_anchor=(0.66, 0.93), ncol=2)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.2, top=0.78, wspace=0.22)
    pl.save(fig, FIG / "01_pipeline_choice.png", "Keeping the band below the mains gives the best pipeline and removes the decision bias",
            "B: as in M1. B1: one mains frequency per trial for all channels. B2: B1 with the band limited to 45 Hz and 3 harmonics. "
            "68 development people, 1 s window. Criterion of the plan: mean of the four accuracies; B2 was chosen.")


def fig_curve(window=1.0):
    c = pd.read_csv(RES / "calibration_curve.csv")
    c = c[c.window_s == window]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.0), sharey=True)
    for ax, name in zip(axes, NAMES):
        d = c[c.electrode == name]
        for method in ("cross", "own", "etrca"):
            m = d[d.method == method].sort_values("k")
            ax.plot(m.k, m["mean"], color=pl.COLOR[name], ls=STYLE[method], lw=2.2 if method == "cross" else 1.6,
                    marker="o", ms=6, mec=pl.SURFACE, mew=1)
            if method == "cross":
                ax.fill_between(m.k, m.ci_low, m.ci_high, color=pl.COLOR[name], alpha=0.13, lw=0)
        f = d[d.method == "fbcca"]["mean"].iloc[0]
        ax.axhline(f, color=pl.INK, lw=1)
        ax.annotate(f"FBCCA, no data from anyone: {f:.2f}", (-0.2, f), xytext=(0, -4), textcoords="offset points", ha="left", va="top", fontsize=8.5)
        ax.set(title=f"{name} headband", xlabel="Calibration blocks of the new user (one block = 48 s)", xticks=[0, 1, 2, 4, 6],
               ylim=(0.2, 1.0), xlim=(-0.3, 6.3))
        ax.set_xticklabels(["0", "1\n48 s", "2\n96 s", "4\n192 s", "6\n288 s"])
    axes[0].set_ylabel(f"Accuracy at {window:g} s, blocks 7 to 10")
    handles = [plt.Line2D([], [], color=pl.INK2, ls=STYLE[m], lw=2, label=TEXT[m]) for m in ("cross", "own", "etrca")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=3)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.19, top=0.80, wspace=0.05)
    return fig


def fig_no_calibration():
    c = pd.read_csv(RES / "calibration_curve.csv")
    c = c[c.k == 0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, name in zip(axes, NAMES):
        for method, ls, lab in (("cross", "solid", "cross-subject template"), ("fbcca", (0, (5, 2)), "FBCCA")):
            d = c[(c.electrode == name) & (c.method == method)].sort_values("window_s")
            ax.plot(d.window_s, d["mean"], color=pl.COLOR[name], ls=ls, lw=2 if method == "cross" else 1.6)
            if method == "cross":
                ax.fill_between(d.window_s, d.ci_low, d.ci_high, color=pl.COLOR[name], alpha=0.13, lw=0)
        ax.axhline(CHANCE, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
        ax.set(title=f"{name} headband", xlabel="Window length (s)", xticks=np.arange(0.2, 2.01, 0.4), ylim=(0, 1))
    axes[0].set_ylabel("Accuracy with no calibration, blocks 7 to 10")
    handles = [plt.Line2D([], [], color=pl.INK2, ls="solid", lw=2, label="cross-subject template (other people's data)"),
               plt.Line2D([], [], color=pl.INK2, ls=(0, (5, 2)), lw=1.6, label="FBCCA (no data from anyone)")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=2)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.80, wspace=0.05)
    return fig


def fig_people():
    d = pd.read_csv(RES / "new_user_frozen.csv")
    d = d[(d.window_s == 1.0) & (d.k == 0)].pivot_table(index=["subject", "electrode"], columns="method", values="accuracy").reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.2), sharey=True)
    for ax, name in zip(axes, NAMES):
        e = d[d.electrode == name]
        ax.plot([0, 1], [0, 1], color=pl.INK, lw=0.8)
        pl.dots(ax, e.fbcca, e.cross, color=pl.COLOR[name], size=34)
        better = int((e.cross > e.fbcca).sum())
        ax.set(title=f"{name} headband: better for {better} of {len(e)} people", xlabel="FBCCA (no data from anyone)",
               xlim=(0, 1.02), ylim=(0, 1.02), aspect="equal")
    axes[0].set_ylabel("Cross-subject template, no calibration")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.14, top=0.82, wspace=0.06)
    return fig


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    fig_pipeline()
    c = pd.read_csv(RES / "calibration_curve.csv")
    start = c[(c.window_s == 1.0) & (c.method == "cross") & (c.k == 0)].set_index("electrode")["mean"]
    pl.save(fig_curve(), FIG / "02_calibration_curve.png",
            f"A template from other people starts a new user at {start['dry']:.2f} (dry) and {start['wet']:.2f} (wet) with no calibration",
            "68 development people as new users (leave-one-subject-out), 1 s window. Band: 95 % bootstrap interval over people.")
    pl.save(fig_no_calibration(), FIG / "03_no_calibration.png", "With no calibration, a template from other people beats FBCCA at every window length",
            "68 development people as new users (leave-one-subject-out). Band: 95 % bootstrap interval over people. Dotted: chance.")
    pl.save(fig_people(), FIG / "04_people.png", "Most new users gain from other people's data (no calibration, 1 s window)",
            "Each dot is one development person with one headband; above the line the cross-subject template is better.")
    print("wrote 4 figures to", FIG)


if __name__ == "__main__":
    main()
