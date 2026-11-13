# M3 plan: a small network, and adaptation to a new user without labels

*13 Nov 2026. **Proposed, waiting for the author's approval. Nothing below has been run.** Written after M2
(`M2_calibration.md`). Anything done differently will be listed under "Deviations" in the M3 report.*

## Purpose

Two questions, both for a new user with **no calibration**:

1. Does a compact network trained on other people decode better than the cross-subject template of M2
   (0.568 with the dry headband and 0.730 with the wet one at 1 s)?
2. Does adapting the network to the new user's **unlabelled** signals help, and more with dry electrodes (H3)?

M3 also measures model size and compute for every method of the project.

## Frozen from M2 and used as is

Pipeline B2 (no sample after the window), the new-user test set (blocks 7 to 10), `n0` = 4. Window: **1 s
only** (a network is trained for one window length; 1 s is the primary window of the project).

## Step 1: how people are split

- **Four folds of people** instead of leave-one-subject-out: the 68 development people are sorted by number
  and dealt into 4 folds of 17. A network is trained on 3 folds (51 people) and tested on the 17 others.
  Reason: on the two processor cores of the analysis machine, one training per left-out person is too slow.
- Inside the 51 training people, 8 are set aside as **validation people** (early stopping). The test people
  are never used for training, validation or any choice.
- The cross-subject template and FBCCA are re-run on the same folds (population = the same 51 people), so the
  comparison with the network is fair.
- One model per headband type (dry model from dry recordings, wet model from wet ones), as for the templates.

## Step 2: the network (fixed now, no architecture search)

Input: the three sub-band signals of pipeline B2 for one trial, `3 x 8 channels x 250 samples`, each sub-band
of each trial scaled to zero mean and unit variance. An EEGNet-type network:

| Layer | What it does | Parameters |
|---|---|---|
| Temporal convolution, 3 -> 8 maps, kernel 63 samples (0.25 s), batch normalisation | learns band-pass filters | 1 528 |
| Spatial convolution over the 8 channels, 2 per map (16 maps), batch normalisation, ELU, average over 4 samples, dropout 0.5 | learns channel combinations | 160 |
| Separable convolution, kernel 15, 16 maps, batch normalisation, ELU, average over 8 samples, dropout 0.5 | short patterns in time | 528 |
| Linear layer to 12 targets | decision | 1 356 |

About 3 600 parameters (the exact count is checked by a unit test). Training: cross-entropy, Adam, learning
rate 0.001, batches of 64, at most 60 epochs, stop when the validation people have not improved for 8 epochs.
**Three random seeds** per fold and headband; accuracies are averaged over seeds and the spread is reported.
PyTorch 2.15 on the processor, pinned in `requirements.txt`.

## Step 3: adaptation without labels (H3)

A new user starts using the device. Their first six blocks (72 trials, 288 s) are available **without
labels**: nobody knows which target they looked at. The trained network is adapted on them, then frozen and
tested on blocks 7 to 10.

- **A0, no adaptation.**
- **A1, statistics only:** the mean and variance stored in the batch-normalisation layers are replaced by
  those of the user's unlabelled trials.
- **A2, entropy minimisation (the method of H3):** A1, then the scale and shift of the batch-normalisation
  layers are updated to make the network's predictions on the unlabelled trials more confident. For a batch,
  `H = - mean over trials of sum over targets of p * log(p)`; one gradient step per batch of 12 trials, one
  pass (6 steps), learning rate 0.001. All other weights stay fixed.
- The order of trials inside a block is not stored in the files (M0), so it is drawn at random with a fixed
  seed.

Secondary, descriptive:

- **Online:** the same adaptation on the test trials themselves, each trial predicted before it is used.
- **The same idea for the template:** the cross-subject template is updated with the user's unlabelled
  trials, using the template's own decisions as labels: `T_f = (n0 * P_f + m_f * J_f) / (n0 + m_f)`, with `J_f`
  the mean of the trials decided as `f` and `m_f` their number. This shows whether a network is needed to
  profit from unlabelled data.

## Hypothesis H3 and its tests (fixed now; run on the lockbox with the others)

For each person, `g = accuracy(A2) - accuracy(A0)` at 1 s, averaged over the three seeds.

- **H3a:** `g > 0` with the dry headband. **H3b:** `g > 0` with the wet headband. One-sided Wilcoxon
  signed-rank tests.
- **H3c ("most for dry"):** `g(dry) - g(wet) > 0`, paired by person, one-sided Wilcoxon signed-rank test.
- These three tests join the six of H1 and H2 in the Holm family (nine so far; H5 is added by the M4 plan).
- On the lockbox the network is trained on all 68 development people (8 of them for validation).

## What is reported (development people, descriptive, no p-value)

- Accuracy at 1 s on blocks 7 to 10, same people and trials: FBCCA, cross-subject template, network A0, A1,
  A2, the online variant and the adapted template; dry and wet; 95 % intervals over people.
- Gain of the adaptation per person; the people it hurts.
- Spread over the three seeds.
- **Size and compute for every method** (FBCCA, templates, ensemble TRCA, network): stored numbers, time of
  one decision on one core including preprocessing, training time. (Carried over from M2.)

## Unit tests (synthetic data, before the recordings are used)

- No test person appears in the training or validation people of their fold; the folds cover everybody once.
- Parameter count and output shape of the network.
- A1 changes the stored statistics only; A2 changes the batch-normalisation scale and shift only; all other
  weights are identical before and after.
- The adaptation functions take no label argument.
- One entropy step lowers the entropy on a toy batch.
- Same seed, same result.

## Expectations written down before running (not hypotheses)

- The network may **not** beat the template at 1 s: 51 people are few for a network, and templates are strong
  on short windows. If so, it is reported as it is.
- The gain of adaptation is expected to be small (0.01 to 0.04), and larger with the dry headband, where the
  signals differ more between people.

## Not in M3

Fine-tuning the network with labelled calibration blocks; other window lengths; any search over
architectures; the lockbox. **H4 (graph-based denoising) is not in this plan:** it needs the description of
the method from the author's thesis; it can get a short plan of its own (M3b) once that is available.

## Outputs

`docs/milestones/M3_network.md`, `results/m3/`, `figures/m3/`, `logs/m3_*.log`, `src/ssvep/network.py`,
`adapt.py`, `scripts/m3_*.py`, unit tests, `requirements.txt` and `run_all.sh` extended, README and analysis
plan updated.
