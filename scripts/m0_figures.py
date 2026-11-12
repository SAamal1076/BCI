"""M0 figures, drawn from the result tables of m0_inventory.py and m0_signal_checks.py.

Figures 1-3 are label-free (all 102 subjects). Figures 4-7 use the 68 development subjects only.
Usage: python scripts/m0_figures.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import plotting as pl  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

plt = pl.plt
RES = ROOT / "results" / "m0"
FIG = ROOT / "figures" / "m0"
NAMES = ("dry", "wet")
EEG_INDEX = {"dry": wd.DRY + 1, "wet": wd.WET + 1}          # position in the files


def legend(ax, **kw):
    handles = [plt.Line2D([], [], color=pl.COLOR[n], lw=2, label=f"{n} headband") for n in NAMES]
    ax.legend(handles=handles, **kw)


def fig_noise():
    ps = pd.read_csv(RES / "noise_per_subject.csv").pivot(index="subject", columns="eeg_index")
    panels = [("line50", "Mains pick-up at 50 Hz (µV)", 1.0, [1, 10, 100, 1000]),
              ("hf_rms", "Noise 60-90 Hz, RMS (µV)", 1.0, [2, 5, 10, 20, 50]),
              ("dc_abs", "Electrode offset (mV)", 1e-3, [1, 10, 100])]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4))
    for ax, (key, label, scale, ticks) in zip(axes, panels):
        wet, dry = ps[key][EEG_INDEX["wet"]] * scale, ps[key][EEG_INDEX["dry"]] * scale
        lo, hi = min(wet.min(), dry.min()) * 0.7, max(wet.max(), dry.max()) * 1.4
        ax.plot([lo, hi], [lo, hi], color=pl.GRID, lw=1.2, zorder=1)
        pl.dots(ax, wet, dry)
        ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi), aspect="equal",
               xlabel="wet headband (position 2 in the files)", ylabel="dry headband (position 1)")
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_locator(plt.FixedLocator(ticks))
            axis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
            axis.set_minor_locator(plt.NullLocator())
        ax.set_title(f"{label}\ndry above wet in {int((dry > wet).sum())} of 102 people", fontsize=10)
        ax.annotate("equal", (hi / 1.5, hi / 1.5), xytext=(-4, -12), textcoords="offset points", ha="right",
                    fontsize=8.5, color=pl.INK2)
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.14, top=0.78, wspace=0.28)
    pl.save(fig, FIG / "01_noise_dry_vs_wet.png",
            "The headband stored first in the files is the noisy one: it is the dry headband",
            "Each dot is one person (median over 120 trials and 8 channels). Label-free, all 102 people. "
            "The readme and the paper label position 1 as wet.")


def fig_spectrum():
    s = pd.read_csv(RES / "noise_spectrum.csv")
    s = s[(s.frequency >= 2) & (s.frequency <= 125)]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.axvspan(9.25, 14.75, color=pl.GRID, alpha=0.6, lw=0, zorder=0)
    for name in NAMES:
        i = EEG_INDEX[name]
        ax.fill_between(s.frequency, s[f"index{i}_q25"], s[f"index{i}_q75"], color=pl.COLOR[name], alpha=0.10, lw=0)
        ax.plot(s.frequency, s[f"index{i}_median"], color=pl.COLOR[name])
    ax.set(yscale="log", xlabel="Frequency (Hz)", ylabel="Amplitude (µV)", xlim=(2, 125))
    ax.set_xticks([10, 25, 50, 75, 100, 125])
    top = s["index1_median"].max()
    ax.annotate("mains, 50 Hz", (50, top), xytext=(6, -2), textcoords="offset points", fontsize=9, va="top")
    ax.annotate("100 Hz", (100, s.loc[s.frequency == 100, "index1_median"].item()), xytext=(6, -2),
                textcoords="offset points", fontsize=9, va="top")
    ax.annotate("stimulus\nfrequencies", (12, ax.get_ylim()[0] * 1.25), ha="center", va="bottom", fontsize=8.5,
                color=pl.INK2)
    legend(ax, loc="upper right")
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.17, top=0.86)
    pl.save(fig, FIG / "02_noise_spectrum.png", "Raw amplitude spectrum: mains interference dominates, mostly on the dry headband",
            "Median over the 102 people of each person's mean spectrum (all trials and channels pooled; linear trend "
            "removed, Hann window). Band: quartiles.")


def fig_impedance():
    per = pd.read_csv(RES / "impedance_per_subject.csv")
    blk = pd.read_csv(RES / "impedance_by_block.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    rng = np.random.default_rng(0)
    for row, name in enumerate(NAMES):
        v = per[per.impedance_index == EEG_INDEX[name]]["mean"].to_numpy()
        pl.dots(ax, v, row + rng.uniform(-0.22, 0.22, len(v)), color=pl.COLOR[name], size=26)
        ax.plot([np.median(v)] * 2, [row - 0.36, row + 0.36], color=pl.INK, lw=1.6, zorder=4)
        ax.annotate(f"median {np.median(v):.0f} kΩ\nmean {v.mean():.0f} kΩ", (np.median(v), row + 0.38),
                    ha="center", va="bottom", fontsize=8.5)
    ax.set(xscale="log", yticks=[0, 1], yticklabels=["dry", "wet"], ylim=(-0.6, 1.95),
           xlabel="Impedance of one person, mean over 8 channels and 10 blocks (kΩ)")
    ax.set_title("Each person: dry is about ten times higher than wet", fontsize=10)
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    for name in NAMES:
        b = blk[blk.impedance_index == EEG_INDEX[name]]
        ax.fill_between(b.block, b.q25, b.q75, color=pl.COLOR[name], alpha=0.10, lw=0)
        ax.plot(b.block, b["median"], color=pl.COLOR[name], marker="o", ms=6, mec=pl.SURFACE, mew=1)
        pl.end_label(ax, b.block.iloc[-1], b["median"].iloc[-1], f"{name}", dx=7)
    ax.set(yscale="log", xlabel="Block (impedance measured before each block)", ylabel="Impedance (kΩ)",
           xticks=range(1, 11), xlim=(0.6, 11.2))
    ax.set_title("Over the ten blocks (median and quartiles of all electrodes)", fontsize=10)
    legend(ax, loc="center right")
    fig.subplots_adjust(left=0.05, right=0.985, bottom=0.17, top=0.80, wspace=0.18)
    pl.save(fig, FIG / "03_impedance.png", "Electrode impedance reproduces the paper: 262 kΩ dry and 20 kΩ wet on average",
            "Impedance.mat, all 102 people. Position 1 of the file is the dry headband, position 2 the wet one.")


def fig_group_spectra():
    g = pd.read_csv(RES / "group_spectrum.csv")
    g = g[(g.frequency >= 6) & (g.frequency <= 32)]
    fig, axes = plt.subplots(4, 3, figsize=(12, 8.6), sharex=True, sharey=True)
    for t, ax in enumerate(axes.ravel()):
        f = wd.TARGET_FREQS[t]
        for k in (1, 2):
            ax.axvline(k * f, color=pl.GRID, lw=5, zorder=0)
        for name in NAMES:
            d = g[(g.electrode == name) & (g.target == t + 1)]
            ax.plot(d.frequency, d.amplitude, color=pl.COLOR[name], lw=1.6)
        ax.set_title(f"target '{wd.TARGET_CHARS[t]}'   {f:g} Hz", fontsize=9.5)
        ax.set_xticks([10, 15, 20, 25, 30])
    for ax in axes[-1]:
        ax.set_xlabel("Frequency (Hz)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Amplitude (µV)")
    legend(axes[0, 2], loc="upper right")
    fig.subplots_adjust(left=0.055, right=0.99, bottom=0.085, top=0.905, wspace=0.06, hspace=0.32)
    pl.save(fig, FIG / "04_group_spectra.png",
            "Every target shows its own peak: at the stimulus frequency and at twice that frequency",
            "Amplitude spectrum of the grand-average Oz waveform (68 development people x 10 blocks), 2 s response "
            "window. Grey bars: the target's frequency f and 2f.")


def fig_attended():
    m = pd.read_csv(RES / "attended_matrix.csv")
    freqs = np.sort(wd.TARGET_FREQS)
    vmin, vmax = 1.0, m.amplitude.max()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    for ax, name in zip(axes, NAMES):
        mat = m[m.electrode == name].pivot(index="attended_frequency", columns="frequency", values="amplitude")
        mat = mat.loc[freqs, freqs].to_numpy()
        im = ax.imshow(mat, cmap=pl.BLUES, vmin=vmin, vmax=vmax, aspect="equal")
        ax.set(xticks=range(12), yticks=range(12))
        ax.set_xticklabels([f"{f:g}" for f in freqs], rotation=90)
        ax.set_yticklabels([f"{f:g}" for f in freqs])
        ax.set_xlabel("Frequency measured in the EEG (Hz)")
        off = mat[~np.eye(12, dtype=bool)]
        ax.set_title(f"{name} headband: {np.diag(mat).mean():.2f} µV at the attended frequency, "
                     f"{off.mean():.2f} µV elsewhere", fontsize=10)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_ylabel("Frequency of the attended target (Hz)")
    fig.subplots_adjust(left=0.065, right=0.90, bottom=0.14, top=0.86, wspace=0.05)
    cax = fig.add_axes([0.915, 0.22, 0.014, 0.56])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Mean single-trial amplitude at Oz (µV)")
    cb.outline.set_visible(False)
    pl.save(fig, FIG / "05_attended_matrix.png",
            "Only the attended target's frequency rises above the noise floor: the target table is right",
            "Rows: target the person looked at. Columns: the 12 stimulus frequencies. Mean over 68 development "
            "people and 10 blocks. All 12 targets flicker at once. Colour scale starts at 1 µV.")


def fig_timing():
    ph = pd.read_csv(RES / "latency_group_phases.csv")
    lg = pd.read_csv(RES / "latency_group.csv")
    ls = pd.read_csv(RES / "latency_per_subject.csv")
    cache = np.load(RES / "cache" / "m0_signal.npz")
    t = wd.epoch_times()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.4))

    ax = axes[0, 0]
    sel = (t >= -0.1) & (t <= 0.6)
    for e, name in enumerate(NAMES):
        ax.plot(t[sel], cache["grand_bp7"][e][sel], color=pl.COLOR[name], lw=1.6)
    ax.axvline(0, color=pl.INK, lw=1)
    ax.axvline(0.14, color=pl.INK2, lw=1, ls=(0, (1, 2)))
    ymax = ax.get_ylim()[1]
    ax.annotate("stimulus on", (0, ymax), xytext=(4, -2), textcoords="offset points", va="top", fontsize=8.5)
    ax.annotate("0.14 s", (0.14, ymax), xytext=(4, -2), textcoords="offset points", va="top", fontsize=8.5)
    ax.set(xlabel="Time from stimulus onset (s)", ylabel="Amplitude (µV)")
    ax.set_title("Grand-average response to the 11.25 Hz target at Oz", fontsize=10)
    legend(ax, loc="lower right")

    ax = axes[0, 1]
    for name in NAMES:
        d = ph[ph.electrode == name].sort_values("frequency")
        row = lg[(lg.electrode == name) & (lg.channel == "Oz")].iloc[0]
        ax.plot(d.frequency, d.fitted, color=pl.COLOR[name], lw=1.4,
                label=f"{name} headband: {row.tau_fit * 1000:.0f} ms (R² = {row.r2_fit:.2f})")
        pl.dots(ax, d.frequency, d.response_minus_stimulus_phase, color=pl.COLOR[name], size=40)
    ax.legend(loc="upper right")
    ax.set(xlabel="Stimulus frequency (Hz)", ylabel="Response phase − stimulus phase (rad)", xlim=(9, 15))
    ax.set_xticks(np.arange(9.25, 15, 1.0))
    ax.set_title("Phase falls on a straight line: its slope is the latency", fontsize=10)

    ax = axes[1, 0]
    for name in NAMES:
        ax.plot(cache["taus"], cache[f"scan_{name}"], color=pl.COLOR[name], lw=1.6)
    ax.axvspan(0.10, 0.18, color=pl.GRID, alpha=0.7, lw=0, zorder=0)
    ax.annotate("accepted\nrange", (0.14, 0.03), ha="center", va="bottom", fontsize=8.5, color=pl.INK2)
    ax.set(xlabel="Assumed latency (s)", ylabel="Phase coherence of the 12 targets", ylim=(0, 1.02))
    ax.set_title("Same estimate without phase unwrapping: one sharp maximum", fontsize=10)
    legend(ax, loc="upper right")

    ax = axes[1, 1]
    bins = np.arange(0.0, 0.4001, 0.01)
    for name, sign in zip(NAMES, (1, -1)):
        h, _ = np.histogram(ls[ls.electrode == name].tau_scan, bins)
        ax.bar(bins[:-1] + 0.005, sign * h, width=0.008, color=pl.COLOR[name])
        med = ls[ls.electrode == name].tau_scan.median()
        ax.annotate(f"{name}: median {med * 1000:.0f} ms", (0.39, sign * 12), ha="right", va="center", fontsize=9)
    ax.axhline(0, color=pl.INK2, lw=0.8)
    ax.set_yticks([-20, -10, 0, 10, 20])
    ax.set_yticklabels([20, 10, 0, 10, 20])
    ax.set(xlabel="Latency of each person (s)", ylabel="Number of people", xlim=(0, 0.4))
    ax.set_title("Each of the 68 people separately (10-block averages at Oz)", fontsize=10)

    fig.subplots_adjust(left=0.06, right=0.985, bottom=0.085, top=0.905, wspace=0.2, hspace=0.34)
    pl.save(fig, FIG / "06_timing.png", "Timing is right: the response follows the stimulus by about 0.13 s",
            "68 development people. Phases are measured from stimulus onset (sample 125 of the epoch) and use the "
            "frequency and phase table of the dataset.")


def fig_snr():
    s = pd.read_csv(RES / "snr_per_subject.csv")
    w = s.pivot(index="subject", columns="electrode")
    ch = pd.read_csv(RES / "snr_per_subject_channel.csv")
    bl = pd.read_csv(RES / "snr_per_subject_block.csv")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.8))

    ax = axes[0, 0]
    x, y = w["snr1_trial_oz"]["wet"], w["snr1_trial_oz"]["dry"]
    lo, hi = -3, 14.5
    ax.plot([lo, hi], [lo, hi], color=pl.GRID, lw=1.2, zorder=1)
    ax.axhline(-1.5, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    ax.axvline(-1.5, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    pl.dots(ax, x, y)
    ax.annotate("noise only\n(−1.5 dB)", (-1.5, hi), xytext=(4, -2), textcoords="offset points", va="top",
                fontsize=8.5, color=pl.INK2)
    ax.set(xlim=(lo, hi), ylim=(lo, hi), aspect="equal", xlabel="wet headband, single-trial SNR at Oz (dB)",
           ylabel="dry headband (dB)")
    ax.set_title(f"A person's SNR is similar with both headbands\ndry below wet in {int((y < x).sum())} of 68; "
                 f"median difference {np.median(y - x):+.1f} dB", fontsize=10)

    ax = axes[0, 1]
    cols = [("snr1_trial_oz", "single trial\nf"), ("snr1_avg_oz", "10-block average\nf"),
            ("snr2_trial_oz", "single trial\n2f"), ("snr2_avg_oz", "10-block average\n2f")]
    for k, (col, _) in enumerate(cols):
        for name, dx in zip(NAMES, (-0.13, 0.13)):
            q25, med, q75 = np.percentile(w[col][name], [25, 50, 75])
            ax.plot([k + dx] * 2, [q25, q75], color=pl.COLOR[name], lw=2)
            pl.dots(ax, [k + dx], [med], color=pl.COLOR[name], size=60)
            ax.annotate(f"{med:.1f}", (k + dx, q75), xytext=(0, 5), textcoords="offset points", ha="center",
                        fontsize=8.5)
    ax.axhline(-1.5, color=pl.INK2, lw=0.8, ls=(0, (1, 2)))
    ax.set_xticks(range(4))
    ax.set_xticklabels([c[1] for c in cols])
    ax.set(ylabel="Narrow-band SNR at Oz (dB)", xlim=(-0.5, 3.5))
    ax.set_title("Averaging ten trials adds about 7 dB (median and quartiles over people)", fontsize=10)
    ax.grid(axis="x", visible=False)
    legend(ax, loc="upper right")

    ax = axes[1, 0]
    order = list(ch.groupby("channel").snr1_trial.median().sort_values(ascending=False).index)
    for name, dx in zip(NAMES, (-0.13, 0.13)):
        for k, c in enumerate(order):
            v = ch[(ch.electrode == name) & (ch.channel == c)].snr1_trial
            q25, med, q75 = np.percentile(v, [25, 50, 75])
            ax.plot([k + dx] * 2, [q25, q75], color=pl.COLOR[name], lw=2)
            pl.dots(ax, [k + dx], [med], color=pl.COLOR[name], size=60)
    ax.set_xticks(range(8))
    ax.set_xticklabels(order)
    ax.set(ylabel="Single-trial SNR at f (dB)", xlim=(-0.5, 7.5))
    ax.set_title("By channel: the midline electrodes POz and Oz carry the most signal", fontsize=10)
    ax.grid(axis="x", visible=False)
    legend(ax, loc="upper right")

    ax = axes[1, 1]
    for name in NAMES:
        g = bl[bl.electrode == name].groupby("block").snr1_trial_oz
        q25, med, q75 = g.quantile(0.25), g.median(), g.quantile(0.75)
        ax.fill_between(med.index, q25, q75, color=pl.COLOR[name], alpha=0.10, lw=0)
        ax.plot(med.index, med, color=pl.COLOR[name], marker="o", ms=6, mec=pl.SURFACE, mew=1)
        pl.end_label(ax, 10, med.iloc[-1], name, dx=7)
    ax.set(xlabel="Block with that headband", ylabel="Single-trial SNR at Oz (dB)", xticks=range(1, 11),
           xlim=(0.6, 10.9))
    ax.set_title("By block: no visible trend over the ten blocks", fontsize=10)
    legend(ax, loc="upper right")

    fig.subplots_adjust(left=0.06, right=0.985, bottom=0.08, top=0.885, wspace=0.2, hspace=0.36)
    pl.save(fig, FIG / "07_snr.png", "Signal-to-noise ratio: low on a single trial, and nearly the same for dry and wet",
            "68 development people. Narrow-band SNR: amplitude at the target frequency over the mean of the 10 "
            "neighbouring frequencies (0.5 Hz apart). Descriptive, no test.")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pl.use_style()
    for f in (fig_noise, fig_spectrum, fig_impedance, fig_group_spectra, fig_attended, fig_timing, fig_snr):
        f()
        print("wrote", f.__name__)


if __name__ == "__main__":
    main()
