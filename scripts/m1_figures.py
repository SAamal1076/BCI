"""M1 figures, drawn from the result tables of results/m1 (68 development subjects) and results/m0.

Usage: python scripts/m1_figures.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import metrics as mt  # noqa: E402
from ssvep import plotting as pl  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

plt = pl.plt
RES = ROOT / "results" / "m1"
FIG = ROOT / "figures" / "m1"
NAMES = ("dry", "wet")
CHANCE = 1 / 12
PUBLISHED = {"cca": {1.0: (0.497, 0.684)},
             "fbcca_paper": {0.2: (0.12, 0.16), 1.0: (0.53, 0.73), 2.0: (0.73, 0.86)},
             "etrca_paper": {0.2: (0.38, 0.66), 1.0: (0.62, 0.88), 2.0: (0.73, 0.93)}}
TITLE = {"cca": "CCA", "fbcca_paper": "FBCCA, published weights", "etrca_paper": "Ensemble TRCA, published weights",
         "fbcca_apriori": "FBCCA (no calibration)", "etrca_apriori": "Ensemble TRCA (per-person calibration)"}


def legend(ax, extra=(), **kw):
    handles = [plt.Line2D([], [], color=pl.COLOR[n], lw=2, label=f"{n} headband") for n in NAMES]
    ax.legend(handles=handles + list(extra), **kw)


def curve(ax, s, variant, method, name, **kw):
    d = s[(s.variant == variant) & (s.method == method) & (s.electrode == name)].sort_values("window_s")
    ax.plot(d.window_s, d["mean"], color=pl.COLOR[name], **kw)
    return d


def fig_gate(s):
    style = {"A": (0, (1, 1.5)), "B": "solid", "C": (0, (5, 2))}
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.9), sharey=True)
    for ax, method in zip(axes, ("cca", "fbcca_paper", "etrca_paper")):
        for e, name in enumerate(NAMES):
            for variant in "ABC":
                curve(ax, s, variant, method, name, ls=style[variant], lw=2.2 if variant == "C" else 1.5)
            for w, pub in PUBLISHED[method].items():
                ax.scatter([w], [pub[e]], s=70, marker="D", facecolor=pl.SURFACE, edgecolor=pl.COLOR[name], linewidth=2, zorder=4)
        ax.axhline(CHANCE, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
        ax.set(xlabel="Window length (s)", xticks=np.arange(0.2, 2.01, 0.4), ylim=(0, 1), title=TITLE[method])
    axes[0].set_ylabel("Accuracy (12 targets)")
    handles = [plt.Line2D([], [], color=pl.INK2, marker="D", mfc=pl.SURFACE, mew=2, ms=8, lw=0, label="published (102 people)")]
    handles += [plt.Line2D([], [], color=pl.INK2, ls=style[v], lw=2, label=lab) for v, lab in
                (("A", "A  cut, then filter; mains kept (gate)"), ("B", "B  past samples; mains removed (project)"),
                 ("C", "C  whole epoch; mains removed"))]
    axes[0].legend(handles=handles, loc="upper left", fontsize=8.5)
    legend(axes[1], loc="upper left")
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.80, wspace=0.06)
    pl.save(fig, FIG / "01_reproduction.png",
            "The published accuracies are reproduced only when the whole epoch is filtered (variant C)",
            "Lines: ours, mean over the 68 development people. Diamonds: Zhu et al. 2021, all 102 people. "
            "The pre-registered gate used variant A and failed.")


def fig_variants(s):
    f = pd.read_csv(RES / "mains_by_context_1s.csv")
    contexts = ["window only", "past samples + window", "whole epoch"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (method, title) in zip(axes, (("FBCCA, a-priori weights", "FBCCA (no calibration)"),
                                         ("ensemble TRCA, a-priori weights", "Ensemble TRCA (per-person calibration)"))):
        for name, dx in zip(NAMES, (-0.1, 0.1)):
            d = f[(f.method == method) & (f.electrode == name)].set_index("context").loc[contexts]
            x = np.arange(3) + dx
            ax.plot(x, d["mains removed"], color=pl.COLOR[name], lw=1.6)
            ax.scatter(x, d["mains removed"], s=80, color=pl.COLOR[name], edgecolor=pl.SURFACE, linewidth=1, zorder=3)
            ax.scatter(x, d["mains kept"], s=80, facecolor=pl.SURFACE, edgecolor=pl.COLOR[name], linewidth=2, zorder=3)
            for xi, v in zip(x, d["mains removed"]):
                ax.annotate(f"{v:.2f}", (xi, v), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8.5)
            for xi, v in zip(x, d["mains kept"]):
                if not np.isnan(v):
                    ax.annotate(f"{v:.2f}", (xi, v), xytext=(0, -15), textcoords="offset points", ha="center", fontsize=8.5)
        ax.axhline(CHANCE, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
        ax.set_xticks(range(3))
        ax.set_xticklabels(["window only\n(reference code)", "past samples + window\n(project, real-time valid)",
                            "whole epoch\n(uses future samples)"])
        ax.set(title=title, ylim=(0, 1), xlim=(-0.5, 2.5))
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Accuracy at 1 s (12 targets)")
    axes[0].annotate("chance", (2.45, CHANCE), xytext=(0, 3), textcoords="offset points", ha="right", va="bottom",
                     fontsize=8.5, color=pl.INK2)
    extra = [plt.Line2D([], [], color=pl.INK2, marker="o", lw=0, ms=9, label="mains removed"),
             plt.Line2D([], [], color=pl.INK2, marker="o", mfc=pl.SURFACE, mew=2, lw=0, ms=9, label="mains kept")]
    legend(axes[0], extra=extra, loc="upper left", ncol=2)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.17, top=0.80, wspace=0.05)
    pl.save(fig, FIG / "02_mains_and_context.png",
            "Why the reference convention fails here: mains interference breaks TRCA, and the filter needs context",
            "68 development people, 1 s window, a-priori weights. What the filter is given before it is applied, "
            "with the 50 Hz component kept or removed.")


def fig_people(acc):
    snr = pd.read_csv(ROOT / "results" / "m0" / "snr_per_subject.csv")[["subject", "electrode", "snr1_trial_oz"]]
    thr = mt.chance_threshold(120, 12)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, method in zip(axes, ("fbcca_apriori", "etrca_apriori")):
        for name in NAMES:
            d = acc[(acc.variant == "B") & (acc.method == method) & (acc.window_s == 1.0) & (acc.electrode == name)]
            d = d.merge(snr, on=["subject", "electrode"])
            pl.dots(ax, d.snr1_trial_oz, d.accuracy, color=pl.COLOR[name], size=30)
        ax.axhline(thr, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
        ax.set(xlabel="Single-trial SNR at Oz from M0 (dB)", title=f"{TITLE[method]}, 1 s window", ylim=(0, 1.02))
    axes[0].set_ylabel("Accuracy of one person")
    axes[0].annotate("not above chance", (13, thr), xytext=(0, -3), textcoords="offset points", ha="right", va="top",
                     fontsize=8.5, color=pl.INK2)
    handles = [plt.Line2D([], [], color=pl.COLOR[n], marker="o", lw=0, ms=7, label=f"{n} headband") for n in NAMES]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.91), ncol=2)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.15, top=0.80, wspace=0.05)
    pl.save(fig, FIG / "03_people.png", "Accuracy differs between people and follows the signal-to-noise ratio measured in M0",
            "Each dot is one person with one headband (68 development people, project pipeline B).")


def fig_dry_wet():
    gap = pd.read_csv(RES / "dry_minus_wet_by_window.csv").set_index("method")
    order = pd.read_csv(RES / "dry_minus_wet_by_order.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    ls = {"cca": (0, (1, 1.5)), "fbcca_apriori": "solid", "etrca_apriori": (0, (5, 2))}
    lab = {"cca": "CCA", "fbcca_apriori": "FBCCA", "etrca_apriori": "ensemble TRCA"}
    x = gap.columns.astype(float)
    for method in ("cca", "fbcca_apriori", "etrca_apriori"):
        ax.plot(x, gap.loc[method], color=pl.NEUTRAL, ls=ls[method], label=lab[method])
    ax.axhline(0, color=pl.INK, lw=0.8)
    ax.set(xlabel="Window length (s)", ylabel="Accuracy, dry minus wet (same person)", xticks=np.arange(0.2, 2.01, 0.4))
    ax.set_title("Gap between dry and wet against window length", fontsize=10)
    ax.set_ylim(-0.40, 0.02)
    ax.legend(loc="center", bbox_to_anchor=(0.5, 0.445), ncol=3)
    ax = axes[1]
    labels, k = [], 0
    for _, r in order.iterrows():
        for dx, col, mk in ((-0.14, "mean, dry worn first", "o"), (0.14, "mean, wet worn first", "s")):
            ax.scatter([k + dx], [r[col]], s=70, marker=mk, color=pl.NEUTRAL, edgecolor=pl.SURFACE, linewidth=1, zorder=3)
            ax.annotate(f"{r[col]:+.2f}", (k + dx, r[col]), xytext=(0, -13), textcoords="offset points", ha="center", fontsize=8.5)
        short = "FBCCA" if r["method"].startswith("FBCCA") else "ens. TRCA"
        labels.append(f"{short}\n{r['window_s']:g} s")
        k += 1
    ax.axhline(0, color=pl.INK, lw=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set(ylabel="Accuracy, dry minus wet", xlim=(-0.6, len(labels) - 0.4))
    lo = min(order["mean, dry worn first"].min(), order["mean, wet worn first"].min())
    ax.set_ylim(lo - 0.06, 0.03)
    ax.grid(axis="x", visible=False)
    ax.set_title("The same gap, by the headband worn first", fontsize=10)
    ax.legend(handles=[plt.Line2D([], [], color=pl.NEUTRAL, marker="o", lw=0, ms=8, label="dry worn first"),
                       plt.Line2D([], [], color=pl.NEUTRAL, marker="s", lw=0, ms=8, label="wet worn first")], loc="lower right")
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.16, top=0.80, wspace=0.2)
    pl.save(fig, FIG / "04_dry_minus_wet.png", "Dry electrodes cost accuracy at every window length, more when the dry headband is worn second",
            "68 development people, project pipeline B, a-priori weights. Descriptive; H1 is tested later as planned.")


def fig_edge():
    e = pd.read_csv(RES / "edge_transients.csv")
    e = e[e.band == 1]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    style = {"A": (0, (1, 1.5)), "B": "solid", "C": (0, (5, 2))}
    for ax, (scen, name) in zip(axes, (("dry-like", "dry"), ("wet-like", "wet"))):
        for variant in "ABC":
            d = e[(e.scenario == scen) & (e.variant == variant)]
            ax.plot(d.window_s, d.error_rms_uv, color=pl.COLOR[name], ls=style[variant], marker="o", ms=6, mec=pl.SURFACE, mew=1)
            pl.end_label(ax, d.window_s.iloc[-1], d.error_rms_uv.iloc[-1], variant, dx=7)
        resp = e[(e.scenario == scen)].response_rms_uv.median()
        ax.axhline(resp, color=pl.INK, lw=1)
        ax.annotate("size of the response", (0.2, resp), xytext=(0, 4), textcoords="offset points", fontsize=8.5, va="bottom")
        ax.set(yscale="log", xlabel="Window length (s)", xticks=[0.2, 0.4, 1.0, 2.0], xlim=(0.1, 2.2),
               title=f"{scen} interference (medians of M0)")
        ax.yaxis.set_major_locator(plt.FixedLocator([0.5, 1, 2, 5, 10, 20]))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_locator(plt.NullLocator())
    axes[0].set_ylabel("Edge error in the window, RMS (µV)")
    fig.subplots_adjust(left=0.06, right=0.97, bottom=0.16, top=0.80, wspace=0.05)
    pl.save(fig, FIG / "05_edge_error.png", "Synthetic epochs: cutting the window before filtering leaves an error larger than the response",
            "Sub-band 1 (6-90 Hz). A: cut, then filter. B: past samples + mains removal. C: whole epoch (uses future samples). "
            "Error = output minus the output with unlimited context.")


def fig_confusion():
    c = pd.read_csv(RES / "wearable_confusion_1s.csv")
    order = np.argsort(wd.TARGET_FREQS)
    freqs = wd.TARGET_FREQS[order]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    for ax, name in zip(axes, NAMES):
        d = c[(c.electrode == name) & (c.method == "fbcca_apriori")]
        m = d.pivot(index="true_target", columns="predicted_target", values="count").to_numpy()[np.ix_(order, order)]
        m = m / m.sum(axis=1, keepdims=True)
        im = ax.imshow(m, cmap=pl.BLUES, vmin=0, vmax=1, aspect="equal")
        ax.set(xticks=range(12), yticks=range(12), xlabel="Decoded frequency (Hz)")
        ax.set_xticklabels([f"{f:g}" for f in freqs], rotation=90)
        ax.set_yticklabels([f"{f:g}" for f in freqs])
        ax.set_title(f"{name} headband: {np.diag(m).mean():.2f} correct", fontsize=10)
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
    axes[0].set_ylabel("Frequency of the attended target (Hz)")
    fig.subplots_adjust(left=0.065, right=0.90, bottom=0.14, top=0.86, wspace=0.05)
    cax = fig.add_axes([0.915, 0.22, 0.014, 0.56])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Share of the trials of that target")
    cb.outline.set_visible(False)
    pl.save(fig, FIG / "06_confusion.png",
            "FBCCA errors pile up on 12.25 and 12.75 Hz, the two targets with a harmonic next to the 50 Hz mains",
            "FBCCA without calibration, 1 s window, 68 development people, project pipeline B, a-priori weights. "
            "4 x 12.25 = 49 Hz and 4 x 12.75 = 51 Hz.")


def fig_itr(s):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, method in zip(axes, ("fbcca_apriori", "etrca_apriori")):
        for name in NAMES:
            d = s[(s.variant == "B") & (s.method == method) & (s.electrode == name)].sort_values("window_s")
            ax.plot(d.window_s, d.itr, color=pl.COLOR[name], marker="o", ms=6, mec=pl.SURFACE, mew=1)
            i = d.itr.idxmax()
            below = name == "dry"                                  # the dry curve is the lower one: label under it
            ax.annotate(f"{d.itr[i]:.0f} bits/min\nat {d.window_s[i]:g} s", (d.window_s[i], d.itr[i]),
                        xytext=(0, -9 if below else 8), textcoords="offset points", ha="center",
                        va="top" if below else "bottom", fontsize=8.5)
        ax.set(xlabel="Window length (s)", xticks=np.arange(0.2, 2.01, 0.4), title=TITLE[method])
    axes[0].set_ylabel("Information transfer rate (bits/min)")
    legend(axes[0], loc="upper left")
    top = s[(s.variant == "B") & s.method.isin(["fbcca_apriori", "etrca_apriori"])].itr.max()
    axes[0].set_ylim(0, top * 1.2)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.80, wspace=0.05)
    pl.save(fig, FIG / "07_itr.png", "Speed: information transfer rate with 0.5 s to move the eyes between targets",
            "68 development people, project pipeline B, a-priori weights. Per person, then averaged.")


def fig_beta():
    b = pd.read_csv(RES / "beta_summary.csv")
    published = {"cca": (72.54, 1.8), "fbcca": (98.79, 1.4), "etrca": (139.58, 0.6)}
    title = {"cca": "CCA (6-80 Hz)", "fbcca": "FBCCA (no calibration)", "etrca": "Ensemble TRCA (per-person calibration)"}
    style = {"A": "solid", "C-": (0, (5, 2))}
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), sharey=True)
    for ax, method in zip(axes, ("cca", "fbcca", "etrca")):
        for variant in ("A", "C-"):
            d = b[(b.variant == variant) & (b.method == method)].sort_values("window_s")
            ax.plot(d.window_s, d.itr, color=pl.NEUTRAL, ls=style[variant], lw=2 if variant == "A" else 1.5)
        pub, win = published[method]
        ax.scatter([win], [pub], s=80, marker="D", facecolor=pl.SURFACE, edgecolor=pl.INK, linewidth=2, zorder=4)
        ax.annotate(f"published peak\n{pub:.0f} bits/min at {win:g} s", (win, pub), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=8.5)
        ax.set(xlabel="Window length (s)", xticks=np.arange(0.2, 2.01, 0.4), title=title[method])
    axes[0].set_ylabel("Information transfer rate (bits/min)")
    axes[0].set_ylim(0, 1.25 * max(b.itr.max(), 139.58))
    handles = [plt.Line2D([], [], color=pl.NEUTRAL, ls=style["A"], lw=2, label="ours: cut the window, then filter (gate)"),
               plt.Line2D([], [], color=pl.NEUTRAL, ls=style["C-"], lw=1.5, label="ours: whole trial filtered"),
               plt.Line2D([], [], color=pl.INK, marker="D", mfc=pl.SURFACE, mew=2, ms=8, lw=0, label="published (Liu et al. 2020)")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.99, 0.93), ncol=3, fontsize=8.5)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.76, wspace=0.05)
    return fig


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    s = pd.read_csv(RES / "accuracy_summary.csv")
    acc = pd.read_csv(RES / "wearable_accuracy.csv")
    fig_gate(s)
    fig_variants(s)
    fig_people(acc)
    fig_dry_wet()
    fig_edge()
    fig_confusion()
    fig_itr(s)
    n = 7
    if (RES / "beta_summary.csv").exists():
        g = pd.read_csv(RES / "gate_beta.csv")
        g = g[g.gate == "G5"]
        ok = int(g.passed.sum())
        head = ("On BETA, the reference dataset, the published peak rates are reproduced" if ok == len(g)
                else f"On BETA, the reference dataset, {ok} of {len(g)} published peak rates are reproduced within 10 %")
        pl.save(fig_beta(), FIG / "08_beta.png", head,
                "70 people, 40 targets, nine channels, a-priori weights, 0.55 s gaze shift as in the BETA paper. "
                "Mean over people.")
        n = 8
    print(f"wrote {n} figures to", FIG)


if __name__ == "__main__":
    main()
