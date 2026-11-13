"""M1 cross-check: the vectorised decoders against slow, literal implementations on one development subject.

The literal versions follow the textbook formula (CCA) and the published reference code line by line
(trca.m, train_model.m, test_model.m of Nakanishi et al. 2018): explicit loops, generalised eigenvectors from
scipy.linalg.eig(Q^-1 S), correlations from numpy.corrcoef. They share no code with ssvep.decoders.

Usage: python scripts/m1_crosscheck.py --raw /path/to/13560281
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import linalg

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import filterbank as fb  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F = wd.FS, wd.TARGET_FREQS
SUBJECT = 1                                   # a development subject
W = dc.fb_weights(5)


def literal_cca(x, f, n_harm=5):
    t = np.arange(1, x.shape[1] + 1) / FS
    y = np.column_stack([fn(2 * np.pi * h * f * t) for h in range(1, n_harm + 1) for fn in (np.sin, np.cos)])
    a, b = x.T - x.T.mean(0), y - y.mean(0)
    m = np.linalg.solve(a.T @ a, a.T @ b) @ np.linalg.solve(b.T @ b, b.T @ a)
    return np.sqrt(np.linalg.eigvals(m).real.max())


def literal_trca(eeg):
    """trca.m. eeg: (trials, channels, samples). Returns the filter with the largest eigenvalue."""
    n_trials, n_ch, _ = eeg.shape
    s = np.zeros((n_ch, n_ch))
    for i in range(n_trials - 1):
        x1 = eeg[i] - eeg[i].mean(axis=1, keepdims=True)
        for j in range(i + 1, n_trials):
            x2 = eeg[j] - eeg[j].mean(axis=1, keepdims=True)
            s += x1 @ x2.T + x2 @ x1.T
    ux = np.concatenate(list(eeg), axis=1)
    ux = ux - ux.mean(axis=1, keepdims=True)
    val, vec = linalg.eig(np.linalg.solve(ux @ ux.T, s))
    return vec[:, np.argmax(val.real)].real


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    args = ap.parse_args()
    x = wd.load_subject(args.raw, SUBJECT)
    rows = []
    for variant, window in (("B", 1.0), ("C", 0.4)):
        n = int(round(window * FS))
        sub = fb.subbands(x, 5, n, variant, wd.RESP_START)                 # (band, e, block, target, ch, n)
        for e, name in enumerate(wd.ELECTRODE_NAMES):
            # ---- CCA and FBCCA
            rho = dc.cca_corr(sub[:, e], dc.reference_bases(F, n, FS, 5))  # (band, block, target, class)
            lit = np.array([[[[literal_cca(sub[b, e, blk, t], f) for f in F] for t in range(12)]
                             for blk in range(10)] for b in range(5)])
            fast_pred = dc.fbcca_scores(rho, W).argmax(-1)
            lit_pred = sum(W[b] * lit[b] ** 2 for b in range(5)).argmax(-1)
            rows.append({"variant": variant, "window_s": window, "electrode": name, "method": "FBCCA",
                         "max_abs_difference_of_correlations": np.abs(rho - lit).max(),
                         "trials_with_same_decision": int((fast_pred == lit_pred).sum()), "trials": fast_pred.size,
                         "accuracy_fast": (fast_pred == np.arange(12)).mean(),
                         "accuracy_literal": (lit_pred == np.arange(12)).mean()})
            # ---- ensemble TRCA, leave-one-block-out, as train_model.m / test_model.m
            _, r_ens = dc.trca_leave_one_block_out(sub[:, e])
            fast_pred = dc.fb_combine_signed(r_ens, W).argmax(-1)
            lit_r = np.zeros((5, 10, 12, 12))
            for blk in range(10):
                train = np.delete(sub[:, e], blk, axis=1)                  # (band, 9 blocks, target, ch, n)
                for b in range(5):
                    templates = train[b].mean(axis=0)                      # (target, ch, n)
                    w = np.array([literal_trca(train[b][:, k]) for k in range(12)])     # (target, ch)
                    for t in range(12):
                        test = sub[b, e, blk, t]
                        for k in range(12):
                            lit_r[b, blk, t, k] = np.corrcoef((w @ test).ravel(), (w @ templates[k]).ravel())[0, 1]
            lit_pred = sum(W[b] * np.sign(lit_r[b]) * lit_r[b] ** 2 for b in range(5)).argmax(-1)
            rows.append({"variant": variant, "window_s": window, "electrode": name, "method": "ensemble TRCA",
                         "max_abs_difference_of_correlations": np.abs(r_ens - lit_r).max(),
                         "trials_with_same_decision": int((fast_pred == lit_pred).sum()), "trials": fast_pred.size,
                         "accuracy_fast": (fast_pred == np.arange(12)).mean(),
                         "accuracy_literal": (lit_pred == np.arange(12)).mean()})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results" / "m1" / "crosscheck.csv", index=False, float_format="%.3g")
    pd.set_option("display.width", 200)
    print(f"subject S{SUBJECT:03d}: vectorised decoders against literal implementations")
    print(df.to_string(index=False))
    assert (df.trials_with_same_decision == df.trials).all(), "decisions differ"
    print("all decisions identical")


if __name__ == "__main__":
    main()
