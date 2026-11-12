"""Filters and narrow-band spectral estimates at exact (off-grid) frequencies.

Why "exact frequency": with a 2 s window the FFT bins are 0.5 Hz apart and the stimulus frequencies of the
wearable dataset (9.25, 9.75, ...) fall half-way between them. The Fourier coefficient is therefore computed
directly at the frequency of interest. For a 2 s rectangular window, sinusoids whose frequencies differ by a
multiple of 0.5 Hz are orthogonal, so a peak at f contributes nothing at f +/- k*0.5 Hz. The mean and slow
drifts are NOT orthogonal to these half-bin frequencies, and neither is mains interference at about
50 Hz: they must be removed first (preprocess_descriptive).
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
    """Zero-phase IIR notch. NOT used for the analyses: on a 2.84 s epoch with strong mains interference it
    leaves an edge transient inside the response window (see tests and M0 audit, deviation D1)."""
    b, a = signal.iirnotch(f0, q, fs=fs)
    return signal.filtfilt(b, a, x, axis=axis)


def remove_mains(x, fs, f0=50.0, half_width=0.5, step=0.01):
    """Remove mains interference from each epoch by least squares, along the last axis.

    The linear trend is removed, then a sinusoid with a linearly varying amplitude,
    (a + b*t)*sin(2*pi*f*t) + (c + d*t)*cos(2*pi*f*t), is fitted and subtracted. f is searched for each
    series between f0 - half_width and f0 + half_width (largest explained energy), because the mains
    frequency is not exactly 50 Hz. No filter is involved, so there is no edge transient and no phase shift.
    Limit: a response component within about 1.5 Hz of f0 (e.g. the 4th harmonic of 12.25 Hz) can be
    partly removed.
    """
    x = signal.detrend(np.asarray(x, dtype=float), axis=-1, type="linear")
    n = x.shape[-1]
    t = np.arange(n) / fs
    tc = (t - t.mean()) / t.std()
    k = int(round(half_width / step))
    flat = x.reshape(-1, n)
    bases, energy = [], []
    for f in f0 + np.arange(-k, k + 1) * step:
        s, c = np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)
        q, _ = np.linalg.qr(np.column_stack([s, c, tc * s, tc * c]))
        bases.append(q)
        energy.append(((flat @ q) ** 2).sum(axis=1))
    best = np.argmax(np.array(energy), axis=0)
    out = flat.copy()
    for i in np.unique(best):
        rows = best == i
        out[rows] -= (flat[rows] @ bases[i]) @ bases[i].T
    return out.reshape(x.shape)


def preprocess_descriptive(x, fs):
    """Preprocessing of the M0 description, along the last axis (a full epoch):
    remove the linear trend, remove mains by least squares, zero-phase band-pass 3-90 Hz.

    The M0 plan specified an IIR notch at 50 Hz; it was replaced by remove_mains (deviation D1 of the audit).
    """
    return bandpass(remove_mains(x, fs), fs, 3.0, 90.0)


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
