"""M1: standard decoders on the wearable dataset. DEVELOPMENT SUBJECTS ONLY (lockbox subjects are not loaded).

Methods: CCA, FBCCA (a-priori and published weights), TRCA and ensemble TRCA with filter bank (a-priori and
published weights; leave-one-block-out). Windows 0.2 to 2.0 s. Filtering variants A, B, C (ssvep.filterbank).
Nothing is tuned here: every setting comes from docs/milestones/M1_plan.md.

Usage: python scripts/m1_baselines_wearable.py --raw /path/to/13560281 [--jobs 2]
"""
import argparse
import os
import pathlib
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.io import loadmat  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import filterbank as fb  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F = wd.FS, wd.TARGET_FREQS
WINDOWS = tuple(round(0.2 * k, 1) for k in range(1, 11))
N_BANDS, N_HARM = 5, 5
W_APRIORI = dc.fb_weights(5, 1.25, 0.25)
# weights published for this dataset (Zhu et al. 2021, grid search on the same recordings): (a, b, N)
PAPER_FBCCA = {"dry": (2.0, 0.25, 5), "wet": (1.25, 0.0, 5)}
PAPER_TRCA = {"dry": (1.25, 0.25, 3), "wet": (1.75, 0.5, 3)}
LABELS = np.arange(wd.N_TARGETS)
FILTERS = [fb.design(n, FS) for n in range(N_BANDS)]
BASES = {}


def bases(n, n_harm=N_HARM):
    if (n, n_harm) not in BASES:
        BASES[(n, n_harm)] = dc.reference_bases(F, n, FS, n_harm)
    return BASES[(n, n_harm)]


def evaluate_subject(job):
    sid, raw = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)                                  # [electrode, block, target, channel, sample]
    whole = fb.subbands(x, N_BANDS, wd.N_SAMPLES - wd.RESP_START, "C", wd.RESP_START, FS, FILTERS)
    acc, by_block, harm, conf = [], [], [], []
    for variant in fb.VARIANTS:
        for window in WINDOWS:
            n = int(round(window * FS))
            sub = (whole[..., :n] if variant == "C"
                   else fb.subbands(x, N_BANDS, n, variant, wd.RESP_START, FS, FILTERS))   # (band, e, block, target, ch, n)
            rho = dc.cca_corr(sub, bases(n))                       # (band, e, block, target, class)
            for e, name in enumerate(wd.ELECTRODE_NAMES):
                r_trca, r_ens = dc.trca_leave_one_block_out(sub[:, e])
                a, b, nb = PAPER_FBCCA[name]
                at, bt, nt = PAPER_TRCA[name]
                scores = {
                    "cca": rho[0, e],
                    "fbcca_apriori": dc.fbcca_scores(rho[:, e], W_APRIORI),
                    "fbcca_paper": dc.fbcca_scores(rho[:, e], dc.fb_weights(nb, a, b)),
                    "trca_apriori": dc.fb_combine_signed(r_trca, W_APRIORI),
                    "etrca_apriori": dc.fb_combine_signed(r_ens, W_APRIORI),
                    "trca_paper": dc.fb_combine_signed(r_trca, dc.fb_weights(nt, at, bt)),
                    "etrca_paper": dc.fb_combine_signed(r_ens, dc.fb_weights(nt, at, bt)),
                }
                for method, s in scores.items():
                    pred = s.argmax(axis=-1)                       # (block, target)
                    correct = pred == LABELS
                    acc.append((sid, name, variant, method, window, correct.mean()))
                    if variant == "B" and window in (1.0, 2.0) and method in ("fbcca_apriori", "etrca_apriori"):
                        by_block += [(sid, name, method, window, blk + 1, correct[blk].mean())
                                     for blk in range(wd.N_BLOCKS)]
                        if window == 1.0:
                            conf.append((name, method, np.bincount(
                                (LABELS[None] * 12 + pred).ravel(), minlength=144).reshape(12, 12)))
                if variant == "A" and window == 1.0:               # paper's Figure 6a: plain CCA, 1 to 6 harmonics
                    for h in range(1, 7):
                        r = dc.cca_corr(sub[0, e], bases(n, h))
                        harm.append((sid, name, h, (r.argmax(axis=-1) == LABELS).mean()))
    return acc, by_block, harm, conf


def compute_time(n_rep=200):
    """Time of one decision at 1 s, variant B, on one core of this machine (milliseconds)."""
    rng = np.random.default_rng(0)
    n = 250
    trial = rng.standard_normal((wd.N_CHANNELS, wd.N_SAMPLES))
    templates = rng.standard_normal((N_BANDS, 12, wd.N_CHANNELS, n))
    w = rng.standard_normal((N_BANDS, 12, wd.N_CHANNELS))
    rows = []

    def clock(fn):
        t0 = time.perf_counter()
        for _ in range(n_rep):
            fn()
        return 1000 * (time.perf_counter() - t0) / n_rep

    sub = fb.subbands(trial, N_BANDS, n, "B", wd.RESP_START, FS, FILTERS)
    rows.append(("preprocessing, variant B (mains removal + 5 sub-bands)",
                 clock(lambda: fb.subbands(trial, N_BANDS, n, "B", wd.RESP_START, FS, FILTERS))))
    rows.append(("preprocessing, variant A (5 sub-bands)",
                 clock(lambda: fb.subbands(trial, N_BANDS, n, "A", wd.RESP_START, FS, FILTERS))))
    rows.append(("CCA, 12 classes, one sub-band", clock(lambda: dc.cca_corr(sub[0], bases(n)))))
    rows.append(("FBCCA, 12 classes, 5 sub-bands", clock(lambda: dc.fbcca_scores(dc.cca_corr(sub, bases(n)), W_APRIORI))))
    rows.append(("ensemble TRCA scoring, 12 classes, 5 sub-bands",
                 clock(lambda: [dc.trca_corr(sub[b][None], templates[b], w[b]) for b in range(N_BANDS)])))
    return pd.DataFrame(rows, columns=["step", "milliseconds_per_decision"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m1"))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cells = loadmat(raw / "Subjects_Information.mat")["Subjects_Information"]
    first = {i: str(cells[i, 10][0]) for i in range(1, 103)}

    jobs = [(sid, raw) for sid in wd.DEVELOPMENT]
    if args.jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.jobs) as pool:
            results = pool.map(evaluate_subject, jobs, chunksize=1)
    else:
        results = [evaluate_subject(j) for j in jobs]

    acc = pd.DataFrame([r for res in results for r in res[0]],
                       columns=["subject", "electrode", "variant", "method", "window_s", "accuracy"])
    acc.insert(1, "first_headband", acc.subject.map(first))
    acc.to_csv(out / "wearable_accuracy.csv", index=False, float_format="%.6f")
    blk = pd.DataFrame([r for res in results for r in res[1]],
                       columns=["subject", "electrode", "method", "window_s", "block", "accuracy"])
    blk.insert(1, "first_headband", blk.subject.map(first))
    blk.to_csv(out / "wearable_accuracy_by_block.csv", index=False, float_format="%.6f")
    pd.DataFrame([r for res in results for r in res[2]],
                 columns=["subject", "electrode", "n_harmonics", "accuracy"]
                 ).to_csv(out / "wearable_cca_harmonics.csv", index=False, float_format="%.6f")
    total = {}
    for res in results:
        for name, method, m in res[3]:
            total[(name, method)] = total.get((name, method), 0) + m
    pd.DataFrame([{"electrode": name, "method": method, "true_target": i + 1, "predicted_target": j + 1,
                   "count": int(m[i, j])} for (name, method), m in sorted(total.items())
                  for i in range(12) for j in range(12)]).to_csv(out / "wearable_confusion_1s.csv", index=False)
    compute_time().to_csv(out / "compute_time.csv", index=False, float_format="%.3f")

    print(f"development subjects: {acc.subject.nunique()} (lockbox subjects not loaded); "
          f"{len(acc)} accuracies; done in {time.time() - t0:.0f} s")
    show = acc[acc.window_s.isin([0.2, 1.0, 2.0])].groupby(["variant", "method", "electrode", "window_s"]).accuracy.mean()
    print(show.unstack(["electrode", "window_s"]).round(3).to_string())


if __name__ == "__main__":
    main()
