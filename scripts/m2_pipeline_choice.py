"""M2, step 0: choose the preprocessing among the three candidates of the plan. DEVELOPMENT SUBJECTS ONLY.

Candidates B, B1, B2 (ssvep.pipeline). Decoders of M1 with the a-priori weights: FBCCA and ensemble TRCA
(leave-one-block-out), 1 s window. Criterion fixed in the plan: mean accuracy over the two methods and the two
headbands. B2 is taken only if it is at least 0.01 above B1; otherwise the better of B1 and B.

Usage: python scripts/m2_pipeline_choice.py --raw /path/to/13560281 [--jobs 2]
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
from ssvep import decoders as dc  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F, N = wd.FS, wd.TARGET_FREQS, 250
LABELS = np.arange(wd.N_TARGETS)
NEAR = np.isin(F, (12.25, 12.75))
BASES = {h: dc.reference_bases(F, N, FS, h) for h in (3, 5)}
MARGIN = 0.01


def evaluate_subject(job):
    sid, raw = job
    assert not wd.is_lockbox(sid)
    x = wd.load_subject(raw, sid)                                   # [electrode, block, target, channel, sample]
    rows = []
    for name in pp.NAMES:
        sub = pp.subbands(x, N, name, wd.RESP_START, FS)            # (band, e, block, target, ch, n)
        w = pp.weights(name)
        rho = dc.cca_corr(sub, BASES[pp.N_HARM[name]])
        for e, el in enumerate(wd.ELECTRODE_NAMES):
            pred = {"fbcca": dc.fbcca_scores(rho[:, e], w).argmax(axis=-1),
                    "etrca": dc.fb_combine_signed(dc.trca_leave_one_block_out(sub[:, e])[1], w).argmax(axis=-1)}
            for method, p in pred.items():
                rows.append((sid, el, name, method, (p == LABELS).mean(), NEAR[p].mean()))
    return rows


def choose(crit):
    """Rule of the plan. crit: criterion per candidate."""
    if crit["B2"] >= crit["B1"] + MARGIN and crit["B2"] >= crit["B"]:
        return "B2"
    return "B1" if crit["B1"] >= crit["B"] else "B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m2"))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(sid, raw) for sid in wd.DEVELOPMENT]
    if args.jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.jobs) as pool:
            results = pool.map(evaluate_subject, jobs, chunksize=1)
    else:
        results = [evaluate_subject(j) for j in jobs]
    d = pd.DataFrame([r for res in results for r in res],
                     columns=["subject", "electrode", "pipeline", "method", "accuracy", "share_12.25_12.75"])
    d.to_csv(out / "pipeline_candidates.csv", index=False, float_format="%.6f")

    cell = d.groupby(["pipeline", "method", "electrode"]).accuracy.mean().unstack(["method", "electrode"])
    crit = cell.mean(axis=1)                                        # mean of the four cells
    chosen = choose(crit)
    share = d.groupby(["pipeline", "method"])["share_12.25_12.75"].mean().unstack("method")
    table = cell.copy()
    table.columns = [f"{m}_{e}" for m, e in table.columns]
    table["criterion"] = crit
    table["fbcca_share_12.25_12.75"] = share["fbcca"]
    table["etrca_share_12.25_12.75"] = share["etrca"]
    table["chosen"] = table.index == chosen
    table.loc[list(pp.NAMES)].to_csv(out / "pipeline_choice.csv", float_format="%.4f")

    print(f"development subjects: {d.subject.nunique()}; 1 s window; a-priori weights")
    print(table.loc[list(pp.NAMES)].round(3).to_string())
    print("(share: part of the decisions that go to 12.25 or 12.75 Hz; 0.167 without bias)")
    print(f"criterion: B {crit['B']:.4f}, B1 {crit['B1']:.4f}, B2 {crit['B2']:.4f}; "
          f"B2 minus B1 = {crit['B2'] - crit['B1']:+.4f} (needed: {MARGIN:+.2f})")
    print(f"chosen pipeline: {chosen}")
    wide = d.pivot_table(index=["subject", "electrode", "method"], columns="pipeline", values="accuracy")
    print("\npeople for whom the candidate is better / equal / worse than B1 (per person and headband):")
    for name in ("B", "B2"):
        for method in ("fbcca", "etrca"):
            diff = (wide[name] - wide["B1"]).xs(method, level="method")
            print(f"  {name} against B1, {method}: {(diff > 0).sum()} / {(diff == 0).sum()} / {(diff < 0).sum()}, "
                  f"mean difference {diff.mean():+.4f}")


if __name__ == "__main__":
    main()
