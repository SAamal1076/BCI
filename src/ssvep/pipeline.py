"""Preprocessing candidates of M2 (step 0 of the M2 plan) for one window of a wearable epoch.

All three use the samples from the start of the epoch to the end of the window and nothing after it.

  B   as in M1: mains removed by least squares with the frequency chosen per channel; reference filter bank
      (5 sub-bands, 6/14/22/30/38 to 90 Hz); 5 harmonics.
  B1  as B, with ONE mains frequency per trial shared by all channels (the same linear operation on every
      channel, so differences between channels are left untouched).
  B2  as B1, with the band limited below the mains: 3 sub-bands, 6/14/22 to 45 Hz (stop band from 50 Hz),
      3 harmonics (highest reference frequency 44.25 Hz).
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from . import decoders as dc
from . import filterbank as fb
from . import spectral as sp

NAMES = ("B", "B1", "B2")
_LOW_PASS, _LOW_STOP = (6.0, 14.0, 22.0), (4.0, 10.0, 16.0)


def remove_mains_shared(x, fs, f0=50.0, half_width=0.5, step=0.01):
    """As spectral.remove_mains, but the mains frequency is chosen once per trial for all channels (largest
    explained energy summed over the channels). x: (..., channels, samples)."""
    x = signal.detrend(np.asarray(x, dtype=float), axis=-1, type="linear")
    n = x.shape[-1]
    t = np.arange(n) / fs
    tc = (t - t.mean()) / t.std()
    k = int(round(half_width / step))
    flat = x.reshape(-1, x.shape[-2], n)
    bases, energy = [], []
    for f in f0 + np.arange(-k, k + 1) * step:
        s, c = np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)
        q, _ = np.linalg.qr(np.column_stack([s, c, tc * s, tc * c]))
        bases.append(q)
        energy.append(((flat @ q) ** 2).sum(axis=(1, 2)))
    best = np.argmax(np.array(energy), axis=0)
    out = flat.copy()
    for i in np.unique(best):
        rows = best == i
        out[rows] -= (flat[rows] @ bases[i]) @ bases[i].T
    return out.reshape(x.shape)


def design_b2(band: int, fs: float = 250.0):
    """Second-order sections of sub-band `band` of B2: Chebyshev type I, pass band from 6, 14 or 22 Hz to 45 Hz,
    stop bands below 4, 10 or 16 Hz and above 50 Hz (3 dB, 40 dB, 0.5 dB ripple; same rule as the reference)."""
    nyq = fs / 2.0
    order, wn = signal.cheb1ord([_LOW_PASS[band] / nyq, 45.0 / nyq], [_LOW_STOP[band] / nyq, 50.0 / nyq], 3, 40)
    return signal.cheby1(order, 0.5, wn, btype="bandpass", output="sos")


def _zero_phase_sos(sos, x):
    return signal.sosfiltfilt(sos, x, axis=-1, padtype="odd", padlen=3 * (2 * len(sos)))


_REFERENCE = [fb.design(n) for n in range(5)]
_B2 = [design_b2(n) for n in range(3)]
N_BANDS = {"B": 5, "B1": 5, "B2": 3}
N_HARM = {"B": 5, "B1": 5, "B2": 3}


def weights(name: str):
    """A-priori sub-band weights n^(-1.25) + 0.25 for the sub-bands of the pipeline."""
    return dc.fb_weights(N_BANDS[name], 1.25, 0.25)


def subbands(x, n_window: int, name: str, start: int, fs: float = 250.0):
    """Sub-band signals of the window [start, start + n_window) of full epochs x (..., channels, samples).
    Returns (n_bands, ..., channels, n_window). No sample after the window is used."""
    seg = x[..., :start + n_window]
    if name == "B":
        seg = sp.remove_mains(seg, fs)
        return np.stack([fb.zero_phase(f, seg)[..., start:] for f in _REFERENCE])
    seg = remove_mains_shared(seg, fs)
    if name == "B1":
        return np.stack([fb.zero_phase(f, seg)[..., start:] for f in _REFERENCE])
    if name == "B2":
        return np.stack([_zero_phase_sos(s, seg)[..., start:] for s in _B2])
    raise ValueError(f"unknown pipeline {name!r}")
