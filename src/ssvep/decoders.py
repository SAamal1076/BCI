"""Standard SSVEP decoders: CCA, filter-bank CCA, TRCA and ensemble TRCA.

Array conventions: a trial is (channels, samples); sub-band data carry a leading band axis.
Nothing here knows about subjects or files; evaluation loops live in the scripts.
"""
from __future__ import annotations

import numpy as np


# ----------------------------------------------------------------------------- sub-band weights
def fb_weights(n_bands: int, a: float = 1.25, b: float = 0.25) -> np.ndarray:
    """w(n) = n^(-a) + b, n = 1..n_bands (Chen et al. 2015)."""
    return np.arange(1, n_bands + 1, dtype=float) ** (-a) + b


# ----------------------------------------------------------------------------- CCA
def reference_bases(freqs, n_samples: int, fs: float, n_harm: int) -> np.ndarray:
    """Orthonormal bases of the centred sine-cosine references, (n_classes, n_samples, 2 * n_harm)."""
    t = np.arange(1, n_samples + 1) / fs
    out = []
    for f in np.atleast_1d(freqs):
        y = np.column_stack([fn(2 * np.pi * h * f * t) for h in range(1, n_harm + 1) for fn in (np.sin, np.cos)])
        q, _ = np.linalg.qr(y - y.mean(axis=0))
        out.append(q)
    return np.array(out)


def cca_corr(x, bases) -> np.ndarray:
    """Largest canonical correlation between each trial and each class reference.

    x: (..., channels, samples). bases: (n_classes, samples, p) from reference_bases.
    Returns (..., n_classes). Computed as the largest singular value of Qx' Qy.
    """
    x = x - x.mean(axis=-1, keepdims=True)
    qx = np.linalg.qr(np.swapaxes(x, -1, -2))[0]                       # (..., samples, channels)
    k, n, p = bases.shape
    m = np.swapaxes(qx, -1, -2) @ bases.transpose(1, 0, 2).reshape(n, k * p)   # (..., channels, k * p)
    m = m.reshape(m.shape[:-1] + (k, p))                               # (..., channels, k, p)
    m = np.moveaxis(m, -2, -3)                                         # (..., k, channels, p)
    return np.linalg.svd(m, compute_uv=False)[..., 0]


def fbcca_scores(rho, weights) -> np.ndarray:
    """rho: (n_bands, ..., n_classes) canonical correlations per sub-band. Returns sum_n w(n) * rho_n^2."""
    w = np.asarray(weights, dtype=float)
    return np.tensordot(w, rho[: len(w)] ** 2, axes=(0, 0))


# ----------------------------------------------------------------------------- TRCA
def trca_filters(sum_x, sum_xx) -> np.ndarray:
    """Task-related component analysis, for any leading batch shape.

    sum_x:  (..., channels, samples)  sum over the training trials of one class (each trial centred in time)
    sum_xx: (..., channels, channels) sum over the same trials of X X'
    Returns the leading filter w (..., channels), unit norm, maximising (w' S w) / (w' Q w) with
    S = sum_{i != j} X_i X_j' = (sum X)(sum X)' - sum X X'   and   Q = sum X X'.
    """
    s = sum_x @ np.swapaxes(sum_x, -1, -2) - sum_xx
    chol = np.linalg.cholesky(sum_xx)
    m = np.linalg.solve(chol, s)
    m = np.linalg.solve(chol, np.swapaxes(m, -1, -2))                  # L^-1 S L^-T (S is symmetric)
    _, vec = np.linalg.eigh((m + np.swapaxes(m, -1, -2)) / 2)
    w = np.linalg.solve(np.swapaxes(chol, -1, -2), vec[..., -1:])[..., 0]
    return w / np.linalg.norm(w, axis=-1, keepdims=True)


def _corr(a, b):
    """Pearson correlation along the last axis (broadcasting)."""
    a = a - a.mean(axis=-1, keepdims=True)
    b = b - b.mean(axis=-1, keepdims=True)
    return (a * b).sum(axis=-1) / np.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1))


def trca_corr(test, templates, w):
    """Correlations of test trials with class templates, for one sub-band.

    test: (n_test, channels, samples). templates: (n_classes, channels, samples). w: (n_classes, channels).
    Returns (r_trca, r_ensemble), each (n_test, n_classes):
      r_trca[t, k]     = corr(w_k' X_t, w_k' T_k)
      r_ensemble[t, k] = correlation of W' X_t with W' T_k taken as one long vector (W = all class filters).
    """
    proj_test = np.einsum("jc,tcs->tjs", w, test)                      # (n_test, filters, samples)
    proj_tmpl = np.einsum("jc,kcs->kjs", w, templates)                 # (n_classes, filters, samples)
    k = np.arange(len(templates))
    r_trca = _corr(proj_test[:, k, :], proj_tmpl[k, k, :][None])
    n_test, n_filt, n_smp = proj_test.shape
    r_ens = _corr(proj_test.reshape(n_test, 1, n_filt * n_smp), proj_tmpl.reshape(1, len(templates), n_filt * n_smp))
    return r_trca, r_ens


def fb_combine_signed(r, weights) -> np.ndarray:
    """r: (n_bands, ..., n_classes) correlations per sub-band. Returns sum_n w(n) * sign(r_n) * r_n^2.

    For non-negative correlations this is the published rule (sum of w(n) r^2). The sign is kept so that a
    response in anti-phase with the template does not count in favour of a class.
    """
    w = np.asarray(weights, dtype=float)
    r = r[: len(w)]
    return np.tensordot(w, np.sign(r) * r ** 2, axes=(0, 0))


def trca_leave_one_block_out(fb):
    """Leave-one-block-out TRCA correlations.

    fb: (n_bands, n_blocks, n_classes, channels, samples), one trial per block and class.
    Returns (r_trca, r_ensemble), each (n_bands, n_blocks, n_classes [true], n_classes [candidate]).
    For each held-out block, filters and templates come from the other blocks only.
    """
    fb = fb - fb.mean(axis=-1, keepdims=True)
    n_bands, n_blocks, n_classes = fb.shape[:3]
    sum_x = fb.sum(axis=1)                                             # (bands, classes, ch, smp)
    xx = fb @ np.swapaxes(fb, -1, -2)                                  # (bands, blocks, classes, ch, ch)
    sum_xx = xx.sum(axis=1)
    r_trca = np.empty((n_bands, n_blocks, n_classes, n_classes))
    r_ens = np.empty_like(r_trca)
    for b in range(n_blocks):
        train_x = sum_x - fb[:, b]
        w = trca_filters(train_x, sum_xx - xx[:, b])                   # (bands, classes, ch)
        templates = train_x / (n_blocks - 1)
        for n in range(n_bands):
            r_trca[n, b], r_ens[n, b] = trca_corr(fb[n, b], templates[n], w[n])
    return r_trca, r_ens
