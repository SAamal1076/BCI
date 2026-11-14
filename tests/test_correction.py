"""Correction of the final evaluation on synthetic data: the flagged trials, the repaired template, the single
corrected run, the built-in check, the reading rule."""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import final_correction as fc  # noqa: E402
import final_evaluation as fe  # noqa: E402
from ssvep import lockbox as lb  # noqa: E402
from ssvep import wearable as wd  # noqa: E402
from test_final import _synthetic  # noqa: E402

STATUS = ("status", "--porcelain", "--untracked-files=no")


def test_the_flagged_trials_come_from_the_m0_file(tmp_path):
    assert fc.saturated_trials() == [(67, wd.DRY, 3, 3)]              # the committed M0 result: one trial in the dataset
    assert not wd.is_lockbox(67) and wd.TARGET_FREQS[3] == 9.75
    path = tmp_path / "flags.csv"
    pd.DataFrame({"subject": [5, 2, 2, 7], "eeg_index": [2, 1, 1, 1], "block": [10, 4, 1, 2], "target": [12, 4, 1, 3],
                  "saturated": [True, True, False, False]}).to_csv(path, index=False)
    assert fc.saturated_trials(path) == [(2, 0, 3, 3), (5, 1, 9, 11)]
    assert fc.describe((2, 0, 3, 3)) == {"subject": 2, "electrode": "dry", "block": 4, "target": 4}


def _cache(folder, people=(1, 2, 4), spoiled=(2, 0, 3, 3)):
    """Small cache in the layout of m3_common: [electrode, block, target, band, channel, sample]; one huge trial."""
    rng = np.random.default_rng(0)
    for sid in people:
        x = rng.standard_normal((2, 10, 12, 3, 2, 6)).astype(np.float32)
        if sid == spoiled[0]:
            x[spoiled[1], spoiled[2], spoiled[3]] *= 300
        np.save(folder / f"S{sid:03d}.npy", x)
    return folder


def test_the_repaired_template_differs_only_where_a_trial_was_left_out(tmp_path):
    cache, people, excluded = _cache(tmp_path), [1, 2, 4], [(2, 0, 3, 3)]
    for e in range(2):                                                 # nothing left out: the bits of the opening
        assert np.array_equal(fc.repaired_template(cache, people, e, []), fe.population_template(cache, people, e))
    dry0, wet0 = (fe.population_template(cache, people, e) for e in range(2))
    dry, wet = (fc.repaired_template(cache, people, e, excluded) for e in range(2))
    assert np.array_equal(wet, wet0) and fc.changed_entries(wet0, wet) == []
    assert fc.changed_entries(dry0, dry) == [3]
    others = [t for t in range(12) if t != 3]
    assert np.array_equal(dry[:, others], dry0[:, others])             # the 11 other targets: the same bits
    x = {sid: np.load(cache / f"S{sid:03d}.npy")[0].astype(float) for sid in people}          # (block, target, band, ch, n)
    keep = [b for b in range(10) if b != 3]
    want = np.mean([x[1][:, 3].mean(axis=0), x[2][keep, 3].mean(axis=0), x[4][:, 3].mean(axis=0)], axis=0)
    assert np.allclose(dry[:, 3], want)                                # that person's mean from the 9 other blocks
    assert np.abs(dry0[:, 3]).max() > 5 * np.abs(dry[:, 3]).max()     # one trial dominated the entry before
    # a flagged trial of someone outside the population changes nothing
    assert np.array_equal(fc.repaired_template(cache, [1, 4], 0, excluded), fe.population_template(cache, [1, 4], 0))
    two = fc.repaired_template(cache, people, 0, [(2, 0, 3, 3), (2, 0, 5, 3)])
    keep = [b for b in range(10) if b not in (3, 5)]
    assert np.allclose(two[:, 3], np.mean([x[1][:, 3].mean(axis=0), x[2][keep, 3].mean(axis=0), x[4][:, 3].mean(axis=0)], axis=0))
    with pytest.raises(ValueError):                                    # no trial left for a target
        fc.repaired_template(cache, people, 0, [(2, 0, b, 3) for b in range(10)])


def test_the_corrected_run_is_made_once_and_after_the_opening(tmp_path):
    opening, marker = tmp_path / lb.MARKER_NAME, tmp_path / "LOCKBOX_CORRECTION.txt"
    clean = {("rev-parse", "HEAD"): "c9", STATUS: ""}
    git = lambda table: (lambda *args: table[args])                    # noqa: E731
    assert fc.authorise("rehearsal", False, False, opening, marker, git(clean)) == (False, None)
    with pytest.raises(lb.LockboxError):                               # the flag is needed
        fc.authorise("lockbox", False, False, opening, marker, git(clean))
    with pytest.raises(lb.LockboxError):                               # the lockbox has not been opened
        fc.authorise("lockbox", True, False, opening, marker, git(clean))
    lb.begin(opening, "c1", "t0")
    with pytest.raises(lb.LockboxError):                               # an opening that did not finish
        fc.authorise("lockbox", True, False, opening, marker, git(clean))
    lb.finish(opening, "t1")
    with pytest.raises(lb.LockboxError):                               # uncommitted changes
        fc.authorise("lockbox", True, False, opening, marker, git({**clean, STATUS: " M x.py"}))
    with pytest.raises(lb.LockboxError):                               # nothing to reproduce before the run
        fc.authorise("lockbox", True, True, opening, marker, git(clean))
    assert fc.authorise("lockbox", True, False, opening, marker, git(clean)) == (True, "c9") and not marker.exists()

    fc.begin(marker, "c9", "t2")
    text = marker.read_text()
    assert lb.state(marker) == "started" and "AFTER THE OPENING" in text and "Not a second test" in text and "commit: c9\n" in text
    with pytest.raises(lb.LockboxError):                               # a second start is refused
        fc.begin(marker, "c9", "t3")
    with pytest.raises(lb.LockboxError):                               # an interrupted run resumes from the same commit only
        fc.begin(marker, "other", "t3", resume=True)
    fc.begin(marker, "c9", "t3", resume=True)
    fc.finish(marker, "t4", passed=True)
    assert lb.state(marker) == "complete" and "check against the opening: passed" in marker.read_text()
    with pytest.raises(lb.LockboxError):                               # run once
        fc.authorise("lockbox", True, False, opening, marker, git(clean))
    for resume in (False, True):
        with pytest.raises(lb.LockboxError):
            fc.begin(marker, "c9", "again", resume=resume)
    assert fc.authorise("lockbox", True, True, opening, marker, git(clean)) == (True, None)
    assert opening.read_text().count("status: complete") == 1          # the record of the opening is not touched
    assert fc.MARKER.name == "LOCKBOX_CORRECTION.txt" and fc.MARKER != fe.MARKER
    assert fc.folder("lockbox") != fe.folder("lockbox") and fc.folder("lockbox", True) != fc.folder("lockbox")


def _write(folder, acc, decisions, imp, lockbox=True):
    folder.mkdir()
    tests = fe.run_tests(fe.quantities(acc, decisions, imp))
    acc.to_csv(folder / "accuracy.csv", index=False, float_format="%.6f")
    decisions.to_csv(folder / "decisions_1s.csv", index=False)
    imp.to_csv(folder / "impedance.csv", index=False, float_format="%.6f")
    (tests if lockbox else fe.withhold(tests)).to_csv(folder / "tests.csv", index=False, float_format="%.6g")
    return folder


def _repaired(acc, decisions, seed=3):
    """Change only what uses the dry template: its accuracies, and some of its wrong decisions become right."""
    rng = np.random.default_rng(seed)
    acc, decisions = acc.copy(), decisions.copy()
    dry = ((acc.electrode == "dry") & acc.method.isin(fc.TEMPLATE_METHODS)).to_numpy()
    acc.loc[dry, "accuracy"] = acc.accuracy[dry] + 0.02 + 0.04 * rng.standard_normal(int(dry.sum()))
    wrong = ((decisions.electrode == "dry") & (decisions.template != decisions.target)).to_numpy()
    fix = wrong & (rng.uniform(size=len(decisions)) < 0.3)
    decisions.loc[fix, "template"] = decisions.target[fix]
    return acc, decisions


def test_the_built_in_check_and_the_four_tests_that_may_change(tmp_path):
    acc, decisions, imp = _synthetic()
    original = _write(tmp_path / "original", acc, decisions, imp)
    acc1, dec1 = _repaired(acc, decisions)
    corrected = _write(tmp_path / "corrected", acc1, dec1, imp)
    fail, changed = fc.check(original, corrected)
    assert not fail
    assert changed["all other accuracies"][0] == 0 and changed["accuracies that use the dry template"][0] > 0
    assert changed["decisions of the wet template"][0] == 0 and changed["decisions of FBCCA"][0] == 0
    assert changed["decisions of the dry template"][0] > 0 and changed["impedance file"] == (0, 1)
    assert changed["tests that use the dry template (estimate, interval, p-value)"] == (4, 4)
    assert changed["the other tests (estimate, interval, p-value)"] == (0, 11)

    t = fc.comparison(original, corrected)                             # the four tests named in the plan, and only they
    assert t.test[t.uses_dry_template].tolist() == [5, 10, 12, 14]
    assert t[t.uses_dry_template].hypothesis.tolist() == ["H2", "H5a", "H5b", "H6"] and (t[t.uses_dry_template].case == "dry").all()
    same = (t.estimate_original == t.estimate_corrected) & (t.p_original == t.p_corrected)
    assert same[~t.uses_dry_template].all() and not same[t.uses_dry_template].any()
    assert (t.supported_in_both == (t.supported_original & t.supported_corrected)).all()      # the reading rule
    assert fc.check(original, original)[0] == []

    def broken(name, change):                                          # anything else that moves is a failure
        a, d, i = acc1.copy(), dec1.copy(), imp.copy()
        change(a, d, i)
        return fc.check(original, _write(tmp_path / name, a, d, i))[0]

    wet_template = acc1.index[(acc1.electrode == "wet") & (acc1.method == "template")][0]
    dry_fbcca = acc1.index[(acc1.electrode == "dry") & (acc1.method == "fbcca")][0]
    wet_decision = dec1.index[dec1.electrode == "wet"][0]

    def wet_accuracy(a, d, i):
        a.loc[wet_template, "accuracy"] += 0.01

    def fbcca_accuracy(a, d, i):
        a.loc[dry_fbcca, "accuracy"] += 0.01

    def wet_template_decision(a, d, i):
        d.loc[wet_decision, "template"] = d.template[wet_decision] % 12 + 1

    def fbcca_decision(a, d, i):
        d.loc[0, "fbcca"] = 2

    def impedance(a, d, i):
        i.loc[0, "log10_median_kohm"] += 0.1

    for k, change in enumerate((wet_accuracy, fbcca_accuracy, wet_template_decision, fbcca_decision, impedance)):
        assert broken(f"broken{k}", change), change.__name__
    assert fc.check(original, _write(tmp_path / "fewer", acc1[acc1.subject != 1], dec1, imp))[0]


def test_the_rehearsal_of_the_correction_keeps_no_p_value(tmp_path):
    acc, decisions, imp = _synthetic(n=23, seed=1)
    original = _write(tmp_path / "original", acc, decisions, imp, lockbox=False)
    corrected = _write(tmp_path / "corrected", *_repaired(acc, decisions), imp, lockbox=False)
    fail, changed = fc.check(original, corrected)
    assert not fail and changed["the other tests (estimate, interval)"] == (0, 11)
    t = fc.comparison(original, corrected)
    assert len(t) == 15 and not [col for col in t.columns if col.startswith(("p_", "supported"))]
    assert {"estimate_original", "estimate_corrected", "ci_low_corrected", "uses_dry_template"} <= set(t.columns)
