"""M5, step 1: scores of every development person at the 18 lengths of signal (0.3 s to 2.0 s).

Folds of M3: 43 people build the template, 8 validation people set the choices of M5, 17 test people are
decoded. A person's scores are computed with the template of every fold in which the person is a validation
or a test person; the person is never among the people of that template.

Two passes, as in M2 (the trials of 68 people at 18 lengths do not fit in memory at once):
  pass 1   mean response of each person, for each length (cache)
  pass 2   scores of each person's 240 trials: FBCCA, and the template of each fold that needs them (cache)

The scores stay in the cache; m5_stopping.py turns them into the result tables.

Usage: python scripts/m5_scores.py --raw /path/to/13560281 [--jobs 2] [--cache DIR]
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import network as nw  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

PEOPLE = sorted(wd.DEVELOPMENT)
FOLDS = nw.folds(PEOPLE)                                               # (train, validation, test) of each fold
N = [sm.n_samples(t) for t in sm.TIMES]
DEFAULT_CACHE = pathlib.Path(tempfile.gettempdir()) / "m5_cache"
LABELS = np.tile(np.arange(wd.N_TARGETS), 10)                          # the 120 trials of a headband: block by block
BLOCKS = np.repeat(np.arange(10), wd.N_TARGETS)


def folds_of(sid):
    """(folds in which the person is a validation person, the fold in which the person is a test person)."""
    val = [i for i, (_, v, _) in enumerate(FOLDS) if sid in v]
    test = [i for i, (_, _, t) in enumerate(FOLDS) if sid in t]
    assert len(test) == 1 and not any(sid in FOLDS[i][0] for i in val + test)
    return val, test[0]


def pass1(job):
    sid, raw, cache = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)                                      # (electrode, block, target, channel, sample)
    np.savez(cache / f"mean_S{sid:03d}.npz", **{f"w{n}": sm.preprocess(x, n).mean(axis=2).astype(np.float32) for n in N})
    return sid                                                         # each: (band, electrode, target, channel, n)


def template(cache, fold, n):
    """Mean response of the 43 training people of a fold: (band, electrode, target, channel, n)."""
    return np.load(cache / f"template_fold{fold}.npz")[f"w{n}"]


def pass2(job):
    sid, raw, cache = job
    assert not wd.is_lockbox(sid)
    val, test = folds_of(sid)
    x = wd.load_subject(raw, sid)
    weights = pp.weights(sm.PIPELINE)
    out = {"fbcca": np.zeros((2, len(N), 120, wd.N_TARGETS))}
    out.update({f"template_fold{f}": np.zeros((2, len(N), 120, wd.N_TARGETS)) for f in val + [test]})
    for j, n in enumerate(N):
        bases = dc.reference_bases(wd.TARGET_FREQS, n, wd.FS, pp.N_HARM[sm.PIPELINE])
        templates = {f: template(cache, f, n) for f in val + [test]}
        for e in range(2):
            sub = sm.preprocess(x[e].reshape(120, *x.shape[3:]), n)   # (band, 120 trials, channel, n)
            fbcca, tmpl = sm.decode(sub, bases, weights, [templates[f][:, e] for f in val + [test]])
            out["fbcca"][e, j] = fbcca
            for f, s in zip(val + [test], tmpl):
                out[f"template_fold{f}"][e, j] = s
    np.savez(cache / f"scores_S{sid:03d}.npz", **out)
    return sid


def scores(cache, sid, decoder, fold=None):
    """Scores of one person: (electrode, length, 120 trials, classes). decoder: 'fbcca' or 'template' (with a fold)."""
    data = np.load(pathlib.Path(cache) / f"scores_S{sid:03d}.npz")
    return data["fbcca"] if decoder == "fbcca" else data[f"template_fold{fold}"]


def prepare(raw, cache, jobs=2):
    """Both passes; a step whose files exist is not done again. Returns the cache folder."""
    raw, cache = pathlib.Path(raw), pathlib.Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    import multiprocessing as mp
    with mp.get_context("fork").Pool(jobs) as pool:
        todo = [(sid, raw, cache) for sid in PEOPLE if not (cache / f"mean_S{sid:03d}.npz").exists()]
        pool.map(pass1, todo, chunksize=1)
        for f, (train, _, _) in enumerate(FOLDS):
            if not (cache / f"template_fold{f}.npz").exists():
                means = [np.load(cache / f"mean_S{sid:03d}.npz") for sid in train]
                np.savez(cache / f"template_fold{f}.npz", **{f"w{n}": np.mean([m[f"w{n}"].astype(float) for m in means], axis=0) for n in N})
        print(f"pass 1: mean responses of {len(PEOPLE)} development people and the templates of {len(FOLDS)} folds "
              f"({len(todo)} people computed now, {time.time() - t0:.0f} s)", flush=True)
        todo = [(sid, raw, cache) for sid in PEOPLE if not (cache / f"scores_S{sid:03d}.npz").exists()]
        pool.map(pass2, todo, chunksize=1)
    print(f"pass 2: scores of {len(PEOPLE)} people x 2 headbands x 120 trials at {len(N)} lengths of signal "
          f"({len(todo)} people computed now, {time.time() - t0:.0f} s in all)", flush=True)
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    cache = prepare(args.raw, args.cache, args.jobs)
    for decoder in ("fbcca", "template"):                              # a first look, at 1.0 s, test people of each fold
        j = sm.TIMES.index(1.0)
        acc = np.array([[(scores(cache, sid, decoder, folds_of(sid)[1])[e, j].argmax(axis=-1) == LABELS).mean() for e in range(2)]
                        for sid in PEOPLE])
        print(f"{decoder:8s} fixed 1.0 s, every person as a test person: dry {acc[:, 0].mean():.3f}, wet {acc[:, 1].mean():.3f}")


if __name__ == "__main__":
    main()
