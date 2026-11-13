# M4 plan: time on task, impedance, who fails and what is confused

*13 Nov 2026. **Proposed, waiting for the author's approval. Nothing below has been run.** Written after M3
(`M3_network.md`) and the author's two decisions of 13 Nov 2026 (recorded in `docs/analysis_plan.md`).
Anything done differently will be listed under "Deviations" in the M4 report.*

## Purpose

M1 to M3 say how well a new user is decoded on average. M4 asks **when** and **for whom** it goes wrong, on
the development people, and fixes the tests of H5. Nothing new is trained and no setting is chosen.

## What is decoded

One decoder throughout, frozen in M2: the **cross-subject template with no calibration**, pipeline B2, 1 s
window, leave-one-subject-out on the 68 development people. All 10 blocks of each headband are decoded (120
trials), and the decision of **every trial** is stored. FBCCA is stored next to it as the reference that uses
no data. Everything below is computed from these decisions and from the label-free measures of M0 (noise
floor, mains pick-up, impedance, single-trial SNR).

## Part A: time on task (first half of H5)

A person wore one headband for 10 blocks, then the other one for 10 blocks. The order of trials inside a
block is not stored (M0), so time has block resolution.

- For each person and headband: accuracy of each block `a_b` (12 trials), and its **slope**
  `s = sum_b (b - 5.5) * (a_b - mean(a)) / sum_b (b - 5.5)^2`, in accuracy per block.
- The same slope for the single-trial SNR at Oz and for the impedance of each block (both from M0).
- The session as a whole: the 20 blocks in the order they were worn, separately for the people who wore the
  dry headband first and for those who wore the wet one first.
- **Ageing of a calibration** (descriptive): a template made of the person's blocks 1 and 2 only, tested on
  each of the blocks 3 to 10. If it loses accuracy faster than the template without calibration, the person's
  response drifts away from what was calibrated.

## Part B: impedance (second half of H5)

`Impedance.mat` gives one value per channel, block, headband and person.

- For each person and headband: `z = log10 of the median impedance over the 8 channels and the 10 blocks`.
- Across people: Spearman correlation of `z` with accuracy (1 s, all blocks), and with SNR, noise floor and
  mains pick-up.
- Within a person: does the impedance of a block go with the accuracy of that block (correlation over the 10
  blocks, then its distribution over people)?

## Part C: who fails and why (descriptive)

- A person **fails** with a headband when their accuracy over the 120 trials is not above chance (below 0.133).
- For each failure: accuracy with the other headband, at 2 s, and with per-person calibration (ensemble TRCA
  of M2); SNR, noise floor, mains pick-up, impedance; order of wearing.
- Reading: fails with one headband and not with the other points to the contact; fails with both points to
  the person's response.
- Across all people: Spearman correlation of accuracy with SNR, noise floor, mains pick-up and impedance.
- No analysis by age or sex: the groups are too small to say anything.

## Part D: what is confused (descriptive)

The 12 targets form a keypad of 4 rows and 3 columns; going down one row adds 0.5 Hz, going right one column
adds 2 Hz (layout to be checked against the figure of the dataset paper). Each error is put in one class:

| Class | Pairs | Share if errors were spread evenly |
|---|---|---|
| 0.5 Hz apart and neighbours on the keypad (same column) | 9 | 18 / 132 |
| 0.5 Hz apart, not neighbours on the keypad | 2 | 4 / 132 |
| neighbours on the keypad in the same row (2 Hz apart) | 8 | 16 / 132 |
| all others | 47 | 94 / 132 |

Also: the share of the decisions that each target receives, and the same tables for FBCCA.

## Hypotheses fixed now (run on the lockbox, with the others)

**H5a, time on task.** With the decoder above, the slope `s` of accuracy over the 10 blocks is negative.
One-sided Wilcoxon signed-rank test over people; two cases (dry, wet).

**H5b, impedance.** Across people, the Spearman correlation between `z` and accuracy is negative. One-sided
permutation test (10 000 permutations, fixed seed); two cases (dry, wet).

**H6, adaptation of the template without labels** (the author's decision after M3). Updating the
cross-subject template with the user's unlabelled blocks 1 to 6 (`T_f = (n0 * P_f + m_f * J_f) / (n0 + m_f)`,
`n0` = 4, the template's own decisions as labels) raises accuracy on blocks 7 to 10 at 1 s. One-sided Wilcoxon
signed-rank test of `adapted - template > 0`; two cases (dry, wet). **This hypothesis was written after its
effect was seen on the development people in M3** (+0.03 dry, +0.07 wet); the lockbox is what tests it.

**Family for the Holm correction, now complete: 15 tests.** H1 (4), H2 (2), H3 (3), H5a (2), H5b (2), H6 (2).
The lockbox is opened once, by a separate short plan after M4, with every method and setting frozen.

On the development people M4 reports estimates and 95 % bootstrap intervals, no p-value.

## Unit tests (synthetic data, before the recordings are used)

- The slope estimator returns a planted slope; a flat series gives zero.
- The permutation test gives small p-values for a planted relation and uniform ones without it.
- The error classes cover the 132 ordered pairs once, with the counts of the table above.
- The test person never enters their own population template (as in M2).

## Expectations written down before running (not hypotheses)

- Accuracy falls a little over the blocks with the dry headband (its impedance rises, M0) and not with the
  wet one.
- Impedance explains little of the differences between people with the dry headband: in M0 it went with mains
  pick-up (0.74) and not with SNR (0.11).
- Most people who fail with the dry headband do not fail with the wet one.
- Errors go to keypad neighbours 0.5 Hz away more often than an even spread would give.

## Not in M4

New decoders or settings; other window lengths; the lockbox; analyses by age or sex.

## Outputs

`docs/milestones/M4_failures.md`, `results/m4/` (with the decision of every trial), `figures/m4/`,
`logs/m4_*.log`, `scripts/m4_*.py`, unit tests, `run_all.sh` extended, README and analysis plan updated.
