"""Diagnostic added during M5 (not in its plan): does one saturated trial spoil the population template?

Found while checking M5 against M4: the dry recording of development person S067 holds the only trial of the
dataset that reaches the limit of the converter (block 4, target 4; flagged in M0, label-free). The population
template of M2 to M4 and of the final evaluation is a plain mean over people, and this one trial dominates its
entry for target 4 (9.75 Hz) with the dry headband.

Here, on the development people only and with nothing else changed (cross-subject template, no calibration,
1 s, all ten blocks, leave-one-subject-out as in M4), the decoder is run twice:
  frozen     the population template as it was (all trials)
  repaired   the same, without that one trial (S067's mean response to target 4 from its 9 other blocks)

No test, no lockbox person. The frozen variant must reproduce the accuracies of M4.

Usage: python scripts/m5_template_check.py [--raw DIR] [--cache DIR] [--jobs 2]
"""
import argparse
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m5_scores as ms  # noqa: E402
from ssvep import decoders as dc  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import transfer as tr  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

OUT = ROOT / "results" / "m5"
N = 250                                                                # 1 s
SID, ELECTRODE, BLOCK, TARGET = 67, wd.DRY, 3, 3                       # S067, dry, block 4, target 4 (0-based indices)
_STATE = {}


def own_mean(cache, sid):
    return np.load(cache / f"mean_S{sid:03d}.npz")[f"w{N}"].astype(float)          # (band, electrode, target, channel, n)


def decode_person(sid):
    s = _STATE
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(s["raw"], sid)
    bases = dc.reference_bases(wd.TARGET_FREQS, N, wd.FS, pp.N_HARM[sm.PIPELINE])
    rows = []
    for e, el in enumerate(wd.ELECTRODE_NAMES):
        sub = sm.preprocess(x[e].reshape(120, *x.shape[3:]), N)
        frozen = tr.leave_one_out_mean(s["total"], own_mean(s["cache"], sid), len(ms.PEOPLE))[:, e]
        repaired = tr.leave_one_out_mean(s["total_repaired"], s["own_repaired"] if sid == SID else own_mean(s["cache"], sid), len(ms.PEOPLE))[:, e]
        _, (a, b) = sm.decode(sub, bases, pp.weights(sm.PIPELINE), [frozen, repaired])
        for variant, scores in (("frozen", a), ("repaired", b)):
            decided = scores.argmax(axis=-1)
            rows += [(sid, el, variant, t + 1, d + 1) for t, d in zip(ms.LABELS, decided)]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(ms.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, cache = pathlib.Path(args.raw), ms.prepare(args.raw, args.cache, args.jobs)
    means = {sid: own_mean(cache, sid) for sid in ms.PEOPLE}
    total = sum(means.values())
    x = wd.load_subject(raw, SID)[ELECTRODE, :, TARGET]                # (block, channel, sample): S067, dry, target 4
    trials = sm.preprocess(x, N)                                       # (band, block, channel, n)
    keep = [b for b in range(10) if b != BLOCK]
    own_repaired = means[SID].copy()
    own_repaired[:, ELECTRODE, TARGET] = trials[:, keep].mean(axis=1).astype(np.float32)
    total_repaired = total - means[SID] + own_repaired

    size = lambda m: np.sqrt((m ** 2).mean(axis=(0, 2, 3)))            # noqa: E731  rms of a template (band, target, ch, n), per target
    population = {"frozen": total[:, ELECTRODE] / len(ms.PEOPLE), "repaired": total_repaired[:, ELECTRODE] / len(ms.PEOPLE)}
    print(f"== the saturated trial: S{SID:03d}, dry headband, block {BLOCK + 1}, target {TARGET + 1} ({wd.TARGET_FREQS[TARGET]} Hz)")
    amp = np.sqrt((trials ** 2).mean(axis=(0, 2, 3)))
    print(f"size (rms after preprocessing) of that trial: {amp[BLOCK]:.0f}; of the person's 9 other trials of the target: median {np.median(amp[keep]):.1f}")
    for variant, m in population.items():
        r = size(m)
        print(f"dry population template, {variant:8s}: size of the entry of target {TARGET + 1}: {r[TARGET]:.2f}; of the 11 other targets: "
              f"median {np.median(np.delete(r, TARGET)):.2f}")

    _STATE.update(raw=raw, cache=cache, total=total, total_repaired=total_repaired, own_repaired=own_repaired)
    import multiprocessing as mp
    with mp.get_context("fork").Pool(args.jobs) as pool:
        results = pool.map(decode_person, ms.PEOPLE, chunksize=1)
    d = pd.DataFrame([r for res in results for r in res], columns=["subject", "electrode", "variant", "target", "decided"])
    d["right"] = d.decided == d.target
    OUT.mkdir(parents=True, exist_ok=True)
    acc = d.groupby(["subject", "electrode", "variant"]).right.mean().unstack("variant")
    acc4 = d[d.target == TARGET + 1].groupby(["subject", "electrode", "variant"]).right.mean().unstack("variant")
    out = acc.join(acc4, rsuffix="_target4").reset_index()
    out.to_csv(OUT / "template_check.csv", index=False, float_format="%.6f")

    m4 = pd.read_csv(ROOT / "results" / "m4" / "decisions_1s.csv")
    ref = m4.assign(right=m4.template == m4.target).groupby(["subject", "electrode"]).right.mean()
    print(f"\n== check: the frozen variant against M4 ({len(ref)} accuracies): largest difference {np.abs(acc.frozen - ref).max():.6f}")

    def ci(v, f="+.3f"):
        lo, hi = st.bootstrap_ci(np.asarray(v, dtype=float))
        return f"{np.mean(v):{f}} [{lo:{f}}, {hi:{f}}]"

    print("\n== accuracy at 1 s, no calibration, all ten blocks, 68 development people (mean; difference with 95 % interval)")
    for el in wd.ELECTRODE_NAMES:
        a, a4 = acc.xs(el, level="electrode"), acc4.xs(el, level="electrode")
        print(f"  {el}: all targets: frozen {a.frozen.mean():.3f}, repaired {a.repaired.mean():.3f}, difference {ci(a.repaired - a.frozen)}; "
              f"people better {int((a.repaired > a.frozen).sum())}, worse {int((a.repaired < a.frozen).sum())}")
        print(f"       target {TARGET + 1} ({wd.TARGET_FREQS[TARGET]} Hz) only: frozen {a4.frozen.mean():.3f}, repaired {a4.repaired.mean():.3f}")
    print("\n== accuracy by target, dry headband (frozen | repaired)")
    by = d[d.electrode == "dry"].groupby(["target", "variant"]).right.mean().unstack("variant")
    by.insert(0, "Hz", wd.TARGET_FREQS)
    print(by.round(3).to_string())
    share = d[d.electrode == "dry"].groupby("variant").decided.apply(lambda s: (s == TARGET + 1).mean())
    print(f"share of all dry decisions given to target {TARGET + 1}: frozen {share.frozen:.3f}, repaired {share.repaired:.3f} (even: {1 / 12:.3f})")


if __name__ == "__main__":
    main()
