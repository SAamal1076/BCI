"""Filters and narrow-band spectral estimates at exact (off-grid) frequencies.

Why "exact frequency": with a 2 s window the FFT bins are 0.5 Hz apart and the stimulus frequencies of the
wearable dataset (9.25, 9.75, ...) fall half-way between them. The Fourier coefficient is therefore computed
directly at the frequency of interest. For a 2 s rectangular window, sinusoids whose frequencies differ by a
multiple of 0.5 Hz are orthogonal, so a peak at f contributes nothing at f +/- k*0.5 Hz. The mean and slow
drifts are NOT orthogonal to these half-bin frequencies and must be removed first (preprocess_descriptive).
"""
from __future__ import annotations

import numpy as np
from scipy import signal


# ----------------------------------------------------------------------------- filters (all zero-phase)
def bandpass(x, fs, low, high, order=4, axis=-1):
    sos = signal.butter(order, [low, high], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=axis)


def lowpass(x, fs, cut, order=4, axis=-1):
    sos = signal.butter(order, cut, btype="lowpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=axis)


def notch(x, fs, f0=50.0, q=25.0, axis=-1):
    b, a = signal.iirnotch(f0, q, fs=fs)
    return signal.filtfilt(b, a, x, axis=axis)


def preprocess_descriptive(x, fs, axis=-1):
    """'BP3-90+notch' of the M0 plan: remove the mean, band-pass 3-90 Hz, notch at 50 Hz. Zero-phase."""
    x = x - x.mean(axis=axis, keepdims=True)
    return notch(bandpass(x, fs, 3.0, 90.0, axis=axis), fs, axis=axis)


# ----------------------------------------------------------------------------- Fourier coefficient
def fourier_coef(x, freqs, fs, t0=0.0):
    """Complex Fourier coefficient at arbitrary frequencies, along the last axis.

    c(f) = (2/N) * sum_n x[n] * exp(-j*2*pi*f*t_n),  t_n = t0 + n/fs.
    |c| is the amplitude of a sinusoid at f. angle(c) is its cosine phase at t = 0, so the phase is
    referred to the time origin given by t0 (use t0 = time of the first sample from stimulus onset).
    Returns an array of shape x.shape[:-1] + (len(freqs),).
    """
    x = np.asarray(x, dtype=float)
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float))
    n = x.shape[-1]
    t = t0 + np.arange(n) / fs
    basis = np.exp(-2j * np.pi * np.outer(t, freqs))      # (n, n_freqs)
    return (2.0 / n) * (x @ basis)


def amplitude(x, freqs, fs):
    return np.abs(fourier_coef(x, freqs, fs))


def sine_phase(coef):
    """Phase psi of A*sin(2*pi*f*t + psi) from its Fourier coefficient."""
    return np.angle(coef) + np.pi / 2


def narrowband_snr_db(x, freqs, fs, n_side=5):
    """Narrow-band SNR in dB: amplitude at f over the mean amplitude of the 2*n_side neighbours
    f +/- k*df, k = 1..n_side, with df = fs/N (0.5 Hz for a 2 s window).

    For pure noise this averages about -1.5 dB, not 0 dB (mean of a log versus log of a mean).
    Returns an array of shape x.shape[:-1] + (len(freqs),).
    """
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float))
    df = fs / x.shape[-1]
    k = np.arange(1, n_side + 1) * df
    neigh = np.concatenate([freqs[:, None] - k, freqs[:, None] + k], axis=1)      # (n_freqs, 2*n_side)
    a_sig = amplitude(x, freqs, fs)
    a_noise = amplitude(x, neigh.ravel(), fs).reshape(x.shape[:-1] + neigh.shape).mean(axis=-1)
    return 20.0 * np.log10(a_sig / a_noise)


def hann_amplitude(x, f, fs):
    """Amplitude at f of a raw segment: linear trend removed, Hann window (robust to drift leakage)."""
    x = signal.detrend(np.asarray(x, dtype=float), axis=-1, type="linear")
    n = x.shape[-1]
    w = signal.windows.hann(n, sym=False)
    t = np.arange(n) / fs
    return 2.0 * np.abs((x * w) @ np.exp(-2j * np.pi * f * t)) / w.sum()


# ----------------------------------------------------------------------------- apparent latency
def apparent_latency_fit(coefs, freqs, phases):
    """Apparent latency from the slope of the response phase against frequency.

    Model: psi_k - phi_k = theta0 - 2*pi*f_k*tau, with psi_k the sine phase of the response at f_k
    (time measured from stimulus onset) and phi_k the stimulus phase.
    Returns tau (s), theta0 (rad) and R2 of the straight line.
    """
    coefs, freqs, phases = map(np.asarray, (coefs, freqs, phases))
    order = np.argsort(freqs)
    f = freqs[order]
    d = np.unwrap(sine_phase(coefs[order]) - phases[order])
    slope, intercept = np.polyfit(f, d, 1)
    resid = d - (slope * f + intercept)
    r2 = 1.0 - (resid ** 2).sum() / ((d - d.mean()) ** 2).sum()
    return {"tau": float(-slope / (2 * np.pi)), "theta0": float(intercept), "r2": float(r2)}


def apparent_latency_scan(coefs, freqs, phases, taus=None):
    """Same quantity without phase unwrapping: tau that makes the 12 phase-corrected unit phasors align.

    R(tau) = |sum_k u_k * exp(-j*phi_k) * exp(j*2*pi*f_k*tau)| / K,  u_k = c_k/|c_k|.
    With frequencies 0.5 Hz apart R has period 2 s. Returns ({tau, r}, taus, R).
    """
    coefs, freqs, phases = map(np.asarray, (coefs, freqs, phases))
    if taus is None:
        taus = np.arange(-250, 751) / 1000.0
    u = coefs / np.abs(coefs) * np.exp(-1j * phases)
    r = np.abs(np.exp(2j * np.pi * np.outer(taus, freqs)) @ u) / len(freqs)
    i = int(np.argmax(r))
    return {"tau": float(taus[i]), "r": float(r[i])}, taus, r
