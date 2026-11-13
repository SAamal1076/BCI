"""BETA reader: the numpy-only MATLAB 5 reader of scripts/beta_reduce.py against scipy, on a synthetic file."""
import pathlib
import sys

import numpy as np
from scipy.io import savemat

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import beta_reduce as br  # noqa: E402
from ssvep import beta as bd  # noqa: E402


def _synthetic_file(path, sid=3, compress=True):
    rng = np.random.default_rng(sid)
    names = [f"X{i}" for i in range(64)]
    for k, c in zip((47, 54, 53, 56, 57, 55, 60, 61, 62), bd.CHANNELS):
        names[k] = c
    chan = np.empty((64, 4), dtype=object)
    for i in range(64):
        chan[i] = [str(i + 1), "0.5", "0.25", names[i]]
    eeg = rng.standard_normal((64, bd.n_samples(sid), bd.N_BLOCKS, bd.N_TARGETS))
    info = {"sub": f"S{sid}", "age": 25.0, "gender": "female", "chan": chan, "freqs": bd.TARGET_FREQS,
            "phases": bd.PHASES_IN_FILES, "bci_quotient": 100.0, "wide_snr": -12.0, "narrow_snr": 4.0, "srate": 250}
    savemat(path, {"data": {"EEG": eeg, "suppl_info": info}}, do_compression=compress)
    return eeg


def test_reader_matches_the_written_arrays(tmp_path):
    for compress in (True, False):
        eeg = _synthetic_file(tmp_path / "S3.mat", compress=compress)
        data = br.read_mat(tmp_path / "S3.mat")["data"]
        assert np.array_equal(data["EEG"], eeg)
        assert np.allclose(np.ravel(data["suppl_info"]["freqs"]), bd.TARGET_FREQS)
        assert str(data["suppl_info"]["chan"][61, 3]) == "OZ"
        assert data["suppl_info"]["sub"] == "S3"


def test_reduced_file_and_original_file_give_the_same_numbers(tmp_path):
    raw, small = tmp_path / "raw", tmp_path / "small"
    raw.mkdir(), small.mkdir()
    eeg = _synthetic_file(raw / "S3.mat")
    meta = br.reduce_file(raw / "S3.mat", small)
    assert meta["channel_index_0based"] == [47, 54, 53, 56, 57, 55, 60, 61, 62] and meta["all_finite"]
    from_reduced, from_original = bd.load_subject(small, 3), bd.load_subject(raw, 3)
    assert from_reduced.shape == (bd.N_BLOCKS, bd.N_TARGETS, bd.N_CHANNELS, 750)
    assert np.array_equal(from_reduced, from_original)
    assert np.allclose(from_reduced[1, 2, bd.OZ], eeg[61, :, 1, 2], atol=1e-6)      # [block, target, channel, sample]
    freqs, phases = bd.load_tables(small, 3)
    assert np.allclose(freqs, bd.TARGET_FREQS) and np.allclose(phases, bd.PHASES_IN_FILES)


def test_tables():
    assert len(bd.TARGET_FREQS) == 40 and bd.TARGET_FREQS[0] == 8.6 and bd.TARGET_FREQS[-1] == 8.4
    assert bd.RESP_START == 158 and bd.n_samples(15) == 750 and bd.n_samples(16) == 1000
    # the authors' correction shifts every phase by the same amount (1.5 pi)
    assert np.allclose(np.mod(bd.PHASES_CORRECTED - bd.PHASES_IN_FILES, 2 * np.pi), 1.5 * np.pi)
