"""M0, steps 1-3 and 6: label-free inventory of the wearable SSVEP dataset (all 102 subjects).

Nothing here uses the target index of a trial for a signal statistic, so lockbox subjects are included.
Electrode types are called "index 1" and "index 2" (position on the electrode axis of the files): which one
is dry is exactly what step 3 has to establish.

Usage: python scripts/m0_inventory.py --raw /path/to/13560281
"""
import argparse
import hashlib
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats
from scipy.io import loadmat, whosmat

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import spectral as sp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

ARTEFACT_UV = 200.0      # descriptive flag: peak-to-peak after preprocessing, any channel
FLAT_RUN = 25            # descriptive flag: identical consecutive samples (0.1 s)
METRICS = ("ptp_bp", "rms_bp", "line50", "hf_rms", "lf_rms", "dc_abs")   # dc_abs: added during M0 (see audit)
RAIL_UV = 374_990.0      # samples beyond this are at the limit of the amplifier range (+/-375 mV)
PAPER_IMPEDANCE = {"dry": 261.67, "wet": 19.63}      # kOhm, Zhu et al. 2021, section 3.5
PAPER_FIRST = {"Dry": 53, "Wet": 49}                 # headband worn first, section 2.4


def file_hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def build_manifest(raw):
    published = {}
    for line in (ROOT / "scripts" / "figshare_md5_wearable.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, size, md5 = line.split()
            published[name] = (int(size), md5)
    rows = []
    for name in sorted(published):
        path = raw / name
        md5, sha = file_hashes(path)
        rows.append({"dataset": "wearable_ssvep", "file": name, "bytes": path.stat().st_size, "md5": md5,
                     "sha256": sha, "md5_equals_figshare": md5 == published[name][1]})
    return pd.DataFrame(rows)


def flat_runs(x, run=FLAT_RUN):
    """True where a series has at least `run` identical consecutive samples (last axis)."""
    same = np.diff(x, axis=-1) == 0
    return np.lib.stride_tricks.sliding_window_view(same, run - 1, axis=-1).all(axis=-1).any(axis=-1)


def value_grid(x):
    """Smallest step between consecutive samples and the share of sample-to-sample differences that are
    multiples of it. Differences are used because they are small numbers: with offsets of tens of
    millivolts, the values themselves are too large to be tested against a step known to 7 digits."""
    d = np.diff(x[:, :2], axis=-1).ravel()            # first two blocks of each electrode index
    step = np.abs(d[d != 0]).min()
    ratio = d / step
    return float(step), float((np.abs(ratio - np.round(ratio)) < 1e-2).mean())


def noise_spectrum(x, nfft=1000):
    """Mean amplitude spectrum of the raw epochs of one subject, per electrode index (label-free: all
    trials pooled). Linear trend removed, Hann window, 0.25 Hz grid. Returns [2, nfft//2 + 1]."""
    from scipy import signal
    y = signal.detrend(x, axis=-1, type="linear") * signal.windows.hann(x.shape[-1], sym=False)
    amp = 2.0 * np.abs(np.fft.rfft(y, n=nfft, axis=-1)) / signal.windows.hann(x.shape[-1], sym=False).sum()
    return amp.mean(axis=(1, 2, 3))


def trial_metrics(x):
    """Label-free metrics per trial and channel. x: [electrode, block, target, channel, sample]."""
    centred = x - x.mean(axis=-1, keepdims=True)
    bp = sp.preprocess_descriptive(x, wd.FS)
    return {
        "ptp_bp": np.ptp(bp, axis=-1),
        "rms_bp": bp.std(axis=-1),
        "line50": sp.hann_amplitude(x, 50.0, wd.FS),
        "hf_rms": sp.bandpass(centred, wd.FS, 60.0, 90.0).std(axis=-1),
        "lf_rms": sp.lowpass(centred, wd.FS, 3.0).std(axis=-1),
        "dc_abs": np.abs(x.mean(axis=-1)),                 # electrode offset
    }


def impedance_tables(raw):
    imp = loadmat(raw / "Impedance.mat")["Impedance"]
    if imp.shape != (8, 10, 2, 102):
        raise ValueError(f"Impedance.mat: unexpected shape {imp.shape}")
    imp = np.transpose(imp, (2, 3, 1, 0))                    # [type index, subject, block, channel]
    rows, per_subject, by_block, by_channel = [], [], [], []
    for i in range(2):
        v = imp[i]
        subj_mean = v.mean(axis=(1, 2))
        rows.append({"impedance_index": i + 1, "n_values": v.size, "mean_all_values": v.mean(),
                     "median_all_values": np.median(v), "min": v.min(), "max": v.max(),
                     "mean_of_subject_means": subj_mean.mean(), "sd_of_subject_means": subj_mean.std(ddof=1),
                     "sem_of_subject_means": subj_mean.std(ddof=1) / np.sqrt(len(subj_mean)),
                     "median_of_subject_medians": np.median(np.median(v, axis=(1, 2))),
                     "subjects_mean_below_40": int((subj_mean < 40).sum()),
                     "subjects_mean_below_500": int((subj_mean < 500).sum()),
                     "share_values_above_1000": float((v > 1000).mean())})
        for s in range(102):
            per_subject.append({"subject": s + 1, "group": "lockbox" if wd.is_lockbox(s + 1) else "development",
                                "impedance_index": i + 1, "mean": v[s].mean(), "median": np.median(v[s]),
                                "max": v[s].max()})
        for b in range(10):
            by_block.append({"impedance_index": i + 1, "block": b + 1, "mean": v[:, b].mean(),
                             "median": np.median(v[:, b]), "q25": np.percentile(v[:, b], 25),
                             "q75": np.percentile(v[:, b], 75)})
        for c, name in enumerate(wd.CHANNELS):
            by_channel.append({"impedance_index": i + 1, "channel": name, "mean": v[:, :, c].mean(),
                               "median": np.median(v[:, :, c]), "q25": np.percentile(v[:, :, c], 25),
                               "q75": np.percentile(v[:, :, c], 75)})
    return imp, pd.DataFrame(rows), pd.DataFrame(per_subject), pd.DataFrame(by_block), pd.DataFrame(by_channel)


def subject_information(raw):
    cells = loadmat(raw / "Subjects_Information.mat")["Subjects_Information"]
    header = [str(c[0]) if c.size else "subject" for c in cells[0]]
    table = pd.DataFrame([[c.squeeze().item() if c.size else None for c in row] for row in cells[1:]],
                         columns=["subject", "sex", "age", "handedness", "dry_comfort", "dry_pain_h",
                                  "wet_comfort", "wet_pain_h", "pref_comfort", "pref_overall", "first"])
    if list(table["subject"]) != [f"sub{i}" for i in range(1, 103)]:
        raise ValueError("Subjects_Information.mat: unexpected subject order")
    table["sid"] = np.arange(1, 103)
    table["group"] = np.where(table["sid"] % 3 == 0, "lockbox", "development")
    return header, table


def summarise_subjects(table):
    rows = []
    for group, part in [("all", table), ("development", table[table.group == "development"]),
                        ("lockbox", table[table.group == "lockbox"])]:
        rows.append({"group": group, "variable": "n", "level": "", "value": len(part)})
        for var in ("first", "sex", "handedness", "dry_comfort", "wet_comfort", "pref_comfort", "pref_overall"):
            for level, n in part[var].value_counts().sort_index().items():
                rows.append({"group": group, "variable": var, "level": level, "value": int(n)})
        for stat, val in (("mean", part.age.mean()), ("sd", part.age.std(ddof=1)), ("min", part.age.min()),
                          ("median", part.age.median()), ("max", part.age.max()),
                          ("n_under_18", int((part.age < 18).sum()))):
            rows.append({"group": group, "variable": "age", "level": stat, "value": round(float(val), 2)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(wd.DEFAULT_DIR))
    ap.add_argument("--out", default=str(ROOT / "results" / "m0"))
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ---- files and checksums
    manifest = build_manifest(raw)
    manifest.drop(columns="md5_equals_figshare").to_csv(ROOT / "data_manifest.csv", index=False)
    n_bad = int((~manifest.md5_equals_figshare).sum())
    print(f"files: {len(manifest)}, total {manifest.bytes.sum() / 1e6:.1f} MB, MD5 different from figshare: {n_bad}")
    if n_bad:
        raise SystemExit("some files differ from the published checksums: " +
                         ", ".join(manifest.file[~manifest.md5_equals_figshare]))

    header, info = subject_information(raw)
    first = dict(zip(info.sid, info["first"]))            # headband worn first: "Dry" or "Wet"

    # ---- per-subject pass
    inventory, per_subject, per_block, per_channel, flagged, spectra = [], [], [], [], [], []
    hashes = {}
    for sid in wd.SUBJECTS:
        path = wd.subject_path(raw, sid)
        (name, shape, dtype), = whosmat(path)
        x = wd.load_subject(raw, sid)
        step, on_grid = value_grid(x)
        inventory.append({"subject": sid, "group": "lockbox" if wd.is_lockbox(sid) else "development",
                          "variable": name, "shape": "x".join(map(str, shape)), "dtype": dtype,
                          "n_nonfinite": int((~np.isfinite(x)).sum()), "min": x.min(), "max": x.max(),
                          "value_step": step, "share_on_value_grid": on_grid})
        m = trial_metrics(x)
        spectra.append(noise_spectrum(x))
        flat = flat_runs(x) | (x.std(axis=-1) == 0)                        # [e, block, target, channel]
        artefact = m["ptp_bp"].max(axis=-1) > ARTEFACT_UV                  # [e, block, target]
        for e in range(2):
            base = {"subject": sid, "group": inventory[-1]["group"], "first_headband": first[sid],
                    "eeg_index": e + 1}
            row = dict(base)
            for k in METRICS:
                row[k] = float(np.median(m[k][e]))
            row["artefact_trials"] = int(artefact[e].sum())
            row["flat_channel_trials"] = int(flat[e].sum())
            row["saturated_trials"] = int((np.abs(x[e]) >= RAIL_UV).any(axis=(-1, -2)).sum())
            per_subject.append(row)
            for b in range(wd.N_BLOCKS):
                r = dict(base, block=b + 1)
                for k in METRICS:
                    r[k] = float(np.median(m[k][e, b]))
                r["artefact_trials"] = int(artefact[e, b].sum())
                per_block.append(r)
            for c, ch in enumerate(wd.CHANNELS):
                r = dict(base, channel=ch)
                for k in METRICS:
                    r[k] = float(np.median(m[k][e, :, :, c]))
                per_channel.append(r)
            sat = (np.abs(x[e]) >= RAIL_UV).any(axis=(-1, -2))
            for b, t in zip(*np.nonzero(artefact[e] | flat[e].any(axis=-1) | sat)):
                c = int(np.argmax(m["ptp_bp"][e, b, t]))
                flagged.append(dict(base, block=b + 1, target=t + 1, max_ptp_bp=float(m["ptp_bp"][e, b, t, c]),
                                    worst_channel=wd.CHANNELS[c], flat=bool(flat[e, b, t].any()),
                                    saturated=bool(sat[b, t])))
            for b in range(wd.N_BLOCKS):
                for t in range(wd.N_TARGETS):
                    hashes.setdefault(hashlib.md5(x[e, b, t].tobytes()).hexdigest(), []).append((sid, e + 1, b + 1, t + 1))
    inventory = pd.DataFrame(inventory)
    per_subject = pd.DataFrame(per_subject)
    inventory.to_csv(out / "inventory.csv", index=False)
    per_subject.to_csv(out / "noise_per_subject.csv", index=False)
    pd.DataFrame(per_block).to_csv(out / "noise_per_subject_block.csv", index=False)
    pd.DataFrame(per_channel).to_csv(out / "noise_per_subject_channel.csv", index=False)
    pd.DataFrame(flagged, columns=["subject", "group", "first_headband", "eeg_index", "block", "target", "max_ptp_bp",
                                   "worst_channel", "flat", "saturated"]).to_csv(out / "flagged_trials.csv", index=False)
    dup = [{"md5": h, "n": len(v), "trials": " ".join(f"S{s:03d}/e{e}/b{b}/t{t}" for s, e, b, t in v)}
           for h, v in hashes.items() if len(v) > 1]
    pd.DataFrame(dup, columns=["md5", "n", "trials"]).to_csv(out / "duplicate_trials.csv", index=False)

    spectra = np.array(spectra)                                              # [subject, index, frequency]
    spec = {"frequency": np.fft.rfftfreq(1000, 1 / wd.FS)}
    for e in range(2):
        q25, med, q75 = np.percentile(spectra[:, e], [25, 50, 75], axis=0)
        spec.update({f"index{e + 1}_median": med, f"index{e + 1}_q25": q25, f"index{e + 1}_q75": q75})
    pd.DataFrame(spec).to_csv(out / "noise_spectrum.csv", index=False)

    print(f"subjects: {len(inventory)}; shapes: {sorted(set(inventory['shape']))}; dtypes: {sorted(set(inventory.dtype))}")
    print(f"non-finite values: {inventory.n_nonfinite.sum()}; amplitude range: {inventory['min'].min():.1f} "
          f"to {inventory['max'].max():.1f}")
    print(f"value step: {inventory.value_step.min():.7g} to {inventory.value_step.max():.7g}; "
          f"share of sample-to-sample differences on that grid: {inventory.share_on_value_grid.min():.4f} to "
          f"{inventory.share_on_value_grid.max():.4f}")
    print(f"trials: {len(hashes) + sum(d['n'] - 1 for d in dup)}; exact duplicates: {len(dup)} groups")
    grouped = per_subject.groupby("eeg_index")
    flags = ["artefact_trials", "flat_channel_trials", "saturated_trials"]
    print("median over subjects of the per-subject medians, and totals of the flags (of 12240 trials per index):")
    print(pd.concat([grouped[list(METRICS)].median(), grouped[flags].sum()], axis=1).round(3).to_string())

    # ---- metadata
    imp, imp_summary, imp_subject, imp_block, imp_channel = impedance_tables(raw)
    imp_summary.to_csv(out / "impedance_summary.csv", index=False)
    imp_subject.to_csv(out / "impedance_per_subject.csv", index=False)
    imp_block.to_csv(out / "impedance_by_block.csv", index=False)
    imp_channel.to_csv(out / "impedance_by_channel.csv", index=False)
    print("impedance (kOhm):")
    print(imp_summary.round(2).T.to_string())

    imp_subject.insert(2, "first_headband", imp_subject.subject.map(first))
    imp_subject.to_csv(out / "impedance_per_subject.csv", index=False)
    print("Subjects_Information columns:", header)
    subj_summary = summarise_subjects(info)
    subj_summary.to_csv(out / "subjects_summary.csv", index=False)
    print(subj_summary[subj_summary.variable.isin(["n", "first", "sex", "age"])].to_string(index=False))

    # ---- step 3: which electrode index is dry (E1-E3; E4 is recorded in the audit)
    ev = []
    means = imp_summary.set_index("impedance_index")["mean_all_values"]
    for i in (1, 2):
        for name, ref in PAPER_IMPEDANCE.items():
            ev.append({"evidence": "E1", "item": f"impedance index {i} mean vs paper {name} ({ref} kOhm)",
                       "value": means[i], "reference": ref, "relative_difference": means[i] / ref - 1})
    wide = per_subject.pivot(index="subject", columns="eeg_index")
    for k in METRICS:
        a, b = wide[k][1], wide[k][2]
        ev.append({"evidence": "E2", "item": f"{k}: subjects with EEG index 2 > index 1 (of 102)",
                   "value": int((b > a).sum()), "reference": 102, "relative_difference": np.median(b / a)})
    imp_med = imp_subject.pivot(index="subject", columns="impedance_index", values="median")
    for k in ("line50", "hf_rms"):
        for i in (1, 2):
            for j in (1, 2):
                rho, p = stats.spearmanr(imp_med[i], wide[k][j])
                ev.append({"evidence": "E3", "item": f"Spearman impedance index {i} vs {k} of EEG index {j}",
                           "value": rho, "reference": p, "relative_difference": np.nan})
    ev = pd.DataFrame(ev)
    ev.to_csv(out / "dry_wet_evidence.csv", index=False)
    print("dry/wet evidence (E1: value = mean kOhm; E2: value = number of subjects, last column = median "
          "ratio index2/index1; E3: value = rho, reference = p):")
    print(ev.round(4).to_string(index=False))

    # ---- acceptance C1, C2
    first_counts = info["first"].value_counts().to_dict()
    c1 = (len(inventory) == 102 and set(inventory["shape"]) == {"8x710x2x10x12"} and inventory.n_nonfinite.sum() == 0)
    dry_i = int(means.idxmax())
    rel = {"dry": means[dry_i] / PAPER_IMPEDANCE["dry"] - 1, "wet": means[3 - dry_i] / PAPER_IMPEDANCE["wet"] - 1}
    acc = pd.DataFrame([
        {"criterion": "C1", "passed": bool(c1),
         "detail": f"{len(inventory)} files, shapes {sorted(set(inventory['shape']))}, "
                   f"{int(inventory.n_nonfinite.sum())} non-finite values"},
        {"criterion": "C2a", "passed": bool(abs(rel["dry"]) <= 0.05 and abs(rel["wet"]) <= 0.05),
         "detail": f"mean impedance: index {dry_i} = {means[dry_i]:.2f} kOhm ({rel['dry']:+.1%} vs paper dry), "
                   f"index {3 - dry_i} = {means[3 - dry_i]:.2f} kOhm ({rel['wet']:+.1%} vs paper wet)"},
        {"criterion": "C2b", "passed": first_counts == PAPER_FIRST, "detail": f"headband worn first: {first_counts}"},
    ])
    acc.to_csv(out / "acceptance_inventory.csv", index=False)
    print(acc.to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
