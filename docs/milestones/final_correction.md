# Correction of the final evaluation: the results with the repaired dry template

*14 Nov 2026. Plan: [`final_correction_plan.md`](final_correction_plan.md), approved by the author on
14 Nov 2026 with its two defaults (Q1: run on the lockbox people once the rehearsal has passed its checks;
Q2: the headline numbers stay those of the opening).*

> **Status: code, unit tests and rehearsal done. The corrected run on the lockbox people has not been made
> yet.** This part (A) is committed before that run.

## A. Before the run

### A1. The correction

**Rule:** a trial that M0 flagged as reaching the limit of the converter is not used to build the population
template. The list comes from `results/m0/flagged_trials.csv` (written in M0 from the raw values of all 102
people, before any decoding). It holds one trial: S067, dry headband, block 4, target 4 (9.75 Hz). S067 is a
development person.

Built from the development people only (`logs/final_correction_lockbox_prepare.log`):

| | Size of that trial | The person's 9 other trials of the target (median) |
|---|---|---|
| S067, dry, block 4, target 4 | 2 900 | 10.5 |

| Dry population template | Entry of the 9.75 Hz target, original | Repaired | The 11 other entries (median) |
|---|---|---|---|
| 68 development people (used for the lockbox people) | 4.27 | 0.91 | 1.01 |
| 45 development people (used in the rehearsal) | 6.42 | 0.99 | 1.09 |

- The repaired dry template differs from the original in the entry of that one target and nowhere else.
- The wet template has the same checksum as in the opening. The six networks are the files of the opening.
- The checksums of the repaired template are in `results/final/lockbox_corrected/frozen.json`, committed
  before the run; the run refuses to start if they do not match.

### A2. Code and unit tests

- `scripts/final_correction.py` builds the repaired template and then calls the decoding function of the
  opening (`final_evaluation.evaluate_person`) and its 15 tests. **`final_evaluation.py` and the modules it
  uses are not edited**: they are the files of the commit of the opening.
- The run on the lockbox people needs `--correct-lockbox`, an opening that is complete and a clean commit. It
  is recorded in `results/final/LOCKBOX_CORRECTION.txt` before the first person is decoded and is refused a
  second time.
- 5 new unit tests on synthetic data (`tests/test_correction.py`): the flagged trials come from the M0 file;
  the repaired template differs only where a trial was left out, and is identical bit for bit when nothing is
  left out; the run is made once and after the opening; the built-in check passes when only the dry template
  results move and fails when anything else moves; the rehearsal keeps no p-value. All 82 tests pass.

### A3. Rehearsal on the development people

The split of the first rehearsal: 23 development people as new people, 45 as population (S067 is one of the
45). No p-value is written or shown. `logs/final_correction_rehearsal.log`.

**Check fixed in the plan: what does not use the dry template is identical to the first rehearsal.** Passed.

| | Differ from the first rehearsal |
|---|---|
| Accuracies that do not use the dry template | 0 of 1 265 |
| Decisions of the wet template | 0 of 2 760 |
| Decisions of FBCCA | 0 of 5 520 |
| Impedance file | identical |
| The 11 tests that do not use the dry template (estimate, interval) | 0 of 11 |
| Accuracies that use the dry template | 103 of 161 |
| Decisions of the dry template | 134 of 2 760 |
| The 4 tests that use the dry template (estimate, interval) | 4 of 4 |

**The dry template numbers move, and by little** (23 development people, 1 s):

| Dry headband | Original | Corrected | Difference [95 % interval] |
|---|---|---|---|
| Template, no calibration, blocks 7 to 10 | 0.576 | 0.589 | +0.013 [+0.001, +0.024] |
| Template, no calibration, all ten blocks | 0.576 | 0.589 | +0.012 [+0.006, +0.018] |
| Template + 2 calibration blocks | 0.629 | 0.634 | +0.005 [-0.004, +0.015] |
| Template adapted without labels | 0.600 | 0.606 | +0.006 [-0.004, +0.018] |
| 9.75 Hz target only (all ten blocks) | 0.335 | 0.513 | |

| Estimate (p-values withheld) | Original | Corrected |
|---|---|---|
| H2 dry: template + 2 blocks minus eTRCA + 6 blocks | +0.133 | +0.139 |
| H5a dry: slope of accuracy per block | -0.0014 | -0.0014 |
| H5b dry: correlation of impedance with accuracy | +0.08 | +0.03 |
| H6 dry: adapted template minus template | +0.024 | +0.017 |

- The other 11 targets change by 0.009 at most.
- The gain of the adaptation (H6 dry) becomes smaller, as the plan suspected: part of it was the adaptation
  repairing the spoiled entry.
- The reproduction mode was run on the rehearsal set: the five result files are identical.

![Rehearsal of the correction](../../figures/final/rehearsal/03_correction.png)
