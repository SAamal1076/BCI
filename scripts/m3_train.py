"""M3: train the networks. DEVELOPMENT SUBJECTS ONLY. 4 folds of people x 2 headbands x 3 seeds = 24 networks.

A network is trained on 43 people, validated on 8 (early stopping) and never sees the 17 test people of its fold.
Finished networks are kept (results/m3/models), so the script can be stopped and started again.

Usage: python scripts/m3_train.py --raw /path/to/13560281 [--jobs 2] [--cache /tmp/m3_cache]
"""
import argparse
import json
import pathlib
import time

import m3_common as c
import numpy as np
import pandas as pd
import torch

from ssvep import network as nw
from ssvep import wearable as wd

MODELS = c.RES / "models"


def name(fold, electrode, seed):
    return f"fold{fold}_{wd.ELECTRODE_NAMES[electrode]}_seed{seed}"


def train_one(job):
    fold, electrode, seed, cache = job
    torch.set_num_threads(1)
    train, val, test = nw.folds(c.PEOPLE)[fold]
    assert not set(test) & (set(train) | set(val))
    x, y = c.labelled(cache, train, electrode)
    xv, yv = c.labelled(cache, val, electrode)
    t0 = time.time()
    model, history = nw.train(nw.standardise(x), y, nw.standardise(xv), yv, seed)
    best = int(np.argmin([h[2] for h in history]))
    torch.save(model.state_dict(), MODELS / f"{name(fold, electrode, seed)}.pt")
    info = {"fold": fold, "electrode": wd.ELECTRODE_NAMES[electrode], "seed": seed, "train_people": len(train),
            "validation_people": len(val), "train_trials": len(x), "epochs_run": len(history), "best_epoch": history[best][0],
            "validation_loss": round(history[best][2], 4), "validation_accuracy": round(history[best][3], 4),
            "train_seconds": round(time.time() - t0, 1)}
    (MODELS / f"{name(fold, electrode, seed)}.json").write_text(json.dumps(info))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(c.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    MODELS.mkdir(parents=True, exist_ok=True)
    cache = c.prepare(args.raw, args.cache, args.jobs)
    jobs = [(f, e, s, cache) for f in range(4) for e in range(2) for s in c.SEEDS
            if not (MODELS / f"{name(f, e, s)}.json").exists()]
    print(f"{24 - len(jobs)} networks already trained, {len(jobs)} to train", flush=True)
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(args.jobs) as pool:
        for info in pool.imap_unordered(train_one, jobs):
            print(json.dumps(info), flush=True)
    log = pd.DataFrame([json.loads(p.read_text()) for p in sorted(MODELS.glob("*.json"))])
    log.to_csv(c.RES / "training_log.csv", index=False)
    print(f"networks: {len(log)}; parameters: {nw.n_parameters(nw.Net())}; mean training time {log.train_seconds.mean():.0f} s; "
          f"epochs run {log.epochs_run.min()} to {log.epochs_run.max()}; validation accuracy {log.validation_accuracy.mean():.3f}")


if __name__ == "__main__":
    main()
