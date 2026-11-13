# M2 plan: new users and calibration

*Proposed on 13 Nov 2026 and **approved by the author the same day**, as written, before anything was run.
Written after M1 (`M1_baselines.md`) and the author's three decisions of 13 Nov 2026 (recorded in
`docs/analysis_plan.md`). Anything done differently is listed under "Deviations" in `M2_calibration.md`.*

## Purpose

A wearable BCI is used by people it has never seen. M2 measures, on the development people, how well a new
user can be decoded with no calibration at all, how accuracy grows with a few calibration blocks, and what dry
electrodes cost. It also fixes how H1 and H2 will be tested on the lockbox.

One calibration block is 12 trials of 4 s (1 s cue, 2 s flicker, 1 s rest): 48 seconds.

## Step 0: correct the pipeline, then freeze it

M1 found a flaw in the mains removal of variant B (the mains frequency is chosen for each channel separately).
Three candidates are compared once on the development people, with the M1 decoders and nothing else:

| | Mains removal | Band and references |
|---|---|---|
| B (as in M1) | least squares, frequency per channel | 6-90 Hz filter bank, 5 harmonics |
| B1 | least squares, **one frequency per trial for all channels** | as B |
| B2 | as B1 | **band limited below the mains:** sub-bands from 6, 14 and 22 Hz to 45 Hz, references with **3 harmonics** (highest reference frequency 44.25 Hz) |

All three use past samples and the window only (no sample after the window), as B.

- **Criterion, fixed now:** mean accuracy at 1 s over FBCCA and ensemble TRCA (leave-one-block-out, a-priori
  weights `n^(-1.25) + 0.25`) and over the two headbands. The best candidate becomes the project pipeline. If
  B2 is not at least 0.01 above B1, B1 is kept (it stays closest to the published settings).
- Also reported for each candidate: share of the decisions on 12.25 and 12.75 Hz, accuracy per headband.
- This is a choice made on development data and it is reported as such. Then the M1 baselines are re-run
  **once** with the chosen pipeline; the M1 numbers stay in the M1 report.
- Before the data: unit tests on synthetic epochs (the shared-frequency removal leaves no decision bias on
  noise; edge error of the new sub-band filters; filter gains at 45 and 50 Hz).

## Step 1: design for a new user

For a test person `s` and one headband:

- **Calibration** = the first `k` blocks of that person with that headband, `k` in {0, 1, 2, 4, 6}.
- **Test** = blocks 7 to 10 (48 trials). The same test trials for every `k` and every method, so all
  comparisons are paired. Calibration always comes before the test in time, as in real use.
- **Other people** = the population. On the development set: leave-one-subject-out (the 67 other development
  people, same headband type). Nothing of person `s`, with either headband, enters the population.
- Windows 0.2 to 2.0 s. Primary window: 1.0 s. Accuracy and ITR (window + 0.5 s).

## Step 2: methods

All share the frozen pipeline, the filter bank and the a-priori sub-band weights.

1. **FBCCA** (`k = 0`): uses no data from anyone. The training-free reference.
2. **Cross-subject template** (`k = 0, 1, 2, 4, 6`), the "cross-subject model" of H2. For each target `f`:
   - population template `P_f`: mean response to `f` over the other people (mean over their blocks first);
   - the user's own template `I_f`: mean of the user's `k` calibration trials of `f`;
   - **combined template** `T_f = (n0 * P_f + k * I_f) / (n0 + k)`. The population counts as `n0` blocks of the
     user's own data. `k = 0` gives the population template alone.
   - decision as in extended CCA (Nakanishi et al. 2014; Chen et al. 2015), for each sub-band `n`:
     `r1 = ` CCA correlation of the trial `X` with the sine-cosine reference `Y_f`;
     `r2 = corr(X w, T_f w)` with `w` the spatial filter of CCA(`X`, `Y_f`);
     `r3 = corr(X v, T_f v)` with `v` the spatial filter of CCA(`T_f`, `Y_f`);
     `score_f = sum_n w(n) * sum_i sign(r_i) * r_i^2`. It needs no trial of the user, so it works for any `k`.
   - `n0` is the only new setting. Grid {0.5, 1, 2, 4, 8}; chosen once on the development people (largest
     mean accuracy at 1 s over `k` in {1, 2, 4} and both headbands), then frozen.
3. **Per-person only** (no population): the same decision with `T_f = I_f` (`k = 1, 2, 4, 6`), and ensemble
   TRCA (`k = 2, 4, 6`; TRCA needs at least two trials per target). Ensemble TRCA with `k = 6` is the
   "full per-person calibration" of H2.

Not in M2: networks and test-time adaptation (M3), forward-only filtering and dynamic stopping (M5),
transfer between headband types, any new spatial-filter method.

## Step 3: what is reported (development people, descriptive)

- **Calibration curve:** accuracy and ITR against `k` (and against calibration time, `k` x 48 s) for the three
  families; dry and wet; with bootstrap 95 % intervals over people.
- **No calibration:** cross-subject template (`k = 0`) against FBCCA, same trials.
- **Dry against wet** with the frozen pipeline, by order of wearing; time cost of dry electrodes.
- Per-person results: people at chance, who gains from the population template and who does not, relation
  with the single-trial SNR of M0.
- Compute time and stored numbers per method.
- No p-value is reported on the development people.

## Hypotheses and how they will be tested (fixed now; run on the lockbox later)

The lockbox (34 people) is opened **once**, after the methods of M3 are frozen, for all hypotheses together.
Then: population = the 68 development people, every setting frozen, each lockbox person is a new user.

- **H1 (wording fixed before M1).** For the same person, method and window, accuracy is lower with the dry
  headband. Four primary cases: FBCCA and ensemble TRCA (leave-one-block-out), at 1 s and 2 s.
  *Test:* crossover analysis. `d = accuracy(dry) - accuracy(wet)` for each person. Estimated effect of the
  electrode: `0.5 * [mean(d | dry worn first) + mean(d | wet worn first)]`, which cancels the effect of being
  the second headband. Tested by a rank-sum test (Mann-Whitney) on "first headband minus second headband"
  between the two orders of wearing, one-sided. The plain paired Wilcoxon test on `d` is reported next to it.
- **H2.** A cross-subject template with **2** calibration blocks (96 s) comes close to full per-person
  calibration with **6** blocks (ensemble TRCA, 288 s), at 1 s. "Close" = not more than **0.05** lower
  (accuracy). *Test:* for each person `e = accuracy(cross-subject, k = 2) - accuracy(ensemble TRCA, k = 6)`;
  one-sided Wilcoxon signed-rank test of `e + 0.05 > 0`. Two cases: dry and wet.
- **Family for the Holm correction:** these six tests, plus the tests of H3 and H5 that the M3 and M4 plans
  will add before the lockbox is opened. H4 is exploratory and stays outside the family.
- Effect sizes with 95 % intervals are reported for every test, whatever the p-value.

## Leakage rules (checked by unit tests on synthetic data before the recordings are used)

- A person's data never enter their own population template (a marker planted in the test person must not
  appear in `P_f`).
- Calibration blocks and test blocks never overlap; spatial filters, templates and `n0` use training data only.
- The choices of step 0 and of `n0` are made on development people; the lockbox is not loaded in M2.
- Splits are by person and by block, never by window.

## Expectations written down before running (not hypotheses)

- With no calibration the population template should beat FBCCA at short windows and matter less at 2 s.
- The gain from the population should shrink as `k` grows.
- H2 may well fail with the wet headband, where per-person calibration is strong (M1: 0.84 at 1 s), and hold
  with the dry one, where it is weak (0.52). Either outcome is reported as it is.

## Outputs

`docs/milestones/M2_calibration.md` (report), `results/m2/`, `figures/m2/`, `logs/m2_*.log`,
`src/ssvep/` (`pipeline.py`, `transfer.py`, `stats.py`), `scripts/m2_*.py`, unit tests, `run_all.sh` extended,
README and analysis plan updated.
