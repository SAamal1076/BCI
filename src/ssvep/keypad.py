"""The stimulus keypad of the wearable dataset, and the classes used to sort decoding errors (M4).

Figure 1 of Zhu et al. (2021): 3 rows of 4 targets, in the order of the data files:
    1  2  3  4        9.25  11.25  13.25   9.75 Hz
    5  6  7  8       11.75  13.75  10.25  12.25
    9  0  *  #       14.25  10.75  12.75  14.75
The frequencies were placed so that two targets that are side by side or one above the other are never 0.5 Hz
apart. This separates two kinds of error: a confusion in frequency and a confusion in space.
"""
from __future__ import annotations

import numpy as np

from . import wearable as wd

N_ROWS, N_COLS = 3, 4
ROW = np.arange(wd.N_TARGETS) // N_COLS
COL = np.arange(wd.N_TARGETS) % N_COLS
CLASSES = ("0.5 Hz apart and neighbours on the keypad (diagonal)", "0.5 Hz apart, not neighbours on the keypad",
           "neighbours on the keypad, not 0.5 Hz apart", "neither")


def frequency_neighbours():
    """(12, 12) bool: the two targets are 0.5 Hz apart."""
    f = wd.TARGET_FREQS
    return np.isclose(np.abs(f[:, None] - f[None, :]), 0.5)


def keypad_neighbours(diagonal: bool = True):
    """(12, 12) bool: the two targets touch on the keypad (side by side, one above the other, or diagonally)."""
    dr, dc = np.abs(ROW[:, None] - ROW[None, :]), np.abs(COL[:, None] - COL[None, :])
    near = (np.maximum(dr, dc) == 1) if diagonal else (dr + dc == 1)
    return near


def error_class():
    """(12, 12) int: class of the error 'true target i decided as j' (index into CLASSES); -1 on the diagonal."""
    fn, kn = frequency_neighbours(), keypad_neighbours()
    cls = np.where(fn & kn, 0, np.where(fn, 1, np.where(kn, 2, 3)))
    cls[np.eye(wd.N_TARGETS, dtype=bool)] = -1
    return cls


def expected_shares():
    """Share of each class if errors were spread evenly over the 11 wrong targets."""
    cls = error_class()
    return np.array([(cls == k).sum() for k in range(len(CLASSES))]) / (wd.N_TARGETS * (wd.N_TARGETS - 1))
