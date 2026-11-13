# Final evaluation plan: the single opening of the lockbox

*13 Nov 2026. **Approved by the author on 13 Nov 2026, before anything below was run.** So far the lockbox
people were used only in the label-free checks of M0 (file integrity, noise, impedance); no decoder has seen
them and no target of their trials has been used. Written after M4 (`M4_failures.md`). Anything done
differently will be listed under "Deviations" in the final report.*

## Purpose

Everything reported so far comes from the 68 development people, on whom the pipeline and one setting were
chosen. The 34 lockbox people (every third subject, set aside in M0) are used **once**, to test the hypotheses
with nothing left to choose. After this step the numbers of the project are either confirmed or corrected.

## What is frozen

| Item | Value | Fixed in |
|---|---|---|
| Preprocessing | pipeline B2 (one mains frequency per trial, sub-bands 6/14/22 to 45 Hz, 3 harmonics, a-priori weights); no sample after the end of the window | M2 |
| Population for a lockbox person | the 68 development people, same type of headband | M2 |
| Weight of the population | `n0` = 4 | M2 |
| New-user design | calibration = first `k` blocks (`k` = 0, 1, 2, 4, 6), test = blocks 7 to 10 | M2 |
| Network | EEGNet-type, 3 572 parameters, 1 s, 3 seeds, at most 60 epochs, patience 8, learning rate 0.001 | M3 |
| Adaptation without labels | on blocks 1 to 6; A2 = batch-normalisation statistics, then entropy minimisation (one pass, 6 steps, learning rate 0.001); template updated with its own decisions | M3 |
| Chance threshold, windows, ITR | as in the reports | M1 to M4 |

No lockbox person contributes to any template, network, statistic or choice.

## What this plan decides, and nothing else

1. **Networks for the lockbox people** are trained on the 68 development people, one network per type of
   headband and seed (6 trainings). Validation people by the rule of M3 (every 6th person from the 4th):
   11 for validation, 57 for training. In M3 the networks were trained inside folds of the development
   people, so they cannot be reused as they are.
2. **No person is excluded.** A file that cannot be read is reported and the person counted as missing; there
   is no other reason to leave someone out.
3. **H4** (graph-based denoising, exploratory) was not carried out and is not tested.
4. **The rehearsal** of the procedure below.

## The 15 tests (all one-sided, familywise level 0.05 by Holm)

`d = accuracy(dry) - accuracy(wet)` for a person.

| | Hypothesis | Quantity per person | Test |
|---|---|---|---|
| H1 x4 | Dry electrodes give lower accuracy | `d` for FBCCA at 1 s and 2 s, and for ensemble TRCA (leave-one-block-out) at 1 s and 2 s | Crossover: rank-sum test of "first headband minus second" between the two orders of wearing |
| H2 x2 | Template + 2 blocks is within 0.05 of ensemble TRCA + 6 blocks | `e = template(k=2) - etrca(k=6)` at 1 s; dry, wet | Wilcoxon signed-rank test of `e + 0.05 > 0` |
| H3 x3 | Entropy adaptation helps the network, more with dry | `g = A2 - A0` at 1 s (mean of 3 seeds): `g(dry)`, `g(wet)`, `g(dry) - g(wet)` | Wilcoxon signed-rank test of `> 0` |
| H5a x2 | Accuracy falls over the 10 blocks | slope `s` of block accuracy (template, no calibration, 1 s); dry, wet | Wilcoxon signed-rank test of `s < 0` |
| H5b x2 | Higher impedance, lower accuracy | across people: Spearman correlation of `log10` median impedance with accuracy (template, no calibration, 1 s, 10 blocks); dry, wet | Permutation test (10 000, seed 0) of `rho < 0` |
| H6 x2 | The template adapted without labels is better | `adapted - template` on blocks 7 to 10 at 1 s; dry, wet | Wilcoxon signed-rank test of `> 0` |

- Wilcoxon tests: zero differences are dropped; if none is left the p-value is 1.
- **Holm:** the 15 p-values are sorted, `p(1) <= ... <= p(15)`; `p(i)` is compared with `0.05 / (16 - i)`;
  the procedure stops at the first one that fails, and every hypothesis before it is supported.
- H6 was written after its effect was seen on the development people (M3); this is said wherever it is reported.
- Expected before opening, from the development people: H1 and H6 supported; H2 supported for dry and
  uncertain for wet; H3 and H5 not supported. This expectation is written down so that it can be compared
  with the outcome.

## What is reported

- For each test: the estimate, its 95 % bootstrap interval (2 000 resamples of people, seed 0), the number of
  people, the p-value and the Holm decision. Results that do not support a hypothesis are in the same table
  as those that do.
- The main descriptive tables again on the lockbox people (all methods with no calibration, the calibration
  curve, dry minus wet), next to the development values, so that the optimism of the development numbers can
  be read directly.
- People not above chance.

## Procedure

1. **One script,** `scripts/final_evaluation.py`, computes every quantity and test above for a list of
   "new" people given a list of "population" people.
2. **Rehearsal on the development people.** The script is first run with every third development person
   (the 1st, 4th, ...: 23 people) as the new people and the other 45 as the population (7 of them for
   validation). This exercises the same code, including the training of the networks, and gives no access to
   the lockbox. The estimates are checked against M2 to M4 and shown to the author. The tests are executed to
   exercise the code, but their p-values are neither written nor shown: the rule "no p-value on the
   development people" stays. Only whether each test returned a finite number is logged.
3. **Lock.** The script, the unit tests and the rehearsal results are committed and the commit is tagged
   `pre-lockbox`. The script refuses to load a lockbox person unless it is started with `--open-lockbox`, and
   refuses to run a second time once `results/final/LOCKBOX_OPENED.txt` exists (it records the date and the
   commit).
4. **Open, once,** after the author has seen the rehearsal and said so: population = the 68 development
   people, new people = the 34 lockbox people.
5. **Report** (`docs/milestones/final_evaluation.md`), README updated with the tested results.

## Rules after the opening

- No method, setting, test or exclusion is changed.
- If an error is found afterwards, the original and the corrected result are both reported, with the reason.
- Any further look at the lockbox people is labelled exploratory.

## Unit tests (synthetic data, before the rehearsal)

- Holm procedure on known p-values; the Wilcoxon wrapper with all-zero differences.
- The script cannot load a lockbox person without `--open-lockbox`, and not twice.
- New people never appear among the population, training or validation people.

## Outputs

`docs/milestones/final_evaluation.md`, `results/final/` (rehearsal and lockbox), `figures/final/`,
`logs/final_*.log`, `scripts/final_evaluation.py`, unit tests, `run_all.sh` extended, README updated.
