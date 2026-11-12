"""M0, steps 4 and 5: timing, spectra and signal-to-noise ratio. DEVELOPMENT SUBJECTS ONLY.

These checks use the target index of each trial, so the 34 lockbox subjects are never loaded here.

Usage: python scripts/m0_signal_checks.py --raw /path/to/13560281
"""
import argparse
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from scipy.io import loadmat

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import spectral as sp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F, PHI = wd.FS, wd.TARGET_FREQS, wd.TARGET_PHASES
WIN = slice(wd.RESP_START, wd.RESP_START + wd.STIM_SAMPLES)
NAMES = wd.ELECTRODE_NAMES                                    # ("dry", "wet") = positions 1 and 2 of the files
C4_GRID = np.arange(8.25, 15.76, 0.5)
SPEC_GRID = np.arange(3.0, 60.01, 0.25)
PAPER_FIG4 = {"wet": (2.597, 1.262, 0.746, 0.316), "dry": (2.444, 1.119, 0.706, 0.305)}   # uV at f..4f, 11.25 Hz, Oz
PAPER_SNR = {"wet": (8.17, 6.01, 3.19, 1.59), "dry": (7.51, 4.91, 3.08, 1.35)}            # dB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m0"))
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    (out / "cache").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    subjects = wd.DEVELOPMENT
    assert not any(wd.is_lockbox(s) for s in subjects)

    cells = loadmat(raw / "Subjects_Information.mat")["Subjects_Information"]
    first = {i: str(cells[i, 10][0]) for i in range(1, 103)}

    tgt = np.arange(wd.N_TARGETS)
    grand = np.zeros((2, wd.N_TARGETS, wd.N_CHANNELS, wd.N_SAMPLES))      # sum of 10-block averages
    grand_bp7 = np.zeros((2, wd.N_SAMPLES))                               # 11.25 Hz target, Oz, 7.25-90 Hz
    attended = np.zeros((2, wd.N_TARGETS, wd.N_TARGETS))                  # sum over subjects, Oz
    rows_s, rows_c, rows_b, rows_t, rows_l = [], [], [], [], []
    harm = 11.25 * np.arange(1, 5)                                        # paper's Figure 4: 11.25 Hz target, Oz
    fig4_amp, fig4_snr_avg, fig4_snr_trial = [], [], []
    for sid in subjects:
        x = wd.load_subject(raw, sid)                                     # [e, block, target, channel, sample]
        clean = sp.remove_mains(x, FS)
        pre = sp.bandpass(clean, FS, 3.0, 90.0)
        win = pre[..., WIN]
        avg = pre.mean(axis=1)                                            # [e, target, channel, sample]
        grand += avg
        grand_bp7 += sp.bandpass(clean[:, :, 1, wd.OZ], FS, 7.25, 90.0).mean(axis=1)

        amp = sp.amplitude(win, F, FS)                                    # [e, block, target, channel, freq]
        snr1 = sp.narrowband_snr_db(win, F, FS)                           # all 12 frequencies, every trial
        snr2 = sp.narrowband_snr_db(win, 2 * F, FS)
        att1 = snr1[:, :, tgt, :, tgt].transpose(1, 2, 0, 3)              # [e, block, target, channel]
        att2 = snr2[:, :, tgt, :, tgt].transpose(1, 2, 0, 3)
        amp1 = amp[:, :, tgt, :, tgt].transpose(1, 2, 0, 3)
        unatt = (snr1.sum(axis=-1) - att1) / (wd.N_TARGETS - 1)           # mean SNR at the 11 other frequencies
        attended += amp[:, :, :, wd.OZ, :].mean(axis=1)

        awin = avg[..., WIN]
        a_snr1 = sp.narrowband_snr_db(awin, F, FS)[:, tgt, :, tgt].transpose(1, 0, 2)      # [e, target, channel]
        a_snr2 = sp.narrowband_snr_db(awin, 2 * F, FS)[:, tgt, :, tgt].transpose(1, 0, 2)
        coef = sp.fourier_coef(awin, F, FS, t0=wd.RESP_T0)[:, tgt, :, tgt].transpose(1, 0, 2)  # [e, target, channel]
        fig4_amp.append(sp.amplitude(awin[:, 1, wd.OZ], harm, FS))                          # [e, harmonic]
        fig4_snr_avg.append(sp.narrowband_snr_db(awin[:, 1, wd.OZ], harm, FS))
        fig4_snr_trial.append(sp.narrowband_snr_db(win[:, :, 1, wd.OZ], harm, FS).mean(axis=1))

        for e, name in enumerate(NAMES):
            base = {"subject": sid, "electrode": name, "first_headband": first[sid]}
            rows_s.append(dict(
                base,
                snr1_trial_oz=att1[e, :, :, wd.OZ].mean(), snr2_trial_oz=att2[e, :, :, wd.OZ].mean(),
                snr1_trial_mean8=att1[e].mean(), snr2_trial_mean8=att2[e].mean(),
                snr1_unattended_oz=unatt[e, :, :, wd.OZ].mean(),
                snr1_avg_oz=a_snr1[e, :, wd.OZ].mean(), snr2_avg_oz=a_snr2[e, :, wd.OZ].mean(),
                snr1_avg_mean8=a_snr1[e].mean(),
                amp1_trial_oz=amp1[e, :, :, wd.OZ].mean(), amp1_avg_oz=np.abs(coef[e, :, wd.OZ]).mean()))
            for c, ch in enumerate(wd.CHANNELS):
                rows_c.append(dict(base, channel=ch, snr1_trial=att1[e, :, :, c].mean(),
                                   snr2_trial=att2[e, :, :, c].mean(), snr1_avg=a_snr1[e, :, c].mean()))
            for b in range(wd.N_BLOCKS):
                rows_b.append(dict(base, block=b + 1, snr1_trial_oz=att1[e, b, :, wd.OZ].mean(),
                                   snr1_trial_mean8=att1[e, b].mean()))
            for t in tgt:
                rows_t.append(dict(base, target=t + 1, frequency=F[t], snr1_trial_oz=att1[e, :, t, wd.OZ].mean(),
                                   snr1_avg_oz=a_snr1[e, t, wd.OZ], amp1_avg_oz=abs(coef[e, t, wd.OZ])))
            fit = sp.apparent_latency_fit(coef[e, :, wd.OZ], F, PHI)
            scan, _, _ = sp.apparent_latency_scan(coef[e, :, wd.OZ], F, PHI)
            rows_l.append(dict(base, tau_scan=scan["tau"], r_scan=scan["r"], tau_fit=fit["tau"], r2_fit=fit["r2"]))

    n = len(subjects)
    grand /= n
    grand_bp7 /= n
    attended /= n
    per_subject = pd.DataFrame(rows_s)
    per_subject.to_csv(out / "snr_per_subject.csv", index=False)
    pd.DataFrame(rows_c).to_csv(out / "snr_per_subject_channel.csv", index=False)
    pd.DataFrame(rows_b).to_csv(out / "snr_per_subject_block.csv", index=False)
    pd.DataFrame(rows_t).to_csv(out / "snr_per_subject_target.csv", index=False)
    latency_subject = pd.DataFrame(rows_l)
    latency_subject.to_csv(out / "latency_per_subject.csv", index=False)
    pd.DataFrame([{"electrode": NAMES[e], "attended_target": i + 1, "attended_frequency": F[i],
                   "frequency": F[j], "amplitude": attended[e, i, j]}
                  for e in range(2) for i in tgt for j in tgt]).to_csv(out / "attended_matrix.csv", index=False)

    # ---- group spectrum of the grand-average Oz waveform, and criterion C4
    gwin = grand[..., WIN]
    spec = sp.amplitude(gwin[:, :, wd.OZ], SPEC_GRID, FS)                 # [e, target, freq]
    pd.DataFrame([{"electrode": NAMES[e], "target": t + 1, "target_frequency": F[t], "frequency": f,
                   "amplitude": spec[e, t, k]} for e in range(2) for t in tgt for k, f in enumerate(SPEC_GRID)]
                 ).to_csv(out / "group_spectrum.csv", index=False)
    c4 = sp.amplitude(gwin[:, :, wd.OZ], C4_GRID, FS)
    c4_rows = []
    for e in range(2):
        for t in tgt:
            order = np.argsort(c4[e, t])[::-1]
            c4_rows.append({"electrode": NAMES[e], "target": t + 1, "target_frequency": F[t],
                            "peak_frequency": C4_GRID[order[0]], "peak_amplitude": c4[e, t, order[0]],
                            "second_frequency": C4_GRID[order[1]], "second_amplitude": c4[e, t, order[1]],
                            "peak_at_target": bool(np.isclose(C4_GRID[order[0]], F[t]))})
    c4_rows = pd.DataFrame(c4_rows)
    c4_rows.to_csv(out / "c4_group_peaks.csv", index=False)

    # ---- timing: group apparent latency from the grand average (Oz = criterion C5; other channels reported)
    gcoef = sp.fourier_coef(gwin, F, FS, t0=wd.RESP_T0)[:, tgt, :, tgt].transpose(1, 0, 2)   # [e, target, channel]
    lat_rows, phase_rows, scans = [], [], {}
    for e in range(2):
        for c, ch in enumerate(wd.CHANNELS):
            fit = sp.apparent_latency_fit(gcoef[e, :, c], F, PHI)
            scan, taus, r = sp.apparent_latency_scan(gcoef[e, :, c], F, PHI)
            lat_rows.append({"electrode": NAMES[e], "channel": ch, "tau_fit": fit["tau"], "theta0": fit["theta0"],
                             "r2_fit": fit["r2"], "tau_scan": scan["tau"], "r_scan": scan["r"]})
            if c == wd.OZ:
                scans[NAMES[e]] = r
                order = np.argsort(F)
                d = np.unwrap(sp.sine_phase(gcoef[e, order, c]) - PHI[order])
                for k, i in enumerate(order):
                    phase_rows.append({"electrode": NAMES[e], "target": i + 1, "frequency": F[i],
                                       "stimulus_phase": PHI[i], "amplitude": abs(gcoef[e, i, c]),
                                       "response_minus_stimulus_phase": d[k],
                                       "fitted": fit["theta0"] - 2 * np.pi * F[i] * fit["tau"]})
        # control: same fit with the phase table ignored
        ctrl, _, _ = sp.apparent_latency_scan(gcoef[e, :, wd.OZ], F, np.zeros(12), taus=np.arange(-1000, 1001) / 1000)
        lat_rows.append({"electrode": NAMES[e], "channel": "Oz, phase table ignored (control)",
                         "tau_fit": np.nan, "theta0": np.nan, "r2_fit": np.nan, "tau_scan": ctrl["tau"],
                         "r_scan": ctrl["r"]})
    latency_group = pd.DataFrame(lat_rows)
    latency_group.to_csv(out / "latency_group.csv", index=False)
    pd.DataFrame(phase_rows).to_csv(out / "latency_group_phases.csv", index=False)

    # ---- comparison with the paper's Figure 4 (11.25 Hz target, Oz); the paper used all 102 subjects
    fig4_amp, fig4_snr_avg, fig4_snr_trial = (np.mean(v, axis=0) for v in (fig4_amp, fig4_snr_avg, fig4_snr_trial))
    f4 = []
    for e, name in enumerate(NAMES):
        a_grand = sp.amplitude(gwin[e, 1, wd.OZ], harm, FS)
        s_grand = sp.narrowband_snr_db(gwin[e, 1, wd.OZ], harm, FS)
        for h in range(4):
            f4.append({"electrode": name, "harmonic": h + 1, "frequency": harm[h],
                       "amplitude_paper_102": PAPER_FIG4[name][h],
                       "amplitude_mean_of_subject_averages": fig4_amp[e, h],
                       "amplitude_grand_average": a_grand[h],
                       "snr_db_paper_102": PAPER_SNR[name][h],
                       "snr_db_single_trial": fig4_snr_trial[e, h],
                       "snr_db_subject_average": fig4_snr_avg[e, h],
                       "snr_db_grand_average": s_grand[h]})
    f4 = pd.DataFrame(f4)
    f4.to_csv(out / "paper_fig4_check.csv", index=False)

    np.savez(out / "cache" / "m0_signal.npz", grand=grand, grand_bp7=grand_bp7, taus=taus,
             scan_dry=scans["dry"], scan_wet=scans["wet"])

    # ---- acceptance
    oz = latency_group[latency_group.channel == "Oz"].set_index("electrode")
    c5 = all(0.10 <= oz.loc[name, "tau_fit"] <= 0.18 for name in NAMES)
    acc = pd.DataFrame([
        {"criterion": "C4", "passed": bool(c4_rows.peak_at_target.all()),
         "detail": f"{int(c4_rows.peak_at_target.sum())} of 24 group spectra peak at the target frequency"},
        {"criterion": "C5", "passed": bool(c5),
         "detail": "; ".join(f"{name}: tau = {oz.loc[name, 'tau_fit'] * 1000:.1f} ms (R2 = {oz.loc[name, 'r2_fit']:.3f}), "
                             f"scan {oz.loc[name, 'tau_scan'] * 1000:.0f} ms (R = {oz.loc[name, 'r_scan']:.3f})"
                             for name in NAMES)},
    ])
    acc.to_csv(out / "acceptance_signal.csv", index=False)

    # ---- log
    pd.set_option("display.width", 200)
    print(f"development subjects: {n} (lockbox subjects not loaded)")
    print("\nC4, group spectrum peaks (grand-average Oz waveform, grid 8.25-15.75 Hz):")
    print(c4_rows.round(3).to_string(index=False))
    print("\ngroup apparent latency:")
    print(latency_group.round(4).to_string(index=False))
    print("\nper-subject apparent latency (scan, Oz, 10-block averages):")
    print(latency_subject.groupby("electrode")[["tau_scan", "r_scan"]].describe().round(3).T.to_string())
    print("\ncomparison with the paper's Figure 4 (11.25 Hz, Oz; ours: 68 development subjects):")
    print(f4.round(3).to_string(index=False))
    cols = ["snr1_trial_oz", "snr2_trial_oz", "snr1_trial_mean8", "snr1_unattended_oz", "snr1_avg_oz",
            "snr2_avg_oz", "amp1_trial_oz", "amp1_avg_oz"]
    print("\nper-subject summaries (dB, amplitudes in uV): median [q25, q75] over development subjects")
    desc = per_subject.groupby("electrode")[cols].quantile([0.25, 0.5, 0.75]).unstack().round(2)
    print(desc.T.to_string())
    wide = per_subject.pivot(index="subject", columns="electrode")
    print("\ndry versus wet, paired by subject (number of the 68 subjects with dry below wet; median of dry - wet):")
    for c in cols:
        d = wide[c]["dry"] - wide[c]["wet"]
        print(f"  {c:20s} dry < wet in {int((d < 0).sum()):2d}/68, median difference {d.median():+.2f}")
    print()
    print(acc.to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
