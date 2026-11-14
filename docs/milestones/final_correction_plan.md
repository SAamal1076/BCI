# Correction plan: the lockbox results with the repaired dry template

*14 Nov 2026. **Approved by the author on 14 Nov 2026, with the two defaults of the table at the end, before any
code was written.** Written after M5 found a flaw in the population template
([`M5_realtime.md`](M5_realtime.md), section F). Anything done differently is listed under "Deviations"
in the correction report ([`final_correction.md`](final_correction.md)). The text below is unchanged.*

## Why

The plan of the final evaluation says: *"If an error is found afterwards, the original and the corrected
result are both reported, with the reason."* The error: the dry population template contains the one trial of
the dataset that reaches the limit of the converter, and that trial dominates its entry for the 9.75 Hz target.

## What this is, and what it is not

- It is the **same analysis as the opening**, with one trial left out of the template.
- It is **not a second test.** The results of the lockbox people have been seen, and the correction was decided
  afterwards. The corrected result is reported **next to** the original one and labelled as computed after the
  opening. The original stays the pre-specified result.

## The correction, and nothing else

**Rule:** a trial that M0 flagged as reaching the limit of the converter is not used to build the population
template.

- M0 made that flag from the raw values alone, before any decoding, for all 102 people
  (`results/m0/flagged_trials.csv`, column `saturated`). It marks **one** trial: S067, dry headband, block 4,
  target 4. S067 is a development person.
- The mean response of S067 to target 4 with the dry headband is therefore taken from the 9 other blocks.
  Every other person, target and the whole wet template are unchanged.

**Not changed:** pipeline B2, `n0` = 4, the design, the 15 tests and the Holm correction, the six networks
(the same files, checked against the checksums committed before the opening), the 34 people, no exclusion.

The networks were trained on trials that include this one. They are not trained again: each trial is scaled
to unit variance before it enters a network, so there it is one ordinary trial among 6 840, not a value that
dominates a mean.

## What can change

Only what uses the dry template: the template with 0 to 6 calibration blocks, the template adapted without
labels, and the template over the ten blocks, all with the dry headband. Of the 15 tests, four: H2 dry, H5a
dry, H5b dry, H6 dry.

**Built-in check:** everything else must come out identical to the opening, to the last digit: FBCCA, ensemble
TRCA, the networks, every wet number, and the estimates and p-values of the 11 other tests (the Holm step is
recomputed over all 15). If it does not, the run is reported as failed and nothing is concluded from it.

## What is reported

- The 15 tests, original and corrected side by side: estimate, interval, p-value, Holm decision.
- The accuracies that use the dry template, original and corrected.
- **Reading rule, fixed now:** in the summary of the project a hypothesis is called supported only if it is
  supported in **both** analyses. Where the two differ, both are shown and the summary says that they differ.
- The headline numbers of the report, the README, the slides and the graphical abstract stay those of the
  opening; the corrected ones are given next to them in the report.

**Expected before running** (from the development people, where the repair raised the dry accuracy by 0.011):
the dry accuracies of the template rise by about 0.01; H2 dry stays supported; H5a and H5b dry stay
unsupported; H6 dry is the uncertain one, because part of its gain may have been the adaptation repairing the
spoiled entry.

## Procedure

1. **Code and unit tests** on synthetic data: the repaired template differs from the original only in the
   flagged trial's person, headband and target; the list of flagged trials comes from the M0 file; the run
   needs `--correct-lockbox`, a clean commit, an opening that is complete, and is refused a second time
   (`results/final/LOCKBOX_CORRECTION.txt`). The script of the opening is not edited, so that its
   reproduction still gives identical files.
2. **Rehearsal on the development people** (the split of the first rehearsal: 23 as new people, 45 as
   population, which includes S067). Checks: everything that does not use the dry template is identical to
   the first rehearsal; the dry template numbers move. No p-value is written or shown.
3. **Commit and push** the code, the tests and the rehearsal.
4. **Run once** on the 34 lockbox people, into `results/final/lockbox_corrected/`.
5. **Report** (`docs/milestones/final_correction.md`), and the two results side by side in
   `final_evaluation.md`, `REPORT.md` and the README.

## Decisions for the author (defaults in bold)

| | Question | Default |
|---|---|---|
| Q1 | After the rehearsal has passed its checks, run on the lockbox people without asking again? | **Yes.** The correction is one trial and the checks are fixed above. If a check fails, stop and report. |
| Q2 | Which numbers are the headline? | **Those of the opening,** with the corrected ones next to them. |

## Outputs

`docs/milestones/final_correction.md`, `scripts/final_correction.py`, unit tests, `results/final/rehearsal_corrected/`,
`results/final/lockbox_corrected/`, `results/final/LOCKBOX_CORRECTION.txt`, `logs/final_correction_*.log`,
`run_all.sh` extended, `final_evaluation.md`, `REPORT.md` and README updated.
