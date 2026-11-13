"""M4: the decision of every trial with the frozen decoder for a new user. DEVELOPMENT SUBJECTS ONLY.

Decoder (frozen in M2): cross-subject template, no calibration, pipeline B2, leave-one-subject-out. FBCCA is
stored next to it. All 10 blocks of each headband are decoded.

Writes to results/m4:
  decisions_1s.csv        one row per trial at 1 s: true target, decision of the template, decision of FBCCA
  accuracy_2s.csv         accuracy per person and headband at 2 s (for the failure analysis)
  ageing_1s.csv           a template made of the person's blocks 1 and 2 only, tested on each of blocks 3 to 10
  impedance_blocks.csv    median impedance over the 8 channels, per person, headband and block (label-free)

Usage: python scripts/m4_decode.py --raw /path/to/13560281 [--jobs 2] [--cache /tmp/m2_cache]
"""
import argparse
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import m2_new_users as m2  # noqa: E402  (also puts src on the path and limits the threads)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.io import loadmat  # noqa: E402

from ssvep import decoders as dc  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import transfer as tr  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

PEOPLE = wd.DEVELOPMENT
WINDOWS = (1.0, 2.0)
OUT = ROOT / "results" / "m4"


def decode(job):
    sid, raw, name, cache = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)
    own_mean = np.load(cache / f"S{sid:03d}.npz")
    weights = pp.weights(name)
    labels, block = np.tile(np.arange(12), 10), np.repeat(np.arange(10), 12)
    decisions, two, ageing = [], [], []
    for window in WINDOWS:
        n = m2.samples(window)
        sub = m2.subbands(x, window, name)                                # (band, e, block, target, ch, n)
        bases = dc.reference_bases(wd.TARGET_FREQS, n, wd.FS, pp.N_HARM[name])
        population = tr.leave_one_out_mean(np.load(cache / f"population_w{n}.npy"), own_mean[f"w{n}"].astype(float), len(PEOPLE))
        for e, el in enumerate(wd.ELECTRODE_NAMES):
            data = sub[:, e]
            part = tr.trial_part(data.reshape(data.shape[0], 120, *data.shape[3:]), bases)
            fbcca = dc.fbcca_scores(part[0], weights).argmax(axis=-1)
            template = tr.ecca_scores(part, population[:, e], bases, weights).argmax(axis=-1)
            if window == 1.0:
                decisions += [(sid, el, b + 1, t + 1, p + 1, q + 1) for b, t, p, q in zip(block, labels, template, fbcca)]
                own = tr.ecca_scores(part, data[:, :2].mean(axis=1), bases, weights).argmax(axis=-1)   # blocks 1 and 2 only
                for b in range(2, 10):
                    sel = block == b
                    ageing.append((sid, el, b + 1, (own[sel] == labels[sel]).mean(), (template[sel] == labels[sel]).mean()))
            else:
                two.append((sid, el, (template == labels).mean(), (fbcca == labels).mean()))
    return decisions, two, ageing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--cache", default=str(pathlib.Path(tempfile.gettempdir()) / "m2_cache"))
    args = ap.parse_args()
    raw, cache = pathlib.Path(args.raw), pathlib.Path(args.cache)
    OUT.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    name, first = m2.chosen_pipeline(ROOT / "results" / "m2"), m2.first_headband(raw)
    import multiprocessing as mp
    with mp.get_context("fork").Pool(args.jobs) as pool:
        todo = [(sid, raw, name, cache) for sid in PEOPLE if not (cache / f"S{sid:03d}.npz").exists()]
        pool.map(m2.pass1, todo, chunksize=1)                             # mean responses, as in M2 (skipped if cached)
        for w in WINDOWS:
            key = f"w{m2.samples(w)}"
            np.save(cache / f"population_{key}.npy", sum(np.load(cache / f"S{sid:03d}.npz")[key].astype(float) for sid in PEOPLE))
        results = pool.map(decode, [(sid, raw, name, cache) for sid in PEOPLE], chunksize=1)

    d = pd.DataFrame([r for res in results for r in res[0]], columns=["subject", "electrode", "block", "target", "template", "fbcca"])
    d.insert(1, "first_headband", d.subject.map(first))
    d.to_csv(OUT / "decisions_1s.csv", index=False)
    pd.DataFrame([r for res in results for r in res[1]], columns=["subject", "electrode", "template", "fbcca"]).to_csv(
        OUT / "accuracy_2s.csv", index=False, float_format="%.6f")
    pd.DataFrame([r for res in results for r in res[2]], columns=["subject", "electrode", "block", "own_blocks_1_2", "template"]).to_csv(
        OUT / "ageing_1s.csv", index=False, float_format="%.6f")

    imp = loadmat(raw / "Impedance.mat")["Impedance"]                     # (channel, block, type, subject); type 0 = dry (M0)
    rows = [(sid, el, b + 1, float(np.median(imp[:, b, e, sid - 1]))) for sid in PEOPLE for e, el in enumerate(wd.ELECTRODE_NAMES)
            for b in range(10)]
    pd.DataFrame(rows, columns=["subject", "electrode", "block", "median_kohm"]).to_csv(OUT / "impedance_blocks.csv", index=False,
                                                                                         float_format="%.4f")
    acc = d.assign(ok=d.template == d.target, okf=d.fbcca == d.target).groupby("electrode")[["ok", "okf"]].mean()
    print(f"pipeline {name}; {d.subject.nunique()} development people, leave-one-subject-out; {len(d)} decisions at 1 s")
    print("accuracy over all 10 blocks at 1 s (template, FBCCA):")
    print(acc.round(3).to_string())


if __name__ == "__main__":
    main()
