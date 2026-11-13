# M6 plan: report, graphical abstract, presentation, repository finish

*13 Nov 2026. **Approved by the author on 14 Nov 2026, with the three defaults (Q1 to Q3), before anything below was produced.** Written after
the final evaluation (`final_evaluation.md`) and the author's decision of the same day to skip M5 (real-time
replay). Anything done differently will be listed under "Deviations" in the M6 note.*

## Purpose

The work is done; M6 makes it readable. A visitor of the repository should get the result in 30 seconds
(graphical abstract), in 5 minutes (presentation) or in 20 minutes (report), and be able to check every
number.

**No new analysis.** No data file is opened for a new computation, and nothing is decoded. Every number comes
from a result file or a log that is already committed. A number that is in no report yet is computed by a
committed script from those result files and labelled descriptive.

## Deliverables

### 1. Final report: `REPORT.md` (repository root)

One document of about 2 500 words and 6 figures, results first.

| Section | Content | Source |
|---|---|---|
| Summary | The question and the answer in five sentences | `final_evaluation.md` |
| Data and design | Dataset, 68 development and 34 lockbox people, plan-code-result order of the commits, the 15 tests | `analysis_plan.md`, M0 |
| Methods | Pipeline B2, FBCCA, ensemble TRCA, cross-subject template, small network, adaptation without labels; what was frozen and when | M1 to M3 |
| Tested results | The 15 tests on the lockbox people, with the expectation written before the opening | `final_evaluation.md` |
| The cost of a new user | Accuracy against calibration time, dry and wet; model size and compute | final evaluation, M3 |
| When it fails | People not above chance, time on task, impedance, confusions | M4, final evaluation |
| What went wrong on the way | Reversed electrode label of the dataset; published accuracies need samples after the window; bias of per-channel mains removal; the plan's wrong keypad layout | M0, M1, M2, M4 |
| Limits | One dataset, offline, cue-guided, 12 targets; H6 post hoc; network possibly under-trained; **M5 (real-time replay) and H4 (graph denoising) not done** | all |
| What I would do next | The real-time step, stated as not done | brief of M5 |
| Reproduce | Commands, time, checksums | README |

Rules of wording: effect sizes with intervals; "supported" only for the seven tests that are; results on the
development people are called descriptive; nothing is claimed about real-time use.

### 2. Graphical abstract: `figures/graphical_abstract.png`

One image, drawn by `scripts/m6_graphical_abstract.py` from the result files (so it can be regenerated),
placed at the top of the README. Three panels and one headline sentence:

1. **Setting:** a new user, an 8-channel headband, 12 flickering targets, dry or wet electrodes (schematic).
2. **The cost of a new user:** accuracy at 1 s against calibration time on the lockbox people; template,
   ensemble TRCA, FBCCA; dry and wet.
3. **What was tested:** the six hypotheses as a strip, supported or not, with the estimate.

Same colours as all figures (dry orange, wet blue); the headline states the finding.

### 3. Presentation: `docs/presentation.pptx` and `docs/presentation.pdf`

Eight slides for a technical reader (five minutes), one message per slide, the same figures as the report:

| # | Slide |
|---|---|
| 1 | The question: decoding for a new user of a wearable headband, and what it costs |
| 2 | Data and design: 102 people, dry and wet, development and lockbox, plans committed before runs |
| 3 | Dry electrodes cost 0.16 to 0.33 of accuracy (H1) |
| 4 | Calibration: other people's data plus 96 s is enough with dry electrodes, not with wet (H2) |
| 5 | Adapting without labels: the template gains, the network does not (H6, H3) |
| 6 | What did not hold: time on task, impedance (H5); the people who fail |
| 7 | What went wrong on the way, and how it was caught |
| 8 | Limits and next step: real-time replay not done |

### 4. Repository finish

- README: graphical abstract and tested results first, then reproduce, then the milestones; M5 marked "not
  carried out (author's decision)"; milestone table completed.
- `CITATION.cff`.
- **Fresh-clone check:** clone the public repository into an empty folder, install `requirements.txt`, run the
  unit tests, re-run M4 and the final steps (`--reproduce`), and compare the result files with the committed
  ones. M1 to M3 were re-run clean at their own milestones.
- Checks before the last push: no raw data, no private brief, no personal e-mail address, licences present,
  every figure referenced exists, every link of README and REPORT resolves.
- `docs/milestones/M6_note.md`: what was produced, the checks and their outcome, deviations.

## Decisions for the author (defaults in bold)

| | Question | Default |
|---|---|---|
| Q1 | Format of the presentation | **PowerPoint file plus a PDF copy in `docs/`** (editable, and readable on GitHub) |
| Q2 | Author line of the report and slides | **Name and repository link, no affiliation** (the project is personal work) |
| Q3 | AI assistance | **README statement stays the only full statement; the report and the last slide carry one line that points to it** |

## Not part of M6

The CV bullet, the LinkedIn post and the message to the team are M7.

## Outputs

`REPORT.md`, `figures/graphical_abstract.png`, `scripts/m6_graphical_abstract.py`, `docs/presentation.pptx`,
`docs/presentation.pdf`, `CITATION.cff`, `docs/milestones/M6_note.md`, README and `run_all.sh` updated.
