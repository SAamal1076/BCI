# Analysis plan

*Version 0, 12 Nov 2026. Committed before any data file was opened. It fixes only what has to be fixed
before the data are seen. Every later section is added, with its date, before the milestone that uses it is
run (see the commit history). Any deviation from this plan is reported as such in the README and the report.*

## Question

Decode which of 12 flickering targets a person is looking at from an 8-channel EEG headband over the back of
the head, for a **new user with no or few calibration trials**, with dry electrodes. Report accuracy, speed
(information transfer rate), calibration cost, model size and the failure cases.

## Data

- **Main:** wearable SSVEP dataset (Zhu et al., *Sensors* 2021): 102 subjects, 12 targets, 8 channels, 10 blocks
  with a dry-electrode headband and 10 blocks with a wet-electrode headband.
- **Reference:** BETA (Liu et al., *Front. Neurosci.* 2020): 70 subjects, 40 targets, 64 channels. Used to check
  that the implementations reproduce published results, and for comparison with laboratory-grade recordings.
- Raw data are never committed. See `DATA.md`.

## Subjects: development and lockbox

- **Lockbox:** every third subject of the wearable dataset, S003, S006, ..., S102 (34 subjects).
  **Development:** the other 68. The rule uses the subject number only and was fixed before any data was opened.
- Until the final evaluation, lockbox files are used only for label-free checks (file integrity, noise level,
  impedance, questionnaire). Nothing that uses the target index of a trial is computed on them.
- Everything exploratory, and every choice or tuning of a method, uses development subjects only.
- The final evaluation on the lockbox is run once, after the methods, their settings and the statistical tests
  have been frozen in this file. How the lockbox subjects are used at that point is specified before M2.
- Any earlier use of lockbox labels would be reported as a deviation.

## No exclusions

All 102 subjects, both electrode types, all blocks, all trials and all channels are kept. Weak or noisy
recordings are reported, not removed.

## Evaluation principles

- Splits are by subject or by block, never by trial window.
- Filters with learned parameters, spatial filters, templates, normalisation and hyperparameters are fitted on
  training data only (nested when tuned).
- Per-person evaluation: leave-one-block-out, same electrode type.
- Calibration-free evaluation: nothing from the test subject is used.
- Few-calibration evaluation: `k` blocks from the new user; the rest of their blocks are the test data.
- Dry versus wet: paired by subject.
- Window lengths from 0.2 s to 2 s.
- Metrics: accuracy (chance level 1/12) and information transfer rate,
  `ITR = (60/T_sel) * [log2 N + P*log2 P + (1 - P)*log2((1 - P)/(N - 1))]` bits/min, with `N` targets, accuracy
  `P`, and `T_sel` = window length + gaze-shift time (value fixed before M1).
- Statistics: per-subject results, mean and standard deviation, paired Wilcoxon signed-rank tests across
  subjects, Holm correction over the pre-registered family.
- Comparison with published numbers is made on the same data and stated fairly. Note fixed now: the dataset
  paper chose its filter-bank parameters by grid search on the same recordings, separately for each electrode
  type, so its offline accuracies are optimistic. Results are reported with parameters fixed a priori and,
  separately, with the published parameters.

## Hypotheses (as first stated on 12 Nov 2026, before any data was opened)

- **H1.** Dry electrodes give lower accuracy than wet ones, and the gap shrinks as the window gets longer.
- **H2.** A cross-subject model plus a few calibration blocks from the new user comes close to full per-person
  calibration (threshold set before M2).
- **H3.** Test-time adaptation improves calibration-free accuracy on new users, most for dry electrodes.
- **H4 (exploratory).** Graph-based multichannel denoising raises the SSVEP signal-to-noise ratio and the
  accuracy for dry electrodes.
- **H5.** Accuracy drops over the session, and electrode impedance explains part of the differences between people.

Notes recorded with the hypotheses, from the dataset paper alone (no data opened):

- The first half of H1 is already published for this dataset (dry below wet), so it is a replication.
- The published gap between wet and dry **grows** with the window for the training-free method (FBCCA: 0.04
  at 0.2 s, 0.13 at 2 s) and **shrinks** for the per-person method (FBTRCA: 0.28 at 0.2 s, 0.20 at 2 s). The
  second half of H1 therefore needs a precise wording (which method, which measure of the gap). **To be fixed
  before M1 and dated here.**
- The paper reports no significant correlation between impedance and accuracy within an electrode type, and
  a significant one (r = -0.24, p = 0.01, FBTRCA) between the wet-minus-dry difference in impedance and in
  accuracy. The second half of H5 is partly a replication as well.
- Trials are stored sorted by target, so the order of trials inside a block is unknown. H5 is tested at the
  resolution of blocks.

## Facts established by M0 (12 Nov 2026) and open points they raise

Facts (see `docs/milestones/M0_data_audit.md`):

- Electrode axis: position 1 = dry, position 2 = wet (`wearable.DRY`, `wearable.WET`). The documented label
  is reversed. To be confirmed by the M1 accuracies.
- The 0.14 s latency and the frequency and phase table are confirmed.
- Mains interference is removed per epoch by least squares (`spectral.remove_mains`), not by an IIR notch.

Open points, to be decided by the author and dated here before the milestone concerned:

- **Dry versus wet is a crossover design.** The headband worn second tends to do worse (M0, descriptive).
  The test of H1 must take the order of wearing into account (before M2).
- **H5** can only be tested between blocks, and between the first and the second headband with order as a
  factor (before M4).
- **Filters of the decoding pipeline** must pass an edge-transient test on synthetic epochs before use (before M1).

## Fixed before M1 (approved 12 Nov 2026, before any accuracy was computed)

Details and sources: `docs/milestones/M1_plan.md`.

- **H1, final wording.** For the same person, method and window length, accuracy is lower with the dry
  headband than with the wet one. Primary cases: FBCCA with a-priori weights and ensemble TRCA, at 1 s and at
  2 s. The gap as a function of window length and the "time cost of dry electrodes" are reported without a
  directional claim. The test (crossover analysis, subjects) is fixed before M2.
- **Baselines.** CCA, FBCCA, TRCA and ensemble TRCA; 5 harmonics; reference filter bank (Chebyshev type I,
  sub-bands from 6, 14, 22, 30, 38 Hz to 90 Hz); a-priori weights `n^(-1.25) + 0.25` with 5 sub-bands. Nothing
  is tuned on these data. Results with the weights published for this dataset are reported separately.
- **Project pipeline from M2 on (variant B):** samples from the start of the epoch to the end of the window,
  least-squares mains removal on that segment, zero-phase filter bank, then the window is kept. No sample
  after the end of the window is used.
- **ITR:** `T_sel` = window + 0.5 s gaze shift. ITR is computed per subject and averaged; it is set to 0 when
  accuracy is at or below chance.
- **Reproduction gate:** G1 to G5 of the M1 plan (0.05 in accuracy on the wearable data, 10 % on the BETA peak ITR).

## Facts established by M1 (13 Nov 2026) and open points they raise

Report: `docs/milestones/M1_baselines.md`. Development subjects only.

- **The reproduction gate failed as pre-registered** (G1 to G3 under the reference convention, variant A).
  G4 passed: wet is above dry in all six comparisons, so position 1 = dry is final. G5 (BETA) is open.
- **Cause, not an error in the decoders:** the mains component inside the pass-band breaks TRCA, and the
  published accuracies are matched only by filtering the whole epoch (samples after the window). The
  published numbers of this dataset are therefore not a valid target for a pipeline without future samples.
- **The mains-removal step of variant B has a flaw** when followed by a decoder that combines channels: the
  mains frequency is chosen per channel. It biases CCA and FBCCA decisions towards 12.25 and 12.75 Hz
  (4th harmonic at 49 and 51 Hz).
- **Nothing was changed after seeing M1 results.** The hypotheses and the settings above stand. Variant B as
  defined above was used for every M1 number.

## Decisions of the author after M1 (13 Nov 2026)

1. **The failed gate.** The diagnosis of the M1 report is accepted. The gate stays recorded as failed
   (G1 to G3). The project goes on with a pipeline that uses no sample after the window.
2. **Mains removal.** The correction (one mains frequency per trial for all channels) is part of the M2
   plan, with one re-run of the baselines. The M1 numbers stay as reported.
3. **BETA.** Gate G5 is kept as the independent check of the decoders. The dataset is reduced to its nine
   channels on the author's computer (`scripts/beta_reduce.py`) and analysed from the reduced files.

## Fixed before M2 (approved 13 Nov 2026, before anything of M2 was run)

Details: `docs/milestones/M2_plan.md`.

- **Pipeline:** chosen once among B (as in M1), B1 (one mains frequency per trial for all channels) and B2
  (B1 with the band limited to 45 Hz and 3 harmonics), by the mean accuracy at 1 s of FBCCA and ensemble TRCA
  over the two headbands, on the development people. B2 is taken only if it is at least 0.01 above B1.
- **New user:** calibration = the first `k` blocks (`k` = 0, 1, 2, 4, 6), test = blocks 7 to 10, other people
  by leave-one-subject-out.
- **Cross-subject template:** `T_f = (n0 * P_f + k * I_f) / (n0 + k)`, extended-CCA decision; `n0` chosen once
  on the development people in {0.5, 1, 2, 4, 8}.
- **H1 test:** crossover analysis (rank-sum test on first minus second headband between the two orders of
  wearing, one-sided); four cases: FBCCA and ensemble TRCA at 1 s and 2 s.
- **H2 (threshold fixed):** cross-subject template with 2 blocks is not more than 0.05 below ensemble TRCA with
  6 blocks, at 1 s; one-sided Wilcoxon signed-rank test; two cases (dry, wet).
- **Lockbox:** opened once, after the methods of M3 are frozen. Holm correction over the six tests above plus
  those that the M3 and M4 plans add. No p-value on the development people.

## Facts established by M2 (13 Nov 2026), development people only

Report: `docs/milestones/M2_calibration.md`.

- **Frozen:** pipeline B2 (one mains frequency per trial for all channels; sub-bands from 6, 14 and 22 Hz to
  45 Hz; 3 harmonics; a-priori weights), `n0` = 4, the new-user design. Both choices were made on the
  development people by the rules fixed before the run.
- With no calibration the cross-subject template is above FBCCA at every window (1 s: +0.10 dry, +0.08 wet).
- H2 on the development people: holds with the dry headband; with the wet one the interval of the difference
  reaches below the margin at 1 s. Nothing in H1, H2, their tests or the margin was changed after seeing this.
- The lockbox has not been loaded.

## Fixed before M3 (approved 13 Nov 2026, before anything of M3 was run)

Details: `docs/milestones/M3_plan.md`.

- **Network:** EEGNet-type, about 3 600 parameters, input = the three sub-bands of pipeline B2 at 1 s; no
  architecture search; three seeds; four folds of people (51 for training, of which 8 for validation; 17 for test).
- **Adaptation without labels** on the new user's first six blocks, test on blocks 7 to 10: A0 none, A1
  batch-normalisation statistics, A2 entropy minimisation on the batch-normalisation scale and shift.
- **H3 tests** (lockbox, 1 s, `g = accuracy(A2) - accuracy(A0)`): H3a `g > 0` dry, H3b `g > 0` wet, H3c
  `g(dry) - g(wet) > 0`; one-sided Wilcoxon signed-rank tests. With H1 and H2 the Holm family has nine tests.
- **H4** is not part of M3.

## Facts established by M3 (13 Nov 2026), development people only

Report: `docs/milestones/M3_network.md`.

- With no calibration at 1 s the network (0.534 dry, 0.621 wet) is below the cross-subject template (0.572,
  0.734).
- H3 on the development people: `g` = +0.008 (dry) and +0.005 (wet); `g(dry) - g(wet)` = +0.003. The tests
  H3a, H3b and H3c stay as fixed and will be run on the lockbox; a null result is expected and will be reported.
- A secondary analysis: the template updated with the user's unlabelled trials gains +0.031 (dry) and +0.071
  (wet). It is not a hypothesis of the project so far. If it is to carry a claim, its test must be fixed in a
  plan before the lockbox is opened.
- The lockbox has not been loaded.

## Decisions of the author after M3 (13 Nov 2026)

1. **Adaptation of the template without labels becomes a hypothesis (H6)**, to be tested on the lockbox. It was
   written after its effect was seen on the development people (M3: +0.03 dry, +0.07 wet); this is stated
   wherever H6 is reported. Its test is fixed in `docs/milestones/M4_plan.md`.
2. **No further training of the network.** The M3 results stand as they are.

## Fixed before M4 (approved 13 Nov 2026, before anything of M4 was run)

Details: `docs/milestones/M4_plan.md`. Decoder for all of M4: cross-subject template, no calibration, 1 s.

- **H5a:** the slope of accuracy over the 10 blocks of a headband is negative; one-sided Wilcoxon signed-rank
  test over people; dry and wet.
- **H5b:** across people, the Spearman correlation between `log10` of the median impedance and accuracy is
  negative; one-sided permutation test (10 000 permutations, fixed seed); dry and wet.
- **H6:** the template updated with the user's unlabelled blocks 1 to 6 (`n0` = 4) is more accurate on blocks
  7 to 10 at 1 s than the template; one-sided Wilcoxon signed-rank test; dry and wet. Written after its effect
  was seen on the development people.
- **Holm family, complete: 15 tests.** H1 (4), H2 (2), H3 (3), H5a (2), H5b (2), H6 (2). The lockbox is opened
  once, by a separate short plan, after M4.

## Facts established by M4 (13 Nov 2026), development people only

Report: `docs/milestones/M4_failures.md`.

- H5a on the development people: slope of accuracy -0.0035 per block (dry) and -0.0016 (wet); the intervals
  include zero. H5b: correlation of impedance with accuracy +0.07 (dry) and +0.21 (wet), not negative.
- The tests of H5a, H5b and H6 stay as fixed. Two null results are expected for H5 and will be reported.
- The keypad has 3 rows of 4 targets; the error classes of the M4 plan were corrected before the decisions
  were looked at (deviation D1 of the M4 report).
- The lockbox has not been loaded.

## Fixed before the final evaluation (approved 13 Nov 2026, before anything of it was run)

Details: `docs/milestones/final_evaluation_plan.md`.

- **Frozen:** pipeline B2, `n0` = 4, the new-user design, the network and its training settings, the two
  adaptations without labels, the 15 tests and the Holm correction at familywise level 0.05.
- **Population for a lockbox person:** the 68 development people. **Networks:** trained on the 68 development
  people, one per type of headband and seed; validation people by the rule of M3 (every 6th from the 4th: 11
  for validation, 57 for training).
- **No person is excluded.** H4 was not carried out and is not tested.
- **Rehearsal** on the development people (23 as new people, 45 as population) before the opening; its
  p-values are neither written nor shown.
- **One opening:** the script needs `--open-lockbox`, and refuses a second run. The commit before the opening
  is tagged `pre-lockbox`. After the opening no method, setting, test or exclusion is changed.

## Facts established by the rehearsal (13 Nov 2026), development people only

Details: `docs/milestones/final_rehearsal.md`.

- With 23 development people as new people and the other 45 as population, the script of the final evaluation
  returns the M2 values exactly where no population is involved (552 accuracies), and close values elsewhere.
- The 15 tests ran; their p-values were neither written nor looked at.
- The population template and the six networks for the lockbox people were built from the 68 development
  people before the opening; their checksums are in the commit tagged `pre-lockbox`.

## Results of the final evaluation (13 Nov 2026), 34 lockbox people, opened once

Details: `docs/milestones/final_evaluation.md`. One-sided tests, Holm at familywise level 0.05 over 15 tests.

| Hypothesis | Tests supported | Estimates |
|---|---|---|
| H1 dry below wet | 4 of 4 | -0.211 (FBCCA 1 s), -0.160 (FBCCA 2 s), -0.333 (eTRCA 1 s), -0.272 (eTRCA 2 s) |
| H2 template + 2 blocks within 0.05 of eTRCA + 6 blocks | dry: yes; wet: no | dry +0.145 [+0.082, +0.211]; wet -0.053 [-0.076, -0.031] |
| H3 entropy adaptation of the network | 0 of 3 | dry +0.007, wet +0.002, dry minus wet +0.005 |
| H5a accuracy falls over the blocks | 0 of 2 | slope per block: dry -0.0027, wet +0.0021 |
| H5b higher impedance, lower accuracy | 0 of 2 | Spearman: dry -0.35 (p 0.019 before the correction, 0.15 after), wet -0.19 |
| H6 template adapted without labels (post hoc) | 2 of 2 | dry +0.040 [+0.020, +0.060]; wet +0.069 [+0.048, +0.090] |

- The outcome is the expectation written in the plan before the opening.
- No method, setting, test or exclusion was changed after the opening. Descriptive numbers computed
  afterwards (`scripts/final_summary.py`) are labelled as such.

## Decision after the final evaluation (13 Nov 2026)

- **M5 (real-time replay) is not carried out** (author's decision). Nothing is claimed about real-time use:
  the decisions of this project are offline, and the only timing evidence is the compute measurement of M3.
- M6 (report, graphical abstract, presentation) contains no new analysis. Plan: `docs/milestones/M6_plan.md`;
  done on 14 Nov 2026 (`docs/milestones/M6_note.md`), with a fresh-clone check in which no tracked file changed.

## After M6 (14 Nov 2026)

- The author asked for a **short version of M5** (streaming replay, latency, stopping when confident). Plan
  proposed and waiting for approval: `docs/milestones/M5_plan.md`. It uses the development people only, changes
  no method, runs no test, and leaves the lockbox opened once.
- Until M5 has been run, the statements "real-time replay not done" in the report and the slides stay true.
