"""Wearable SSVEP dataset (Zhu et al., Sensors 2021): constants, loader, subject split.

Layout in the files:      data[channel, sample, electrode, block, target] = [8, 710, 2, 10, 12]
Layout used in this code: x[electrode, block, target, channel, sample]   = [2, 10, 12, 8, 710]

Everything here comes from the dataset documentation (Readme.pdf, stimulation_information.pdf, the paper)
and is checked on the files in M0 (docs/milestones/M0_data_audit.md).
"""
from __future__ import annotations

import os
import pathlib

import numpy as np
from scipy.io import loadmat

FS = 250.0                       # Hz (recorded at 1000 Hz, stored at 250 Hz)
CHANNELS = ("POz", "PO3", "PO4", "PO5", "PO6", "Oz", "O1", "O2")
OZ = CHANNELS.index("Oz")
N_SAMPLES = 710                  # 2.84 s
ONSET = 125                      # stimulus onset, 0.5 s after the start of the epoch
LATENCY = 35                     # 0.14 s visual latency
RESP_START = ONSET + LATENCY     # 160, first sample of the response window
STIM_SAMPLES = 500               # 2 s of stimulation
POST_SAMPLES = 50                # 0.2 s after the stimulation
N_ELECTRODES, N_BLOCKS, N_TARGETS, N_CHANNELS = 2, 10, 12, 8
FILE_SHAPE = (N_CHANNELS, N_SAMPLES, N_ELECTRODES, N_BLOCKS, N_TARGETS)

# Targets in file order (stimulation_information.pdf). Luminance: 0.5 * (1 + sin(2*pi*f*t + phase)).
TARGET_CHARS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "*", "#")
TARGET_FREQS = np.array([9.25, 11.25, 13.25, 9.75, 11.75, 13.75,
                         10.25, 12.25, 14.25, 10.75, 12.75, 14.75])
TARGET_PHASES = np.pi * np.array([0.0, 0.0, 0.0, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 1.5, 1.5, 1.5])

# Electrode type along the first axis of load_subject(). Settled in M0 (audit, section 3): position 1 of the
# files is the DRY headband and position 2 the WET one, in the EEG files and in Impedance.mat. This is the
# opposite of the label printed in the dataset readme and paper ("1: wet, 2: dry").
DRY, WET = 0, 1
ELECTRODE_NAMES = ("dry", "wet")

# Subjects. The lockbox rule was fixed before any data was opened (docs/analysis_plan.md).
SUBJECTS = tuple(range(1, 103))
LOCKBOX = tuple(s for s in SUBJECTS if s % 3 == 0)        # S003, S006, ..., S102 (34)
DEVELOPMENT = tuple(s for s in SUBJECTS if s % 3 != 0)    # the other 68

DEFAULT_DIR = pathlib.Path(os.environ.get("WEARABLE_DIR", "data/wearable_ssvep"))


def is_lockbox(sid: int) -> bool:
    return sid % 3 == 0


def subject_path(raw_dir, sid: int) -> pathlib.Path:
    return pathlib.Path(raw_dir) / f"S{sid:03d}.mat"


def load_subject(raw_dir, sid: int) -> np.ndarray:
    """EEG of one subject, float64, [electrode, block, target, channel, sample] = [2, 10, 12, 8, 710]."""
    data = loadmat(subject_path(raw_dir, sid))["data"]
    if data.shape != FILE_SHAPE:
        raise ValueError(f"S{sid:03d}: unexpected shape {data.shape}, expected {FILE_SHAPE}")
    return np.ascontiguousarray(np.transpose(data, (2, 3, 4, 0, 1)), dtype=np.float64)


def epoch_times() -> np.ndarray:
    """Time of each sample of an epoch in seconds, 0 = stimulus onset."""
    return (np.arange(N_SAMPLES) - ONSET) / FS


def response_window(x: np.ndarray, seconds: float = 2.0) -> np.ndarray:
    """Cut the response window (starts 0.14 s after stimulus onset) along the last axis."""
    n = int(round(seconds * FS))
    if not 0 < n <= STIM_SAMPLES:
        raise ValueError("window length must be in (0, 2] s")
    if x.shape[-1] != N_SAMPLES:
        raise ValueError("last axis must be a full epoch of 710 samples")
    return x[..., RESP_START:RESP_START + n]


RESP_T0 = LATENCY / FS   # time of the first sample of the response window, from stimulus onset (0.14 s)
