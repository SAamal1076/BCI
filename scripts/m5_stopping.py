"""M5, step 2: confidence, the stopping rule and the best fixed window, chosen on validation people and
applied to test people. Reads the scores of m5_scores.py; writes the tables of results/m5 and prints the summary.

For each fold, headband and decoder (cross-subject template, FBCCA):
  on the 8 validation people   b_T for each length of signal (scores -> probabilities), then theta and, for
                               comparison, the best fixed length, both by the highest mean ITR
  on the 17 test people        the decisions of the stopping rule and of the fixed window

Usage: python scripts/m5_stopping.py [--raw DIR] [--cache DIR]
"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m5_scores as ms  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

OUT = ROOT / "results" / "m5"
NAMES, DECODERS, TIMES = wd.ELECTRODE_NAMES, ("template", "fbcca"), np.array(sm.TIMES)
BINS = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0000001)                       # confidence at the decision


def stacked(cache, people, decoder, fold, e):
    """Scores of several people: (trials, lengths, classes), with the label and the person of each trial."""
    s = np.concatenate([ms.scores(cache, sid, decoder, fold)[e].transpose(1, 0, 2) for sid in people])
    return s, np.tile(ms.LABELS, len(people)), np.repeat(people, 120)


def confidence(scores, b):
    """Confidence and decision at every update: (trials, lengths) each."""
    p = np.stack([sm.probabilities(scores[:, j], b[j]) for j in range(scores.shape[1])], axis=1)
    return p.max(axis=-1), p.argmax(axis=-1)


def ci(v, f="+.3f"):
    v = np.asarray(v, dtype=float)
    lo, hi = st.bootstrap_ci(v)
    return f"{v.mean():{f}} [{lo:{f}}, {hi:{f}}]"


def analyse(cache):
    settings, trials, by_window = [], [], []
    for fold, (_, val, test) in enumerate(ms.FOLDS):
        for e, el in enumerate(NAMES):
            for decoder in DECODERS:
                s, labels, person = stacked(cache, val, decoder, fold, e)
                b = [sm.fit_scale(s[:, j], labels) for j in range(len(TIMES))]
                conf, dec = confidence(s, b)
                theta, itr_theta = sm.choose_theta(conf, dec, labels, person)
                jw, itr_window = sm.choose_window(dec, labels, person)
                settings.append({"fold": fold, "electrode": el, "decoder": decoder, "theta": theta, "fixed_window_s": TIMES[jw],
                                 "validation_itr_stopping": itr_theta.max(), "validation_itr_fixed": itr_window.max(),
                                 **{f"b_{t:.1f}": bj for t, bj in zip(TIMES, b)}})
                s, labels, person = stacked(cache, test, decoder, fold, e)
                conf, dec = confidence(s, b)
                i, rows = sm.stop(conf, theta), np.arange(len(labels))
                trials.append(pd.DataFrame({
                    "subject": person, "fold": fold, "electrode": el, "decoder": decoder, "block": np.tile(ms.BLOCKS, len(test)) + 1,
                    "target": labels + 1, "decided": dec[rows, i] + 1, "time_s": TIMES[i], "confidence": conf[rows, i],
                    "fixed_window_s": TIMES[jw], "fixed_decided": dec[:, jw] + 1}))
                right = dec == labels[:, None]
                for sid in test:
                    by_window += [(sid, el, decoder, t, right[person == sid, j].mean()) for j, t in enumerate(TIMES)]
    return (pd.DataFrame(settings), pd.concat(trials, ignore_index=True),
            pd.DataFrame(by_window, columns=["subject", "electrode", "decoder", "window_s", "accuracy"]))


def people_table(trials):
    t = trials.assign(right=trials.decided == trials.target, fixed_right=trials.fixed_decided == trials.target,
                      late=trials.time_s == TIMES[-1])
    g = t.groupby(["subject", "fold", "electrode", "decoder"])
    p = g.agg(accuracy=("right", "mean"), time_s=("time_s", "mean"), share_at_2s=("late", "mean"),
              fixed_window_s=("fixed_window_s", "first"), fixed_accuracy=("fixed_right", "mean")).reset_index()
    p["itr"] = [sm.person_itr(a, s) for a, s in zip(p.accuracy, p.time_s)]             # accuracy and mean time of the person
    p["fixed_itr"] = [sm.person_itr(a, s) for a, s in zip(p.fixed_accuracy, p.fixed_window_s)]
    return p


def same_time(people, by_window):
    """Accuracy of the stopping rule against a fixed window that is at least as long as its mean decision time."""
    rows = []
    for (el, decoder), p in people.groupby(["electrode", "decoder"]):
        mean_time = p.time_s.mean()
        window = TIMES[np.searchsorted(TIMES, mean_time - 1e-9)]         # the next update time, not a shorter one
        fixed = by_window[(by_window.electrode == el) & (by_window.decoder == decoder) & np.isclose(by_window.window_s, window)]
        d = p.set_index("subject").accuracy - fixed.set_index("subject").accuracy
        rows.append({"electrode": el, "decoder": decoder, "mean_time_s": mean_time, "fixed_window_s": window,
                     "accuracy_stopping": p.accuracy.mean(), "accuracy_fixed": fixed.accuracy.mean(), "difference": ci(d.to_numpy())})
    return pd.DataFrame(rows)


def reliability(trials):
    t = trials.assign(right=trials.decided == trials.target, bin=pd.cut(trials.confidence, BINS, right=False))
    r = t.groupby(["decoder", "electrode", "bin"], observed=True).agg(decisions=("right", "size"), confidence=("confidence", "mean"),
                                                                       correct=("right", "mean")).reset_index()
    r["bin"] = r.bin.astype(str)
    return r


def report(settings, trials, by_window, people):
    print(f"== M5: {people.subject.nunique()} development people, each decoded once as a test person; {len(trials)} decisions; "
          f"updates every {sm.PIECE_S} s from {TIMES[0]} s to {TIMES[-1]} s; {sm.GAZE_S} s added for moving the eyes")
    print("\n== 1. chosen on the validation people of each fold (theta of the stopping rule; best fixed window)")
    print(settings[["fold", "electrode", "decoder", "theta", "fixed_window_s", "validation_itr_stopping", "validation_itr_fixed"]]
          .round(1).to_string(index=False))
    print("scale b_T (median over folds) at 0.3, 1.0 and 2.0 s:")
    print(settings.groupby(["decoder", "electrode"])[["b_0.3", "b_1.0", "b_2.0"]].median().round(1).to_string())

    print("\n== 2. test people: stopping rule against the best fixed window, mean [95 % interval over people]")
    rows = []
    for (decoder, el), p in people.groupby(["decoder", "electrode"], sort=False):
        rows.append({"decoder": decoder, "electrode": el,
                     "ITR stopping": ci(p.itr, ".1f"), "ITR fixed": ci(p.fixed_itr, ".1f"), "ITR difference": ci(p.itr - p.fixed_itr, "+.1f"),
                     "relative": f"{(p.itr.mean() / p.fixed_itr.mean() - 1) * 100:+.0f} %",
                     "people faster with stopping": f"{int((p.itr > p.fixed_itr).sum())} of {len(p)}"})
    print(pd.DataFrame(rows).to_string(index=False))
    rows = []
    for (decoder, el), p in people.groupby(["decoder", "electrode"], sort=False):
        rows.append({"decoder": decoder, "electrode": el, "accuracy stopping": ci(p.accuracy, ".3f"), "mean time stopping (s)": ci(p.time_s, ".2f"),
                     "accuracy fixed": ci(p.fixed_accuracy, ".3f"), "fixed window (s), by fold": sorted(p.fixed_window_s.unique()),
                     "decided at 2.0 s": f"{p.share_at_2s.mean() * 100:.0f} %"})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== 3. accuracy at the same time: stopping rule against a fixed window at least as long as its mean decision time")
    print(same_time(people, by_window).round(3).to_string(index=False))

    print("\n== 4. fixed windows on the test people (mean accuracy; ITR of the mean person is not shown, see section 2)")
    a = by_window.groupby(["decoder", "electrode", "window_s"]).accuracy.mean().unstack("window_s")
    print(a[[0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0]].round(3).to_string())

    print("\n== 5. when the rule decides (share of the decisions of the test people, %)")
    t = trials.assign(when=pd.cut(trials.time_s, [0, 0.55, 1.05, 1.55, 1.95, 2.05], labels=["0.3-0.5 s", "0.6-1.0 s", "1.1-1.5 s", "1.6-1.9 s", "2.0 s"]))
    print((t.groupby(["decoder", "electrode"]).when.value_counts(normalize=True).unstack("when") * 100).round(1).to_string())
    right = trials.assign(right=trials.decided == trials.target, late=trials.time_s == TIMES[-1])
    print("accuracy of the decisions taken before 2.0 s and of those forced at 2.0 s:")
    print(right.groupby(["decoder", "electrode", "late"]).right.mean().unstack("late").rename(columns={False: "before 2.0 s", True: "at 2.0 s"}).round(3).to_string())

    print("\n== 6. can the confidence be believed? decisions of the test people by confidence at the decision")
    r = reliability(trials)
    print(r.assign(confidence=r.confidence.round(3), correct=r.correct.round(3)).to_string(index=False))
    for (decoder, el), d in r.groupby(["decoder", "electrode"], sort=False):
        gap = np.average(np.abs(d.correct - d.confidence), weights=d.decisions)
        print(f"  {decoder:8s} {el}: mean confidence {np.average(d.confidence, weights=d.decisions):.3f}, accuracy "
              f"{np.average(d.correct, weights=d.decisions):.3f}, mean |gap| {gap:.3f}")

    print("\n== 7. the people for whom stopping helps least and most (template, ITR stopping minus fixed, bits/min)")
    for el in NAMES:
        p = people[(people.decoder == "template") & (people.electrode == el)]
        d = (p.itr - p.fixed_itr)
        rho = sps.spearmanr(p.fixed_accuracy, d)[0]
        print(f"  {el}: min {d.min():+.1f}, median {d.median():+.1f}, max {d.max():+.1f}; Spearman with the fixed-window accuracy {rho:+.2f}; "
              f"people with ITR 0 under both rules: {int(((p.itr == 0) & (p.fixed_itr == 0)).sum())}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(ms.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    cache = ms.prepare(args.raw, args.cache, args.jobs)
    OUT.mkdir(parents=True, exist_ok=True)
    settings, trials, by_window = analyse(cache)
    people = people_table(trials)
    settings.to_csv(OUT / "settings.csv", index=False, float_format="%.6g")
    trials.to_csv(OUT / "decisions.csv", index=False, float_format="%.4f")
    by_window.to_csv(OUT / "accuracy_by_window.csv", index=False, float_format="%.6f")
    people.to_csv(OUT / "people.csv", index=False, float_format="%.6f")
    reliability(trials).to_csv(OUT / "reliability.csv", index=False, float_format="%.6f")
    report(settings, trials, by_window, people)


if __name__ == "__main__":
    main()
