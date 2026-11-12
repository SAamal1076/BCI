"""Dataset constants, the development/lockbox split and the loader (run: python -m pytest -q tests)."""
import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import wearable as wd  # noqa: E402

needs_data = pytest.mark.skipif(not wd.subject_path(wd.DEFAULT_DIR, 1).exists(),
                                reason="raw data not available (set WEARABLE_DIR)")


def test_epoch_layout_adds_up():
    assert wd.ONSET + wd.LATENCY + wd.STIM_SAMPLES + wd.POST_SAMPLES == wd.N_SAMPLES == 710
    assert wd.ONSET / wd.FS == 0.5 and wd.LATENCY / wd.FS == 0.14 and wd.RESP_START == 160
    t = wd.epoch_times()
    assert t[wd.ONSET] == 0.0 and np.isclose(t[wd.RESP_START], 0.14)


def test_target_table_is_a_joint_frequency_phase_code():
    order = np.argsort(wd.TARGET_FREQS)
    f, phi = wd.TARGET_FREQS[order], wd.TARGET_PHASES[order]
    assert len(set(wd.TARGET_FREQS)) == 12 and len(wd.TARGET_CHARS) == 12
    assert np.allclose(np.diff(f), 0.5) and f[0] == 9.25 and f[-1] == 14.75
    assert np.allclose(np.mod(np.diff(phi), 2 * np.pi), 0.5 * np.pi)      # +0.5*pi per 0.5 Hz step


def test_development_and_lockbox_split():
    assert len(wd.LOCKBOX) == 34 and len(wd.DEVELOPMENT) == 68
    assert set(wd.LOCKBOX) | set(wd.DEVELOPMENT) == set(range(1, 103))
    assert not set(wd.LOCKBOX) & set(wd.DEVELOPMENT)
    assert wd.LOCKBOX[:3] == (3, 6, 9) and wd.LOCKBOX[-1] == 102
    assert all(wd.is_lockbox(s) for s in wd.LOCKBOX) and not any(wd.is_lockbox(s) for s in wd.DEVELOPMENT)


def test_response_window():
    x = np.zeros((2, 3, wd.N_SAMPLES))
    x[..., wd.RESP_START] = 1.0
    assert wd.response_window(x).shape == (2, 3, 500) and wd.response_window(x)[0, 0, 0] == 1.0
    assert wd.response_window(x, 0.2).shape == (2, 3, 50)
    with pytest.raises(ValueError):
        wd.response_window(x, 2.5)
    with pytest.raises(ValueError):
        wd.response_window(x[..., :700])


@needs_data
def test_loader_layout_on_a_development_subject():
    x = wd.load_subject(wd.DEFAULT_DIR, 1)
    assert x.shape == (2, 10, 12, 8, 710) and x.dtype == np.float64 and np.isfinite(x).all()
