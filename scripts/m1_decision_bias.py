"""M1, post hoc diagnostic (not in the plan): why do the errors of CCA and FBCCA pile up on 12.25 and 12.75 Hz?

Idea to test: the 4th harmonic of these two targets is 49 and 51 Hz, next to the 50 Hz mains. With a 1 s window
the frequency resolution is about 1 Hz, so what is left of the mains correlates with exactly these two references.

Test: plain CCA (sub-band 1, 1 s window) with different sets of reference harmonics, for the five filtering
variants (mains kept: A, C-; mains removed: A+, B, C). If the idea is right, the two targets attract decisions
only when the 4th harmonic is in the references.

Second check, on the signal itself: the amplitude between 46 and 54 Hz in the same 1 s window, before and after
the mains removal of variant B. If something is left beside 50 Hz, it shows at 49 and 51 Hz.

Third check, on synthetic epochs (no data needed): noise with a 1/f spectrum plus a 50 Hz component that is
absent, steady, or has an amplitude that wanders by a few percent. This shows which ingredient makes the bias.

Fourth check: the mains removal of the project (ssvep.spectral.remove_mains) chooses the mains frequency for
each channel separately, so each channel gets a slightly different operation. Variants B* and C* are B and C
with ONE frequency per trial, shared by the 8 channels (the same linear operation on every channel). They exist
only in this script, to test the explanation; they are not part of the M1 results.

The share of the decisions that go to each target and the spectrum need no labels. The accuracy does, so as
everywhere in M1 only the DEVELOPMENT SUBJECTS are loaded.

Usage: python scripts/m1_decision_bias.py --raw /path/to/13560281 [--jobs 2]
"""
import argparse
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import filterbank as fb  # noqa: E402
from ssvep import spectral as sp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F = wd.FS, wd.TARGET_FREQS
N = 250                                                             # 1 s window
SETS = {"1": (1,), "1-2": (1, 2), "1-3": (1, 2, 3), "1-4": (1, 2, 3, 4), "1-5": (1, 2, 3, 4, 5),
        "1-3 and 5": (1, 2, 3, 5)}
LABELS = np.arange(wd.N_TARGETS)
NEAR_MAINS = np.isin(F, (12.25, 12.75))
FILTER = [fb.design(0, FS)]
VARIANTS = ("A", "C-", "A+", "B", "C", "B*", "C*")
MAINS = {"A": "kept", "C-": "kept", "A+": "removed", "B": "removed", "C": "removed",
         "B*": "removed, one frequency", "C*": "removed, one frequency"}
NEAR = np.arange(46.0, 54.5, 1.0)                                    # 1 Hz apart: orthogonal over a 1 s window
CONTEXT = {"A": "window only", "A+": "window only", "B": "past samples + window", "C": "whole epoch",
           "C-": "whole epoch", "B*": "past samples + window", "C*": "whole epoch"}


def bases(harmonics):
    """Orthonormal bases of the centred references for a chosen list of harmonics (as dc.reference_bases)."""
    t = np.arange(1, N + 1) / FS
    out = []
    for f in F:
        y = np.column_stack([fn(2 * np.pi * h * f * t) for h in harmonics for fn in (np.sin, np.cos)])
        out.append(np.linalg.qr(y - y.mean(axis=0))[0])
    return np.array(out)


BASES = {k: bases(h) for k, h in SETS.items()}
assert np.allclose(np.abs(BASES["1-5"]), np.abs(dc.reference_bases(F, N, FS, 5)))


def remove_mains_shared(x, fs, f0=50.0, half_width=0.5, step=0.01):
    """As ssvep.spectral.remove_mains, but the frequency is chosen once per trial for all channels
    (largest explained energy summed over the channels). x: (..., channels, samples)."""
    x = sp.signal.detrend(np.asarray(x, dtype=float), axis=-1, type="linear")
    n = x.shape[-1]
    t = np.arange(n) / fs
    tc = (t - t.mean()) / t.std()
    k = int(round(half_width / step))
    flat = x.reshape(-1, x.shape[-2], n)
    q_all, energy = [], []
    for f in f0 + np.arange(-k, k + 1) * step:
        s, c = np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)
        q, _ = np.linalg.qr(np.column_stack([s, c, tc * s, tc * c]))
        q_all.append(q)
        energy.append(((flat @ q) ** 2).sum(axis=(1, 2)))
    best = np.argmax(np.array(energy), axis=0)
    out = flat.copy()
    for i in np.unique(best):
        rows = best == i
        out[rows] -= (flat[rows] @ q_all[i]) @ q_all[i].T
    return out.reshape(x.shape)


def window_data(x, variant):
    """Sub-band 1 of the 1 s window, (..., channels, N)."""
    stop = wd.RESP_START + N
    if variant == "B*":
        return fb.zero_phase(FILTER[0], remove_mains_shared(x[..., :stop], FS))[..., wd.RESP_START:]
    if variant == "C*":
        return fb.zero_phase(FILTER[0], remove_mains_shared(x, FS))[..., wd.RESP_START:stop]
    return fb.subbands(x, 1, N, variant, wd.RESP_START, FS, FILTER)[0]


def evaluate_subject(job):
    sid, raw = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)
    rows = []
    for variant in VARIANTS:
        sub = window_data(x, variant)                                          # (e, block, target, ch, n)
        for key, b in BASES.items():
            pred = dc.cca_corr(sub, b).argmax(axis=-1)                         # (e, block, target)
            for e, name in enumerate(wd.ELECTRODE_NAMES):
                counts = np.bincount(pred[e].ravel(), minlength=12)
                rows.append((sid, name, variant, key, (pred[e] == LABELS).mean(), *counts))
    stop = wd.RESP_START + N
    kept = sp.signal.detrend(x[..., wd.RESP_START:stop], axis=-1, type="linear")
    removed = sp.remove_mains(x[..., :stop], FS)[..., wd.RESP_START:stop]
    spec = [(sid, name, label, *sp.amplitude(seg[e], NEAR, FS).mean(axis=(0, 1, 2)))
            for label, seg in (("kept", kept), ("removed", removed)) for e, name in enumerate(wd.ELECTRODE_NAMES)]
    return rows, spec


def synthetic(n_trials=3000, seed=1):
    """Share of the decisions on 12.25 and 12.75 Hz for noise-only epochs (no response at all): 8 channels of
    spatially mixed 1/f noise (unit variance) plus a 50 Hz component common to the channels."""
    rng = np.random.default_rng(seed)
    n = wd.N_SAMPLES
    t = np.arange(n) / FS
    gain = 1 / np.maximum(np.fft.rfftfreq(n, 1 / FS), 1.0) ** 0.75
    rows = []
    for label, amp, wander in (("no mains", 0.0, 0.0), ("steady mains, 40 x the noise", 40.0, 0.0),
                               ("wandering mains (3 %), 8 x the noise", 8.0, 0.03),
                               ("wandering mains (3 %), 40 x the noise", 40.0, 0.03)):
        w = np.fft.irfft(np.fft.rfft(rng.standard_normal((n_trials, 8, n)), axis=-1) * gain, n=n, axis=-1)
        w = np.einsum("ij,tjn->tin", np.eye(8) + 0.5 * rng.standard_normal((8, 8)), w)
        w /= w.std()
        f0 = 50 + rng.uniform(-0.05, 0.05, (n_trials, 1, 1))
        phase = rng.uniform(0, 2 * np.pi, (n_trials, 1, 1)) + rng.uniform(-0.3, 0.3, (n_trials, 8, 1))
        envelope = 1 + wander * np.cumsum(rng.standard_normal((n_trials, 1, n)), axis=-1) / np.sqrt(n)
        x = w + amp * rng.uniform(0.5, 1.5, (n_trials, 8, 1)) * envelope * np.sin(2 * np.pi * f0 * t + phase)
        for variant in VARIANTS:
            sub = window_data(x, variant)
            for key in ("1-3", "1-5"):
                pred = dc.cca_corr(sub, BASES[key]).argmax(axis=-1)
                rows.append((label, MAINS[variant], variant, key, NEAR_MAINS[pred].mean()))
    return pd.DataFrame(rows, columns=["synthetic_epochs", "mains", "variant", "harmonics", "share"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m1"))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    syn = synthetic()
    syn.to_csv(out / "decision_bias_synthetic.csv", index=False, float_format="%.4f")
    print("== synthetic epochs without any response: share of the decisions on 12.25 or 12.75 Hz")
    print("   (plain CCA, 1 s window; these two targets get fewer decisions than 2/12 here because the 1/f noise")
    print("   favours the low targets; what matters is the change along a row)")
    print("   mains kept: A, C- | removed, frequency chosen per channel: A+, B, C | removed, one frequency per trial: B*, C*")
    for key in ("1-3", "1-5"):
        wide = syn[syn.harmonics == key].pivot(index="synthetic_epochs", columns="variant", values="share")
        print(f"references with harmonics {key}:")
        print(wide.loc[list(dict.fromkeys(syn.synthetic_epochs)), list(VARIANTS)].round(3).to_string())

    jobs = [(sid, raw) for sid in wd.DEVELOPMENT]
    if args.jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.jobs) as pool:
            results = pool.map(evaluate_subject, jobs, chunksize=1)
    else:
        results = [evaluate_subject(j) for j in jobs]
    cols = [f"n_{f:g}Hz" for f in F]
    d = pd.DataFrame([r for res in results for r in res[0]],
                     columns=["subject", "electrode", "variant", "harmonics", "accuracy"] + cols)
    d["share_12.25_12.75"] = d[[c for c, near in zip(cols, NEAR_MAINS) if near]].sum(axis=1) / d[cols].sum(axis=1)

    g = d.groupby(["variant", "electrode", "harmonics"], sort=False)
    t = g.agg(accuracy=("accuracy", "mean"), share=("share_12.25_12.75", "mean")).reset_index()
    t["mains"] = t.variant.map(MAINS)
    t["context"] = t.variant.map(CONTEXT)
    t = t.rename(columns={"share": "share_of_decisions_on_12.25_and_12.75_Hz"})
    t = t[["mains", "context", "variant", "electrode", "harmonics", "accuracy", "share_of_decisions_on_12.25_and_12.75_Hz"]]
    t.to_csv(out / "decision_bias_1s.csv", index=False, float_format="%.4f")

    print(f"\n== recordings. development subjects: {d.subject.nunique()}; plain CCA, sub-band 1, 1 s window")
    print("share of the decisions that go to 12.25 or 12.75 Hz (no bias: 2/12 = 0.167), and accuracy")
    print("variants: A cut then filter, mains kept | C- whole epoch, mains kept | A+ cut then filter, mains removed")
    print("          B past samples, mains removed | C whole epoch, mains removed")
    print("          B*, C*: as B and C with one mains frequency per trial shared by the channels (this script only)")
    for col, label in (("share_of_decisions_on_12.25_and_12.75_Hz", "share of the decisions on 12.25 or 12.75 Hz"),
                       ("accuracy", "accuracy")):
        w = t.pivot(index=["mains", "context", "variant", "electrode"], columns="harmonics", values=col)[list(SETS)]
        print(f"\n{label}, by the harmonics in the references:")
        print(w.round(3).to_string())
    by_freq = [c for _, c in sorted(zip(F, cols))]
    full = d[d.harmonics == "1-5"].groupby(["variant", "electrode"])[by_freq].sum()
    full.columns = [c[2:-2] for c in by_freq]
    print("\nshare of the decisions per target frequency (Hz), harmonics 1-5 (no bias: 0.083):")
    print((full.div(full.sum(axis=1), axis=0)).round(3).to_string())

    names = [f"{f:g} Hz" for f in NEAR]
    spec = pd.DataFrame([r for res in results for r in res[1]], columns=["subject", "electrode", "mains"] + names)
    spec.to_csv(out / "amplitude_near_mains_1s.csv", index=False, float_format="%.4f")
    med = spec.groupby(["electrode", "mains"])[names].median()
    print("\namplitude near the mains in the 1 s window (µV, median over people of the mean over "
          "channels and trials);\nremoved = mains removal of variant B, no band-pass filter:")
    print(med.round(3).to_string())
    side = spec[["49 Hz", "51 Hz"]].mean(axis=1) / spec[["47 Hz", "48 Hz", "52 Hz", "53 Hz"]].mean(axis=1)
    ratio = side.groupby([spec.electrode, spec.mains]).median()
    print("\nratio of the amplitude at 49 and 51 Hz to the amplitude at 47, 48, 52 and 53 Hz (1 = nothing special):")
    print(ratio.round(2).to_string())


if __name__ == "__main__":
    main()
