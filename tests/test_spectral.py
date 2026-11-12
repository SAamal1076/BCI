"""Spectral functions on synthetic signals (run: python -m pytest -q tests).

These tests are the gate of M0: they must pass before the functions are used on the recordings.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import spectral as sp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS = wd.FS
N = wd.STIM_SAMPLES                      # 2 s window
T = np.arange(N) / FS
TE = wd.epoch_times()                    # full epoch, 0 = stimulus onset
WIN = slice(wd.RESP_START, wd.RESP_START + N)


def wrap(a):
    return np.angle(np.exp(1j * a))


def test_amplitude_and_phase_are_exact_at_half_bin_frequencies():
    for f in wd.TARGET_FREQS:
        c = sp.fourier_coef(3.0 * np.sin(2 * np.pi * f * T + 0.7), f, FS)[0]
        assert abs(abs(c) - 3.0) < 1e-9
        assert abs(wrap(sp.sine_phase(c) - 0.7)) < 1e-9


def test_a_peak_does_not_leak_into_neighbours_half_a_hertz_apart():
    f = 11.25
    neigh = f + 0.5 * np.array([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
    assert sp.amplitude(np.sin(2 * np.pi * f * T + 1.1), neigh, FS).max() < 1e-9


def test_offset_and_drift_bias_the_raw_estimate_and_preprocessing_removes_the_bias():
    x = 300.0 + 80.0 * TE + 2.0 * np.sin(2 * np.pi * 9.25 * TE)        # offset + drift + 2 uV response
    raw = sp.amplitude(x[WIN], 9.25, FS)[0]
    clean = sp.amplitude(sp.preprocess_descriptive(x, FS)[WIN], 9.25, FS)[0]
    assert abs(raw - 2.0) > 1.0          # raw: wrong by more than 50 %
    assert abs(clean - 2.0) < 0.05       # after BP3-90+notch: within 2.5 %


def _gain_and_phase_error(f):
    y = sp.preprocess_descriptive(np.sin(2 * np.pi * f * TE + 0.3), FS)[WIN]
    c = sp.fourier_coef(y, f, FS, t0=wd.RESP_T0)[0]
    return abs(c), abs(wrap(sp.sine_phase(c) - 0.3))


def test_preprocessing_is_zero_phase_and_flat_at_the_fundamental_and_second_harmonic():
    for f in (9.25, 11.25, 14.75, 18.5, 22.5, 29.5):          # all f and 2f of the 12 targets lie in 9.25-29.5 Hz
        gain, phase_error = _gain_and_phase_error(f)
        assert abs(gain - 1.0) < 0.005 and phase_error < 0.005


def test_notch_attenuates_higher_harmonics_close_to_50_hz():
    # Documented limit of BP3-90+notch: harmonics near the mains frequency are attenuated (phase is kept).
    assert 0.95 < _gain_and_phase_error(45.0)[0] < 0.98       # 4th harmonic of 11.25 Hz: about -4 %
    assert 0.45 < _gain_and_phase_error(49.0)[0] < 0.55       # 4th harmonic of 12.25 Hz: about -50 %
    assert _gain_and_phase_error(45.0)[1] < 0.005


def test_notch_removes_mains_interference():
    y = sp.preprocess_descriptive(30.0 * np.sin(2 * np.pi * 50.0 * TE + 0.4), FS)[WIN]
    assert sp.amplitude(y, 50.0, FS)[0] < 0.3          # 30 uV of mains reduced by more than 40 dB


def test_snr_of_pure_noise_is_about_minus_one_and_a_half_db():
    x = np.random.default_rng(0).standard_normal((20000, N))
    snr = sp.narrowband_snr_db(x, 11.25, FS).mean()
    assert -2.0 < snr < -1.0


def test_snr_of_a_known_sinusoid_in_white_noise():
    # noise amplitude per frequency is Rayleigh with mean sigma*sqrt(pi/N): expected SNR = 22.0 dB for A = sigma
    rng = np.random.default_rng(1)
    x = np.sin(2 * np.pi * 12.75 * T) + rng.standard_normal((5000, N))
    snr = sp.narrowband_snr_db(x, 12.75, FS).mean()
    assert abs(snr - 20 * np.log10(1.0 / np.sqrt(np.pi / N))) < 0.5


def test_hann_amplitude_ignores_offset_and_drift():
    x = 500.0 + 200.0 * TE + 7.0 * np.sin(2 * np.pi * 50.0 * TE + 1.0)
    assert abs(sp.hann_amplitude(x, 50.0, FS) - 7.0) < 0.1


def _responses(tau, theta0=0.4, noise=0.0, seed=0, phases=wd.TARGET_PHASES):
    """Fourier coefficients of 12 synthetic responses delayed by tau, as the M0 timing check computes them."""
    rng = np.random.default_rng(seed)
    t = wd.RESP_T0 + T                                   # time from stimulus onset
    coefs = []
    for f, phi in zip(wd.TARGET_FREQS, phases):
        x = np.sin(2 * np.pi * f * (t - tau) + phi + theta0) + noise * rng.standard_normal(N)
        coefs.append(sp.fourier_coef(x, f, FS, t0=wd.RESP_T0)[0])
    return np.array(coefs)


def test_latency_fit_and_scan_recover_a_planted_delay():
    for tau in (0.100, 0.137, 0.180):
        c = _responses(tau, noise=1.0, seed=3)
        fit = sp.apparent_latency_fit(c, wd.TARGET_FREQS, wd.TARGET_PHASES)
        scan, _, _ = sp.apparent_latency_scan(c, wd.TARGET_FREQS, wd.TARGET_PHASES)
        assert abs(fit["tau"] - tau) < 0.005 and fit["r2"] > 0.95
        assert abs(scan["tau"] - tau) < 0.005 and scan["r"] > 0.9


def test_latency_is_wrong_by_half_a_second_if_the_phase_table_is_ignored():
    c = _responses(0.140)
    scan, _, _ = sp.apparent_latency_scan(c, wd.TARGET_FREQS, np.zeros(12), taus=np.arange(-1000, 1001) / 1000.0)
    assert min(abs(scan["tau"] - (0.140 - 0.5)), abs(scan["tau"] - (0.140 + 1.5))) < 0.002


def test_phase_reference_is_stimulus_onset_whatever_the_window_start():
    f, tau = 10.25, 0.140
    x = np.sin(2 * np.pi * f * (TE - tau) + 1.0)
    a = sp.fourier_coef(x[160:660], f, FS, t0=(160 - wd.ONSET) / FS)[0]
    b = sp.fourier_coef(x[185:685], f, FS, t0=(185 - wd.ONSET) / FS)[0]
    assert abs(wrap(np.angle(a) - np.angle(b))) < 1e-9
