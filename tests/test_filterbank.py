"""Filter bank and the three ways of filtering a short window (run: python -m pytest -q tests)."""
import pathlib
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import filterbank as fb  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS = wd.FS


def gain_db(ba, f):
    _, h = signal.freqz(*ba, worN=[f], fs=FS)
    return 20 * np.log10(abs(h[0]))


def test_design_follows_the_reference_implementation():
    # cheb1ord(Wp, Ws, 3, 40) then cheby1(N, 0.5, Wn): orders and band edges of the first five sub-bands.
    # The order is computed for 3 dB of ripple and the filter is built with 0.5 dB, so the reference design
    # reaches 33 to 37 dB at the stop edges (single pass), not the nominal 40 dB.
    assert [(len(fb.design(n)[0]) - 1) // 2 for n in range(5)] == [6, 6, 6, 7, 7]
    for n in range(5):
        ba = fb.design(n)
        assert abs(gain_db(ba, fb.PASS[n]) + 0.5) < 0.01 and abs(gain_db(ba, 90.0) + 0.5) < 0.01   # ripple edge
        assert gain_db(ba, fb.STOP[n]) < -33 and gain_db(ba, 100.0) < -33
        inside = np.linspace(fb.PASS[n] + 1, 89, 50)
        assert all(-0.51 < gain_db(ba, f) < 0.01 for f in inside)
        assert np.abs(np.roots(ba[1])).max() < 1.0                                                  # stable


def test_transfer_function_form_is_numerically_sound():
    x = np.random.default_rng(0).standard_normal((4, 2000))
    for n in range(5):
        order = (len(fb.design(n)[0]) - 1) // 2
        nyq = FS / 2
        sos = signal.cheby1(order, 0.5, [fb.PASS[n] / nyq, 90 / nyq], btype="bandpass", output="sos")
        ref = signal.sosfiltfilt(sos, x, axis=-1, padtype="odd", padlen=3 * 2 * order)
        assert np.abs(fb.zero_phase(fb.design(n), x) - ref).max() < 1e-6


def test_shapes_and_shortest_window():
    x = np.random.default_rng(1).standard_normal((2, 3, 8, wd.N_SAMPLES))
    for variant in fb.VARIANTS:
        for n_window in (50, 250, 500):
            y = fb.subbands(x, 5, n_window, variant, wd.RESP_START)
            assert y.shape == (5, 2, 3, 8, n_window) and np.isfinite(y).all()


def test_variants_a_and_b_ignore_samples_after_the_window_and_c_does_not():
    rng = np.random.default_rng(2)
    x = rng.standard_normal((8, wd.N_SAMPLES))
    future = x.copy()
    stop = wd.RESP_START + 250
    future[:, stop:] = 50.0 * rng.standard_normal((8, wd.N_SAMPLES - stop))        # change only the future
    for variant, uses_future in (("A", False), ("B", False), ("C", True)):
        d = np.abs(fb.subbands(x, 5, 250, variant, wd.RESP_START) - fb.subbands(future, 5, 250, variant, wd.RESP_START))
        assert (d.max() > 1e-3) == uses_future


def test_variant_a_ignores_samples_before_the_window_and_b_uses_them():
    rng = np.random.default_rng(3)
    x = rng.standard_normal((8, wd.N_SAMPLES))
    past = x.copy()
    past[:, :wd.RESP_START] = 50.0 * rng.standard_normal((8, wd.RESP_START))
    d_a = np.abs(fb.subbands(x, 5, 250, "A", wd.RESP_START) - fb.subbands(past, 5, 250, "A", wd.RESP_START))
    d_b = np.abs(fb.subbands(x, 5, 250, "B", wd.RESP_START) - fb.subbands(past, 5, 250, "B", wd.RESP_START))
    assert d_a.max() == 0.0 and d_b.max() > 1e-3
