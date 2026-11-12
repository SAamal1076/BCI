# M1 plan: reproduce the standard methods and their published results

*Proposed on 12 Nov 2026 and **approved by the author the same day**, as written, before anything was run. The
approval includes the proposed wording of H1 and the gaze-shift time of 0.5 s. Written from the two dataset
papers and from the public reference implementation only. Anything done differently is listed under
"Deviations" in `M1_baselines.md`.*

## Purpose

Before anything new is built, show that our implementations of the three standard SSVEP decoders give the
numbers that others published on the same data. If they do not, later comparisons mean nothing. M1 also gives
the final confirmation of which headband is dry (M0, criterion C3).

## The three methods in one paragraph each

**CCA (no training).** For each candidate frequency `f`, build reference signals
`Y_f = [sin(2*pi*f*t), cos(2*pi*f*t), ..., sin(2*pi*Nh*f*t), cos(2*pi*Nh*f*t)]` and find the combination of the
EEG channels and the combination of the references that correlate most:
`rho_f = max over w_x, w_y of corr(X*w_x, Y_f*w_y)`. The answer is the frequency with the largest `rho_f`.
Each sine-cosine pair fits any phase, so CCA ignores the phase code of the targets.

**FBCCA (no training).** The same after splitting the EEG into `N` sub-bands (sub-band `n` starts higher and
keeps only the upper harmonics), then `score_f = sum_n w(n) * rho_{f,n}^2` with `w(n) = n^(-a) + b`.
Harmonics have a better signal-to-noise ratio than the fundamental, which sits in the strong background
activity around 10 Hz.

**TRCA and ensemble TRCA (per-person calibration).** From a person's calibration trials of target `k`, find the
channel combination `w_k` that makes the trials most alike: maximise `(w' S w) / (w' Q w)`, with `S` the sum of
covariances **between** different trials and `Q` the covariance of all trials. The test trial is compared with
the person's average response to each target, both filtered by `w_k` (ensemble: by all 12 filters together),
and sub-bands are combined as in FBCCA. Unlike CCA it uses the phase of the response.

## Data

- **Wearable dataset, 68 development subjects only.** The 34 lockbox subjects are not loaded. Dry = position 1,
  wet = position 2 (M0). All 8 channels. Window starts 0.14 s after stimulus onset.
- **BETA, all 70 subjects** (reference dataset, no lockbox). The nine channels of the BETA paper (Pz, PO3, PO5,
  PO4, PO6, POz, O1, Oz, O2), latency 0.13 s. A short data check comes first: file layout, channel names,
  frequency and phase table (the dataset has a published correction of its phase table), spectral peaks.
- Window lengths: 0.2 to 2.0 s in steps of 0.2 s.

## Settings (all taken from published sources, none tuned by us)

| | Value | Source |
|---|---|---|
| Harmonics `Nh` | 5 | both dataset papers |
| Filter bank | Chebyshev type I, sub-band `n` from 6, 14, 22, 30, 38 Hz to 90 Hz (stop bands 4, 10, 16, 24, 32 and 100 Hz; 3 dB, 40 dB; 0.5 dB ripple), forward-backward | reference implementation of Nakanishi et al. 2018 (after Chen et al. 2015) |
| A-priori weights | `w(n) = n^(-1.25) + 0.25`, `N = 5` sub-bands, for FBCCA and for TRCA | same (its FBCCA default) |
| Published weights, wearable paper | FBCCA: dry `a = 2, b = 0.25`, wet `a = 1.25, b = 0`, `N = 5`. FBTRCA: dry `a = 1.25, b = 0.25`, wet `a = 1.75, b = 0.5`, `N = 3` | Zhu et al. 2021 (grid search on the same data) |
| CCA band | sub-band 1 (wearable); 6-80 Hz (BETA, as in its paper) | |
| TRCA evaluation | leave-one-block-out: 10 folds (wearable), 4 folds (BETA); templates and spatial filters from the training blocks only | papers |
| ITR | `60/T_sel * [log2 N + P*log2 P + (1-P)*log2((1-P)/(N-1))]`, per subject, then averaged | |
| `T_sel` | project value: window + 0.5 s gaze shift. For comparison only: window alone (wearable paper), window + 0.55 s (BETA paper) | |

## Three ways of filtering a short window (the M0 lesson)

M0 showed that a filter applied to a short epoch can leave an edge transient larger than the response. The
papers do not say exactly how they filtered, so three variants are run on the wearable data:

- **A, reference convention (used for the gate):** cut the window, then filter it. This is what the public
  reference implementation does. No mains removal.
- **B, project pipeline (used from M2 on):** take the samples from the start of the epoch to the end of the
  window, remove mains by least squares on that segment, filter it, keep the window. The 0.64 s before the
  window are past samples that a real-time system also has; they absorb the start-up transient. **No sample
  after the end of the window is used.** B is chosen now, for validity; the choice does not depend on M1 results.
- **C, whole-epoch filtering (diagnostic only):** filter the full 2.84 s epoch, then cut. It uses samples that
  come **after** the decision time, so it cannot run in real time. It is run only to measure how much this
  common shortcut flatters short windows.

Before the data are used, a synthetic test measures the edge transient of each sub-band filter in A, B and C
for a response of 2 microvolts with 67 microvolts of mains (the dry median of M0).

## Reproduction gate

Published values are for all 102 subjects (wearable) and we use 68, so a tolerance is needed. The standard
error of the published means is 0.02 to 0.03; the expected difference between a 68-subject mean and the
102-subject mean is about 0.015 to 0.02. Pipeline details are not fully specified either.

| | Target (accuracy unless stated) | Passes if |
|---|---|---|
| G1 | Wearable, CCA, 1 s, `Nh = 5`: dry 0.497, wet 0.684 | within 0.05 |
| G2 | Wearable, FBCCA, published weights: 1 s dry 0.53, wet 0.73; 2 s dry 0.73, wet 0.86 | within 0.05 |
| G3 | Wearable, TRCA with filter bank ("FBTRCA"), published weights: 1 s dry 0.62, wet 0.88; 2 s dry 0.73, wet 0.93. The paper does not say whether it used the ensemble form; the gate takes the ensemble form (default of the reference implementation) and the plain form is reported next to it | within 0.05 |
| G4 | Dry or wet (final check of M0's C3): wet above dry for every method at 1 s and 2 s | all six comparisons |
| G5 | BETA, peak ITR with 0.55 s gaze shift: CCA 72.5 bits/min at 1.8 s; FBCCA 98.8 at 1.4 s; ensemble TRCA with filter bank 139.6 at 0.6 s | peak within 10 %, at the same window +/- 0.2 s |

Rules:

- **No tuning to reach a target.** If a gate fails, the implementation is checked against the unit tests and
  the reference code, the difference is documented, and the author decides how to go on.
- The gate uses variant A. B and C are reported next to it.
- The paper's weights were tuned on the data they are evaluated on, so its numbers are optimistic. The
  a-priori weights are reported too; they are the fair training-free baseline for M2.

## What is reported (development subjects, descriptive, no hypothesis test)

- Accuracy and ITR against window length for CCA, FBCCA, TRCA and ensemble TRCA; dry and wet; variants A, B, C.
- Per-subject accuracies; number of people at chance; relation with the single-trial SNR of M0.
- Dry minus wet for the same person, separately for the two orders of wearing (crossover view).
- Size of the optimism: published weights against a-priori weights; variant C against B.
- Confusion matrices at 1 s (which targets are mistaken for which).
- Compute time per decision and number of parameters of each method.

## Unit tests (synthetic signals, must pass before the data are used)

- CCA: exact correlation on a known case; chance level (1/12) on noise; accuracy rises with amplitude.
- Filter bank: pass-band and stop-band gains of every sub-band; coefficients equal to those of the reference design.
- TRCA: recovers a planted spatial pattern; a trial of the held-out block never enters the templates or the
  filters (checked by planting a marker in the held-out block); with shuffled training labels accuracy
  falls to chance.
- ITR: known values (`P = 1`, `P = 1/N`).
- Edge transients of variants A, B, C (above).

## Wording of H1 (to be fixed with this plan, before any accuracy is computed)

The published numbers contradict "the gap shrinks as the window gets longer" for the training-free method.
Proposed wording:

- **H1.** For the same person, method and window length, accuracy is lower with the dry headband than with
  the wet one. Primary cases: FBCCA (a-priori weights) and ensemble TRCA, at 1 s and at 2 s.
- **Reported without a directional claim:** the gap as a function of window length, and the "time cost of dry
  electrodes" (the extra window length the dry headband needs to reach the accuracy of the wet one).
- The test (crossover analysis with the order of wearing, on which subjects) is fixed in the M2 plan. M1
  reports the development subjects descriptively.

## Outputs

`docs/milestones/M1_baselines.md` (report, gate table, deviations), `results/m1/`, `figures/m1/`, `logs/m1_*.log`,
`src/ssvep/` (`filterbank.py`, `decoders.py`, `metrics.py`, `beta.py`), `scripts/m1_*.py`, new unit tests,
`run_all.sh` extended. README and analysis plan updated.

## Not in M1

Cross-subject models, calibration curves, networks, any tuning, any hypothesis test, any lockbox subject.
