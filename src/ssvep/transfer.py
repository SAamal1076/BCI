"""Decoding a new user with a template: population template, the user's own template, or a mix of the two.

Decision as in extended CCA (Nakanishi et al. 2014; Chen et al. 2015), with three correlations per sub-band:
  r1 = canonical correlation of the trial X with the sine-cosine reference Y_f
  r2 = corr(X w, T_f w), w = spatial filter of CCA(X, Y_f)
  r3 = corr(X v, T_f v), v = spatial filter of CCA(T_f, Y_f)
  score_f = sum over sub-bands n of w(n) * sum_i sign(r_i) * r_i^2
It needs a template T_f but no trial of the user, so it works with zero calibration blocks.
"""
from __future__ import annotations

import numpy as np


def combined_template(population, own, k: int, n0: float):
    """T = (n0 * P + k * I) / (n0 + k): the population counts as n0 blocks of the user's own data.
    k = 0 gives the population template; own may then be None."""
    if k == 0:
        return population
    return (n0 * population + k * own) / (n0 + k)


def cca_filters(x, bases):
    """Largest canonical correlation and its spatial filter, for every class.

    x: (..., channels, samples). bases: (n_classes, samples, p) from decoders.reference_bases.
    Returns rho (..., n_classes) and w (..., n_classes, channels) with corr(w' x, best reference) = rho.
    """
    x = x - x.mean(axis=-1, keepdims=True)
    q, r = np.linalg.qr(np.swapaxes(x, -1, -2))                         # (..., samples, ch), (..., ch, ch)
    k, n, p = bases.shape
    m = np.swapaxes(q, -1, -2) @ bases.transpose(1, 0, 2).reshape(n, k * p)
    m = np.moveaxis(m.reshape(m.shape[:-1] + (k, p)), -2, -3)           # (..., classes, ch, p)
    u, s, _ = np.linalg.svd(m, full_matrices=False)
    w = np.linalg.solve(r[..., None, :, :], u[..., :, :1])[..., 0]      # (..., classes, ch)
    return s[..., 0], w


def _corr(a, b):
    a = a - a.mean(axis=-1, keepdims=True)
    b = b - b.mean(axis=-1, keepdims=True)
    return (a * b).sum(axis=-1) / np.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1))


def trial_part(x, bases):
    """Everything that depends on the test trials only. x: (bands, trials, channels, samples).
    Returns r1 (bands, trials, classes), w (bands, trials, classes, channels) and the centred trials."""
    xc = x - x.mean(axis=-1, keepdims=True)
    r1, w = cca_filters(xc, bases)
    return r1, w, xc


def ecca_features(part, template, bases):
    """r1, r2, r3 for test trials against a template (bands, classes, channels, samples).
    part comes from trial_part. Each feature is (bands, trials, classes)."""
    r1, w, xc = part
    tc = template - template.mean(axis=-1, keepdims=True)
    r2 = _corr(np.einsum("btkc,btcn->btkn", w, xc), np.einsum("btkc,bkcn->btkn", w, tc))
    v = cca_filters(tc, bases)[1]                                       # (bands, classes [template], classes, ch)
    v = np.einsum("bkkc->bkc", v)                                       # filter of CCA(T_f, Y_f) for each f
    r3 = _corr(np.einsum("bkc,btcn->btkn", v, xc), np.einsum("bkc,bkcn->bkn", v, tc)[:, None])
    return r1, r2, r3


def ecca_scores(part, template, bases, weights):
    """Scores (trials, classes) of the template decoder."""
    feats = ecca_features(part, template, bases)
    total = sum(np.sign(r) * r ** 2 for r in feats)                     # (bands, trials, classes)
    return np.tensordot(np.asarray(weights, dtype=float), total[: len(weights)], axes=(0, 0))


TEST_BLOCKS = (6, 7, 8, 9)                                              # blocks 7 to 10, the same for every k


def split_blocks(k: int):
    """Calibration blocks (the first k) and test blocks (7 to 10), as 0-based indices. They never overlap."""
    if not 0 <= k <= TEST_BLOCKS[0]:
        raise ValueError("k must be between 0 and 6")
    return tuple(range(k)), TEST_BLOCKS


def leave_one_out_mean(total, own, n_people: int):
    """Population mean without the test person: (sum over all people - the person's own part) / (n - 1)."""
    return (total - own) / (n_people - 1)
