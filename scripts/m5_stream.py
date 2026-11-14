"""M5, step 3: the recordings replayed as a stream. Is every update the same as the fixed-window code, and how
long does an update take?

The first block of every development person and headband (1 632 trials) is replayed in pieces of 0.1 s through
stream.StreamDecoder, with the template of the fold in which the person is a test person. Each of the 18
updates of a trial is compared with the scores m5_scores.py computed from whole trials, and its time on the
processor is measured (preprocessing and decision separately).

The times are measurements on the machine that runs this script; they differ from run to run.

Usage: python scripts/m5_stream.py [--raw DIR] [--cache DIR] [--jobs 2]
"""
import argparse
import os
import pathlib
import platform
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m5_scores as ms  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

OUT = ROOT / "results" / "m5"
PIECE = sm.n_samples(sm.PIECE_S)                                       # 25 samples
BLOCK = 0                                                              # the first block


def replay_person(job):
    sid, raw, cache = job
    assert not wd.is_lockbox(sid)
    fold = ms.folds_of(sid)[1]
    x = wd.load_subject(raw, sid)
    rows, seconds = [], []
    for e, el in enumerate(wd.ELECTRODE_NAMES):
        decoder = sm.StreamDecoder({n: ms.template(cache, fold, n)[:, e] for n in ms.N})
        ref_f, ref_t = ms.scores(cache, sid, "fbcca")[e], ms.scores(cache, sid, "template", fold)[e]   # (length, 120, classes)
        for target in range(wd.N_TARGETS):                             # trial index in the block-by-block order: BLOCK * 12 + target
            decoder.reset()
            updates = [u for piece in sm.pieces(x[e, BLOCK, target], PIECE) for u in decoder.push(piece)]
            assert [u[0] for u in updates] == list(sm.TIMES)
            trial = BLOCK * wd.N_TARGETS + target
            for j, (_, fbcca, tmpl) in enumerate(updates):
                rows.append((sid, el, target + 1, sm.TIMES[j], float(np.abs(fbcca - ref_f[j, trial]).max()), float(np.abs(tmpl - ref_t[j, trial]).max()),
                             int(fbcca.argmax() == ref_f[j, trial].argmax()), int(tmpl.argmax() == ref_t[j, trial].argmax())))
            seconds.append(decoder.seconds)
    return rows, np.array(seconds)                                     # seconds: (trials, 18, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(ms.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    cache = ms.prepare(args.raw, args.cache, args.jobs)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    import multiprocessing as mp
    with mp.get_context("fork").Pool(args.jobs) as pool:
        results = pool.map(replay_person, [(sid, pathlib.Path(args.raw), cache) for sid in ms.PEOPLE], chunksize=1)
    check = pd.DataFrame([r for res in results for r in res[0]],
                         columns=["subject", "electrode", "target", "time_s", "diff_fbcca", "diff_template", "same_fbcca", "same_template"])
    seconds = np.concatenate([res[1] for res in results])              # (trials, 18, 2)
    n_trials = len(seconds)
    print(f"== M5 stream: {n_trials} trials of {check.subject.nunique()} development people replayed in pieces of {sm.PIECE_S} s "
          f"({PIECE} samples); {len(check)} updates; {time.time() - t0:.0f} s")
    print("\n== 1. the stream against the fixed-window code (scores of whole trials)")
    summary = check.groupby("electrode").agg(updates=("time_s", "size"), largest_difference_fbcca=("diff_fbcca", "max"),
                                             largest_difference_template=("diff_template", "max"),
                                             same_decision_fbcca=("same_fbcca", "sum"), same_decision_template=("same_template", "sum"))
    print(summary.to_string())
    same = bool((check.same_fbcca == 1).all() and (check.same_template == 1).all())
    print(f"every decision of the stream equals the decision of the fixed-window code: {same}; largest difference of a score: "
          f"{max(check.diff_fbcca.max(), check.diff_template.max()):.2e}")
    summary.to_csv(OUT / "stream_check.csv", float_format="%.3g")

    print(f"\n== 2. time of one update on one processor core ({platform.processor() or platform.machine()}, Python {platform.python_version()}, "
          f"NumPy {np.__version__}), milliseconds")
    ms_ = seconds * 1000
    total = ms_.sum(axis=-1)
    lat = pd.DataFrame({"time_s": sm.TIMES, "updates": n_trials,
                        "preprocessing_median_ms": np.median(ms_[..., 0], axis=0), "decision_median_ms": np.median(ms_[..., 1], axis=0),
                        "total_median_ms": np.median(total, axis=0), "total_p95_ms": np.percentile(total, 95, axis=0),
                        "total_max_ms": total.max(axis=0)})
    lat["real_time_factor_p95"] = lat.total_p95_ms / (sm.PIECE_S * 1000)
    lat.to_csv(OUT / "latency.csv", index=False, float_format="%.3f")
    print(lat.round(2).to_string(index=False))
    print(f"all updates: median {np.median(total):.1f} ms, 95th percentile {np.percentile(total, 95):.1f} ms, largest {total.max():.1f} ms; "
          f"time between two updates {sm.PIECE_S * 1000:.0f} ms; updates slower than that: {int((total > sm.PIECE_S * 1000).sum())} of {total.size}")
    print(f"a whole trial (18 updates): median {np.median(total.sum(axis=1)):.0f} ms of processor time for 2 s of signal")


if __name__ == "__main__":
    main()
