"""Decoders on synthetic signals (run: python -m pytest -q tests). Gate of M1: must pass before the data are used."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import metrics as mt  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F, PHI = wd.FS, wd.TARGET_FREQS, wd.TARGET_PHASES
N = 250                                           # 1 s window
T = np.arange(N) / FS


def synthetic_trials(amplitude, n_blocks=10, n_channels=8, seed=0, n=N):
    """(n_blocks, 12, channels, n): each target = its sinusoid (+ 2nd harmonic) on a fixed spatial pattern,
    plus spatially correlated noise of unit variance."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    pattern = rng.standard_normal(n_channels)
    mix = rng.standard_normal((n_channels, n_channels)) / np.sqrt(n_channels)
    x = np.einsum("ij,bkjs->bkis", mix, rng.standard_normal((n_blocks, 12, n_channels, n)))
    for k in range(12):
        resp = np.sin(2 * np.pi * F[k] * t + PHI[k]) + 0.5 * np.sin(4 * np.pi * F[k] * t + 2 * PHI[k])
        x[:, k] += amplitude * pattern[:, None] * resp
    return x


def cca_accuracy(x, n_harm=5):
    rho = dc.cca_corr(x, dc.reference_bases(F, x.shape[-1], FS, n_harm))       # (blocks, 12, 12)
    return (rho.argmax(axis=-1) == np.arange(12)).mean()


def lobo_accuracy(x, ensemble):
    r_trca, r_ens = dc.trca_leave_one_block_out(x[None])                       # one sub-band
    r = (r_ens if ensemble else r_trca)[0]
    return (r.argmax(axis=-1) == np.arange(12)).mean()


# ----------------------------------------------------------------------------- CCA
def test_cca_equals_the_textbook_formula():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((3, 8, 200))
    bases = dc.reference_bases(F[:4], 200, FS, 3)
    rho = dc.cca_corr(x, bases)
    t = np.arange(1, 201) / FS
    for i in range(3):
        for k in range(4):
            y = np.column_stack([fn(2 * np.pi * h * F[k] * t) for h in (1, 2, 3) for fn in (np.sin, np.cos)])
            a = x[i].T - x[i].T.mean(0)
            b = y - y.mean(0)
            m = np.linalg.solve(a.T @ a, a.T @ b) @ np.linalg.solve(b.T @ b, b.T @ a)
            assert abs(np.sqrt(np.linalg.eigvals(m).real.max()) - rho[i, k]) < 1e-9


def test_cca_finds_a_clean_sinusoid_whatever_its_phase():
    x = np.stack([np.sin(2 * np.pi * F[k] * T + 1.234 * k)[None].repeat(8, 0) * np.arange(1, 9)[:, None]
                  for k in range(12)])
    rho = dc.cca_corr(x + 1e-6 * np.random.default_rng(0).standard_normal(x.shape), dc.reference_bases(F, N, FS, 5))
    assert (rho.argmax(axis=-1) == np.arange(12)).all() and np.allclose(np.diag(rho), 1.0, atol=1e-6)


def test_cca_is_at_chance_on_noise_and_improves_with_amplitude():
    acc = [cca_accuracy(synthetic_trials(a, n_blocks=40, seed=1)) for a in (0.0, 0.01, 0.02, 0.05)]
    assert abs(acc[0] - 1 / 12) < 0.04
    assert acc[0] < acc[1] < acc[2] < acc[3] and acc[3] > 0.97


def test_filter_bank_weights_and_score():
    w = dc.fb_weights(5)
    assert np.allclose(w, [1.25, 2 ** -1.25 + 0.25, 3 ** -1.25 + 0.25, 4 ** -1.25 + 0.25, 5 ** -1.25 + 0.25])
    assert np.allclose(dc.fb_weights(3, a=2.0, b=0.0), [1.0, 0.25, 1 / 9])
    rho = np.random.default_rng(0).uniform(0, 1, (5, 7, 12))
    assert np.allclose(dc.fbcca_scores(rho, w), sum(w[n] * rho[n] ** 2 for n in range(5)))
    assert np.allclose(dc.fbcca_scores(rho, w[:3]), sum(w[n] * rho[n] ** 2 for n in range(3)))


# ----------------------------------------------------------------------------- TRCA
def test_trca_recovers_a_planted_source_better_than_any_single_channel():
    rng = np.random.default_rng(2)
    n_trials, n_ch = 9, 8
    source = np.sin(2 * np.pi * 11.25 * T)
    pattern = rng.standard_normal(n_ch)
    mix = rng.standard_normal((n_ch, n_ch))
    x = 0.3 * pattern[None, :, None] * source + np.einsum("ij,njs->nis", mix, rng.standard_normal((n_trials, n_ch, N)))
    x = x - x.mean(-1, keepdims=True)
    w = dc.trca_filters(x.sum(0), (x @ x.transpose(0, 2, 1)).sum(0))
    mean_trial = x.mean(0)
    r_trca = abs(np.corrcoef(w @ mean_trial, source)[0, 1])
    r_best_channel = max(abs(np.corrcoef(mean_trial[c], source)[0, 1]) for c in range(n_ch))
    assert r_trca > 0.9 and r_trca > r_best_channel + 0.1


def test_trca_filter_solves_the_generalised_eigenproblem():
    rng = np.random.default_rng(3)
    x = rng.standard_normal((6, 8, 100))
    x = x - x.mean(-1, keepdims=True)
    sum_x, q = x.sum(0), (x @ x.transpose(0, 2, 1)).sum(0)
    s = sum_x @ sum_x.T - q
    w = dc.trca_filters(sum_x, q)
    lam = (w @ s @ w) / (w @ q @ w)
    assert np.allclose(s @ w, lam * (q @ w), atol=1e-8)
    assert lam >= np.linalg.eigvals(np.linalg.solve(q, s)).real.max() - 1e-9


def test_ensemble_correlation_equals_correlation_of_the_stacked_signals():
    rng = np.random.default_rng(4)
    test, templates, w = rng.standard_normal((5, 8, 60)), rng.standard_normal((12, 8, 60)), rng.standard_normal((12, 8))
    r_trca, r_ens = dc.trca_corr(test, templates, w)
    for t in range(5):
        for k in range(12):
            assert abs(np.corrcoef((w @ test[t]).ravel(), (w @ templates[k]).ravel())[0, 1] - r_ens[t, k]) < 1e-10
            assert abs(np.corrcoef(w[k] @ test[t], w[k] @ templates[k])[0, 1] - r_trca[t, k]) < 1e-10


def test_trca_and_ensemble_trca_decode_clear_responses():
    x = synthetic_trials(0.6, seed=5)
    assert lobo_accuracy(x, ensemble=False) > 0.95 and lobo_accuracy(x, ensemble=True) > 0.95


def test_held_out_block_never_enters_templates_or_filters():
    # Noise only, plus a strong marker that is unique to every (block, target) trial. A decoder that sees the
    # held-out trial during training recognises its marker; an honest one cannot do better than chance.
    rng = np.random.default_rng(6)
    x = rng.standard_normal((10, 12, 8, N))
    x += 5.0 * rng.standard_normal((10, 12, 8, 1)) * rng.standard_normal((10, 12, 1, N))
    assert lobo_accuracy(x, ensemble=False) < 0.2 and lobo_accuracy(x, ensemble=True) < 0.2
    # positive control: the same decoder trained on all blocks, held-out one included, is far above chance
    xc = x - x.mean(-1, keepdims=True)
    w = dc.trca_filters(xc.sum(0), (xc @ xc.transpose(0, 1, 3, 2)).sum(0))
    r_trca, _ = dc.trca_corr(xc[0], xc.mean(0), w)
    assert (r_trca.argmax(-1) == np.arange(12)).mean() > 0.8


def test_trca_is_at_chance_when_training_labels_are_shuffled():
    rng = np.random.default_rng(7)
    x = synthetic_trials(0.6, seed=7)
    shuffled = np.stack([x[b, rng.permutation(12)] for b in range(10)])
    assert lobo_accuracy(shuffled, ensemble=True) < 0.25


def test_signed_combination_does_not_reward_anti_phase():
    r = np.zeros((2, 1, 3))
    r[:, 0, 0], r[:, 0, 1], r[:, 0, 2] = 0.5, -0.9, 0.2
    assert dc.fb_combine_signed(r, dc.fb_weights(2)).argmax() == 0


# ----------------------------------------------------------------------------- metrics
def test_itr_known_values():
    assert np.isclose(mt.itr_bits_per_min(1.0, 12, 1.0), 60 * np.log2(12))
    assert mt.itr_bits_per_min(1 / 12, 12, 1.0) == 0 and mt.itr_bits_per_min(0.0, 12, 1.0) == 0
    bits = np.log2(12) + 0.5 * np.log2(0.5) + 0.5 * np.log2(0.5 / 11)
    assert np.isclose(mt.itr_bits_per_min(0.5, 12, 2.5), 60 / 2.5 * bits)
    p = np.linspace(0.1, 1.0, 10)
    assert (np.diff(mt.itr_bits_per_min(p, 12, 1.0)) > 0).all()


def test_chance_threshold():
    thr = mt.chance_threshold(120, 12)
    assert 1 / 12 < thr < 0.17
    assert mt.chance_threshold(1200, 12) < thr
