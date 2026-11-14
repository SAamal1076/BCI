"""M5 figures, from the tables of results/m5 (and, for the animation, the cached scores of one person).

  01_speed_accuracy.png   accuracy against the time of the decision: fixed windows and the stopping rule
  02_people.png           ITR of each person: stopping rule against the best fixed window
  03_reliability.png      can the confidence be believed?
  04_latency.png          time of one update on the processor
  replay.gif              the first block of one test person, replayed at the speed of the recording

The person of the animation is fixed by the plan: the one with the median accuracy (stopping rule, template,
dry headband) among the test people of the first fold.

Usage: python scripts/m5_figures.py [--cache DIR] [--no-gif]
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m5_scores as ms  # noqa: E402
from ssvep import keypad as kp  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

plt = pl.plt
RES, FIG = ROOT / "results" / "m5", ROOT / "figures" / "m5"
NAMES, TIMES = wd.ELECTRODE_NAMES, np.array(sm.TIMES)


def band(v):
    lo, hi = zip(*[st.bootstrap_ci(np.asarray(x)) for x in v])
    return lo, hi


def fig_speed(people, by_window):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.0), sharey=True)
    for ax, el in zip(axes, NAMES):
        for decoder, color, ls, label in (("fbcca", pl.NEUTRAL, (0, (4, 2)), "FBCCA"), ("template", pl.COLOR[el], "-", "template")):
            w = by_window[(by_window.electrode == el) & (by_window.decoder == decoder)]
            v = [w[np.isclose(w.window_s, t)].accuracy.to_numpy() for t in TIMES]
            if decoder == "template":
                ax.fill_between(TIMES, *band(v), color=color, alpha=0.13, lw=0)
            ax.plot(TIMES, [x.mean() for x in v], color=color, ls=ls, lw=2.2 if decoder == "template" else 1.6)
            p = people[(people.electrode == el) & (people.decoder == decoder)]
            ax.scatter([p.time_s.mean()], [p.accuracy.mean()], marker="D", s=95, color=color, edgecolor=pl.SURFACE, linewidth=1.2, zorder=4)
            y = 0.21 if decoder == "template" else 0.11
            ax.scatter([0.45], [y], marker="D", s=60, color=color, edgecolor=pl.SURFACE, linewidth=1.0, transform=ax.transAxes, clip_on=False)
            ax.text(0.48, y, f"{label}, stopping rule: {p.accuracy.mean():.2f} after {p.time_s.mean():.2f} s",
                    transform=ax.transAxes, va="center", fontsize=8.8, color=pl.INK)
        ax.set(title=f"{el.capitalize()} headband", xlabel="Signal used for the decision (s)", xlim=(0.25, 2.05), xticks=[0.3, 0.5, 1.0, 1.5, 2.0])
    axes[0].set(ylabel="Accuracy, 12 targets, no calibration")
    handles = [plt.Line2D([], [], color=pl.INK2, ls="-", lw=2.2, label="cross-subject template, fixed window"),
               plt.Line2D([], [], color=pl.NEUTRAL, ls=(0, (4, 2)), lw=1.6, label="FBCCA, fixed window"),
               plt.Line2D([], [], color=pl.INK2, ls="none", marker="D", ms=8, mec=pl.SURFACE, label="stopping rule (mean time of its decisions)")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=3)
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.17, top=0.78, wspace=0.06)
    t = people[people.decoder == "template"].groupby("electrode")
    gain = (t.itr.mean() / t.fixed_itr.mean() - 1) * 100
    return fig, (f"Stopping when confident against the best fixed window: {gain.dry:+.0f} % bits per minute with dry electrodes, "
                 f"{gain.wet:+.0f} % with wet ones"), "Lines: mean over the 68 development people, each decoded as a test person; band: 95 % interval. Template built from other people."


def fig_people(people):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.4))
    counts = {}
    for ax, el in zip(axes, NAMES):
        p = people[(people.electrode == el) & (people.decoder == "template")]
        top = max(p.itr.max(), p.fixed_itr.max()) * 1.06
        ax.plot([0, top], [0, top], color=pl.INK2, lw=0.9, ls=(0, (1, 2)))
        ax.scatter(p.fixed_itr, p.itr, s=46, color=pl.COLOR[el], edgecolor=pl.SURFACE, linewidth=0.9, alpha=0.9)
        counts[el] = int((p.itr > p.fixed_itr).sum())
        ax.annotate("above the line:\nstopping is faster", (0.04 * top, 0.95 * top), va="top", fontsize=8.8, color=pl.INK2)
        ax.set(title=f"{el.capitalize()} headband", xlabel="Best fixed window (bits/min)", xlim=(0, top), ylim=(0, top))
        ax.set_aspect("equal")
    axes[0].set(ylabel="Stopping when confident (bits/min)")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.13, top=0.84, wspace=0.2)
    return fig, f"Stopping when confident is faster for {counts['dry']} of 68 people with dry electrodes and {counts['wet']} of 68 with wet ones", \
        "Each dot is one development person as a test person; cross-subject template, no calibration; 0.5 s added to every decision for moving the eyes."


def fig_reliability(rel):
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    ax.plot([0, 1], [0, 1], color=pl.INK2, lw=0.9, ls=(0, (1, 2)))
    gap = {}
    for el in NAMES:
        r = rel[(rel.decoder == "template") & (rel.electrode == el)]
        ax.plot(r.confidence, r.correct, color=pl.COLOR[el], marker="o", ms=7, mec=pl.SURFACE, mew=1, lw=2, label=f"{el} headband")
        gap[el] = float(np.average(r.confidence - r.correct, weights=r.decisions))
    ax.annotate("on the line: the confidence\nis the share of right decisions", (0.03, 0.97), va="top", fontsize=8.8, color=pl.INK2)
    ax.set(xlabel="Confidence at the decision", ylabel="Share of right decisions", xlim=(0, 1), ylim=(0, 1))
    ax.set_aspect("equal")
    ax.legend(loc="lower right")
    fig.subplots_adjust(left=0.13, right=0.97, bottom=0.15, top=0.88)
    word = lambda g: f"{abs(g):.2f} too {'high' if g > 0 else 'low'}"   # noqa: E731
    return fig, f"The confidence is {word(gap['dry'])} with dry electrodes, {word(gap['wet'])} with wet ones", \
        "Decisions of the 68 test people (template), grouped by confidence.\nBelow 0.5: decided at 2.0 s without reaching the threshold."


def fig_latency(lat):
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.stackplot(lat.time_s, lat.preprocessing_median_ms, lat.decision_median_ms, colors=[pl.GRID, pl.NEUTRAL], labels=["preprocessing (median)", "decision (median)"], lw=0)
    ax.plot(lat.time_s, lat.total_p95_ms, color=pl.INK, lw=1.8, label="whole update, 95th percentile")
    ax.axhline(100, color=pl.INK2, lw=1.0, ls=(0, (4, 2)))
    ax.annotate("100 ms: the time between two updates", (0.32, 100), xytext=(0, -5), textcoords="offset points", va="top", fontsize=8.8, color=pl.INK2)
    ax.set(xlabel="Signal used by the update (s)", ylabel="Time on one processor core (ms)", xlim=(0.3, 2.0), ylim=(0, 108))
    ax.legend(loc="center right")
    fig.subplots_adjust(left=0.1, right=0.97, bottom=0.14, top=0.86)
    worst = lat.total_p95_ms.max()
    return fig, f"An update takes at most {worst:.0f} ms (95th percentile) of the 100 ms it has", \
        "Python and NumPy on the analysis machine, one core; 1 632 replayed trials. A measurement of this code, not of a device."


def shrink(path, colours=48):
    """Rewrite the animation with one small palette for all frames (about a quarter of the size)."""
    from PIL import Image
    im = Image.open(path)
    frames, durations = [], []
    for k in range(im.n_frames):                                      # equal frames were merged by the writer: keep their durations
        im.seek(k)
        frames.append(im.convert("RGB"))
        durations.append(im.info.get("duration", 100))
    palette = frames[len(frames) // 2].quantize(colours, method=Image.Quantize.MEDIANCUT)
    small = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    small[0].save(path, save_all=True, append_images=small[1:], duration=durations, loop=0, optimize=True)


def median_person(people):
    p = people[(people.fold == 0) & (people.electrode == "dry") & (people.decoder == "template")].sort_values(["accuracy", "subject"])
    return int(p.subject.iloc[len(p) // 2])


def replay_gif(cache, people, settings, out, hold=6):
    sid = median_person(people)
    row = settings[(settings.fold == 0) & (settings.electrode == "dry") & (settings.decoder == "template")].iloc[0]
    b, theta = [row[f"b_{t:.1f}"] for t in TIMES], float(row.theta)
    s = ms.scores(cache, sid, "template", 0)[0][:, :12]                 # dry headband, first block: (lengths, 12 trials, classes)
    prob = np.stack([sm.probabilities(s[j], b[j]) for j in range(len(TIMES))])           # (lengths, trials, classes)
    stop = sm.stop(prob.max(axis=-1).T, theta)                          # update at which each trial is decided
    frames = [(trial, j, j == stop[trial]) for trial in range(12) for j in list(range(stop[trial] + 1)) + [stop[trial]] * hold]

    fig = plt.figure(figsize=(8.4, 4.4), dpi=80)
    ax = fig.add_axes([0.02, 0.06, 0.5, 0.78])
    ax.set(xlim=(0, 4), ylim=(0, 3))
    ax.axis("off")
    keys, marks = [], []
    for i, char in enumerate(wd.TARGET_CHARS):
        x, y = kp.COL[i] + 0.06, 2 - kp.ROW[i] + 0.06
        key = FancyBboxPatch((x, y), 0.88, 0.88, boxstyle="round,pad=0,rounding_size=0.1", fc=pl.SURFACE, ec=pl.GRID, lw=1.5)
        ax.add_patch(key)
        ax.text(x + 0.44, y + 0.52, char, ha="center", va="center", fontsize=17, fontweight="bold", color=pl.INK)
        marks.append(ax.text(x + 0.44, y + 0.17, "", ha="center", va="center", fontsize=9, color=pl.INK))
        keys.append(key)
    fig.text(0.02, 0.95, f"Replay of recorded trials: person S{sid:03d}, dry electrodes, no calibration", fontsize=12.5, fontweight="bold", va="top")
    fig.text(0.02, 0.012, "Shade of a key: probability given by the decoder. Thick outline: the target the person was told to look at. "
             "Frames 0.1 s apart, as recorded.", fontsize=7.6, color=pl.INK2, va="bottom")
    tx = fig.add_axes([0.58, 0.6, 0.38, 0.1])
    tx.set(xlim=(0, 2.0), ylim=(0, 1), yticks=[], xticks=[0, 0.5, 1.0, 1.5, 2.0], xlabel="signal received (s)")
    tx.xaxis.label.set_fontsize(8.5)
    tx.tick_params(labelsize=8)
    tx.grid(False)
    bar = Rectangle((0, 0), 0, 1, fc=pl.COLOR["dry"], ec="none")
    tx.add_patch(bar)
    cx = fig.add_axes([0.58, 0.33, 0.38, 0.1])
    cx.set(xlim=(0, 1), ylim=(0, 1), yticks=[], xticks=[0, 0.5, 1.0], xlabel=f"confidence (it stops at {theta:.2f})")
    cx.xaxis.label.set_fontsize(8.5)
    cx.tick_params(labelsize=8)
    cx.grid(False)
    cbar = Rectangle((0, 0), 0, 1, fc=pl.NEUTRAL, ec="none")
    cx.add_patch(cbar)
    cx.axvline(theta, color=pl.INK, lw=1.5)
    head = fig.text(0.58, 0.83, "", fontsize=11, fontweight="bold", va="top")
    tally = fig.text(0.58, 0.17, "", fontsize=10, va="top", linespacing=1.5)
    done = {"right": 0, "n": 0, "seconds": 0.0, "last": -1}

    def draw(frame):
        trial, j, decided = frame
        p = prob[j, trial]
        for i, key in enumerate(keys):
            key.set_facecolor(pl.COLOR["dry"])
            key.set_alpha(None)
            key.set_facecolor((*plt.matplotlib.colors.to_rgb(pl.COLOR["dry"]), float(0.04 + 0.9 * p[i])))
            key.set_edgecolor(pl.INK if i == trial else pl.GRID)
            key.set_linewidth(3.2 if i == trial else 1.5)
            marks[i].set_text("")
        bar.set_width(TIMES[j])
        cbar.set_width(float(p.max()))
        head.set_text(f"Trial {trial + 1} of 12")
        if decided:
            choice = int(p.argmax())
            marks[choice].set_text("decided: right" if choice == trial else "decided: wrong")
            if done["last"] != trial:
                done.update(right=done["right"] + int(choice == trial), n=done["n"] + 1, seconds=done["seconds"] + TIMES[j], last=trial)
        if done["n"]:
            tally.set_text(f"right so far: {done['right']} of {done['n']}\nmean time of a decision: {done['seconds'] / done['n']:.2f} s")
        return keys + marks + [bar, cbar, head, tally]

    FuncAnimation(fig, draw, frames=frames, blit=False).save(out, writer=PillowWriter(fps=10), dpi=90)
    plt.close(fig)
    shrink(out)
    right = int(sum(prob[stop[t], t].argmax() == t for t in range(12)))
    return sid, theta, right, float(TIMES[stop].mean()), len(frames)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ms.DEFAULT_CACHE))
    ap.add_argument("--no-gif", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    people, by_window = pd.read_csv(RES / "people.csv"), pd.read_csv(RES / "accuracy_by_window.csv")
    rel, lat, settings = pd.read_csv(RES / "reliability.csv"), pd.read_csv(RES / "latency.csv"), pd.read_csv(RES / "settings.csv")
    for stem, (fig, title, note) in (("01_speed_accuracy", fig_speed(people, by_window)), ("02_people", fig_people(people)),
                                     ("03_reliability", fig_reliability(rel)), ("04_latency", fig_latency(lat))):
        pl.save(fig, FIG / f"{stem}.png", title, note)
        print(f"figures/m5/{stem}.png: {title}")
    if not args.no_gif:
        sid, theta, right, seconds, frames = replay_gif(pathlib.Path(args.cache), people, settings, FIG / "replay.gif")
        size = (FIG / "replay.gif").stat().st_size / 1e6
        print(f"figures/m5/replay.gif: person S{sid:03d} (median accuracy among the test people of the first fold, dry headband), first block: "
              f"{right} of 12 right, mean decision time {seconds:.2f} s, theta {theta:.2f}; {frames} frames, {size:.1f} MB")


if __name__ == "__main__":
    main()
