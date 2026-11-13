"""M3: size and compute of every method, for one decision on a 1 s window (one processor core, synthetic signals).

The time does not depend on what the signals contain, so no recording is needed.

Usage: python scripts/m3_compute.py
"""
import time

import m3_common as c
import numpy as np
import pandas as pd
import torch

from ssvep import decoders as dc
from ssvep import network as nw
from ssvep import pipeline as pp
from ssvep import transfer as tr
from ssvep import wearable as wd


def clock(fn, repeat=200):
    fn()
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn()
    return 1000 * (time.perf_counter() - t0) / repeat


def main():
    torch.set_num_threads(1)
    rng = np.random.default_rng(0)
    epoch = rng.standard_normal((1, 8, wd.RESP_START + c.N))           # the samples a real-time system has at decision time
    trial = rng.standard_normal((3, 1, 8, c.N))                         # (band, trial, ch, n)
    weights, bases = pp.weights("B2"), dc.reference_bases(wd.TARGET_FREQS, c.N, c.FS, 3)
    template = rng.standard_normal((3, 12, 8, c.N))
    filters = rng.standard_normal((3, 12, 8))
    model = nw.Net().eval()
    x = torch.as_tensor(nw.standardise(trial.transpose(1, 0, 2, 3)))
    rows = [
        ("preprocessing B2 (mains removal, 3 sub-bands)", clock(lambda: pp.subbands(epoch, c.N, "B2", wd.RESP_START)), 0, "nothing"),
        ("FBCCA", clock(lambda: dc.fbcca_scores(dc.cca_corr(trial, bases), weights)), 0, "nothing"),
        ("cross-subject template", clock(lambda: tr.ecca_scores(tr.trial_part(trial, bases), template, bases, weights)),
         template.size, "other people's data; no data of the user"),
        ("ensemble TRCA", clock(lambda: [dc.trca_corr(trial[b], template[b], filters[b]) for b in range(3)]),
         template.size + filters.size, "labelled blocks of the user"),
        ("network (3 572 parameters)", clock(lambda: model(x)), nw.n_parameters(model) + 80, "other people's data; no data of the user"),
    ]
    d = pd.DataFrame(rows, columns=["step", "ms_per_decision", "stored_numbers", "needs"])
    d.to_csv(c.RES / "compute.csv", index=False, float_format="%.3f")
    print("time of one decision at 1 s on one core, and what each method stores:")
    print(d.round(3).to_string(index=False))
    print("(the template decoder recomputes the spatial filters of the template at every call; they could be stored)")


if __name__ == "__main__":
    main()
