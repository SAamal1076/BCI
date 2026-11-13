"""M2: the M1 baselines re-run once with the pipeline chosen in step 0. DEVELOPMENT SUBJECTS ONLY.

CCA (sub-band 1), FBCCA, TRCA and ensemble TRCA (leave-one-block-out), a-priori weights, windows 0.2 to 2.0 s.

Usage: python scripts/m2_baselines.py --raw /path/to/13560281 [--jobs 2]
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
from ssvep import pipeline as pp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F = wd.FS, wd.TARGET_FREQS
WINDOWS = tuple(round(0.2 * k, 1) for k in range(1, 11))
LABELS = np.arange(wd.N_TARGETS)


def chosen_pipeline(out):
    t = pd.read_csv(pathlib.Path(out) / "pipeline_choice.csv")
    return str(t.loc[t.chosen, "pipeline"].iloc[0])


def first_headband(raw):
    cells = loadmat(pathlib.Path(raw) / "Subjects_Information.mat")["Subjects_Information"]
    return {i: str(cells[i, 10][0]) for i in range(1, 103)}


def evaluate_subject(job):
    sid, raw, name = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)
    w = pp.weights(name)
    acc, conf = [], []
    for window in WINDOWS:
        n = int(round(window * FS))
        sub = pp.subbands(x, n, name, wd.RESP_START, FS)            # (band, e, block, target, ch, n)
        rho = dc.cca_corr(sub, dc.reference_bases(F, n, FS, pp.N_HARM[name]))
        for e, el in enumerate(wd.ELECTRODE_NAMES):
            r_trca, r_ens = dc.trca_leave_one_block_out(sub[:, e])
            scores = {"cca": rho[0, e], "fbcca": dc.fbcca_scores(rho[:, e], w),
                      "trca": dc.fb_combine_signed(r_trca, w), "etrca": dc.fb_combine_signed(r_ens, w)}
            for method, s in scores.items():
                pred = s.argmax(axis=-1)
                acc.append((sid, el, method, window, (pred == LABELS).mean()))
                if window == 1.0 and method in ("fbcca", "etrca"):
                    conf.append((el, method, np.bincount((LABELS[None] * 12 + pred).ravel(), minlength=144).reshape(12, 12)))
    return acc, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m2"))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    name, first, t0 = chosen_pipeline(out), first_headband(raw), time.time()
    jobs = [(sid, raw, name) for sid in wd.DEVELOPMENT]
    import multiprocessing as mp
    with mp.get_context("fork").Pool(args.jobs) as pool:
        results = pool.map(evaluate_subject, jobs, chunksize=1)
    acc = pd.DataFrame([r for res in results for r in res[0]], columns=["subject", "electrode", "method", "window_s", "accuracy"])
    acc.insert(1, "first_headband", acc.subject.map(first))
    acc.to_csv(out / "baseline_accuracy.csv", index=False, float_format="%.6f")
    total = {}
    for res in results:
        for el, method, m in res[1]:
            total[(el, method)] = total.get((el, method), 0) + m
    pd.DataFrame([{"electrode": el, "method": method, "true_target": i + 1, "predicted_target": j + 1, "count": int(m[i, j])}
                  for (el, method), m in sorted(total.items()) for i in range(12) for j in range(12)]
                 ).to_csv(out / "baseline_confusion_1s.csv", index=False)
    print(f"pipeline {name}; development subjects: {acc.subject.nunique()}; done in {time.time() - t0:.0f} s")
    show = acc[acc.window_s.isin([0.2, 0.6, 1.0, 1.4, 2.0])].groupby(["method", "electrode", "window_s"]).accuracy.mean()
    print(show.unstack("window_s").round(3).to_string())


if __name__ == "__main__":
    main()
