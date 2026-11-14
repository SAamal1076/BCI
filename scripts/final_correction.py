"""Correction of the final evaluation: the same analysis, with the saturated trial left out of the population template.

Plan: docs/milestones/final_correction_plan.md (approved by the author on 14 Nov 2026, before this file was written).

Why: M5 found that the dry population template contains the one trial of the dataset that reaches the limit of
the converter (S067, dry headband, block 4, target 4; flagged in M0 from the raw values, before any decoding).
That trial dominates the template's entry for the 9.75 Hz target. The plan of the final evaluation says: "If an
error is found afterwards, the original and the corrected result are both reported, with the reason."

What changes: the population template is built without the trials that M0 flagged as saturated. Nothing else.
Each person is decoded by the function of the opening (final_evaluation.evaluate_person) with the same networks,
the same people and the same 15 tests. The script of the opening is not edited.

THIS IS NOT A SECOND TEST. The results of the lockbox people had been seen when the correction was decided.
The corrected result is reported next to the original one and labelled as computed after the opening.

Two sets of people, as in final_evaluation.py:
  rehearsal   23 development people as new people, 45 as population (S067 is one of them). p-values withheld.
  lockbox     the 34 lockbox people, population = the 68 development people. ONE RUN, recorded in
              results/final/LOCKBOX_CORRECTION.txt and refused a second time.

Stages:
  prepare     population only, never a new person: the repaired template and its checksums (frozen.json),
              committed before the run.
  evaluate    decodes the new people, runs the tests, writes the tables, and makes the built-in check:
              everything that does not use the dry template must be identical to the original run.
  report      prints the two results side by side from the result files (no data needed).

Usage:
  python scripts/final_correction.py prepare  --set rehearsal --raw /path/to/13560281
  python scripts/final_correction.py evaluate --set rehearsal --raw /path/to/13560281
  python scripts/final_correction.py prepare  --set lockbox   --raw /path/to/13560281     (development people only)
  python scripts/final_correction.py evaluate --set lockbox   --raw /path/to/13560281 --correct-lockbox
        refused unless the lockbox has been opened and the commit is clean, and refused once it has been run;
        afterwards, --reproduce recomputes the same numbers into results/final/lockbox_corrected_reproduction.
"""
import argparse
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import final_evaluation as fe  # noqa: E402
import m3_common as c  # noqa: E402
from ssvep import lockbox as lb  # noqa: E402
from ssvep import metrics as mt  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FLAGS = ROOT / "results" / "m0" / "flagged_trials.csv"                # written in M0, label-free, all 102 people
MARKER = fe.OUT / "LOCKBOX_CORRECTION.txt"
NAMES = fe.NAMES
RULE = "A trial that M0 flagged as reaching the limit of the converter is not used to build the population template."
TEMPLATE_METHODS = ("template", "template_adapted")                   # the methods that use the population template
AFFECTED = (("H2", "dry"), ("H5a", "dry"), ("H5b", "dry"), ("H6", "dry"))          # the tests that use the dry template
FILES = ("accuracy.csv", "decisions_1s.csv", "impedance.csv", "tests.csv", "comparison.csv")
FROZEN_KEYS = ("new", "population", "flagged_saturated_trials", "left_out_of_the_template", "original_template_sha256",
               "template_sha256", "network_sha256")


# ---------------------------------------------------------------- the correction

def saturated_trials(path=FLAGS):
    """The trials that M0 flagged as saturated: sorted list of (subject, electrode, block, target), indices from 0."""
    d = pd.read_csv(path)
    d = d[d.saturated.astype(str).str.lower() == "true"]
    return sorted((int(r.subject), int(r.eeg_index) - 1, int(r.block) - 1, int(r.target) - 1) for r in d.itertuples())


def describe(trial):
    sid, e, b, t = trial
    return {"subject": sid, "electrode": NAMES[e], "block": b + 1, "target": t + 1}


def repaired_template(cache, population, electrode, excluded):
    """final_evaluation.population_template without the excluded trials: the mean response of a person to a target
    is taken over that person's other blocks. With nothing excluded for this headband the result is the same,
    bit for bit."""
    means = []
    for sid in population:
        x = c.load(cache, sid, electrode)                              # (block, target, band, channel, sample)
        m = x.mean(axis=0, dtype=float)
        mine = [(b, t) for s, e, b, t in excluded if s == sid and e == electrode]
        for target in sorted({t for _, t in mine}):
            keep = [b for b in range(x.shape[0]) if (b, target) not in mine]
            if not keep:
                raise ValueError(f"S{sid:03d}: no trial left for target {target + 1}")
            m[target] = x[keep, target].mean(axis=0, dtype=float)
        means.append(m)
    return np.mean(means, axis=0).transpose(1, 0, 2, 3)                # (band, target, channel, sample)


def changed_entries(original, repaired):
    """Targets whose template entry differs in at least one value."""
    return [int(t) for t in np.flatnonzero((original != repaired).any(axis=(0, 2, 3)))]


def folder(name: str, reproduce: bool = False) -> pathlib.Path:
    return fe.OUT / (f"{name}_corrected_reproduction" if reproduce else f"{name}_corrected")


def prepared(name, cache, flags=FLAGS):
    """Checksums of everything the new people will be decoded with, and the repaired templates."""
    sets, excluded, original = fe.people_sets(name), saturated_trials(flags), fe.prepared(name, cache)
    templates = [repaired_template(cache, sets["population"], e, excluded) for e in range(2)]
    info = {"set": name, "rule": RULE, "new": sets["new"], "population": sets["population"],
            "flagged_saturated_trials": [describe(t) for t in excluded],
            "left_out_of_the_template": [describe(t) for t in excluded if t[0] in sets["population"]],
            "original_template_sha256": original["template_sha256"],
            "template_sha256": {el: fe.sha(templates[e]) for e, el in enumerate(NAMES)},
            "network_sha256": original["network_sha256"]}
    return info, templates


def prepare(name, raw, cache, jobs, flags=FLAGS):
    """Population only. Checks that the original template and the networks are those of the original run, builds the
    repaired template, shows what it changes, writes the checksums."""
    sets, out = fe.people_sets(name), folder(name)
    cache = c.prepare(raw, cache, jobs)                                # development people only (asserted there)
    before = json.loads((fe.folder(name) / "frozen.json").read_text())
    info, templates = prepared(name, cache, flags)
    if info["original_template_sha256"] != before["template_sha256"] or info["network_sha256"] != before["network_sha256"]:
        raise lb.LockboxError("the original template or the networks differ from the frozen.json of the original run")
    excluded = saturated_trials(flags)
    print(f"set {name}: population {len(sets['population'])} development people; rule: {RULE}")
    print(f"trials flagged as saturated in M0 (all 102 people): {info['flagged_saturated_trials']}")
    print(f"of these, inside the population: {info['left_out_of_the_template']}")
    rms = lambda a, axes: np.sqrt((a.astype(float) ** 2).mean(axis=axes))        # noqa: E731
    for sid, e, b, t in excluded:
        if sid not in sets["population"]:
            continue
        size = rms(c.load(cache, sid, e)[:, t], (1, 2, 3))             # per block
        print(f"  S{sid:03d}, {NAMES[e]}, block {b + 1}, target {t + 1} ({wd.TARGET_FREQS[t]} Hz): size (rms after preprocessing) "
              f"{size[b]:.0f}; the person's 9 other trials of the target: median {np.median(np.delete(size, b)):.1f}")
    expected = {e: sorted({t for s, el, _, t in excluded if el == e and s in sets["population"]}) for e in range(2)}
    for e, el in enumerate(NAMES):
        original = fe.population_template(cache, sets["population"], e)
        changed = changed_entries(original, templates[e])
        size0, size1 = rms(original, (0, 2, 3)), rms(templates[e], (0, 2, 3))
        print(f"{el} template: entries that changed: targets {[t + 1 for t in changed]} (expected {[t + 1 for t in expected[e]]}); "
              f"checksum {'unchanged' if info['template_sha256'][el] == before['template_sha256'][el] else 'changed'}")
        for t in changed:
            others = np.delete(size1, changed)
            print(f"  target {t + 1} ({wd.TARGET_FREQS[t]} Hz): size of the entry {size0[t]:.2f} -> {size1[t]:.2f}; "
                  f"the other targets: median {np.median(others):.2f}")
        if changed != expected[e]:
            raise lb.LockboxError(f"{el} template: the repair changed other entries than the flagged ones")
    out.mkdir(parents=True, exist_ok=True)
    info["versions"] = {"numpy": np.__version__, "pandas": pd.__version__}
    (out / "frozen.json").write_text(json.dumps(info, indent=1))
    print(f"networks: the {len(info['network_sha256'])} files of the original run, checksums unchanged; "
          f"checksums written to {(out / 'frozen.json').relative_to(ROOT)}")


# ---------------------------------------------------------------- the run is made once

def authorise(name, correct_lockbox, reproduce, opening=fe.MARKER, marker=MARKER, git=fe._git):
    """Decides whether the lockbox people may be loaded for the correction. Returns (may be loaded, commit).
    Nothing is written here; the run is recorded by begin() just before the first person is decoded."""
    if name != "lockbox":
        return False, None
    if not correct_lockbox:
        raise lb.LockboxError("the lockbox set needs --correct-lockbox")
    if lb.state(opening) != "complete":
        raise lb.LockboxError("the correction comes after the opening; the lockbox has not been opened")
    if reproduce:
        if lb.state(marker) != "complete":
            raise lb.LockboxError("--reproduce is for after the corrected run; it has not been made")
        return True, None
    if lb.state(marker) == "complete":
        raise lb.LockboxError("the corrected analysis has already been run; it is run once (use --reproduce to recompute the same numbers)")
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise lb.LockboxError("the working tree has uncommitted changes; the corrected run needs a clean commit")
    return True, commit


def begin(marker, commit: str, when: str, resume: bool = False) -> None:
    """Record the corrected run before anyone is decoded. Refuses a second run. A run that was interrupted before
    it finished may be resumed from the same commit only."""
    marker = pathlib.Path(marker)
    now = lb.state(marker)
    if now == "closed":
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("The lockbox people were decoded a second time, AFTER THE OPENING, for the correction of the\n"
                          "population template (docs/milestones/final_correction_plan.md). Not a second test.\n"
                          f"started: {when}\ncommit: {commit}\nstatus: started\n")
        return
    if now == "complete":
        raise lb.LockboxError("the corrected analysis has already been run; it is run once")
    if not resume:
        raise lb.LockboxError("a corrected run was started and did not finish; it can only be resumed, from the same commit")
    if f"commit: {commit}\n" not in marker.read_text():
        raise lb.LockboxError("the interrupted run was started from another commit")
    with marker.open("a") as f:
        f.write(f"resumed: {when}\n")


def finish(marker, when: str, passed: bool) -> None:
    with pathlib.Path(marker).open("a") as f:
        f.write(f"built-in check against the opening: {'passed' if passed else 'FAILED'}\nfinished: {when}\nstatus: complete\n")


# ---------------------------------------------------------------- the built-in check and the comparison

def _text(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def affected_tests(tests):
    return np.array([(h, case) in AFFECTED for h, case in zip(tests.hypothesis, tests.case)])


def check(original, corrected):
    """Everything that does not use the dry template must be identical in the two sets of result files, as written.
    Returns (failures, {what: (number that changed, out of)})."""
    original, corrected = pathlib.Path(original), pathlib.Path(corrected)
    fail, changed = [], {}

    a, b = _text(original / "accuracy.csv"), _text(corrected / "accuracy.csv")
    keys = [col for col in a.columns if col not in ("accuracy", "pseudo_label_accuracy")]
    if a.shape != b.shape or not a[keys].equals(b[keys]):
        fail.append("accuracy.csv: not the same rows")
    else:
        dry = ((a.electrode == "dry") & a.method.isin(TEMPLATE_METHODS)).to_numpy()
        differ = ((a.accuracy != b.accuracy) | (a.pseudo_label_accuracy != b.pseudo_label_accuracy)).to_numpy()
        changed["accuracies that use the dry template"] = (int((differ & dry).sum()), int(dry.sum()))
        changed["all other accuracies"] = (int((differ & ~dry).sum()), int((~dry).sum()))
        if (differ & ~dry).any():
            fail.append(f"accuracy.csv: {int((differ & ~dry).sum())} accuracies that do not use the dry template differ")

    a, b = _text(original / "decisions_1s.csv"), _text(corrected / "decisions_1s.csv")
    keys = ["subject", "electrode", "block", "target"]
    if a.shape != b.shape or not a[keys].equals(b[keys]):
        fail.append("decisions_1s.csv: not the same rows")
    else:
        dry, differ = (a.electrode == "dry").to_numpy(), (a.template != b.template).to_numpy()
        changed["decisions of the dry template"] = (int((differ & dry).sum()), int(dry.sum()))
        changed["decisions of the wet template"] = (int((differ & ~dry).sum()), int((~dry).sum()))
        changed["decisions of FBCCA"] = (int((a.fbcca != b.fbcca).sum()), len(a))
        if (differ & ~dry).any():
            fail.append("decisions_1s.csv: decisions of the wet template differ")
        if (a.fbcca != b.fbcca).any():
            fail.append("decisions_1s.csv: decisions of FBCCA differ")

    same = (original / "impedance.csv").read_bytes() == (corrected / "impedance.csv").read_bytes()
    changed["impedance file"] = (0 if same else 1, 1)
    if not same:
        fail.append("impedance.csv: differs")

    a, b = _text(original / "tests.csv"), _text(corrected / "tests.csv")
    keys = ["test", "hypothesis", "case", "quantity", "n"]
    if a.shape != b.shape or list(a.columns) != list(b.columns) or not a[keys].equals(b[keys]):
        fail.append("tests.csv: not the same tests")
    else:
        uses = affected_tests(a)
        cols = ["estimate", "ci_low", "ci_high"] + (["p"] if "p" in a else [])
        differ = (a[cols] != b[cols]).any(axis=1).to_numpy()
        what = "estimate, interval" + (", p-value" if "p" in a else "")
        changed[f"tests that use the dry template ({what})"] = (int((differ & uses).sum()), int(uses.sum()))
        changed[f"the other tests ({what})"] = (int((differ & ~uses).sum()), int((~uses).sum()))
        if (differ & ~uses).any():
            fail.append(f"tests.csv: tests that do not use the dry template differ: {a.test[differ & ~uses].tolist()}")
    return fail, changed


def comparison(original, corrected):
    """The 15 tests, original and corrected side by side. 'supported_in_both' is the reading rule of the plan."""
    o, k = pd.read_csv(pathlib.Path(original) / "tests.csv"), pd.read_csv(pathlib.Path(corrected) / "tests.csv")
    t = o[["test", "hypothesis", "case", "quantity", "n"]].copy()
    t["uses_dry_template"] = affected_tests(o)
    for col in ["estimate", "ci_low", "ci_high"] + (["p", "p_holm", "supported"] if "p" in o else []):
        t[f"{col}_original"], t[f"{col}_corrected"] = o[col], k[col]
    if "supported" in o:
        t["supported_in_both"] = o.supported & k.supported
    return t


# ---------------------------------------------------------------- stage: evaluate (new people)

def evaluate(name, raw, cache, jobs, opened, reproduce, commit=None, resume=False, flags=FLAGS):
    sets, out, ref = fe.people_sets(name), folder(name, reproduce), fe.folder(name)
    cache = c.prepare(raw, cache, jobs)
    frozen = json.loads((folder(name) / "frozen.json").read_text())
    now, templates = prepared(name, cache, flags)
    same = all(frozen[key] == now[key] for key in FROZEN_KEYS)
    if not same and not reproduce:
        raise lb.LockboxError("the repaired template, the networks or the list of flagged trials differ from frozen.json")
    for f in FILES[:4]:
        if not (ref / f).exists():
            raise lb.LockboxError(f"the original result {f} is missing; the correction is compared with it")
    if name == "lockbox" and not reproduce:
        begin(MARKER, commit, fe.utc_now(), resume)                    # recorded before anyone is decoded
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(jobs, initializer=fe._init, initargs=(name, raw, opened, templates)) as pool:
        results = pool.map(fe.evaluate_person, sets["new"], chunksize=1)          # the function of the opening
    acc = pd.DataFrame([r for res in results for r in res[0]], columns=fe.COLUMNS)
    acc.insert(1, "first_headband", acc.subject.map(fe.first_headband(raw)))
    decisions = pd.DataFrame([r for res in results for r in res[1]], columns=["subject", "electrode", "block", "target", "template", "fbcca"])
    imp = fe.impedance(raw, sets["new"])
    tests = fe.run_tests(fe.quantities(acc, decisions, imp))           # the family of 15, Holm over all 15 again
    acc.to_csv(out / "accuracy.csv", index=False, float_format="%.6f")
    decisions.to_csv(out / "decisions_1s.csv", index=False)
    imp.to_csv(out / "impedance.csv", index=False, float_format="%.6f")
    (tests if name == "lockbox" else fe.withhold(tests)).to_csv(out / "tests.csv", index=False, float_format="%.6g")
    comparison(ref, out).to_csv(out / "comparison.csv", index=False, float_format="%.6g")
    fail, _ = check(ref, out)
    if name == "lockbox" and not reproduce:
        finish(MARKER, fe.utc_now(), not fail)
    print(f"set {name}: {len(sets['new'])} new people decoded with the repaired template of {len(sets['population'])} development people "
          f"in {time.time() - t0:.0f} s; frozen.json {'matches' if same else 'DIFFERS (reproduction on another machine?)'}")
    if reproduce:
        first = folder(name)
        for f in FILES:
            print(f"  {f}: {'identical to' if (out / f).read_bytes() == (first / f).read_bytes() else 'DIFFERENT from'} the corrected run")
    return not fail


# ---------------------------------------------------------------- stage: report

def ci(v, f="+.3f"):
    v = np.asarray(v, dtype=float)
    lo, hi = st.bootstrap_ci(v)
    return f"{v.mean():{f}} [{lo:{f}}, {hi:{f}}]"


def report(name, reproduce=False):
    ref, out = fe.folder(name), folder(name, reproduce)
    frozen = json.loads((folder(name) / "frozen.json").read_text())
    acc0, acc1 = pd.read_csv(ref / "accuracy.csv"), pd.read_csv(out / "accuracy.csv")
    dec0, dec1 = pd.read_csv(ref / "decisions_1s.csv"), pd.read_csv(out / "decisions_1s.csv")
    people = sorted(acc1.subject.unique())
    lockbox = name == "lockbox"
    print(f"== correction of the final evaluation, set '{name}': {len(people)} new people, population {len(frozen['population'])} "
          f"development people")
    print(f"rule: {RULE}")
    print(f"left out of the template: {frozen['left_out_of_the_template']}")
    if lockbox:
        print("COMPUTED AFTER THE OPENING. Not a second test: the original result stays the pre-specified one; both are reported.")

    print("\n== 1. built-in check: what does not use the dry template must be identical to the original run")
    fail, changed = check(ref, out)
    for what, (n, total) in changed.items():
        print(f"  {what}: {n} of {total} differ")
    print(f"  CHECK {'PASSED' if not fail else 'FAILED: ' + '; '.join(fail)}")
    if fail:
        print("  The check failed: nothing is concluded from this run.")
        return False

    print("\n== 2. the 15 tests, original | corrected (one-sided; Holm at familywise level 0.05 over all 15, in each analysis)")
    t = comparison(ref, out)
    show = t[["test", "hypothesis", "case"]].copy()
    show["dry template"] = np.where(t.uses_dry_template, "yes", "")
    for v in ("original", "corrected"):
        show[f"estimate [95 % interval], {v}"] = [f"{e:+.4f} [{lo:+.4f}, {hi:+.4f}]" for e, lo, hi in
                                                  zip(t[f"estimate_{v}"], t[f"ci_low_{v}"], t[f"ci_high_{v}"])]
    if lockbox:
        for v in ("original", "corrected"):
            show[f"p, {v}"], show[f"p (Holm), {v}"] = t[f"p_{v}"].map("{:.2g}".format), t[f"p_holm_{v}"].map("{:.2g}".format)
            show[f"supported, {v}"] = t[f"supported_{v}"]
        show["supported in both"] = t.supported_in_both
        print(show.to_string(index=False))
        print(f"supported after Holm: original {int(t.supported_original.sum())}, corrected {int(t.supported_corrected.sum())}, "
              f"in both {int(t.supported_in_both.sum())} of {len(t)}; decisions that differ: "
              f"{t.test[t.supported_original != t.supported_corrected].tolist()}")
        print("\n   reading rule fixed in the plan: a hypothesis is called supported only if it is supported in both analyses")
        for hyp, g in t.groupby("hypothesis", sort=False):
            word = lambda s: "supported" if s.all() else ("not supported" if not s.any() else f"mixed ({int(s.sum())} of {len(s)})")   # noqa: E731
            print(f"   {hyp:4s} original: {word(g.supported_original):22s} corrected: {word(g.supported_corrected):22s} "
                  f"in both: {word(g.supported_in_both)}")
    else:
        print(show.to_string(index=False))
        print("REHEARSAL: the tests were executed in both analyses; the p-values are withheld (development people).")

    print("\n== 3. accuracies that use the dry template, 1 s: mean over people, original | corrected | corrected minus original [95 % interval]")
    mean = lambda d: d[d.electrode == "dry"].groupby(["design", "method", "k", "subject"]).accuracy.mean()      # noqa: E731
    m0, m1 = mean(acc0), mean(acc1)
    rows = []
    for design, method, label in (("ten_blocks", "template", "all ten blocks, no calibration"), ("new_user", "template", "blocks 7 to 10"),
                                  ("new_user", "template_adapted", "blocks 7 to 10, adapted without labels")):
        for k in sorted(acc1[(acc1.design == design) & (acc1.method == method)].k.unique()):
            a, b = m0.loc[(design, method, k)].loc[people], m1.loc[(design, method, k)].loc[people]
            d = b - a
            rows.append({"method": method, "trials": label, "calibration blocks": k, "original": f"{a.mean():.3f}", "corrected": f"{b.mean():.3f}",
                         "difference": ci(d), "people better": int((d > 0).sum()), "equal": int((d == 0).sum()), "worse": int((d < 0).sum())})
    print(pd.DataFrame(rows).to_string(index=False))
    for label, acc in (("original", acc0), ("corrected", acc1)):
        a = acc[(acc.method == "template_adapted") & (acc.electrode == "dry")].pseudo_label_accuracy.mean()
        print(f"accuracy of the dry template's own decisions on blocks 1 to 6 (used as labels), {label}: {a:.3f}")

    print("\n== 4. the quantities of the four tests that use the dry template, and what is next to them (per person, 1 s)")
    f = lambda acc, method, k=0, el="dry": (acc[(acc.design == "new_user") & (acc.method == method) & (acc.k == k) & (acc.electrode == el)]   # noqa: E731
                                           .groupby("subject").accuracy.mean().loc[people])
    for label, acc in (("original", acc0), ("corrected", acc1)):
        print(f"  {label:9s} template minus FBCCA {ci(f(acc, 'template') - f(acc, 'fbcca'))}; adapted template minus FBCCA "
              f"{ci(f(acc, 'template_adapted') - f(acc, 'fbcca'))}; template + 2 blocks minus eTRCA + 6 blocks "
              f"{ci(f(acc, 'template', 2) - f(acc, 'etrca', 6))}")

    print("\n== 5. dry headband, template with no calibration, all ten blocks: accuracy by target, original | corrected")
    by = pd.DataFrame({"Hz": wd.TARGET_FREQS}, index=pd.RangeIndex(1, 13, name="target"))
    share = {}
    for label, dec in (("original", dec0), ("corrected", dec1)):
        d = dec[dec.electrode == "dry"]
        by[label] = d.assign(ok=d.template == d.target).groupby("target").ok.mean()
        share[label] = d.template.value_counts(normalize=True)
    by["difference"] = by.corrected - by.original
    print(by.round(3).to_string())
    for item in frozen["left_out_of_the_template"]:
        if item["electrode"] == "dry":
            t_ = item["target"]
            print(f"share of all dry decisions given to target {t_}: original {share['original'].get(t_, 0):.3f}, corrected "
                  f"{share['corrected'].get(t_, 0):.3f} (even: {1 / 12:.3f})")

    print("\n== 6. people not above chance with the dry template at 1 s over the ten blocks (120 trials)")
    thr = mt.chance_threshold(120, 12)
    for label, dec in (("original", dec0), ("corrected", dec1)):
        d = dec[dec.electrode == "dry"]
        a = d.assign(ok=d.template == d.target).groupby("subject").ok.mean()
        print(f"  {label:9s} below {thr:.3f}: {int((a < thr).sum())} of {len(a)}; {[f'S{s:03d}' for s in a.index[a < thr]]}")

    if lockbox:
        print("\n== 7. expectation written in the plan before the run, and the outcome (the four tests that use the dry template)")
        expected = {"H2": "stays supported", "H5a": "stays not supported", "H5b": "stays not supported", "H6": "uncertain"}
        for r in t[t.uses_dry_template].itertuples():
            print(f"  {r.hypothesis:3s} dry  expected: {expected[r.hypothesis]:19s} original: {'supported' if r.supported_original else 'not supported':13s} "
                  f"corrected: {'supported' if r.supported_corrected else 'not supported'}")
        d = m1.loc[("new_user", "template", 0)].loc[people] - m0.loc[("new_user", "template", 0)].loc[people]
        print(f"  dry accuracy of the template, blocks 7 to 10: expected to rise by about 0.01; it changed by {d.mean():+.3f}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prepare", "evaluate", "report"])
    ap.add_argument("--set", dest="name", choices=["rehearsal", "lockbox"], default="rehearsal")
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(c.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--correct-lockbox", action="store_true")
    ap.add_argument("--reproduce", action="store_true", help="after the corrected run: recompute into results/final/<set>_corrected_reproduction")
    ap.add_argument("--resume-interrupted", action="store_true", help="continue a corrected run that did not finish (same commit)")
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare(args.name, args.raw, args.cache, args.jobs)
        return
    if args.stage == "evaluate":
        opened, commit = authorise(args.name, args.correct_lockbox, args.reproduce)
        evaluate(args.name, args.raw, args.cache, args.jobs, opened, args.reproduce, commit, args.resume_interrupted)
    if not report(args.name, args.reproduce):
        sys.exit(1)


if __name__ == "__main__":
    main()
