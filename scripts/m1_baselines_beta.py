"""M1: standard decoders on BETA, the reference dataset (all 70 people; gate G5 of the M1 plan).

Methods: CCA (6-80 Hz, as in the BETA paper), FBCCA, TRCA and ensemble TRCA with the reference filter bank and
the a-priori weights (a = 1.25, b = 0.25, 5 sub-bands; these are also the settings of the BETA paper). TRCA:
leave-one-block-out over the 4 blocks. Windows 0.2 to 2.0 s, starting 0.13 s after stimulus onset.

Filtering: A = cut the window, then filter (reference convention; the gate). C- = filter the whole trial, then
cut (uses samples after the window). The amplifier removed the mains, so no mains removal is applied.

Usage: python scripts/m1_baselines_beta.py --raw /path/to/beta [--jobs 2]
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import beta as bd  # noqa: E402
from ssvep import decoders as dc  # noqa: E402
from ssvep import filterbank as fb  # noqa: E402

FS, F = bd.FS, bd.TARGET_FREQS
WINDOWS = tuple(round(0.2 * k, 1) for k in range(1, 11))
VARIANTS = ("A", "C-")
N_BANDS, N_HARM = 5, 5
W = dc.fb_weights(N_BANDS, 1.25, 0.25)
FILTERS = [fb.design(n, FS) for n in range(N_BANDS)]
CCA_FILTER = [fb.design_band(6.0, 80.0, 4.0, 90.0, FS)]
LABELS = np.arange(bd.N_TARGETS)
BASES = {}


def bases(n):
    if n not in BASES:
        BASES[n] = dc.reference_bases(F, n, FS, N_HARM)
    return BASES[n]


def evaluate_subject(job):
    sid, raw = job
    x = bd.load_subject(raw, sid)                                  # [block, target, channel, sample]
    rest = x.shape[-1] - bd.RESP_START
    rows = []
    for variant in VARIANTS:
        whole = variant.startswith("C")
        if whole:                                                  # filter once, cut later
            full = fb.subbands(x, N_BANDS, rest, variant, bd.RESP_START, FS, FILTERS)
            full_cca = fb.subbands(x, 1, rest, variant, bd.RESP_START, FS, CCA_FILTER)
        for window in WINDOWS:
            n = int(round(window * FS))
            sub = full[..., :n] if whole else fb.subbands(x, N_BANDS, n, variant, bd.RESP_START, FS, FILTERS)
            one = full_cca[..., :n] if whole else fb.subbands(x, 1, n, variant, bd.RESP_START, FS, CCA_FILTER)
            r_trca, r_ens = dc.trca_leave_one_block_out(sub)       # (band, block, true target, candidate)
            scores = {
                "cca": dc.cca_corr(one[0], bases(n)),
                "fbcca": dc.fbcca_scores(dc.cca_corr(sub, bases(n)), W),
                "trca": dc.fb_combine_signed(r_trca, W),
                "etrca": dc.fb_combine_signed(r_ens, W),
            }
            for method, s in scores.items():
                rows.append((sid, variant, method, window, (s.argmax(axis=-1) == LABELS).mean()))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(bd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m1"))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    jobs = [(sid, raw) for sid in bd.SUBJECTS]
    if args.jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.jobs) as pool:
            results = pool.map(evaluate_subject, jobs, chunksize=1)
    else:
        results = [evaluate_subject(j) for j in jobs]
    acc = pd.DataFrame([r for res in results for r in res], columns=["subject", "variant", "method", "window_s", "accuracy"])
    acc.to_csv(out / "beta_accuracy.csv", index=False, float_format="%.6f")
    print(f"BETA: {acc.subject.nunique()} people, {len(acc)} accuracies, done in {time.time() - t0:.0f} s")
    show = acc[acc.window_s.isin([0.2, 0.6, 1.0, 1.4, 2.0])].groupby(["variant", "method", "window_s"]).accuracy.mean()
    print(show.unstack("window_s").round(3).to_string())


if __name__ == "__main__":
    main()
