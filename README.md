# Wearable SSVEP decoding for new users: calibration cost, dry electrodes, honest evaluation

**Status: M0 (data check) in progress. There is no decoding result yet.** This README is filled in milestone
by milestone; nothing is reported here before it has been run and reviewed.

A leakage-safe, pre-specified analysis of steady-state visual evoked potential (SSVEP) decoding from an
8-channel wearable EEG headband, on the open dataset of Zhu et al. (*Sensors*, 2021): 102 people, 12 flickering
targets, each person recorded with a **dry-electrode** and a **wet-electrode** headband.

**Question.** How well can the gazed target be decoded for a *new user* with no or few calibration trials,
with dry electrodes, and what does it cost in accuracy, speed (information transfer rate), calibration time
and model size?

> **AI assistance.** The code, analyses, figures and reports in this repository were written and run with an AI
> assistant (Anthropic's Claude) under the author's direction. Direction, research questions, decisions and review are
> the author's; see [Authorship and AI assistance](#authorship-and-ai-assistance).

## How the work is organised

Each milestone has a plan that is committed **before** it is run, and a report committed after it
(see the commit history).

| Milestone | Content | Plan | Report |
|---|---|---|---|
| M0 | Data check: files, layout, electrode type, timing, spectra, signal-to-noise ratio, impedance | [`M0_plan.md`](docs/milestones/M0_plan.md) | in progress |
| M1 | Reproduce the standard methods (CCA, FBCCA, TRCA) and their published results | | |
| M2 | New users and calibration: calibration-free and few-calibration decoding, dry vs wet | | |
| M3 | Small network and test-time adaptation; model size and compute | | |
| M4 | Interpretation and failure cases: time on task, impedance, confusions | | |
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

## Repository layout

```
src/ssvep/      wearable.py (dataset constants, loader, development/lockbox split), spectral.py (filters,
                Fourier coefficient at an exact frequency, narrow-band SNR, apparent latency)
scripts/        m0_inventory.py (label-free checks, all subjects), m0_signal_checks.py (timing, spectra,
                SNR, development subjects only)
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

## Licence

To be added before the repository is made public. The datasets keep their own licences (see `DATA.md`).

## References

- F. Zhu, L. Jiang, G. Dong, X. Gao, Y. Wang, "An Open Dataset for Wearable SSVEP-Based Brain-Computer
  Interfaces", *Sensors* 21(4):1256, 2021. doi: 10.3390/s21041256
- B. Liu, X. Huang, Y. Wang, X. Chen, X. Gao, "BETA: A Large Benchmark Database Toward SSVEP-BCI Application",
  *Frontiers in Neuroscience* 14:627, 2020. doi: 10.3389/fnins.2020.00627
