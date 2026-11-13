# Wearable SSVEP decoding for new users: calibration cost, dry electrodes, honest evaluation

**Status: M0 (data check), M1 (standard decoders), M2 (new users and calibration) and M3 (small network,
adaptation without labels) done on the development people, 13 Nov 2026. The hypotheses have not been tested yet: the 34 lockbox people are untouched and will be
used once, at the end.** This README is filled in milestone by
milestone; nothing is reported here before it has been run and reviewed.

A leakage-safe, pre-specified analysis of steady-state visual evoked potential (SSVEP) decoding from an
8-channel wearable EEG headband, on the open dataset of Zhu et al. (*Sensors*, 2021): 102 people, 12 flickering
targets, each person recorded with a **dry-electrode** and a **wet-electrode** headband.

**Question.** How well can the gazed target be decoded for a *new user* with no or few calibration trials,
with dry electrodes, and what does it cost in accuracy, speed (information transfer rate), calibration time
and model size?

> **AI assistance.** The code, analyses, figures and reports in this repository were written and run with an AI
> assistant (Anthropic's Claude) under the author's direction. Direction, research questions, decisions and review are
> the author's; see [Authorship and AI assistance](#authorship-and-ai-assistance).

## What is known so far (M0, data check)

Full report: [`docs/milestones/M0_data_audit.md`](docs/milestones/M0_data_audit.md).

1. **The electrode label of the dataset documentation is reversed.** Position 1 of the electrode axis is the
   dry headband and position 2 the wet one, in the EEG files and in `Impedance.mat` (the readme and the paper
   say "1: wet, 2: dry"). Four independent lines of evidence agree, among them the paper's own impedance values.
2. **Timing and the target table are right:** each of the 12 targets peaks at its own frequency, and the
   response follows the stimulus by 133 to 135 ms.
3. **One 2 s trial carries little signal:** narrow-band SNR of about 3.5 dB at Oz (pure noise: -1.5 dB), below
   1 dB for about a third of the people. It depends on the person far more than on the headband.
4. **Dry and wet differ in noise, hardly in SNR:** over five times more mains pick-up with dry electrodes, but
   only 0.4 dB less SNR at Oz. The headband worn second tends to do worse, so the comparison is a crossover.
5. **The samples are untouched converter values:** 250 Hz was obtained without an anti-aliasing filter, and an
   IIR notch on these short epochs leaves an edge transient (replaced by a least-squares mains removal).

<p align="center"><img src="figures/m0/01_noise_dry_vs_wet.png" width="900" alt="Mains pick-up, high-frequency noise and electrode offset per person: the headband stored first in the files is the noisy one, the dry headband"></p>

## What is known so far (M3, small network and adaptation without labels, 68 development people)

Full report: [`docs/milestones/M3_network.md`](docs/milestones/M3_network.md). New users with no calibration,
1 s window.

1. **A small network (3 572 parameters) trained on other people does not beat the template built from other
   people:** 0.53 against 0.57 with dry electrodes, 0.62 against 0.73 with wet ones.
2. **Adapting the network to the new user without labels** (batch-normalisation statistics, entropy
   minimisation) changes accuracy by less than 0.01.
3. **The same unlabelled signals help the template much more:** updated with its own decisions as labels it
   reaches 0.60 (dry) and 0.81 (wet), about what one to two labelled calibration blocks give.
4. Every decoder decides in less than 6 ms on one processor core; the preprocessing takes 6 ms.

<p align="center"><img src="figures/m3/01_methods.png" width="850" alt="Accuracy at 1 s with no calibration for FBCCA, the template from other people, the template adapted without labels, and the network with and without adaptation, for dry and wet electrodes"></p>

## What is known so far (M2, new users and calibration, 68 development people)

Full report: [`docs/milestones/M2_calibration.md`](docs/milestones/M2_calibration.md). Descriptive results with
95 % intervals over people; every person is decoded as a new user (leave-one-subject-out).

1. **With no calibration at all, a template built from other people beats FBCCA** at every window length: at
   1 s, 0.57 against 0.47 with dry electrodes and 0.73 against 0.65 with wet ones.
2. **Two calibration blocks of the user (96 s) bring it to 0.61 (dry) and 0.82 (wet).** Other people's data
   help most when the user has given little, and no longer matter after four blocks.
3. **Per-person calibration with ensemble TRCA needs many blocks** and stays behind with dry electrodes: 0.52
   (dry) and 0.85 (wet) after six blocks (288 s).
4. **Dry electrodes cost 0.18 in accuracy at 1 s with FBCCA and 0.28 with ensemble TRCA** (same person).
5. **The pipeline was corrected and frozen:** one mains frequency per trial for all channels, band below the
   mains (45 Hz). No sample after the decision window is used anywhere.

<p align="center"><img src="figures/m2/02_calibration_curve.png" width="900" alt="Accuracy of a new user at 1 s against the number of calibration blocks, for the cross-subject template, the user's own template and ensemble TRCA, with dry and wet electrodes"></p>

## What is known so far (M1, standard decoders, 68 development people)

Full report: [`docs/milestones/M1_baselines.md`](docs/milestones/M1_baselines.md).

1. **The pre-registered reproduction gate failed.** With the convention of the public reference code (cut
   the window, then filter; mains kept), none of the ten published accuracies of the dataset paper is
   reproduced within 0.05, and TRCA with the dry headband is at chance (0.14 against a published 0.62).
2. **The decoders are right; the cause is the filtering.** A second, literal implementation gives the same
   decision on 960 of 960 trials. (a) The 50 Hz mains is inside every sub-band and breaks TRCA on this
   unshielded recording. (b) The published values are matched (13 of 14 within 0.05) only when the whole
   2.84 s epoch is filtered before the window is cut, which uses samples recorded after the end of the window.
3. **Without future samples** (project pipeline): FBCCA with no calibration reaches 0.45 (dry) and 0.62 (wet)
   at 1 s, 0.68 and 0.83 at 2 s; ensemble TRCA with per-person calibration 0.52 and 0.84 at 1 s. With the dry
   headband 4 to 7 of 68 people are not above chance at 1 s.
4. **Dry electrodes cost 0.15 to 0.17 in accuracy with FBCCA and 0.26 to 0.33 with ensemble TRCA** for the
   same person. In time: 1.06 s with the dry headband for what the wet one reaches in 0.6 s.
5. **A flaw was found in our own mains-removal step:** it treats each channel separately, which creates a
   small artefact next to 50 Hz and pulls CCA decisions towards the two targets whose 4th harmonic is 49 and
   51 Hz. To be corrected in the M2 plan; the M1 numbers are reported with it.
6. **On BETA, the laboratory reference dataset, the same code reproduces the published peak rates within
   4 %** (gate G5, 3 of 3: CCA 70.2 against 72.5 bits/min, FBCCA 96.8 against 98.8, ensemble TRCA 139.9 against
   139.6), and there the filtering convention hardly matters.

<p align="center"><img src="figures/m1/01_reproduction.png" width="900" alt="Accuracy against window length for CCA, FBCCA and ensemble TRCA with three ways of filtering; the published values lie on the curves obtained by filtering the whole epoch"></p>

## How the work is organised

Each milestone has a plan that is committed **before** it is run, and a report committed after it
(see the commit history).

| Milestone | Content | Plan | Report |
|---|---|---|---|
| M0 | Data check: files, layout, electrode type, timing, spectra, signal-to-noise ratio, impedance | [`M0_plan.md`](docs/milestones/M0_plan.md) | [`M0_data_audit.md`](docs/milestones/M0_data_audit.md) |
| M1 | Reproduce the standard methods (CCA, FBCCA, TRCA) and their published results | [`M1_plan.md`](docs/milestones/M1_plan.md) | [`M1_baselines.md`](docs/milestones/M1_baselines.md) |
| M2 | New users and calibration: calibration-free and few-calibration decoding, dry vs wet | [`M2_plan.md`](docs/milestones/M2_plan.md) | [`M2_calibration.md`](docs/milestones/M2_calibration.md) |
| M3 | Small network and test-time adaptation; model size and compute | [`M3_plan.md`](docs/milestones/M3_plan.md) | [`M3_network.md`](docs/milestones/M3_network.md) |
| M4 | Interpretation and failure cases: time on task, impedance, confusions | [`M4_plan.md`](docs/milestones/M4_plan.md) | |
| M5 | Real-time replay with measured latency | | |
| M6 | Report and visual summary | | |

The hypotheses and the evaluation rules are in [`docs/analysis_plan.md`](docs/analysis_plan.md).

**Development and lockbox subjects.** Every third subject (S003, S006, ..., S102; 34 people) is a lockbox:
until the final evaluation their recordings are used only for label-free checks. All method development uses
the other 68 people. The rule was fixed before any data file was opened.

## Data

Not included. See [`DATA.md`](DATA.md) for the sources, the licences and the checksums.

## Reproduce

```bash
pip install -r requirements.txt
WEARABLE_DIR=/path/to/13560281 BETA_DIR=/path/to/12264401 ./run_all.sh
```

Python 3.13. On two cores M0 takes about two minutes, M1 about fifteen, its BETA part about twenty-five more,
M2 about fifteen and M3 about an hour (24 small networks are trained on the processor; PyTorch 2.15). `BETA_DIR` is optional and may hold the original files or the reduced ones (see `DATA.md`).

## Repository layout

```
src/ssvep/      wearable.py (dataset constants, loader, development/lockbox split), spectral.py (filters,
                mains removal, Fourier coefficient at an exact frequency, narrow-band SNR, apparent latency),
                filterbank.py (reference filter bank, ways of filtering a short window), decoders.py (CCA,
                FBCCA, TRCA, ensemble TRCA), metrics.py (ITR, chance threshold), beta.py (reference dataset),
                pipeline.py (preprocessing candidates of M2; B2 is the frozen one), transfer.py (template
                decoder for new users), stats.py (tests reserved for the lockbox), network.py (EEGNet-type
                network, training, folds of people), adapt.py (adaptation without labels),
                plotting.py (one figure style)
scripts/        m0_inventory.py (label-free checks, all subjects), m0_signal_checks.py (timing, spectra,
                SNR, development subjects only), m0_figures.py, m0_summary.py (every number of the audit),
                check_beta_files.py
                m1_edge_transients.py (synthetic), m1_baselines_wearable.py (development subjects only),
                m1_crosscheck.py (second implementation), m1_decision_bias.py (diagnostic),
                m1_summary.py (every number of the report), m1_figures.py
                beta_reduce.py (BETA to nine channels, numpy only), m1_beta_check.py, m1_baselines_beta.py,
                m1_beta_summary.py (gate G5)
                m2_pipeline_choice.py, m2_baselines.py, m2_new_users.py (leave-one-subject-out),
                m2_summary.py (every number of the report), m2_figures.py
                m3_train.py (24 networks, can be resumed), m3_evaluate.py, m3_compute.py, m3_summary.py,
                m3_figures.py
tests/          unit tests on synthetic signals (python -m pytest -q tests)
docs/           analysis_plan.md, milestones/ (one plan and one report per milestone)
results/        result tables (CSV), one folder per milestone
figures/        figures, one folder per milestone
logs/           run logs
```

## Authorship and AI assistance

Project direction, research questions, decisions and review: the author, Salman Almuhammad Alali. The code and
the reports were written and run with an AI assistant (Anthropic's Claude) under the author's direction,
milestone by milestone; every milestone is reviewed and approved before the next one starts.

History note: on 13 Nov 2026 the author recorded on the commits was changed from the assistant's default
identity to the author's name; the assistant stays named as co-author on every commit. The content, the order
and the dates of the commits are unchanged. Only the commit identifiers changed, so identifiers quoted in
earlier versions of the reports no longer resolve.

## Licence: free for non-commercial use, commercial use by licence

This work is **free for everyone for non-commercial use**: research, teaching, study, personal projects,
and use by universities, public research institutes, non-profits and government bodies.
**Commercial use is not permitted without a commercial licence** from the author.

- **Code** (`src/`, `scripts/`, `tests/`, `run_all.sh`):
  [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) (see `LICENSE`).
- **Reports, documentation, figures, result tables, trained networks and logs**:
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (see `LICENSE-docs`). Credit the author when you reuse them.
- **Commercial licence** (for example, use in a product, a paid service or company R&D): contact the author,
  [Salman Almuhammad Alali](https://github.com/SAamal1076).
- **Datasets**: not included; they keep their own licences (CC BY 4.0, see `DATA.md`).

## References

- F. Zhu, L. Jiang, G. Dong, X. Gao, Y. Wang, "An Open Dataset for Wearable SSVEP-Based Brain-Computer
  Interfaces", *Sensors* 21(4):1256, 2021. doi: 10.3390/s21041256
- B. Liu, X. Huang, Y. Wang, X. Chen, X. Gao, "BETA: A Large Benchmark Database Toward SSVEP-BCI Application",
  *Frontiers in Neuroscience* 14:627, 2020. doi: 10.3389/fnins.2020.00627
