"""One plotting style for every figure of the repository (static PNG, light surface).

Colour follows the entity everywhere: dry headband = orange, wet headband = blue. Text is never coloured.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3de"
COLOR = {"dry": "#eb6834", "wet": "#2a78d6"}
NEUTRAL = "#6b6a66"
BLUES = LinearSegmentedColormap.from_list("blues", ["#f3f7fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                                                    "#256abf", "#184f95", "#0d366b"])


def use_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 10, "axes.labelcolor": INK2, "text.color": INK, "axes.titlecolor": INK,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.edgecolor": GRID, "axes.linewidth": 1.0, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "lines.linewidth": 2.0, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "legend.frameon": False, "legend.fontsize": 9, "figure.dpi": 100, "savefig.dpi": 160,
        "xtick.major.size": 0, "ytick.major.size": 0,
    })


def dots(ax, x, y, color=NEUTRAL, size=34, **kw):
    """Markers with a ring in the surface colour, so that overlapping dots stay readable."""
    return ax.scatter(x, y, s=size, color=color, edgecolor=SURFACE, linewidth=0.9, zorder=3, **kw)


def end_label(ax, x, y, text, dx=4, dy=0, **kw):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", va="center", fontsize=9,
                color=INK, **kw)


def save(fig, path, title=None, note=None):
    if title:
        fig.suptitle(title, x=0.012, y=0.995, ha="left", va="top", fontsize=13, fontweight="bold", color=INK)
    if note:
        fig.text(0.012, 0.004, note, ha="left", va="bottom", fontsize=8.5, color=INK2)
    fig.savefig(path)
    plt.close(fig)
