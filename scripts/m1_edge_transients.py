"""M1, before the data: edge error of the three ways of filtering a short window, on synthetic epochs.

A long synthetic recording is built (response + offset + drift + mains + background noise) with one epoch in
its middle. "Ideal" is the sub-band signal obtained by filtering the long recording, so that the window has
all the context it could wish for. The error of a variant is its output minus the ideal one, in the window.
For A the ideal keeps the mains component (A does not remove it); for B and C the ideal is mains-free.

Usage: python scripts/m1_edge_transients.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import signal

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import filterbank as fb  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS = wd.FS
N_REAL = 200
N_LONG = 14 * 250                      # 14 s
E0 = 6 * 250                           # first sample of the epoch inside the long recording
WINDOWS = (0.2, 0.4, 1.0, 2.0)
# medians of M0 (docs/milestones/M0_data_audit.md, section 4): mains (uV), offset (uV), drift RMS (uV), noise RMS (uV)
SCENARIOS = {"dry-like": (67.0, 70e3, 55.0, 14.5), "wet-like": (12.0, 8.6e3, 28.0, 12.6)}


def synthetic(rng, mains_uv, offset_uv, drift_uv, noise_uv):
    t = np.arange(N_LONG) / FS
    onset = (E0 + wd.ONSET) / FS
    on = (t >= onset + 0.1) & (t < onset + 2.1)
    phase = rng.uniform(0, 2 * np.pi, (N_REAL, 1))
    response = on * sum(a * np.sin(2 * np.pi * h * 11.25 * (t - onset) + h * phase)
                        for h, a in ((1, 2.0), (2, 1.0), (3, 0.6)))
    f_m = rng.uniform(49.95, 50.05, (N_REAL, 1))
    mains = mains_uv * np.sin(2 * np.pi * f_m * t + rng.uniform(0, 2 * np.pi, (N_REAL, 1)))
    white = rng.standard_normal((N_REAL, N_LONG))
    drift = signal.sosfiltfilt(signal.butter(2, 1.0, fs=FS, output="sos"), np.cumsum(white, axis=1), axis=1)
    drift = drift_uv * drift / drift[:, E0:E0 + wd.N_SAMPLES].std(axis=1, keepdims=True)
    spec = np.fft.rfft(rng.standard_normal((N_REAL, N_LONG)), axis=1)
    freq = np.fft.rfftfreq(N_LONG, 1 / FS)
    noise = np.fft.irfft(spec / np.sqrt(np.maximum(freq, 1.0)), n=N_LONG, axis=1)       # 1/f power above 1 Hz
    band = signal.sosfiltfilt(signal.butter(4, [3, 90], btype="bandpass", fs=FS, output="sos"), noise, axis=1)
    noise = noise_uv * noise / band.std(axis=1, keepdims=True)
    offset = offset_uv * rng.choice([-1.0, 1.0], (N_REAL, 1))
    return response, offset + drift + noise, mains


def main():
    out = ROOT / "results" / "m1"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261112)
    filters = [fb.design(n) for n in range(5)]
    rows = []
    for name, params in SCENARIOS.items():
        response, rest, mains = synthetic(rng, *params)
        epoch = (response + rest + mains)[:, E0:E0 + wd.N_SAMPLES]
        ideal_with_mains = [fb.zero_phase(f, response + rest + mains) for f in filters]
        ideal_clean = [fb.zero_phase(f, response + rest) for f in filters]
        ideal_response = [fb.zero_phase(f, response) for f in filters]
        for window in WINDOWS:
            n = int(round(window * FS))
            w0 = E0 + wd.RESP_START
            for variant in fb.VARIANTS:
                y = fb.subbands(epoch, 5, n, variant, wd.RESP_START)                     # (5, N_REAL, n)
                for band in range(5):
                    ideal = (ideal_with_mains if variant == "A" else ideal_clean)[band][:, w0:w0 + n]
                    err = y[band] - ideal
                    edge = min(25, n // 2)
                    rows.append({
                        "scenario": name, "variant": variant, "window_s": window, "band": band + 1,
                        "error_rms_uv": np.median(err.std(axis=1)),
                        "error_rms_first_0.1s_uv": np.median(np.sqrt((err[:, :edge] ** 2).mean(axis=1))),
                        "error_rms_last_0.1s_uv": np.median(np.sqrt((err[:, -edge:] ** 2).mean(axis=1))),
                        "response_rms_uv": np.median(ideal_response[band][:, w0:w0 + n].std(axis=1)),
                        "mains_left_uv": mains.std() if variant == "A" else 0.0})
    df = pd.DataFrame(rows)
    df["error_over_response"] = df.error_rms_uv / df.response_rms_uv
    df.to_csv(out / "edge_transients.csv", index=False)
    pd.set_option("display.width", 200)
    print("median RMS of the edge error in the window (uV); response RMS in the same sub-band for scale")
    for name in SCENARIOS:
        d = df[df.scenario == name]
        print(f"\n{name}: sub-band 1 (6-90 Hz)")
        print(d[d.band == 1].pivot(index="window_s", columns="variant", values="error_rms_uv").round(2).to_string())
        print("  response RMS:", d[(d.band == 1) & (d.variant == "A")].set_index("window_s").response_rms_uv.round(2).to_dict())
        print(f"{name}: sub-band 2 (14-90 Hz)")
        print(d[d.band == 2].pivot(index="window_s", columns="variant", values="error_rms_uv").round(2).to_string())
        print("  response RMS:", d[(d.band == 2) & (d.variant == "A")].set_index("window_s").response_rms_uv.round(2).to_dict())
    print("\nfirst and last 0.1 s of a 1 s window, sub-band 1:")
    print(df[(df.band == 1) & (df.window_s == 1.0)][["scenario", "variant", "error_rms_first_0.1s_uv",
                                                     "error_rms_last_0.1s_uv", "mains_left_uv"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
