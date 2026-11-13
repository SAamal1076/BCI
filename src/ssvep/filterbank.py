"""Filter bank of the reference implementation (Nakanishi et al. 2018, after Chen et al. 2015) and the three
ways of filtering a short window that M1 compares.

Sub-band n passes [PASS[n], 90] Hz: Chebyshev type I, order from cheb1ord (3 dB at the pass edges, 40 dB at
the stop edges STOP[n] and 100 Hz), 0.5 dB ripple, applied forward and backward.

Variants (x is a full epoch of 710 samples, the window starts at sample `start`):
  A  reference convention: cut the window, then filter it. No mains removal.
  B  project pipeline: samples from the start of the epoch to the END OF THE WINDOW, least-squares mains
     removal on that segment, filter, keep the window. No sample after the end of the window is used.
  C  whole epoch (diagnostic): mains removal and filter on the full epoch, then cut. Uses future samples.

Two more variants were added after the reproduction gate failed, to separate the effect of the mains
component from the effect of the context given to the filter (post hoc diagnostics, M1 report):
  A+ as A, with least-squares mains removal on the cut window before filtering
  C- as C, without mains removal
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from .spectral import remove_mains

PASS = (6.0, 14.0, 22.0, 30.0, 38.0, 46.0, 54.0, 62.0, 70.0, 78.0)
STOP = (4.0, 10.0, 16.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 72.0)
VARIANTS = ("A", "B", "C")
DIAGNOSTIC_VARIANTS = ("A+", "C-")


def design(band: int, fs: float = 250.0, high_pass: float = 90.0, high_stop: float = 100.0):
    """(b, a) of sub-band `band` (0-based), exactly as in the reference implementation."""
    nyq = fs / 2.0
    order, wn = signal.cheb1ord([PASS[band] / nyq, high_pass / nyq], [STOP[band] / nyq, high_stop / nyq], 3, 40)
    return signal.cheby1(order, 0.5, wn, btype="bandpass")


def design_band(low: float, high: float, low_stop: float, high_stop: float, fs: float = 250.0):
    """(b, a) of a single band-pass with the same design rule (used for the 6-80 Hz band of the BETA paper)."""
    nyq = fs / 2.0
    order, wn = signal.cheb1ord([low / nyq, high / nyq], [low_stop / nyq, high_stop / nyq], 3, 40)
    return signal.cheby1(order, 0.5, wn, btype="bandpass")


def zero_phase(ba, x):
    """Forward-backward filtering along the last axis with the padding of MATLAB's filtfilt
    (odd extension of 3 * filter order samples), so that short windows behave as in the reference code."""
    b, a = ba
    return signal.filtfilt(b, a, x, axis=-1, padtype="odd", padlen=3 * (max(len(a), len(b)) - 1))


def subbands(x, n_bands: int, n_window: int, variant: str, start: int, fs: float = 250.0, filters=None):
    """Sub-band signals of the window [start, start + n_window) of full epochs x (..., n_samples).

    Returns an array (n_bands, ..., n_window).
    """
    if filters is None:
        filters = [design(n, fs) for n in range(n_bands)]
    stop = start + n_window
    if variant == "A":
        seg = x[..., start:stop]
        return np.stack([zero_phase(f, seg) for f in filters])
    if variant == "B":
        seg = remove_mains(x[..., :stop], fs)
        return np.stack([zero_phase(f, seg)[..., start:] for f in filters])
    if variant == "C":
        seg = remove_mains(x, fs)
        return np.stack([zero_phase(f, seg)[..., start:stop] for f in filters])
    if variant == "A+":
        seg = remove_mains(x[..., start:stop], fs)
        return np.stack([zero_phase(f, seg) for f in filters])
    if variant == "C-":
        return np.stack([zero_phase(f, x)[..., start:stop] for f in filters])
    raise ValueError(f"unknown variant {variant!r}")
