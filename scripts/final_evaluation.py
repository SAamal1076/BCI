"""Final evaluation: every quantity and the 15 tests for NEW people, given a POPULATION of other people.

Plan: docs/milestones/final_evaluation_plan.md (approved before this file was written).

Two sets of people, one code path:
  rehearsal   new = every third development person (23), population = the other 45 development people.
              The lockbox is not touched. The tests are executed, their p-values are withheld.
  lockbox     new = the 34 lockbox people, population = the 68 development people. ONE OPENING.

Stages:
  prepare     population only, never a new person: cache of the 1 s trials, population template, six networks
              (2 headbands x 3 seeds). For the lockbox set this stage uses development people only, so it is
              run and committed BEFORE the opening; frozen.json holds the checksums of what was prepared.
  evaluate    decodes the new people, runs the tests, writes the tables.
  report      prints the tables again from the result files (no data needed).

Everything is frozen (M2, M3): pipeline B2, n0 = 4, calibration = first k blocks, test = blocks 7 to 10.

Usage:
  python scripts/final_evaluation.py prepare  --set rehearsal --raw /path/to/13560281
  python scripts/final_evaluation.py evaluate --set rehearsal --raw /path/to/13560281
  python scripts/final_evaluation.py prepare  --set lockbox   --raw /path/to/13560281     (development people only)
  python scripts/final_evaluation.py evaluate --set lockbox   --raw /path/to/13560281 --open-lockbox
        refused unless the commit is clean and tagged pre-lockbox, and refused once the lockbox has been opened;
        afterwards, --reproduce recomputes the same numbers into results/final/lockbox_reproduction.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from scipy.io import loadmat  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m3_common as c  # noqa: E402
from ssvep import adapt as ad  # noqa: E402
from ssvep import decoders as dc  # noqa: E402
from ssvep import lockbox as lb  # noqa: E402
from ssvep import metrics as mt  # noqa: E402
from ssvep import network as nw  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import transfer as tr  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

PIPELINE, N0, MARGIN, ALPHA = "B2", 4.0, 0.05, 0.05                   # frozen in M2 and in the plans
WINDOWS, K_BLOCKS, SEEDS = (1.0, 2.0), (1, 2, 4, 6), (0, 1, 2)
NAMES = wd.ELECTRODE_NAMES
OUT = ROOT / "results" / "final"
MARKER = OUT / lb.MARKER_NAME
COLUMNS = ["subject", "electrode", "design", "method", "window_s", "k", "seed", "accuracy", "pseudo_label_accuracy"]
_STATE = {}


# ---------------------------------------------------------------- people

def people_sets(name: str):
    """New people, population, and the split of the population into training and validation people
    (rule of M3: every 6th person of the sorted population, starting with the 4th, is a validation person)."""
    dev = sorted(wd.DEVELOPMENT)
    if name == "rehearsal":
        new = dev[0::3]
        population = [p for p in dev if p not in new]
    elif name == "lockbox":
        new, population = list(wd.LOCKBOX), dev
    else:
        raise ValueError(name)
    validation = population[3::6]
    train = [p for p in population if p not in validation]
    lb.check_disjoint(new, population, train, validation)
    return {"new": new, "population": population, "train": train, "validation": validation}


def folder(name: str, reproduce: bool = False) -> pathlib.Path:
    return OUT / (f"{name}_reproduction" if reproduce else name)


# ---------------------------------------------------------------- stage: prepare (population only)

def population_template(cache, population, electrode):
    """Mean response per target over the population, (band, target, channel, sample). As in M3."""
    mean = np.mean([c.load(cache, sid, electrode).mean(axis=0, dtype=float) for sid in population], axis=0)
    return mean.transpose(1, 0, 2, 3)


def sha(a) -> str:
    data = a if isinstance(a, bytes) else np.ascontiguousarray(a).tobytes()
    return hashlib.sha256(data).hexdigest()


def train_one(job):
    name, electrode, seed, cache = job
    torch.set_num_threads(1)
    sets = people_sets(name)
    x, y = c.labelled(cache, sets["train"], electrode)
    xv, yv = c.labelled(cache, sets["validation"], electrode)
    t0 = time.time()
    model, history = nw.train(nw.standardise(x), y, nw.standardise(xv), yv, seed)
    best = int(np.argmin([h[2] for h in history]))
    stem = folder(name) / "models" / f"{NAMES[electrode]}_seed{seed}"
    torch.save(model.state_dict(), stem.with_suffix(".pt"))
    info = {"electrode": NAMES[electrode], "seed": seed, "train_people": len(sets["train"]),
            "validation_people": len(sets["validation"]), "train_trials": len(x), "epochs_run": len(history),
            "best_epoch": history[best][0], "validation_loss": round(history[best][2], 4),
            "validation_accuracy": round(history[best][3], 4), "train_seconds": round(time.time() - t0, 1)}
    stem.with_suffix(".json").write_text(json.dumps(info))
    return info


def prepared(name, cache):
    """Checksums of everything the new people will be decoded with."""
    sets, models = people_sets(name), folder(name) / "models"
    return {"set": name, **sets,
            "template_sha256": {el: sha(population_template(cache, sets["population"], e)) for e, el in enumerate(NAMES)},
            "network_sha256": {f"{el}_seed{s}": sha((models / f"{el}_seed{s}.pt").read_bytes()) for el in NAMES for s in SEEDS}}


def prepare(name, raw, cache, jobs):
    sets, models = people_sets(name), folder(name) / "models"
    models.mkdir(parents=True, exist_ok=True)
    cache = c.prepare(raw, cache, jobs)                                # development people only (asserted there)
    todo = [(name, e, s, cache) for e in range(2) for s in SEEDS if not (models / f"{NAMES[e]}_seed{s}.json").exists()]
    print(f"set {name}: population {len(sets['population'])} development people ({len(sets['train'])} for training, "
          f"{len(sets['validation'])} for validation); {6 - len(todo)} networks already trained, {len(todo)} to train", flush=True)
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(jobs) as pool:
        for info in pool.imap_unordered(train_one, todo):
            print(json.dumps(info), flush=True)
    log = pd.DataFrame([json.loads(p.read_text()) for p in sorted(models.glob("*.json"))])
    log.to_csv(folder(name) / "training_log.csv", index=False)
    frozen = prepared(name, cache)
    frozen["versions"] = {"numpy": np.__version__, "torch": torch.__version__, "pandas": pd.__version__}
    (folder(name) / "frozen.json").write_text(json.dumps(frozen, indent=1))
    print(f"networks: {len(log)}; epochs run {log.epochs_run.min()} to {log.epochs_run.max()}; validation accuracy "
          f"{log.validation_accuracy.mean():.3f}; checksums written to {(folder(name) / 'frozen.json').relative_to(ROOT)}")


# ---------------------------------------------------------------- stage: evaluate (new people)

def _init(name, raw, opened, templates):
    torch.set_num_threads(1)
    models = {}
    for e, el in enumerate(NAMES):
        for s in SEEDS:
            models[(e, s)] = nw.Net()
            models[(e, s)].load_state_dict(torch.load(folder(name) / "models" / f"{el}_seed{s}.pt"))
    _STATE.update(raw=raw, opened=opened, templates=templates, models=models)


def evaluate_person(sid):
    """Every accuracy of one new person. Returns (rows of COLUMNS, decisions at 1 s over the ten blocks)."""
    s = _STATE
    lb.require_access(sid, s["opened"])                               # before any file is read
    x = wd.load_subject(s["raw"], sid)
    w = pp.weights(PIPELINE)
    rows, decisions = [], []

    def add(el, design, method, window, k, seed, correct, extra=np.nan):
        rows.append((sid, el, design, method, window, k, seed, float(np.mean(correct)), extra))

    for window in WINDOWS:
        n = int(round(window * wd.FS))
        sub = pp.subbands(x, n, PIPELINE, wd.RESP_START, wd.FS)        # (band, electrode, block, target, ch, n)
        bases = dc.reference_bases(wd.TARGET_FREQS, n, wd.FS, pp.N_HARM[PIPELINE])
        rho = dc.cca_corr(sub, bases)
        for e, el in enumerate(NAMES):                                 # the person's own ten blocks (H1), as in M2
            r_ens = dc.trca_leave_one_block_out(sub[:, e])[1]
            add(el, "ten_blocks", "fbcca", window, 0, -1, dc.fbcca_scores(rho[:, e], w).argmax(axis=-1) == np.arange(12))
            add(el, "ten_blocks", "etrca_lobo", window, 0, -1, dc.fb_combine_signed(r_ens, w).argmax(axis=-1) == np.arange(12))
        if window != 1.0:
            continue
        sub = sub - sub.mean(axis=-1, keepdims=True)
        labels, labels_unl, labels_all = np.tile(np.arange(12), 4), np.tile(np.arange(12), 6), np.tile(np.arange(12), 10)
        for e, el in enumerate(NAMES):
            data, population = sub[:, e], s["templates"][e]            # (band, block, target, ch, n), (band, target, ch, n)
            bands = data.shape[0]

            # all ten blocks with no calibration (H5), as in M4
            part = tr.trial_part(data.reshape(bands, 120, *data.shape[3:]), bases)
            template = tr.ecca_scores(part, population, bases, w).argmax(axis=-1)
            fbcca = dc.fbcca_scores(part[0], w).argmax(axis=-1)
            add(el, "ten_blocks", "template", window, 0, -1, template == labels_all)
            decisions += [(sid, el, b + 1, t + 1, p + 1, q + 1)
                          for b, t, p, q in zip(np.repeat(np.arange(10), 12), labels_all, template, fbcca)]

            # new user: calibration = first k blocks, test = blocks 7 to 10 (H2), as in M2
            test = data[:, list(tr.TEST_BLOCKS)].reshape(bands, 48, *data.shape[3:])
            part = tr.trial_part(test, bases)
            add(el, "new_user", "fbcca", window, 0, -1, dc.fbcca_scores(part[0], w).argmax(axis=-1) == labels)
            add(el, "new_user", "template", window, 0, -1, tr.ecca_scores(part, population, bases, w).argmax(axis=-1) == labels)
            for k in K_BLOCKS:
                cal_blocks, test_blocks = tr.split_blocks(k)
                assert not set(cal_blocks) & set(test_blocks)
                cal = data[:, list(cal_blocks)]
                own = cal.mean(axis=1)
                add(el, "new_user", "own", window, k, -1, tr.ecca_scores(part, own, bases, w).argmax(axis=-1) == labels)
                add(el, "new_user", "template", window, k, -1,
                    tr.ecca_scores(part, tr.combined_template(population, own, k, N0), bases, w).argmax(axis=-1) == labels)
                if k >= 2:
                    sum_x = cal.sum(axis=1)
                    filters = dc.trca_filters(sum_x, (cal @ np.swapaxes(cal, -1, -2)).sum(axis=1))
                    r_ens = np.stack([dc.trca_corr(test[b], sum_x[b] / k, filters[b])[1] for b in range(bands)])
                    add(el, "new_user", "etrca", window, k, -1, dc.fb_combine_signed(r_ens, w).argmax(axis=-1) == labels)

            # adaptation without labels on blocks 1 to 6 (H6, H3), as in M3
            unl = data[:, :6].reshape(bands, 72, *data.shape[3:])
            decided = tr.ecca_scores(tr.trial_part(unl, bases), population, bases, w).argmax(axis=-1)
            adapted = population.copy()
            for f in range(wd.N_TARGETS):
                m = int((decided == f).sum())
                if m:
                    adapted[:, f] = (N0 * population[:, f] + m * unl[:, decided == f].mean(axis=1)) / (N0 + m)
            add(el, "new_user", "template_adapted", window, 0, -1, tr.ecca_scores(part, adapted, bases, w).argmax(axis=-1) == labels,
                float(np.mean(decided == labels_unl)))
            xu, xt = nw.standardise(unl.transpose(1, 0, 2, 3)), nw.standardise(test.transpose(1, 0, 2, 3))
            for seed in SEEDS:
                model = s["models"][(e, seed)]
                add(el, "new_user", "net_A0", window, 0, seed, nw.predict(model, xt).argmax(axis=1) == labels)
                add(el, "new_user", "net_A1", window, 0, seed, nw.predict(ad.adapt_statistics(model, xu), xt).argmax(axis=1) == labels)
                add(el, "new_user", "net_A2", window, 0, seed, nw.predict(ad.adapt_entropy(model, xu), xt).argmax(axis=1) == labels)
                online = np.concatenate(ad.online(model, [xt[i:i + 12] for i in range(0, 48, 12)]))
                add(el, "new_user", "net_online", window, 0, seed, online == labels)
    return rows, decisions


def first_headband(raw):
    cells = loadmat(pathlib.Path(raw) / "Subjects_Information.mat")["Subjects_Information"]
    return {i: str(cells[i, 10][0]) for i in range(1, 103)}


def impedance(raw, people):
    """log10 of the median impedance: over the 8 channels of a block, then over the 10 blocks (as in M4). Label-free."""
    imp = loadmat(pathlib.Path(raw) / "Impedance.mat")["Impedance"]    # (channel, block, type, subject); type 0 = dry (M0)
    rows = [(sid, el, float(np.log10(np.median(np.median(imp[:, :, e, sid - 1], axis=0))))) for sid in people for e, el in enumerate(NAMES)]
    return pd.DataFrame(rows, columns=["subject", "electrode", "log10_median_kohm"])


# ---------------------------------------------------------------- the 15 tests

def quantities(acc, decisions, imp):
    """Per-person quantities of the 15 tests, people sorted by subject number."""
    people = sorted(acc.subject.unique())
    first = acc.drop_duplicates("subject").set_index("subject").first_headband.str.lower().str.startswith("dry")

    def get(design, method, window=1.0, k=0):
        d = acc[(acc.design == design) & (acc.method == method) & (acc.window_s == window) & (acc.k == k)]
        return d.groupby(["subject", "electrode"]).accuracy.mean().unstack("electrode").loc[people]      # mean over the seeds

    ok = decisions.assign(ok=decisions.template == decisions.target)
    blocks = ok.groupby(["subject", "electrode", "block"]).ok.mean().unstack("block")
    z = imp.set_index(["subject", "electrode"]).log10_median_kohm.unstack("electrode").loc[people]
    q = {"people": people, "dry_first": first.loc[people].to_numpy(), "d": {}, "e": {}, "g": {}, "slope": {}, "z": {}, "acc10": {}, "h6": {}}
    for method in ("fbcca", "etrca_lobo"):
        for window in WINDOWS:
            a = get("ten_blocks", method, window)
            q["d"][(method, window)] = (a.dry - a.wet).to_numpy()
    e = get("new_user", "template", k=2) - get("new_user", "etrca", k=6)
    g = get("new_user", "net_A2") - get("new_user", "net_A0")
    h6 = get("new_user", "template_adapted") - get("new_user", "template")
    a10 = get("ten_blocks", "template")
    for el in NAMES:
        q["e"][el], q["g"][el], q["h6"][el] = e[el].to_numpy(), g[el].to_numpy(), h6[el].to_numpy()
        q["slope"][el] = st.block_slope(blocks.xs(el, level="electrode").loc[people].to_numpy())
        q["z"][el], q["acc10"][el] = z[el].to_numpy(), a10[el].to_numpy()
    return q


def run_tests(q):
    """The family of 15 one-sided tests, in a fixed order. Returns a table with estimate, interval and p-value."""
    rows = []

    def add(hyp, case, quantity, n, estimate, ci, p):
        rows.append({"test": len(rows) + 1, "hypothesis": hyp, "case": case, "quantity": quantity, "n": int(n),
                     "estimate": float(estimate), "ci_low": float(ci[0]), "ci_high": float(ci[1]), "p": float(p)})

    for (method, window), d in q["d"].items():
        add("H1", f"{method.replace('_lobo', '')} {window:g} s", "dry minus wet accuracy (crossover estimate)", len(d),
            st.crossover_effect(d, q["dry_first"]), st.crossover_ci(d, q["dry_first"]), st.crossover_test(d, q["dry_first"], "less"))
    for el in NAMES:
        v = q["e"][el]
        add("H2", el, f"template k=2 minus eTRCA k=6 (margin -{MARGIN})", len(v), v.mean(), st.bootstrap_ci(v),
            st.wilcoxon_one_sided(v + MARGIN, "greater"))
    for case, v in (("dry", q["g"]["dry"]), ("wet", q["g"]["wet"]), ("dry minus wet", q["g"]["dry"] - q["g"]["wet"])):
        add("H3", case, "network: A2 minus A0", len(v), v.mean(), st.bootstrap_ci(v), st.wilcoxon_one_sided(v, "greater"))
    for el in NAMES:
        v = q["slope"][el]
        add("H5a", el, "slope of accuracy per block", len(v), v.mean(), st.bootstrap_ci(v), st.wilcoxon_one_sided(v, "less"))
    for el in NAMES:
        rho, p = st.spearman_permutation_test(q["z"][el], q["acc10"][el], "less", 10000, 0)
        add("H5b", el, "Spearman of log10 impedance with accuracy", len(q["z"][el]), rho, st.spearman_ci(q["z"][el], q["acc10"][el]), p)
    for el in NAMES:
        v = q["h6"][el]
        add("H6", el, "adapted template minus template", len(v), v.mean(), st.bootstrap_ci(v), st.wilcoxon_one_sided(v, "greater"))
    t = pd.DataFrame(rows)
    assert len(t) == 15 and np.isfinite(t.p).all()
    supported, adjusted = st.holm(t.p.to_numpy(), ALPHA)
    rank = t.p.rank(method="first").astype(int)
    t["holm_threshold"] = ALPHA / (len(t) + 1 - rank)
    t["p_holm"], t["supported"] = adjusted, supported
    return t


def withhold(t):
    """Rehearsal: the tests were executed, their outcome is not kept (no p-value on development people)."""
    t = t.copy()
    t["p_computed"] = np.isfinite(t.p)
    return t.drop(columns=["p", "holm_threshold", "p_holm", "supported"])


# ---------------------------------------------------------------- authorisation of the opening

def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def authorise(name, open_lockbox, reproduce, marker=MARKER, git=_git):
    """Decides whether the new people of this set may be loaded. Returns (lockbox people may be loaded, commit).
    Nothing is written here; the opening is recorded by lockbox.begin just before the first person is decoded."""
    if name != "lockbox":
        return False, None
    if not open_lockbox:
        raise lb.LockboxError("the lockbox set needs --open-lockbox")
    if reproduce:
        if lb.state(marker) != "complete":
            raise lb.LockboxError("--reproduce is for after the opening; the lockbox has not been opened")
        return True, None
    if lb.state(marker) == "complete":
        raise lb.LockboxError("the lockbox has already been opened; use --reproduce to recompute the same numbers")
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise lb.LockboxError("the working tree has uncommitted changes; the opening needs a clean commit")
    if git("rev-parse", "pre-lockbox^{commit}") != commit:
        raise lb.LockboxError("the commit is not the one tagged pre-lockbox")
    return True, commit


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def evaluate(name, raw, cache, jobs, opened, reproduce, commit=None, resume=False):
    sets, out = people_sets(name), folder(name, reproduce)
    out.mkdir(parents=True, exist_ok=True)
    cache = c.prepare(raw, cache, jobs)
    frozen, now = json.loads((folder(name) / "frozen.json").read_text()), prepared(name, cache)
    same = all(frozen[key] == now[key] for key in ("new", "population", "train", "validation", "template_sha256", "network_sha256"))
    if not same and not reproduce:
        raise lb.LockboxError("the population template or the networks differ from frozen.json")
    if name == "lockbox" and not reproduce:
        lb.begin(MARKER, commit, utc_now(), resume)                    # the opening is recorded before anyone is decoded
    templates = [population_template(cache, sets["population"], e) for e in range(2)]
    t0 = time.time()
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(jobs, initializer=_init, initargs=(name, raw, opened, templates)) as pool:
        results = pool.map(evaluate_person, sets["new"], chunksize=1)
    acc = pd.DataFrame([r for res in results for r in res[0]], columns=COLUMNS)
    acc.insert(1, "first_headband", acc.subject.map(first_headband(raw)))
    decisions = pd.DataFrame([r for res in results for r in res[1]], columns=["subject", "electrode", "block", "target", "template", "fbcca"])
    imp = impedance(raw, sets["new"])
    tests = run_tests(quantities(acc, decisions, imp))
    acc.to_csv(out / "accuracy.csv", index=False, float_format="%.6f")
    decisions.to_csv(out / "decisions_1s.csv", index=False)
    imp.to_csv(out / "impedance.csv", index=False, float_format="%.6f")
    (tests if name == "lockbox" else withhold(tests)).to_csv(out / "tests.csv", index=False, float_format="%.6g")
    if name == "lockbox" and not reproduce:
        lb.finish(MARKER, utc_now())
    print(f"set {name}: {len(sets['new'])} new people decoded with a population of {len(sets['population'])} development people "
          f"in {time.time() - t0:.0f} s; frozen.json {'matches' if same else 'DIFFERS (reproduction on another machine?)'}")
    if reproduce:
        ref = folder(name)
        for f in ("accuracy.csv", "decisions_1s.csv", "impedance.csv", "tests.csv"):
            print(f"  {f}: {'identical to' if (out / f).read_bytes() == (ref / f).read_bytes() else 'DIFFERENT from'} the opening")


# ---------------------------------------------------------------- stage: report

def ci(v, f="+.3f"):
    v = np.asarray(v, dtype=float)
    lo, hi = st.bootstrap_ci(v)
    return f"{v.mean():{f}} [{lo:{f}}, {hi:{f}}]"


def earlier():
    """The same quantities on the development people, from the result files of M2, M3 and M4 (for comparison)."""
    m2, m3, m4 = ROOT / "results" / "m2", ROOT / "results" / "m3", ROOT / "results" / "m4"
    b = pd.read_csv(m2 / "baseline_accuracy.csv")
    b = b[b.method.isin(["fbcca", "etrca"]) & b.window_s.isin(WINDOWS)].assign(design="ten_blocks", k=0)
    b["method"] = b.method.replace({"etrca": "etrca_lobo"})
    n = pd.read_csv(m2 / "new_user_accuracy.csv")
    n = n[(n.window_s == 1.0) & (n.n0.isna() | (n.n0 == N0))].assign(design="new_user")
    n["method"] = n.method.replace({"cross": "template"})
    t = pd.read_csv(m3 / "new_user_accuracy.csv")
    t = t[t.method != "fbcca"]
    t = t[t.method != "template"].groupby(["subject", "electrode", "method"], as_index=False).accuracy.mean().assign(design="new_user", window_s=1.0, k=0)
    d = pd.read_csv(m4 / "decisions_1s.csv")
    a = d.assign(accuracy=d.template == d.target).groupby(["subject", "electrode"], as_index=False).accuracy.mean()
    a = a.assign(design="ten_blocks", method="template", window_s=1.0, k=0)
    cols = ["subject", "electrode", "design", "method", "window_s", "k", "accuracy"]
    return pd.concat([b[cols], n[cols], t[cols], a[cols]], ignore_index=True)


def report(name, reproduce=False):
    out = folder(name, reproduce)
    acc, decisions, tests = pd.read_csv(out / "accuracy.csv"), pd.read_csv(out / "decisions_1s.csv"), pd.read_csv(out / "tests.csv")
    people = sorted(acc.subject.unique())
    first = acc.drop_duplicates("subject").first_headband.str.lower().str.startswith("dry")
    print(f"== final evaluation, set '{name}': {len(people)} new people (dry worn first: {int(first.sum())}, wet worn first: "
          f"{int((~first).sum())}); pipeline {PIPELINE}, n0 = {N0:g}")
    frozen = json.loads((folder(name) / "frozen.json").read_text())
    print(f"population: {len(frozen['population'])} development people ({len(frozen['train'])} for training, {len(frozen['validation'])} "
          f"for validation of the networks)")

    print("\n== 1. the 15 tests (one-sided; Holm at familywise level 0.05)")
    show = tests.copy()
    show["estimate [95 % interval]"] = [f"{r.estimate:+.4f} [{r.ci_low:+.4f}, {r.ci_high:+.4f}]" for r in show.itertuples()]
    keep = ["test", "hypothesis", "case", "quantity", "n", "estimate [95 % interval]"]
    if "p" in show:
        show["p"], show["threshold"], show["p (Holm)"] = show.p.map("{:.2g}".format), show.holm_threshold.map("{:.4f}".format), show.p_holm.map("{:.2g}".format)
        print(show[keep + ["p", "threshold", "p (Holm)", "supported"]].to_string(index=False))
        print(f"supported after Holm: {int(tests.supported.sum())} of {len(tests)}")
    else:
        print(show[keep + ["p_computed"]].to_string(index=False))
        print("REHEARSAL: the tests were executed and returned finite p-values; the p-values are withheld (development people).")

    ref = earlier()
    same_people = name == "rehearsal"
    if same_people:
        ref = ref[ref.subject.isin(people)]
    mean = lambda d: d.groupby(["design", "method", "window_s", "k", "electrode", "subject"]).accuracy.mean()   # noqa: E731
    new, old = mean(acc), mean(ref)
    old_keys = set(old.index.droplevel("subject"))
    label = "the same people in M2 to M4" if same_people else "the 68 development people (M2 to M4)"

    def table(design, methods, windows=(1.0,)):
        rows = []
        for method in methods:
            for window in windows:
                ks = sorted(acc[(acc.design == design) & (acc.method == method)].k.unique())
                for k in ks:
                    row = {"method": method, "window_s": window, "k": k}
                    for el in NAMES:
                        key = (design, method, window, k, el)
                        v = new.loc[key]
                        row[el] = ci(v, ".3f")
                        row[f"{el}, {label}"] = f"{old.loc[key].mean():.3f}" if key in old_keys else "-"
                    rows.append(row)
        print(pd.DataFrame(rows).to_string(index=False))

    print(f"\n== 2. no calibration, blocks 7 to 10, 1 s: mean accuracy [95 % interval over people]; next to it: {label}")
    table("new_user", ["fbcca", "template", "template_adapted", "net_A0", "net_A1", "net_A2", "net_online"])
    pl_acc = acc[acc.method == "template_adapted"].groupby("electrode").pseudo_label_accuracy.mean()
    print(f"accuracy of the template's own decisions on blocks 1 to 6 (used as labels): dry {pl_acc.dry:.3f}, wet {pl_acc.wet:.3f}")
    print("\n== 3. calibration curve, blocks 7 to 10, 1 s (k = number of calibration blocks; one block = 48 s)")
    table("new_user", ["template", "own", "etrca"])
    print("\n== 4. the person's own ten blocks (ensemble TRCA: leave-one-block-out) and the template with no calibration")
    table("ten_blocks", ["fbcca", "etrca_lobo"], WINDOWS)
    table("ten_blocks", ["template"])

    print("\n== 5. people not above chance at 1 s over the ten blocks (120 trials)")
    thr = mt.chance_threshold(120, 12)
    ok = decisions.assign(template=decisions.template == decisions.target, fbcca=decisions.fbcca == decisions.target)
    a = ok.groupby(["subject", "electrode"])[["template", "fbcca"]].mean()
    for method in ("template", "fbcca"):
        fail = a[method].unstack("electrode") < thr
        who = {el: [f"S{s:03d}" for s in fail.index[fail[el]]] for el in NAMES}
        print(f"  {method}: below {thr:.3f}: dry {int(fail.dry.sum())}, wet {int(fail.wet.sum())} of {len(fail)}; {who}")

    if same_people:
        print("\n== 6. check of the code path against M2 to M4, same people")
        exact = [("ten_blocks", "fbcca"), ("ten_blocks", "etrca_lobo"), ("new_user", "fbcca"), ("new_user", "own"), ("new_user", "etrca")]
        both = pd.concat([new.rename("new"), old.rename("old")], axis=1).dropna().reset_index()
        both["diff"] = (both.new - both.old).abs()
        for design, method in exact:
            d = both[(both.design == design) & (both.method == method)]
            print(f"  {design:10s} {method:11s} needs no population: {len(d)} accuracies, largest difference {d['diff'].max():.6f}")
        rest = both[~both.set_index(["design", "method"]).index.isin(exact)]
        print("  with another population (45 instead of 67 or 51 people) or other networks: mean accuracy now, before, mean |difference| per person")
        print(rest.groupby(["design", "method", "k", "electrode"])[["new", "old", "diff"]].mean().round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prepare", "evaluate", "report"])
    ap.add_argument("--set", dest="name", choices=["rehearsal", "lockbox"], default="rehearsal")
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--cache", default=str(c.DEFAULT_CACHE))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--open-lockbox", action="store_true")
    ap.add_argument("--reproduce", action="store_true", help="after the opening: recompute into results/final/lockbox_reproduction")
    ap.add_argument("--resume-interrupted", action="store_true", help="continue an opening that did not finish (same commit)")
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare(args.name, args.raw, args.cache, args.jobs)
    elif args.stage == "evaluate":
        opened, commit = authorise(args.name, args.open_lockbox, args.reproduce)
        evaluate(args.name, args.raw, args.cache, args.jobs, opened, args.reproduce, commit, args.resume_interrupted)
        report(args.name, args.reproduce)
    else:
        report(args.name, args.reproduce)


if __name__ == "__main__":
    main()
