"""M4 code on synthetic data: slope over blocks, permutation test, keypad and error classes."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import keypad as kp  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import wearable as wd  # noqa: E402


def test_block_slope_returns_a_planted_slope():
    b = np.arange(1, 11)
    assert np.isclose(st.block_slope(0.7 - 0.02 * b), -0.02)
    assert np.isclose(st.block_slope(np.full(10, 0.5)), 0.0)
    rng = np.random.default_rng(0)
    noisy = 0.6 - 0.01 * b + 0.1 * rng.standard_normal((2000, 10))
    assert abs(st.block_slope(noisy).mean() + 0.01) < 0.002 and st.block_slope(noisy).shape == (2000,)


def test_permutation_test_sees_a_planted_relation_and_nothing_else():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(34)
    rho, p = st.spearman_permutation_test(x, -x + 0.8 * rng.standard_normal(34), n_perm=2000)
    assert rho < -0.5 and p < 0.01
    assert st.spearman_permutation_test(x, x, n_perm=2000)[1] > 0.99            # wrong direction: not significant
    ps = [st.spearman_permutation_test(rng.standard_normal(34), rng.standard_normal(34), n_perm=300, seed=i)[1] for i in range(200)]
    assert 0.02 < np.mean(np.array(ps) < 0.05) < 0.10 and 0.4 < np.mean(ps) < 0.6     # about uniform without a relation
    assert st.spearman_permutation_test(x, x[::-1], seed=3) == st.spearman_permutation_test(x, x[::-1], seed=3)


def test_keypad_matches_the_figure_of_the_paper():
    by_char = dict(zip(wd.TARGET_CHARS, zip(kp.ROW, kp.COL, wd.TARGET_FREQS)))
    assert by_char["1"] == (0, 0, 9.25) and by_char["4"] == (0, 3, 9.75) and by_char["7"] == (1, 2, 10.25)
    assert by_char["0"] == (2, 1, 10.75) and by_char["#"] == (2, 3, 14.75)
    # side by side or one above the other is never 0.5 Hz apart (design of the paper)
    assert not (kp.frequency_neighbours() & kp.keypad_neighbours(diagonal=False)).any()
    assert kp.frequency_neighbours().sum() == 22 and kp.keypad_neighbours(diagonal=False).sum() == 34


def test_error_classes_cover_every_wrong_pair_once():
    cls = kp.error_class()
    assert (np.diag(cls) == -1).all() and (cls[~np.eye(12, dtype=bool)] >= 0).all() and np.array_equal(cls, cls.T)
    counts = [(cls == k).sum() for k in range(4)]
    assert counts == [12, 10, 46, 64] and sum(counts) == 132
    assert np.allclose(kp.expected_shares(), np.array(counts) / 132) and np.isclose(kp.expected_shares().sum(), 1)
