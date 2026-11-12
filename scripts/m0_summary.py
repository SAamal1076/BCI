"""M0: every number quoted in docs/milestones/M0_data_audit.md, recomputed from the result tables.

Also writes results/m0/acceptance.csv (C1-C5) and two small descriptive tables.
Usage: python scripts/m0_summary.py > logs/m0_summary.log
"""
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import wearable as wd  # noqa: E402

RES = ROOT / "results" / "m0"
IDX = {"dry": wd.DRY + 1, "wet": wd.WET + 1}
# E4: electrode axis used by an independent published loader of this dataset (read 12 Nov 2026):
# SSVEP-Analysis-Toolbox, SSVEPAnalysisToolbox/datasets/wearabledataset.py:
#   WearableDataset_wet -> mat_data['data'][:, :, 1, :, :]   WearableDataset_dry -> mat_data['data'][:, :, 0, :, :]
E4_DRY_POSITION = 1


def q(v):
    a, b, c = np.percentile(v, [25, 50, 75])
    return f"{b:.2f} [{a:.2f}, {c:.2f}]"


def main():
    pd.set_option("display.width", 200)
    inv = pd.read_csv(RES / "inventory.csv")
    noise = pd.read_csv(RES / "noise_per_subject.csv")
    flagged = pd.read_csv(RES / "flagged_trials.csv")
    imp = pd.read_csv(RES / "impedance_summary.csv").set_index("impedance_index")
    imp_s = pd.read_csv(RES / "impedance_per_subject.csv")
    imp_b = pd.read_csv(RES / "impedance_by_block.csv")
    ev = pd.read_csv(RES / "dry_wet_evidence.csv")
    snr = pd.read_csv(RES / "snr_per_subject.csv")
    snr_c = pd.read_csv(RES / "snr_per_subject_channel.csv")
    snr_t = pd.read_csv(RES / "snr_per_subject_target.csv")
    snr_b = pd.read_csv(RES / "snr_per_subject_block.csv")
    lat = pd.read_csv(RES / "latency_per_subject.csv")
    lat_g = pd.read_csv(RES / "latency_group.csv")
    spec = pd.read_csv(RES / "noise_spectrum.csv").set_index("frequency")
    manifest = pd.read_csv(ROOT / "data_manifest.csv")

    print("== files")
    w = manifest[manifest.dataset == "wearable_ssvep"]
    other = manifest[manifest.dataset != "wearable_ssvep"]
    print(f"wearable files: {len(w)}, {w.bytes.sum() / 1e6:.1f} MB; other datasets in the manifest: "
          f"{other.groupby('dataset').size().to_dict()}, {other.bytes.sum() / 1e6:.1f} MB")
    print(f"subjects {len(inv)}, shapes {sorted(set(inv['shape']))}, non-finite {int(inv.n_nonfinite.sum())}, "
          f"range {inv['min'].min():.1f} to {inv['max'].max():.1f} uV, value step {inv.value_step.median():.7f} uV, "
          f"differences on the grid {inv.share_on_value_grid.min():.4f}")

    print("\n== label-free noise, per electrode type (median [q25, q75] over the 102 per-subject medians)")
    for name, i in IDX.items():
        d = noise[noise.eeg_index == i]
        print(f"{name} (position {i}): " + "; ".join(f"{k} {q(d[k])}" for k in
                                                     ("line50", "hf_rms", "lf_rms", "rms_bp", "ptp_bp")) +
              f"; offset mV {q(d.dc_abs / 1000)}")
        print(f"   artefact-flag trials {int(d.artefact_trials.sum())} of {len(d) * 120} "
              f"({d.artefact_trials.sum() / (len(d) * 120):.1%}); subjects with more than half of their trials "
              f"flagged: {int((d.artefact_trials > 60).sum())}; flat {int(d.flat_channel_trials.sum())}; "
              f"at amplifier limit {int(d.saturated_trials.sum())}; largest mains pick-up: "
              f"S{int(d.loc[d.line50.idxmax(), 'subject']):03d} {d.line50.max():.0f} uV")
    print("saturated trials:", flagged[flagged.saturated][["subject", "eeg_index", "block", "target"]].to_dict("records"))
    print("noise spectrum (median over subjects, uV) at 50 Hz and 100 Hz, positions 1 and 2:",
          spec.loc[50.0, ["index1_median", "index2_median"]].round(1).tolist(),
          spec.loc[100.0, ["index1_median", "index2_median"]].round(1).tolist(),
          "; floor at 75 Hz:", spec.loc[75.0, ["index1_median", "index2_median"]].round(2).tolist())

    print("\n== impedance (kOhm)")
    print(imp.round(2).T.to_string())
    for name, i in IDX.items():
        b = imp_b[imp_b.impedance_index == i]
        print(f"{name}: median of all electrodes, block 1 = {b['median'].iloc[0]:.1f}, block 10 = {b['median'].iloc[-1]:.1f}; "
              f"median over people of a person's mean = {imp_s[imp_s.impedance_index == i]['mean'].median():.0f}")

    print("\n== which position is dry (evidence table)")
    print(ev.round(4).to_string(index=False))

    print("\n== subjects")
    print(pd.read_csv(RES / "subjects_summary.csv").query("variable in ['n', 'first', 'sex', 'age']").to_string(index=False))

    print("\n== development subjects: SNR (dB) and amplitude (uV), median [q25, q75] over 68 people")
    wide = snr.pivot(index="subject", columns="electrode")
    for col in ("snr1_trial_oz", "snr2_trial_oz", "snr1_trial_mean8", "snr1_unattended_oz", "snr1_avg_oz",
                "snr2_avg_oz", "amp1_trial_oz", "amp1_avg_oz"):
        d = wide[col]["dry"] - wide[col]["wet"]
        print(f"{col:20s} dry {q(wide[col]['dry'])}   wet {q(wide[col]['wet'])}   dry < wet in "
              f"{int((d < 0).sum())}/68, median difference {d.median():+.2f}")
    s1 = wide["snr1_trial_oz"]
    print(f"Spearman between a person's dry and wet single-trial SNR: {stats.spearmanr(s1['dry'], s1['wet'])[0]:.2f}")
    for name in ("dry", "wet"):
        print(f"{name}: people with single-trial SNR at Oz below 0 dB: {int((s1[name] < 0).sum())}, below 1 dB: "
              f"{int((s1[name] < 1).sum())}; range {s1[name].min():.1f} to {s1[name].max():.1f}")
    att = pd.read_csv(RES / "attended_matrix.csv")
    c4 = pd.read_csv(RES / "c4_group_peaks.csv")
    for name in ("dry", "wet"):
        m = att[att.electrode == name]
        on = m[m.attended_frequency == m.frequency].amplitude
        off = m[m.attended_frequency != m.frequency].amplitude
        g = c4[c4.electrode == name]
        print(f"{name}: mean single-trial amplitude at Oz, attended frequency {on.mean():.2f} uV, other stimulus "
              f"frequencies {off.mean():.2f} uV; grand-average peak at the target frequency "
              f"{g.peak_amplitude.min():.2f} to {g.peak_amplitude.max():.2f} uV, largest other peak "
              f"{g.second_amplitude.max():.2f} uV")
    floor = noise.assign(ratio=noise.floor_planned_notch / noise.floor_adopted)
    print(f"noise floor at stimulus-free frequencies (uV, median over people): dry "
          f"{floor[floor.eeg_index == IDX['dry']].floor_adopted.median():.2f}, wet "
          f"{floor[floor.eeg_index == IDX['wet']].floor_adopted.median():.2f}; planned notch / adopted removal: "
          f"median {floor.ratio.median():.3f}, max dry {floor[floor.eeg_index == IDX['dry']].ratio.max():.2f}, "
          f"max wet {floor[floor.eeg_index == IDX['wet']].ratio.max():.3f}, above 1.05 in "
          f"{int((floor.ratio > 1.05).sum())} of {len(floor)} recordings")
    print("by channel (median single-trial SNR at f):")
    print(snr_c.groupby(["channel", "electrode"]).snr1_trial.median().unstack().round(2)
          .sort_values("wet", ascending=False).T.to_string())
    print("by target frequency at Oz (median single-trial SNR):")
    print(snr_t.groupby(["frequency", "electrode"]).snr1_trial_oz.median().unstack().round(2).T.to_string())
    print("by block at Oz (median single-trial SNR):")
    print(snr_b.groupby(["block", "electrode"]).snr1_trial_oz.median().unstack().round(2).T.to_string())

    order = []
    for name in ("dry", "wet"):
        d = snr[snr.electrode == name]
        worn_first = d.first_headband.str.lower() == name
        order.append({"electrode": name, "n_worn_first": int(worn_first.sum()),
                      "snr1_trial_oz_median_worn_first": d[worn_first].snr1_trial_oz.median(),
                      "n_worn_second": int((~worn_first).sum()),
                      "snr1_trial_oz_median_worn_second": d[~worn_first].snr1_trial_oz.median()})
    order = pd.DataFrame(order)
    first = snr.drop_duplicates("subject").set_index("subject").first_headband
    diff = s1["dry"] - s1["wet"]
    order["median_dry_minus_wet_same_people"] = [diff[first == "Dry"].median(), diff[first == "Wet"].median()]
    order["people_with_dry_below_wet"] = [f"{int((diff[first == 'Dry'] < 0).sum())}/{int((first == 'Dry').sum())}",
                                          f"{int((diff[first == 'Wet'] < 0).sum())}/{int((first == 'Wet').sum())}"]
    order.to_csv(RES / "snr_by_wearing_order.csv", index=False)
    print("by wearing order (descriptive). Rows: headband; 'worn first' and 'worn second' are different people.")
    print("Last two columns: within-person dry - wet for the people who wore THAT headband first.")
    print(order.round(2).to_string(index=False))

    rel = []
    for name, i in IDX.items():
        m = snr[snr.electrode == name].merge(imp_s[imp_s.impedance_index == i], on="subject")
        n_ = noise[noise.eeg_index == i].merge(imp_s[imp_s.impedance_index == i], on="subject")
        for label, a, b in (("impedance vs single-trial SNR at Oz (68 development people)", m["median"], m.snr1_trial_oz),
                            ("impedance vs mains pick-up (102 people)", n_["median"], n_.line50),
                            ("impedance vs noise 60-90 Hz (102 people)", n_["median"], n_.hf_rms)):
            rho, p = stats.spearmanr(a, b)
            rel.append({"electrode": name, "relation": label, "spearman_rho": rho, "p_uncorrected": p, "n": len(a)})
    rel = pd.DataFrame(rel)
    rel.to_csv(RES / "impedance_relations.csv", index=False)
    print("impedance of a person (median over channels and blocks) against noise and SNR, descriptive:")
    print(rel.round(3).to_string(index=False))

    print("\n== timing")
    print(lat_g.round(4).to_string(index=False))
    for name in ("dry", "wet"):
        d = lat[lat.electrode == name]
        ok = d[(d.tau_scan >= 0.10) & (d.tau_scan <= 0.18)]
        print(f"{name}: per-person latency (scan) median {d.tau_scan.median() * 1000:.0f} ms, quartiles "
              f"{d.tau_scan.quantile(.25) * 1000:.0f}-{d.tau_scan.quantile(.75) * 1000:.0f} ms; inside 100-180 ms: "
              f"{len(ok)}/68; phase coherence median {d.r_scan.median():.2f}, below 0.7 in {int((d.r_scan < 0.7).sum())} people")
    print("\n== comparison with the paper's Figure 4")
    print(pd.read_csv(RES / "paper_fig4_check.csv").round(2).to_string(index=False))

    # ---- acceptance table C1-C5
    a = pd.concat([pd.read_csv(RES / "acceptance_inventory.csv"), pd.read_csv(RES / "acceptance_signal.csv")])
    e2 = ev[ev.evidence == "E2"].set_index("item")["value"]
    n_line = int(e2[[k for k in e2.index if k.startswith("line50")][0]])
    n_hf = int(e2[[k for k in e2.index if k.startswith("hf_rms")][0]])
    high = int(imp.mean_all_values.idxmax())
    c3 = high == 1 and n_line < 51 and n_hf < 51 and E4_DRY_POSITION == 1 and wd.DRY == 0
    a = pd.concat([a, pd.DataFrame([{
        "criterion": "C3", "passed": bool(c3),
        "detail": f"position 1 is dry: impedance position {high} has the dry value of the paper; position 1 is "
                  f"noisier in {102 - n_line}/102 people (mains) and {102 - n_hf}/102 (60-90 Hz); an independent "
                  f"loader uses position {E4_DRY_POSITION} for dry. The label printed in the readme (1 = wet) is wrong."}])])
    a = a.sort_values("criterion").reset_index(drop=True)
    a.to_csv(RES / "acceptance.csv", index=False)
    print("\n== acceptance")
    for _, r in a.iterrows():
        print(f"{r.criterion:4s} {'PASS' if r.passed else 'FAIL'}  {r.detail}")


if __name__ == "__main__":
    main()
