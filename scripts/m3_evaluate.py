"""M3: decode the test people of each fold as new users with no calibration. DEVELOPMENT SUBJECTS ONLY.

For every test person and headband, on blocks 7 to 10 (48 trials, 1 s window):
  fbcca              no data from anyone
  template           cross-subject template of M2, population = the 51 training and validation people of the fold
  template_adapted   the template updated with the person's blocks 1 to 6 WITHOUT labels (its own decisions as labels)
  net_A0             network, no adaptation
  net_A1             network, batch-normalisation statistics of the person's blocks 1 to 6 (no labels)
  net_A2             A1 + entropy minimisation on those blocks (no labels); the method of H3
  net_online         adaptation on the test blocks themselves, each block decided before it is used

Usage: python scripts/m3_evaluate.py [--cache /tmp/m3_cache] [--jobs 2]     (after m3_train.py)
"""
import argparse
import pathlib

import m3_common as c
import numpy as np
import pandas as pd
import torch

from ssvep import adapt as ad
from ssvep import decoders as dc
from ssvep import network as nw
from ssvep import pipeline as pp
from ssvep import transfer as tr
from ssvep import wearable as wd

N0 = 4.0                                                               # frozen in M2
MODELS = c.RES / "models"


def evaluate_fold(job):
    fold, cache = job
    torch.set_num_threads(1)
    train, val, test = nw.folds(c.PEOPLE)[fold]
    population_people = train + val
    assert not set(test) & set(population_people)
    weights, bases = pp.weights(c.PIPELINE), dc.reference_bases(wd.TARGET_FREQS, c.N, c.FS, pp.N_HARM[c.PIPELINE])
    labels = np.tile(np.arange(wd.N_TARGETS), 4)
    labels_unl = np.tile(np.arange(wd.N_TARGETS), 6)                   # used only to report how good the pseudo-labels are
    rows = []
    for e, el in enumerate(wd.ELECTRODE_NAMES):
        population = np.mean([c.load(cache, sid, e).mean(axis=0, dtype=float) for sid in population_people], axis=0)
        population = population.transpose(1, 0, 2, 3)                  # (band, target, ch, n)
        models = {}
        for seed in c.SEEDS:
            models[seed] = nw.Net()
            models[seed].load_state_dict(torch.load(MODELS / f"fold{fold}_{el}_seed{seed}.pt"))
        for sid in test:
            d = c.load(cache, sid, e).astype(float)                    # (block, target, band, ch, n)
            unl, tst = d[:6].reshape(72, 3, 8, c.N), d[6:].reshape(48, 3, 8, c.N)

            def add(method, seed, correct, extra=np.nan):
                rows.append((fold, sid, el, method, seed, float(np.mean(correct)), extra))

            part = tr.trial_part(tst.transpose(1, 0, 2, 3), bases)
            add("fbcca", -1, dc.fbcca_scores(part[0], weights).argmax(axis=-1) == labels)
            add("template", -1, tr.ecca_scores(part, population, bases, weights).argmax(axis=-1) == labels)
            decided = tr.ecca_scores(tr.trial_part(unl.transpose(1, 0, 2, 3), bases), population, bases, weights).argmax(axis=-1)
            adapted = population.copy()
            for f in range(wd.N_TARGETS):
                m = int((decided == f).sum())
                if m:
                    adapted[:, f] = (N0 * population[:, f] + m * unl[decided == f].mean(axis=0)) / (N0 + m)
            add("template_adapted", -1, tr.ecca_scores(part, adapted, bases, weights).argmax(axis=-1) == labels,
                float(np.mean(decided == labels_unl)))

            xu, xt = nw.standardise(unl), nw.standardise(tst)
            for seed, model in models.items():
                add("net_A0", seed, nw.predict(model, xt).argmax(axis=1) == labels)
                add("net_A1", seed, nw.predict(ad.adapt_statistics(model, xu), xt).argmax(axis=1) == labels)
                add("net_A2", seed, nw.predict(ad.adapt_entropy(model, xu), xt).argmax(axis=1) == labels)
                online = np.concatenate(ad.online(model, [xt[i:i + 12] for i in range(0, 48, 12)]))
                add("net_online", seed, online == labels)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(c.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(args.jobs) as pool:
        results = pool.map(evaluate_fold, [(f, pathlib.Path(args.cache)) for f in range(4)])
    d = pd.DataFrame([r for res in results for r in res],
                     columns=["fold", "subject", "electrode", "method", "seed", "accuracy", "pseudo_label_accuracy"])
    d.to_csv(c.RES / "new_user_accuracy.csv", index=False, float_format="%.6f")
    print(f"{d.subject.nunique()} development people as new users (4 folds), 1 s window, blocks 7-10")
    print(d.groupby(["method", "electrode"]).accuracy.mean().unstack("electrode").round(3).to_string())


if __name__ == "__main__":
    main()
