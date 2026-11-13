"""M1: short data check of BETA before it is decoded (all 70 people; BETA has no lockbox, it is a reference set).

Checks: files and layout; the reduced files come from the verified originals (MD5); channel selection;
frequency and phase tables identical in every file; values finite; mains component; and that each of the 40
targets gives its largest spectral peak at its own frequency (group average at Oz).

Usage: python scripts/m1_beta_check.py --raw /path/to/beta [--manifest data_manifest.csv]
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import beta as bd  # noqa: E402
from ssvep import spectral as sp  # noqa: E402

FS, F = bd.FS, bd.TARGET_FREQS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(bd.DEFAULT_DIR))
    ap.add_argument("--manifest", default=str(ROOT / "data_manifest.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "m1"))
    args = ap.parse_args()
    raw, out = pathlib.Path(args.raw), pathlib.Path(args.out)
    manifest = pd.read_csv(args.manifest)
    md5 = manifest[manifest.dataset == "beta"].set_index("file").md5

    rows, mean_oz = [], np.zeros((bd.N_TARGETS, 2 * FS))
    grid = np.arange(46.0, 54.5, 1.0)
    for sid in bd.SUBJECTS:
        x = bd.load_subject(raw, sid)                                   # [block, target, channel, sample]
        freqs, phases = bd.load_tables(raw, sid)
        meta = raw / f"S{sid}.json"
        m = json.loads(meta.read_text()) if meta.exists() else {}
        resp = x[..., bd.RESP_START:bd.RESP_START + 2 * FS]             # 2 s of response, every person has it
        mean_oz += resp[:, :, bd.OZ].mean(axis=0) / len(bd.SUBJECTS)
        near = sp.amplitude(sp.signal.detrend(resp[..., :FS], axis=-1), grid, FS).mean(axis=(0, 1, 2))
        rows.append({
            "subject": sid, "samples": x.shape[-1], "stim_s": bd.stim_seconds(sid),
            "finite": bool(np.isfinite(x).all()) and m.get("all_finite", True),
            "freq_table_ok": bool(np.allclose(freqs, F)),
            "phase_table_as_in_files": bool(np.allclose(phases, bd.PHASES_IN_FILES)),
            "phase_table_as_corrected": bool(np.allclose(phases, bd.PHASES_CORRECTED)),
            "channels_ok": m.get("channels", list(bd.CHANNELS)) == list(bd.CHANNELS),
            "channel_index": str(m.get("channel_index_0based", "")),
            "md5_equals_figshare": (m["md5_source"] == md5.get(f"S{sid}.mat")) if m else None,
            "rms_uv": float(x.std()), "max_abs_uv": float(np.abs(x).max()),
            "amp_50hz_uv": float(near[4]), "amp_47_53hz_uv": float(near[[1, 2, 6, 7]].mean()),
        })
    d = pd.DataFrame(rows)
    d.to_csv(out / "beta_check.csv", index=False, float_format="%.4f")

    amp = sp.amplitude(mean_oz, F, FS)                                  # (target, candidate frequency)
    own = amp.argmax(axis=1) == np.arange(bd.N_TARGETS)
    pd.DataFrame(amp, index=[f"{f:g}" for f in F], columns=[f"{f:g}" for f in F]).to_csv(
        out / "beta_group_amplitude_oz.csv", float_format="%.4f")

    print(f"people: {len(d)}; 2 s of stimulation: {(d.stim_s == 2).sum()}, 3 s: {(d.stim_s == 3).sum()}; "
          f"samples per trial: {sorted(d.samples.unique())}")
    print(f"all values finite: {d.finite.all()}; frequency table identical in all files: {d.freq_table_ok.all()}")
    print(f"phase table equal to the one stored in the files (0, 0.5, 1, 1.5 pi ...): {d.phase_table_as_in_files.sum()} of {len(d)}; "
          f"equal to the authors' correction of June 2022 (1.5, 0, 0.5, 1 pi ...): {d.phase_table_as_corrected.sum()} of {len(d)}")
    print("  (the phase table is not used by CCA, FBCCA or TRCA)")
    print(f"nine channels found by name in every file: {d.channels_ok.all()}; positions: {sorted(d.channel_index.unique())}")
    if d.md5_equals_figshare.notna().any():
        print(f"reduced files made from originals whose MD5 equals figshare's: {int(d.md5_equals_figshare.sum())} of {len(d)}")
    print(f"RMS over people (uV): median {d.rms_uv.median():.1f}, range {d.rms_uv.min():.1f} to {d.rms_uv.max():.1f}; "
          f"largest absolute value {d.max_abs_uv.max():.0f} uV")
    print(f"amplitude at 50 Hz against 47-53 Hz, 1 s window (uV, median over people): {d.amp_50hz_uv.median():.3f} "
          f"against {d.amp_47_53hz_uv.median():.3f} (a hardware notch removed the mains)")
    print(f"group average at Oz: largest of the 40 candidate frequencies is the target's own in {own.sum()} of 40 targets")
    if not own.all():
        for k in np.where(~own)[0]:
            print(f"  target {F[k]:g} Hz peaks at {F[amp[k].argmax()]:g} Hz")


if __name__ == "__main__":
    main()
