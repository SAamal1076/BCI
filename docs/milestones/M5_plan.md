# M5 plan (short version): streaming replay, latency, stopping when confident

*14 Nov 2026. **Approved by the author the same day, with the three defaults (Q1 to Q3), before anything below was run.** On 13 Nov the author
decided to skip M5; on 14 Nov, after M6, he asked for a short version. Anything done differently will be
listed under "Deviations" in the M5 report.*

## Purpose

Every result so far uses a fixed window: the decoder waits 1 s (or 2 s) and then decides. A device does not
work like that. It receives samples as they arrive, and it should decide **as soon as it is sure**. M5 asks
three questions:

1. Does the frozen decoder give the same decisions when the signal arrives in small pieces?
2. How long does one update take on a processor, compared with the time between two updates?
3. How much faster is a decoder that stops when it is confident, at what cost in accuracy?

## What is not touched

- **The lockbox stays opened once.** M5 uses the 68 development people only, and every number is descriptive:
  estimates with 95 % intervals over people, no test and no p-value.
- **No method is changed:** pipeline B2, the cross-subject template with no calibration, FBCCA as the
  reference that uses nobody's data. Nothing is trained.

## People

The 4 folds of M3: in each fold 43 people build the template, 8 **validation** people set the two things M5
has to choose, and 17 **test** people are replayed. Every development person is a test person once, decoded by
a template and by settings that never saw them.

## Part A: the stream

- A recording is replayed in pieces of 0.1 s (25 samples), in the order of the samples. The decoder knows when
  the flicker starts, as a device that draws the flicker does.
- From 0.3 s to 2.0 s after the start of the response the decoder updates every 0.1 s (18 updates), each time
  with all samples received so far and none after.
- **Check:** the scores of the stream are the same numbers as those of the fixed-window code of M2, for every
  update. This is tested on synthetic signals and then on recordings (one block of every person and headband:
  1 632 trials, 29 376 updates).
- The stream is an object inside the program. Lab Streaming Layer is not used: it would change where the
  samples come from, not what is done with them.

## Part B: latency

For each update, the time the processor needs for the preprocessing and for the decision is measured (one
core, median and 95th percentile, for each length of signal).

- Real-time factor: `time of one update / 0.1 s`. Below 1, the decoder keeps up with the stream.
- Latency of a decision: `signal used + time of the last update`.

These are measurements of Python code on the analysis machine, not of a device.

## Part C: stopping when confident

**Confidence.** After `T` seconds the decoder has one score `s_f` per target. The scores are turned into
probabilities with one number `b_T` per length of signal:

`p_f = exp(b_T s_f) / sum_g exp(b_T s_g)`

`b_T` is the value that makes the true targets most probable on the validation people (it minimises
`- sum log p_true`). Without it the scores of a short and of a long signal could not be compared.

**Rule.** Decide at the first update where `max_f p_f >= theta`; at 2.0 s decide in any case.

**Speed.** With `N` = 12 targets, accuracy `P` and mean decision time `T_mean` of a person (0.5 s is added for
moving the eyes, as in M2):

`ITR = 60 / (T_mean + 0.5) * [ log2 N + P log2 P + (1 - P) log2((1 - P) / (N - 1)) ]` bits/min

**Two choices, both made on the validation people of the fold, by the same criterion (highest mean ITR):**

- `theta`, among 0.50, 0.55, ..., 0.95, 0.97, 0.99;
- for comparison, the best **fixed** window among the 18 lengths.

**Reported on the test people,** for the template and for FBCCA, dry and wet:

| Quantity | Meaning |
|---|---|
| ITR, accuracy, mean decision time | stopping rule against the best fixed window |
| Difference of ITR per person | the gain of stopping, with its interval |
| Accuracy at the same mean time | stopping rule against a fixed window of that length |
| Distribution of decision times | how often the rule waits until 2.0 s |
| Reliability of the confidence | among decisions made with confidence near 0.6, 0.7, ..., how many are right |

**Expected before running:** the stopping rule gives a higher ITR than the best fixed window for both
headbands, with a larger gain for wet electrodes; the confidence is too high for the people who are hard to
decode; one update takes well under 0.1 s. If the rule does not beat the fixed window, that is the result.

## Limits known in advance

- A replay of recordings, not a live recording: no person reacts to the decisions.
- The decoder is told when the flicker starts. Detecting that the user is looking at no target is not studied.
- Trials last 2 s, so the rule cannot wait longer.
- Development people, on whom the preprocessing was chosen.

## Unit tests (synthetic signals, before any recording)

- Stream and fixed-window code give identical scores at every update; a piece of signal that has not arrived
  yet never changes a score.
- The probabilities sum to 1; `b_T` found on synthetic scores makes the confidence reliable.
- The rule never decides before 0.3 s, always decides by 2.0 s, and a higher `theta` never decides earlier.
- ITR formula at known values; validation and test people never overlap with the people of the template.

## Outputs

- `docs/milestones/M5_realtime.md` (report), `results/m5/`, `figures/m5/` (speed against accuracy; decision
  times; reliability; latency), `logs/m5_*.log`.
- `figures/m5/replay.gif`: a short replay of consecutive trials of one test person, chosen by a rule fixed
  here (the person with the median accuracy among the test people of fold 1, dry headband), not by looking.
- `src/ssvep/stream.py`, `scripts/m5_*.py`, `tests/test_m5.py`, `run_all.sh` extended.
- `REPORT.md`, README and the slides: the sentences "real-time replay not done" replaced by what M5 shows and
  what it still does not show; a new section of the report, **"Recommendations for a product team"**, written
  from the tested results and from M5.

## Decisions for the author (defaults in bold)

| | Question | Default |
|---|---|---|
| Q1 | Use the lockbox people a second time for M5? | **No.** "Opened once" stays true; M5 is descriptive on development people. |
| Q2 | Put the replay animation at the top of the README, under the graphical abstract? | **Yes** |
| Q3 | Add the section "Recommendations for a product team" to the report? | **Yes** |

Estimated computing time: about 30 minutes.
