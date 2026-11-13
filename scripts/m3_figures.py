"""M3 figures, drawn from the tables of results/m3 (development people).

Usage: python scripts/m3_figures.py     (after m3_summary.py)
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import plotting as pl  # noqa: E402
from ssvep import stats as st  # noqa: E402

plt = pl.plt
RES, FIG = ROOT / "results" / "m3", ROOT / "figures" / "m3"
NAMES = ("dry", "wet")
SHOW = [("fbcca", "FBCCA"), ("template", "Template from\nother people"), ("template_adapted", "Template,\nadapted without labels"),
        ("net_A0", "Network"), ("net_A1", "Network,\nA1 statistics"), ("net_A2", "Network,\nA2 entropy")]


def fig_methods(p):
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for j, name in enumerate(NAMES):
        d = p.xs(name, level="electrode")
        for i, (m, _) in enumerate(SHOW):
            lo, hi = st.bootstrap_ci(d[m].to_numpy())
            x = i + (j - 0.5) * 0.22
            ax.plot([x, x], [lo, hi], color=pl.COLOR[name], lw=2, solid_capstyle="round")
            ax.scatter([x], [d[m].mean()], s=70, color=pl.COLOR[name], edgecolor=pl.SURFACE, linewidth=1.2, zorder=3)
            ax.annotate(f"{d[m].mean():.2f}", (x, hi), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=8.5)
    ax.set(xticks=range(len(SHOW)), ylim=(0.3, 0.9), ylabel="Accuracy at 1 s, no calibration, blocks 7 to 10", xlim=(-0.5, len(SHOW) - 0.5))
    ax.set_xticklabels([t for _, t in SHOW])
    ax.grid(axis="x", visible=False)
    ax.axvline(2.5, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    handles = [plt.Line2D([], [], color=pl.COLOR[n], marker="o", ms=7, lw=2, label=f"{n} headband") for n in NAMES]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.91), ncol=2)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.17, top=0.80)
    return fig


def fig_people(p):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.2), sharey=True)
    for ax, name in zip(axes, NAMES):
        d = p.xs(name, level="electrode")
        ax.plot([0, 1], [0, 1], color=pl.INK, lw=0.8)
        pl.dots(ax, d.template, d.net_A0, color=pl.COLOR[name], size=34)
        better = int((d.net_A0 > d.template + 1e-9).sum())
        ax.set(title=f"{name} headband: network better for {better} of {len(d)} people", xlabel="Template from other people",
               xlim=(0, 1.02), ylim=(0, 1.02), aspect="equal")
    axes[0].set_ylabel("Network, no adaptation (mean of 3 seeds)")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.14, top=0.82, wspace=0.06)
    return fig


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    p = pd.read_csv(RES / "per_person.csv").set_index(["subject", "electrode"])
    mean = p.groupby("electrode").mean()
    diff = (mean.net_A0 - mean.template)
    if (diff < 0).all():
        head = "With no calibration the small network stays below the template built from other people"
    elif (diff > 0).all():
        head = "With no calibration the small network is above the template built from other people"
    else:
        head = "With no calibration the small network and the template from other people are close"
    gain = (mean.net_A2 - mean.net_A0)
    note = (f"Adaptation without labels changes the network by {gain['dry']:+.3f} (dry) and {gain['wet']:+.3f} (wet). "
            "68 development people in 4 folds; bars: 95 % interval over people.")
    pl.save(fig_methods(p), FIG / "01_methods.png", head, note)
    pl.save(fig_people(p), FIG / "02_network_against_template.png", "Network against template, person by person (no calibration, 1 s window)",
            "Each dot is one development person with one headband; above the line the network is better.")
    print("wrote 2 figures to", FIG)


if __name__ == "__main__":
    main()
