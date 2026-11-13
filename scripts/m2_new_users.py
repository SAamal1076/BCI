"""M2: decoding a new user with 0 to 6 calibration blocks. DEVELOPMENT SUBJECTS ONLY (leave-one-subject-out).

Design of the M2 plan: calibration = the first k blocks of the person (k = 0, 1, 2, 4, 6), test = blocks 7 to 10
(48 trials), population = the other development people with the same type of headband.

Methods on the same test trials:
  fbcca   no data from anyone
  cross   cross-subject template T = (n0 P + k I) / (n0 + k), extended-CCA decision; k = 0 uses P alone
  own     the same decision with the person's own template only (k >= 1)
  etrca   ensemble TRCA trained on the person's k calibration blocks (k >= 2)

Two passes. Pass 1 stores, for every person, the mean response per target (over the 10 blocks) in a cache
folder. Pass 2 decodes each person with the population template made of the 67 others.

Usage: python scripts/m2_new_users.py --raw /path/to/13560281 [--jobs 2] [--cache /tmp/m2_cache]
"""
import argparse
import os
import pathlib
import sys
import tempfile
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import transfer as tr  # noqa: E402
from ssvep import wearable as wd  # noqa: E402
from m2_baselines import chosen_pipeline, first_headband  # noqa: E402

FS, F = wd.FS, wd.TARGET_FREQS
WINDOWS = tuple(round(0.2 * k, 1) for k in range(1, 11))
K_BLOCKS = (0, 1, 2, 4, 6)
N0_GRID = (0.5, 1.0, 2.0, 4.0, 8.0)
PEOPLE = wd.DEVELOPMENT


def samples(window):
    return int(round(window * FS))


def subbands(x, window, name):
    sub = pp.subbands(x, samples(window), name, wd.RESP_START, FS)      # (band, e, block, target, ch, n)
    return sub - sub.mean(axis=-1, keepdims=True)


def pass1(job):
    sid, raw, name, cache = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)
    np.savez(cache / f"S{sid:03d}.npz", **{f"w{samples(w)}": subbands(x, w, name).mean(axis=2).astype(np.float32)
                                          for w in WINDOWS})
    return sid


def pass2(job):
    sid, raw, name, cache = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)
    own_mean = np.load(cache / f"S{sid:03d}.npz")
    weights = pp.weights(name)
    labels = np.tile(np.arange(wd.N_TARGETS), len(tr.TEST_BLOCKS))
    rows = []
    for window in WINDOWS:
        n = samples(window)
        sub = subbands(x, window, name)
        bases = dc.reference_bases(F, n, FS, pp.N_HARM[name])
        population = tr.leave_one_out_mean(np.load(cache / f"population_w{n}.npy"), own_mean[f"w{n}"].astype(float),
                                           len(PEOPLE))                 # (band, e, target, ch, n), without this person
        for e, el in enumerate(wd.ELECTRODE_NAMES):
            data = sub[:, e]                                            # (band, block, target, ch, n)
            test = data[:, list(tr.TEST_BLOCKS)].reshape(data.shape[0], -1, *data.shape[3:])
            part = tr.trial_part(test, bases)

            def add(method, k, n0, scores):
                rows.append((sid, el, window, method, k, n0, (scores.argmax(axis=-1) == labels).mean()))

            add("fbcca", 0, np.nan, dc.fbcca_scores(part[0], weights))
            add("cross", 0, np.nan, tr.ecca_scores(part, population[:, e], bases, weights))
            for k in K_BLOCKS[1:]:
                cal_blocks, test_blocks = tr.split_blocks(k)
                assert not set(cal_blocks) & set(test_blocks)
                cal = data[:, list(cal_blocks)]                         # (band, k, target, ch, n)
                own = cal.mean(axis=1)
                add("own", k, np.nan, tr.ecca_scores(part, own, bases, weights))
                for n0 in N0_GRID:
                    add("cross", k, n0, tr.ecca_scores(part, tr.combined_template(population[:, e], own, k, n0), bases, weights))
                if k >= 2:
                    sum_x = cal.sum(axis=1)
                    filters = dc.trca_filters(sum_x, (cal @ np.swapaxes(cal, -1, -2)).sum(axis=1))
                    r_ens = np.stack([dc.trca_corr(test[b], sum_x[b] / k, filters[b])[1] for b in range(data.shape[0])])
                    add("etrca", k, np.nan, dc.fb_combine_signed(r_ens, weights))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m2"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--cache", default=str(pathlib.Path(tempfile.gettempdir()) / "m2_cache"))
    args = ap.parse_args()
    raw, out, cache = pathlib.Path(args.raw), pathlib.Path(args.out), pathlib.Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    name, first, t0 = chosen_pipeline(out), first_headband(raw), time.time()
    jobs = [(sid, raw, name, cache) for sid in PEOPLE]
    import multiprocessing as mp
    with mp.get_context("fork").Pool(args.jobs) as pool:
        pool.map(pass1, jobs, chunksize=1)
        for w in WINDOWS:                                               # sum over the development people
            key = f"w{samples(w)}"
            np.save(cache / f"population_{key}.npy", sum(np.load(cache / f"S{sid:03d}.npz")[key].astype(float) for sid in PEOPLE))
        print(f"pass 1 done in {time.time() - t0:.0f} s (mean responses of {len(PEOPLE)} development people)", flush=True)
        results = pool.map(pass2, jobs, chunksize=1)
    d = pd.DataFrame([r for res in results for r in res],
                     columns=["subject", "electrode", "window_s", "method", "k", "n0", "accuracy"])
    d.insert(1, "first_headband", d.subject.map(first))
    d.to_csv(out / "new_user_accuracy.csv", index=False, float_format="%.6f")
    print(f"pipeline {name}; {d.subject.nunique()} development people as new users; {len(d)} accuracies; "
          f"done in {time.time() - t0:.0f} s")
    one = d[d.window_s == 1.0]
    print("mean accuracy at 1 s, test blocks 7-10 (cross: all n0 pooled here; the choice of n0 is made in m2_summary.py):")
    print(one.groupby(["method", "k", "electrode"]).accuracy.mean().unstack("electrode").round(3).to_string())


if __name__ == "__main__":
    main()
