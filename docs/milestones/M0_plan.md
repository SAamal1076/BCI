# M0 plan: data check (wearable SSVEP dataset)

*12 Nov 2026. Approved by the author before it was run (the plan was presented and approved in conversation;
this is its English version). Committed before any data file was opened. Anything done differently is listed
under "Deviations" in [`M0_data_audit.md`](M0_data_audit.md).*

## Purpose

Check that the files are what the paper and the readme say they are, before any decoding: the right files,
the right array layout, the right electrode type, the right timing and the right target-to-frequency table.
**No classifier is run in M0.**

## The signal in one paragraph

When a person looks at a target that flickers at `f` Hz, the visual cortex produces an oscillation at `f` and
its harmonics (`2f`, `3f`, ...). It is phase-locked to the flicker and delayed by roughly 0.14 s. Each of the
12 targets has its own frequency and phase. A decoder can only work if (1) the spectral peak is at the right
frequency when the person looks at that target, (2) the response starts at the right time, and (3) it has the
right phase. M0 checks these three things.

## What the documentation says (to be confirmed on the files)

Sources: `Readme.pdf` and `stimulation_information.pdf` of the dataset; Zhu et al., *Sensors* 21(4):1256, 2021.

- Files: `S001.mat` ... `S102.mat`, `Impedance.mat`, `Subjects_Information.mat`
  (figshare, doi 10.6084/m9.figshare.13560281).
- Each subject file holds `data` with dimensions [8, 710, 2, 10, 12] =
  channel x time x electrode type x block x target, at 250 Hz (recorded at 1000 Hz), **not filtered**.
- Channels in file order: POz, PO3, PO4, PO5, PO6, Oz, O1, O2. Reference and ground on the forehead.
- Epoch of 2.84 s: 0.5 s before stimulus onset, 0.14 s visual latency, 2 s of stimulation, 0.2 s after.
  So stimulus onset is sample 125, and the 2 s response window is samples 160 to 659.
- Trial: 1 s cue, 2 s flicker, 1 s rest with online feedback. 60 Hz monitor. Room without electromagnetic shielding.
- Targets in file order (frequency in Hz, phase in units of pi):

| index | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| character | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 | * | # |
| frequency | 9.25 | 11.25 | 13.25 | 9.75 | 11.75 | 13.75 | 10.25 | 12.25 | 14.25 | 10.75 | 12.75 | 14.75 |
| phase | 0 | 0 | 0 | 0.5 | 0.5 | 0.5 | 1 | 1 | 1 | 1.5 | 1.5 | 1.5 |

  Stimulus luminance (paper, eq. 1): `s(t) = 0.5 * (1 + sin(2*pi*f*t + phi))`.

Open points in the documentation that M0 must settle:

1. Which index of the electrode axis of `data` is dry and which is wet. It is stated only for
   `Impedance.mat` (1 = wet, 2 = dry). A mistake here would invert every dry-vs-wet result.
2. The axis order of `Impedance.mat` (readme: [8, 10, 2, 102]; paper: [2, 8, 10, 102]).
3. The content of `Subjects_Information.mat` (10 columns are described, then "the last column" = wearing order).
4. Trials were presented in random order inside a block but are stored sorted by target, so the order of
   trials inside a block is lost. Consequence for the time-on-task hypothesis (H5) and for the real-time replay
   (M5) is recorded in the audit.

## Development and lockbox subjects (fixed now, before any data is opened)

- **Lockbox:** every third subject, S003, S006, ..., S102 (34 subjects). **Development:** the other 68.
- The rule uses the subject number only. The balance of wearing order, sex and age between the two groups
  is reported in the audit (metadata only).
- Until the final evaluation, lockbox files are used only for **label-free** checks (file integrity, noise
  level, impedance, questionnaire). Nothing that uses the target index of a trial is computed on them.
- Everything exploratory or tuned in later milestones uses development subjects only.

## Preprocessing used for the descriptive analysis of M0

Applied to each epoch and channel over the full 710 samples, then the window of interest is cut:

1. subtract the mean;
2. zero-phase Butterworth band-pass 3-90 Hz (order 4, second-order sections, forward-backward);
3. zero-phase second-order notch at 50 Hz, Q = 25 (mains frequency where the data were recorded).

Called `BP3-90+notch` below. Zero-phase filters do not shift the phase of the response.

Why it is needed: with a 2 s window the frequency resolution is 0.5 Hz, and the stimulus frequencies lie
half-way between the usual FFT bins (9.25 Hz = 18.5 x 0.5 Hz). At these half-bin positions the mean and
slow drifts of raw data leak into the estimate, so they are removed first.

These settings are for the M0 description only. Decoding pipelines define their own filters in
`docs/analysis_plan.md` before they are run.

## Step 0. Repository and plan

Create the repository, commit this plan and the first version of `docs/analysis_plan.md`. Then write the
loader, the spectral functions and their tests on **synthetic signals**; the tests must pass before the
functions are used on the data.

## Step 1. Inventory and integrity (label-free, all 102 subjects)

- Size, MD5 and SHA-256 of every file; MD5 compared with the checksums published by figshare.
- MAT version, variable names, shape, data type, number of non-finite values, amplitude range.
- Per trial and channel:
  - `ptp_bp`: peak-to-peak amplitude after `BP3-90+notch`;
  - `rms_bp`: RMS after `BP3-90+notch`;
  - `line50`: amplitude at 50 Hz of the raw epoch (mean and linear trend removed, Hann window);
  - `hf_rms`: RMS in the 60-90 Hz band (zero-phase Butterworth, order 4);
  - `lf_rms`: RMS of the raw epoch (mean removed) below 3 Hz (zero-phase Butterworth low-pass, order 4): drift.
- Descriptive flags (nothing is removed): non-finite values; flat channel (zero variance, or at least 25
  identical consecutive samples = 0.1 s); large artefact (`ptp_bp` > 200 microvolts on any channel).
- Exact duplicates of a trial (hash of the 8 x 710 array), inside and across subjects.
- Summaries per subject x electrode index, per block and per channel.

**No subject, block, trial or channel is excluded in this project because of these flags.** They are reported.

## Step 2. Metadata

- `Impedance.mat`: identify the axes by their sizes (8 channels, 10 blocks, 2 types, 102 subjects); mean
  impedance per type over channels, blocks and subjects, compared with the paper (dry 261.67 kOhm, wet 19.63 kOhm).
- `Subjects_Information.mat`: columns, sex, age, questionnaire answers, wearing order compared with the paper
  (53 subjects wore the dry headband first, 49 the wet one first). Only group summaries are stored in the
  repository, not the per-subject table.

## Step 3. Which electrode index is dry

Lines of evidence:

- **E1, documentation.** `Impedance.mat` is documented as 1 = wet, 2 = dry. The magnitudes (about 262 vs 20
  kOhm) show which impedance index is which. If the EEG array follows the same convention, index 2 is dry.
- **E2, noise in the EEG array (label-free).** For each subject, the medians of `line50` and `hf_rms` are
  compared between the two EEG electrode indices. Expectation fixed now: the dry headband is noisier (higher
  contact impedance gives more mains pick-up and more electrode noise). Reported: number of subjects in which
  index 2 is larger than index 1, for each metric.
- **E3, link between the two files without any naming convention (supportive only).** Spearman correlation
  across subjects between the impedance of each impedance index and the EEG noise of each EEG index. If
  impedance is related to noise at all, the matching pair should show the stronger association. A null result
  here does not count against the decision.
- **E4, independent convention.** The electrode index used by an independent published loader of this dataset.

Decision rule: the index is accepted if E1 and at least one of E2 and E4 agree, and neither E2 nor E4
contradicts. The final confirmation is the reproduction of the published accuracies in M1 (FBCCA at 2 s in the
paper: wet 0.86, dry 0.73). If the lines of evidence contradict each other: stop and report.

## Step 4. Timing (label-dependent, development subjects only)

For each electrode type and target `k`, take the grand-average Oz waveform (average over development subjects
and the 10 blocks, after `BP3-90+notch`) in the response window (samples 160-659) and compute its complex
Fourier coefficient at the target frequency, with time measured **from stimulus onset** (sample 125):

```
c_k   = (2/N) * sum_n x[n] * exp(-j*2*pi*f_k*t_n),     t_n = (n - 125)/250 s,  N = 500
psi_k = angle(c_k) + pi/2                              (phase of a sine, to match the stimulus formula)
psi_k - phi_k = theta0 - 2*pi*f_k*tau                  (phi_k = stimulus phase from the table)
```

- **Line fit (primary).** Sort the targets by frequency, unwrap `psi_k - phi_k`, fit a straight line against
  `f_k`. The slope gives the apparent latency `tau = -slope/(2*pi)`. Reported: `tau`, `theta0`, R2.
- **Phase-coherence scan (robustness, no unwrapping).** `R(tau) = |sum_k u_k * exp(-j*phi_k) * exp(j*2*pi*f_k*tau)| / 12`
  with `u_k = c_k/|c_k|`, for `tau` from -0.25 to 0.75 s in 1 ms steps; `tau* = argmax R`. The frequencies are
  0.5 Hz apart, so `R` repeats every 2 s and there is no ambiguity in this range.
- **Per subject:** the same scan on each development subject's own 10-block averages; the distribution of
  `tau*` and of `R(tau*)` is reported.
- **Time-domain view (supplementary):** grand-average Oz waveform for the 11.25 Hz target, band-pass
  7.25-90 Hz as in the paper's Figure 4a, with the onset marked.

What this checks at once: the position of the onset in the epoch, the target-to-(frequency, phase) table, and
the 0.14 s latency. If the phase table were ignored, the fitted `tau` would be wrong by 0.5 s. Caveat: the
apparent latency is a phase slope (a group delay) and need not equal the 0.14 s used to cut the epochs
exactly, hence a tolerance in the acceptance criterion.

## Step 5. Spectra and signal-to-noise ratio (label-dependent, development subjects only)

Definitions, on the 2 s response window after `BP3-90+notch`:

```
A(f)   = |c(f)|,   c(f) = (2/N) * sum_n x[n] * exp(-j*2*pi*f*t_n)        N = 500,  df = 250/500 = 0.5 Hz
SNR(f) = 20*log10( A(f) / mean_{k=1..5}[ A(f - k*df), A(f + k*df) ] )   dB   (mean of the 10 neighbours)
```

- `A(f)` is evaluated at the exact frequency, not on the FFT grid. With a 2 s rectangular window, a sinusoid
  at `f` contributes nothing at `f +/- k*0.5 Hz`.
- The paper's equation 3 prints a sum over the neighbours while its text says "mean"; the mean is used here.
- At the fundamental, the neighbours `f +/- k*0.5 Hz` are the frequencies of other targets, which flicker at
  the same time in peripheral vision. The SNR is therefore conservative.
- Known property of this definition (checked by a unit test): for pure noise the average SNR is about
  -1.5 dB, not 0 dB (mean of a logarithm versus logarithm of a mean).
- Averaging `M` phase-locked trials raises the SNR by up to `10*log10(M)` dB. Both are reported: the
  **single-trial** SNR (what a decoder sees) and the SNR of the **10-block average**.

Outputs:

- Per subject x electrode type: single-trial SNR at `f` and `2f` (mean over the 120 trials) and SNR of the
  10-block average (mean over the 12 targets), at Oz and averaged over the 8 channels.
- The same by channel, by block and by target.
- Attended-target matrix: mean single-trial amplitude at Oz at each of the 12 stimulus frequencies (columns)
  when each target (rows) was attended.
- Group spectrum: amplitude spectrum of the grand-average Oz waveform, per target and electrode type, on a
  0.25 Hz grid from 3 to 60 Hz.
- Comparison with the paper's Figure 4 for the 11.25 Hz target at Oz (amplitudes at `f` to `4f`: wet
  2.597 / 1.262 / 0.746 / 0.316 microvolts; dry 2.444 / 1.119 / 0.706 / 0.305). The paper used all 102
  subjects and M0 uses the 68 development subjects, so only approximate agreement is expected. This is not an
  acceptance criterion.
- Dry versus wet, paired by subject; SNR by block and by wearing order.

Statistics: descriptive only (medians, quartiles, number of subjects with dry below wet). **No hypothesis
test in M0.**

## Step 6. Impedance summary

Distribution per electrode type, per channel and per block; relation between impedance and noise or SNR
across subjects (descriptive).

## Step 7. Terms of use

Check the licence of the dataset at its source and write `DATA.md` (where to download, expected layout,
checksums, citation). Raw data are never committed.

## Acceptance criteria

| | Criterion |
|---|---|
| C1 | The 102 subject files load; `data` has shape (8, 710, 2, 10, 12); all values are finite. |
| C2 | Mean impedance per type within 5 % of the paper (261.67 and 19.63 kOhm); wearing order 53 dry-first, 49 wet-first. |
| C3 | The electrode index is settled by the decision rule of step 3. |
| C4 | For each electrode type and each target, the amplitude spectrum of the grand-average Oz waveform on the grid 8.25, 8.75, ..., 15.75 Hz is largest at the target's own frequency (24 checks). |
| C5 | Group apparent latency `tau` (line fit) between 0.10 and 0.18 s for both electrode types. |

If a criterion fails, it is reported as failed and investigated. Nothing is fixed silently; the author decides
what to do next.

## Outputs

- `docs/milestones/M0_data_audit.md`: the audit report with the acceptance table and the deviations.
- `results/m0/*.csv`, `figures/m0/*.png`, `logs/m0_*.log`.
- `data_manifest.csv`: checksums of the raw files.
- `src/ssvep/`: loader and spectral functions; `tests/`: unit tests.

## Not in M0

- Any classification, any tuning, any exclusion.
- Any label-dependent statistic on lockbox subjects.
- The reference dataset (BETA): only its file checksums are recorded now. Its own data check has a short
  plan before M1.

## Additions made when writing this English version (before any data was opened)

The author approved the plan and asked that needed adjustments be made directly. Compared with the plan as
presented in conversation, this version adds:

1. the development/lockbox split (recommended in the conversation, approved);
2. the `BP3-90+notch` preprocessing, required by the half-bin position of the stimulus frequencies;
3. the phase-coherence scan and the time-domain view as supplements to the line fit of step 4;
4. the comparison of the files' MD5 with the checksums published by figshare;
5. the checksums of the BETA files.
