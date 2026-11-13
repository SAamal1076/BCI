"""BETA dataset (Liu et al., Front. Neurosci. 2020): constants and loader.

Reference dataset of the project: 70 people, 64 channels, 40 targets, 4 blocks, recorded with a laboratory
amplifier outside a shielded room. The files were band-pass filtered (3-100 Hz) and sampled at 250 Hz by the
authors; the amplifier had a 50 Hz notch. The project uses the nine channels of the BETA paper.

A trial is 0.5 s before stimulus onset + stimulation (2 s for S1-S15, 3 s for S16-S70) + 0.5 s after it.
"""
from __future__ import annotations

import json
import os
import pathlib

import numpy as np

FS = 250
CHANNELS = ("PZ", "PO3", "PO5", "PO4", "PO6", "POZ", "O1", "OZ", "O2")
OZ = CHANNELS.index("OZ")
SUBJECTS = tuple(range(1, 71))
N_BLOCKS, N_TARGETS, N_CHANNELS = 4, 40, 9
ONSET = 125                                    # samples before stimulus onset (0.5 s)
LATENCY = 33                                   # 0.13 s visual latency of the BETA paper (32.5 samples, rounded up)
RESP_START = ONSET + LATENCY
# order of the targets in the files: 8.6, 8.8, ..., 15.8, 8.0, 8.2, 8.4 Hz
TARGET_FREQS = np.round(np.concatenate([np.arange(8.6, 15.81, 0.2), [8.0, 8.2, 8.4]]), 1)
# phase table stored in the files, and the one of the authors' correction of 15 June 2022 (same order)
PHASES_IN_FILES = np.tile([0.0, 0.5, 1.0, 1.5], 10) * np.pi
PHASES_CORRECTED = np.tile([1.5, 0.0, 0.5, 1.0], 10) * np.pi
DEFAULT_DIR = pathlib.Path(os.environ.get("BETA_DIR", "data/beta"))


def stim_seconds(sid: int) -> float:
    return 2.0 if sid <= 15 else 3.0


def n_samples(sid: int) -> int:
    return int(round((1.0 + stim_seconds(sid)) * FS))


def _from_mat(path):
    from scipy.io import loadmat
    data = loadmat(path, struct_as_record=False, squeeze_me=True)["data"]
    info = data.suppl_info
    names = [str(c).strip().upper() for c in info.chan[:, 3]]
    eeg = data.EEG[[names.index(c) for c in CHANNELS]].astype(np.float32)
    return eeg, np.asarray(info.freqs, dtype=float), np.asarray(info.phases, dtype=float)


def load_subject(raw_dir, sid: int):
    """EEG of one person, float64 [block, target, channel, sample], nine channels, microvolts.

    Reads S<n>.npy written by scripts/beta_reduce.py if it is there, else the original S<n>.mat. Both give the
    same numbers: the nine channels in single precision.
    """
    raw_dir = pathlib.Path(raw_dir)
    small = raw_dir / f"S{sid}.npy"
    eeg = np.load(small) if small.exists() else _from_mat(raw_dir / f"S{sid}.mat")[0]
    if eeg.shape != (N_CHANNELS, n_samples(sid), N_BLOCKS, N_TARGETS):
        raise ValueError(f"S{sid}: unexpected shape {eeg.shape}")
    return eeg.transpose(2, 3, 0, 1).astype(np.float64)


def load_tables(raw_dir, sid: int):
    """Frequency and phase table stored with the data of one person: (freqs, phases)."""
    raw_dir = pathlib.Path(raw_dir)
    meta = raw_dir / f"S{sid}.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        return np.array(m["freqs"]), np.array(m["phases"])
    return _from_mat(raw_dir / f"S{sid}.mat")[1:]
