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

## To be fixed before the milestone that needs it

| Before | What |
|---|---|
| M2 | Proposed in `docs/milestones/M2_plan.md` (waiting for approval): correction of the pipeline and its choice among three candidates, design for a new user, cross-subject template, calibration curve, use of the lockbox, tests of H1 (crossover) and H2 (margin 0.05), family for the Holm correction. |
| M3 | Network, test-time adaptation settings, compute budget, seeds. |
| M4 | Time-on-task and impedance analyses (H5). |
| M5 | Real-time replay: stream order, latency measurement, stopping rule. |
