"""Final evaluation on synthetic data: Holm, the Wilcoxon wrapper, the lockbox guard, the people, the 15 tests."""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import final_evaluation as fe  # noqa: E402
from ssvep import lockbox as lb  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import wearable as wd  # noqa: E402


def test_holm_stops_at_the_first_failure():
    supported, adjusted = st.holm([0.001, 0.04, 0.03, 0.005], alpha=0.05)
    # sorted: 0.001 <= 0.05/4, 0.005 <= 0.05/3, 0.03 > 0.05/2: stop; 0.04 is not supported although 0.04 <= 0.05/1
    assert supported.tolist() == [True, False, False, True]
    assert np.allclose(adjusted, [0.004, 0.06, 0.06, 0.015])
    assert st.holm([0.2], 0.05)[0].tolist() == [False] and st.holm([0.01] * 5, 0.05)[0].all()
    assert not st.holm([0.011] * 5, 0.05)[0].any() and st.holm([0.9, 0.8], 0.05)[1].max() <= 1.0
    rng = np.random.default_rng(0)                                      # familywise error under the null stays below alpha
    false_alarm = np.mean([st.holm(rng.uniform(size=15), 0.05)[0].any() for _ in range(4000)])
    assert false_alarm < 0.065


def test_wilcoxon_wrapper_drops_zeros_and_keeps_the_direction():
    assert st.wilcoxon_one_sided(np.zeros(12), "greater") == 1.0 and st.wilcoxon_one_sided(np.zeros(12), "less") == 1.0
    v = np.array([0.10, 0.21, 0.32, -0.05, 0.26, 0.15, 0.43, 0.08])
    with_zeros = np.concatenate([v, np.zeros(6)])
    assert st.wilcoxon_one_sided(with_zeros, "greater") == st.wilcoxon_one_sided(v, "greater") < 0.05
    assert st.wilcoxon_one_sided(v, "less") > 0.9
    assert np.isclose(st.wilcoxon_one_sided(v + 0.05, "greater"), st.noninferiority_test(v, np.zeros(8), 0.05))


def test_intervals_cover_a_planted_effect():
    rng = np.random.default_rng(2)
    first = np.arange(34) % 2 == 0
    d = -0.15 + np.where(first, 0.04, -0.04) + 0.05 * rng.standard_normal(34)     # treatment -0.15, period effect 0.04
    lo, hi = st.crossover_ci(d, first)
    assert lo < -0.15 < hi and hi - lo < 0.08 and abs(st.crossover_effect(d, first) + 0.15) < 0.03
    x = rng.standard_normal(34)
    lo, hi = st.spearman_ci(x, -x + 0.5 * rng.standard_normal(34))
    assert lo < hi < 0


def test_a_lockbox_person_cannot_be_loaded_without_the_opening(tmp_path):
    lb.require_access(1, opened=False)
    lb.require_access(3, opened=True)
    with pytest.raises(lb.LockboxError):
        lb.require_access(3, opened=False)
    fe._STATE.update(raw=tmp_path / "no_such_folder", opened=False, templates=None, models=None)
    with pytest.raises(lb.LockboxError):                               # refused before any file is looked for
        fe.evaluate_person(6)
    fe._STATE.clear()


def test_the_lockbox_opens_once(tmp_path):
    marker = tmp_path / "final" / lb.MARKER_NAME
    assert lb.state(marker) == "closed"
    lb.begin(marker, "abc123", "2026-11-13T20:00:00+00:00")
    assert lb.state(marker) == "started" and "commit: abc123" in marker.read_text()
    with pytest.raises(lb.LockboxError):                               # a second start is refused
        lb.begin(marker, "abc123", "later")
    with pytest.raises(lb.LockboxError):                               # an interrupted opening resumes from the same commit only
        lb.begin(marker, "other", "later", resume=True)
    lb.begin(marker, "abc123", "later", resume=True)
    lb.finish(marker, "end")
    assert lb.state(marker) == "complete"
    for resume in (False, True):
        with pytest.raises(lb.LockboxError):
            lb.begin(marker, "abc123", "again", resume=resume)


def test_authorisation_of_the_opening(tmp_path):
    marker = tmp_path / lb.MARKER_NAME
    clean = {("rev-parse", "HEAD"): "c1", ("status", "--porcelain", "--untracked-files=no"): "", ("rev-parse", "pre-lockbox^{commit}"): "c1"}
    git = lambda table: (lambda *args: table[args])                    # noqa: E731
    assert fe.authorise("rehearsal", False, False, marker, git(clean)) == (False, None)
    with pytest.raises(lb.LockboxError):                               # the flag is needed
        fe.authorise("lockbox", False, False, marker, git(clean))
    with pytest.raises(lb.LockboxError):                               # uncommitted changes
        fe.authorise("lockbox", True, False, marker, git({**clean, ("status", "--porcelain", "--untracked-files=no"): " M x.py"}))
    with pytest.raises(lb.LockboxError):                               # not the tagged commit
        fe.authorise("lockbox", True, False, marker, git({**clean, ("rev-parse", "pre-lockbox^{commit}"): "c0"}))
    with pytest.raises(lb.LockboxError):                               # nothing to reproduce before the opening
        fe.authorise("lockbox", True, True, marker, git(clean))
    assert fe.authorise("lockbox", True, False, marker, git(clean)) == (True, "c1") and not marker.exists()
    lb.begin(marker, "c1", "t0")
    lb.finish(marker, "t1")
    with pytest.raises(lb.LockboxError):                               # opened once
        fe.authorise("lockbox", True, False, marker, git(clean))
    assert fe.authorise("lockbox", True, True, marker, git(clean)) == (True, None)


def test_new_people_never_meet_the_population():
    r, box = fe.people_sets("rehearsal"), fe.people_sets("lockbox")
    assert (len(r["new"]), len(r["population"]), len(r["train"]), len(r["validation"])) == (23, 45, 38, 7)
    assert (len(box["new"]), len(box["population"]), len(box["train"]), len(box["validation"])) == (34, 68, 57, 11)
    assert not any(wd.is_lockbox(s) for s in r["new"] + r["population"])
    assert set(box["new"]) == set(wd.LOCKBOX) and set(box["population"]) == set(wd.DEVELOPMENT)
    for sets in (r, box):
        assert not set(sets["new"]) & set(sets["population"]) and not set(sets["train"]) & set(sets["validation"])
        assert set(sets["train"]) | set(sets["validation"]) == set(sets["population"])
    with pytest.raises(lb.LockboxError):
        lb.check_disjoint([1, 2], [2, 4], [2], [4])
    with pytest.raises(lb.LockboxError):
        lb.check_disjoint([1], [2, 3], [2], [3])                       # a lockbox person in the population
    with pytest.raises(lb.LockboxError):
        lb.check_disjoint([1], [2, 4, 5], [2], [4])                    # the split does not cover the population


def _synthetic(n=34, seed=0):
    """Accuracy tables of n people with planted effects: dry 0.2 below wet, adapted template +0.05, the rest null."""
    rng = np.random.default_rng(seed)
    people = np.arange(1, n + 1)
    first = {s: "Dry" if s % 2 else "Wet" for s in people}
    rows, decisions, imp = [], [], []
    for s in people:
        skill = 0.1 * rng.standard_normal()
        for el, base in (("dry", 0.55), ("wet", 0.75)):
            a = float(np.clip(base + skill, 0.05, 0.95))
            noise = lambda: 0.03 * rng.standard_normal()               # noqa: E731
            for window in (1.0, 2.0):
                for method in ("fbcca", "etrca_lobo"):
                    rows.append((s, el, "ten_blocks", method, window, 0, -1, a + noise(), np.nan))
            rows.append((s, el, "ten_blocks", "template", 1.0, 0, -1, a, np.nan))
            rows.append((s, el, "new_user", "template", 1.0, 0, -1, a + noise(), np.nan))
            rows.append((s, el, "new_user", "template_adapted", 1.0, 0, -1, a + 0.05 + noise(), 0.6))
            rows.append((s, el, "new_user", "template", 1.0, 2, -1, a + 0.04 + noise(), np.nan))
            rows.append((s, el, "new_user", "etrca", 1.0, 6, -1, a + noise(), np.nan))
            for seed_ in (0, 1, 2):
                rows.append((s, el, "new_user", "net_A0", 1.0, 0, seed_, a + noise(), np.nan))
                rows.append((s, el, "new_user", "net_A2", 1.0, 0, seed_, a + noise(), np.nan))
            correct = rng.uniform(size=120) < a
            decisions += [(s, el, t // 12 + 1, t % 12 + 1, t % 12 + 1 if correct[t] else (t + 1) % 12 + 1, 1) for t in range(120)]
            imp.append((s, el, rng.standard_normal()))
    acc = pd.DataFrame(rows, columns=fe.COLUMNS)
    acc.insert(1, "first_headband", acc.subject.map(first))
    return (acc, pd.DataFrame(decisions, columns=["subject", "electrode", "block", "target", "template", "fbcca"]),
            pd.DataFrame(imp, columns=["subject", "electrode", "log10_median_kohm"]))


def test_the_family_of_15_tests_finds_what_was_planted_and_nothing_else():
    t = fe.run_tests(fe.quantities(*_synthetic()))
    assert len(t) == 15 and t.hypothesis.tolist() == ["H1"] * 4 + ["H2"] * 2 + ["H3"] * 3 + ["H5a"] * 2 + ["H5b"] * 2 + ["H6"] * 2
    by = t.groupby("hypothesis").supported
    assert by.all()["H1"] and by.all()["H2"] and by.all()["H6"]         # planted: dry below wet, k=2 not worse, adaptation helps
    assert not by.any()["H3"] and not by.any()["H5a"] and not by.any()["H5b"]
    h1 = t[t.hypothesis == "H1"]
    assert (h1.estimate < -0.15).all() and (h1.ci_high < 0).all() and (t.n == 34).all()
    assert np.allclose(np.sort(t.holm_threshold), 0.05 / np.arange(15, 0, -1)) and (t.p_holm >= t.p).all()


def test_the_rehearsal_keeps_no_p_value():
    t = fe.withhold(fe.run_tests(fe.quantities(*_synthetic(n=23, seed=1))))
    assert len(t) == 15 and t.p_computed.all()
    assert not {"p", "p_holm", "holm_threshold", "supported"} & set(t.columns)
    assert {"estimate", "ci_low", "ci_high", "n"} <= set(t.columns)
