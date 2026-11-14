"""M5: the frozen decoder fed by a stream, the confidence of a decision, and a rule that stops when confident.

The decoder is the one frozen in M2: pipeline B2, FBCCA and the cross-subject template with no calibration.
Nothing is trained here except one number per length of signal, which turns scores into probabilities.

  preprocess, decode, window_scores   scores of whole trials for one length of signal (the fixed-window code path)
  StreamDecoder   the same scores when the samples arrive in pieces; uses no sample that has not arrived
  fit_scale, probabilities, stop, person_itr, choose_theta, choose_window
"""
from __future__ import annotations

import time

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

from . import decoders as dc
from . import metrics as mt
from . import pipeline as pp
from . import transfer as tr
from . import wearable as wd

PIPELINE = "B2"
PIECE_S, GAZE_S = 0.1, 0.5                                            # a piece of the stream; time to move the eyes (M2)
TIMES = tuple(round(0.1 * k, 1) for k in range(3, 21))                 # 18 updates, 0.3 s to 2.0 s after the response starts
THETAS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.97, 0.99)


def n_samples(seconds: float, fs: float = wd.FS) -> int:
    return int(round(seconds * fs))


def preprocess(x, n: int, start: int = wd.RESP_START, fs: float = wd.FS):
    """Sub-bands of the n samples after the start of the response, mean removed: (bands, trials, channels, n).
    x: (trials, channels, samples), at least start + n samples; later samples are not used."""
    sub = pp.subbands(x, n, PIPELINE, start, fs)
    return sub - sub.mean(axis=-1, keepdims=True)


def decode(sub, bases, weights, templates=()):
    """FBCCA scores (trials, classes) and, for each template (bands, classes, channels, n), the scores of the
    template decoder. sub comes from preprocess."""
    part = tr.trial_part(sub, bases)
    return dc.fbcca_scores(part[0], weights), [tr.ecca_scores(part, template, bases, weights) for template in templates]


def window_scores(x, n: int, bases, weights, template=None, start: int = wd.RESP_START, fs: float = wd.FS):
    """The fixed-window code path: FBCCA scores and template scores (or None) for a signal of n samples."""
    fbcca, tmpl = decode(preprocess(x, n, start, fs), bases, weights, () if template is None else (template,))
    return fbcca, (tmpl[0] if tmpl else None)


def pieces(epoch, piece: int):
    """Replay of one recording (channels, samples): successive pieces of `piece` samples, in the order of time."""
    for a in range(0, epoch.shape[-1], piece):
        yield epoch[..., a:a + piece]


class StreamDecoder:
    """Scores of one trial while its samples arrive.

    The decoder is told where the response starts (sample `start` of the trial), as a device that draws the
    flicker is. At each time of `times` it gives the scores computed from the samples received so far, cut at
    that time: a sample that has not arrived cannot enter, and one that arrived later than the update is not used.
    """

    def __init__(self, templates=None, times=TIMES, start: int = wd.RESP_START, fs: float = wd.FS, freqs=wd.TARGET_FREQS):
        self.times, self.start, self.fs = tuple(times), start, fs
        self.n = [n_samples(t, fs) for t in self.times]
        self.templates = templates                                     # {n: (bands, classes, channels, n)} or None
        self.bases = {n: dc.reference_bases(freqs, n, fs, pp.N_HARM[PIPELINE]) for n in self.n}
        self.weights = pp.weights(PIPELINE)
        self.reset()

    def reset(self):
        self._buffer, self._received, self._next, self.seconds = [], 0, 0, []

    def push(self, piece):
        """Add a piece (channels, samples). Returns the updates it made possible, each as
        (time in s, FBCCA scores (classes,), template scores (classes,) or None)."""
        piece = np.asarray(piece, dtype=float)
        self._buffer.append(piece)
        self._received += piece.shape[-1]
        out = []
        while self._next < len(self.n) and self._received >= self.start + self.n[self._next]:
            n = self.n[self._next]
            t0 = time.perf_counter()
            x = np.concatenate(self._buffer, axis=-1)[None, :, :self.start + n]
            sub = preprocess(x, n, self.start, self.fs)
            t1 = time.perf_counter()
            fbcca, tmpl = decode(sub, self.bases[n], self.weights, () if self.templates is None else (self.templates[n],))
            self.seconds.append((t1 - t0, time.perf_counter() - t1))   # preprocessing and decision, on the processor
            out.append((self.times[self._next], fbcca[0], tmpl[0][0] if tmpl else None))
            self._next += 1
        return out


# ---------------------------------------------------------------- confidence

def probabilities(scores, b: float):
    """p_f = exp(b s_f) / sum_g exp(b s_g), along the last axis."""
    z = b * np.asarray(scores, dtype=float)
    return np.exp(z - logsumexp(z, axis=-1, keepdims=True))


def fit_scale(scores, labels, upper: float = 1000.0) -> float:
    """The b that makes the true targets most probable: minimises -sum log p_true. scores: (trials, classes)."""
    scores, labels = np.asarray(scores, dtype=float), np.asarray(labels)
    rows = np.arange(len(labels))

    def loss(b):
        z = b * scores
        return float(np.mean(logsumexp(z, axis=-1) - z[rows, labels]))

    return float(minimize_scalar(loss, bounds=(0.0, upper), method="bounded", options={"xatol": 1e-6}).x)


# ---------------------------------------------------------------- stopping rule and speed

def stop(confidence, theta: float):
    """Index of the update at which each trial is decided: the first one with confidence >= theta, the last
    update otherwise. confidence: (trials, updates)."""
    hit = np.asarray(confidence) >= theta
    hit[:, -1] = True
    return hit.argmax(axis=1)


def person_itr(correct, seconds, n_classes: int = wd.N_TARGETS, gaze: float = GAZE_S) -> float:
    """ITR in bits/min of one person: accuracy over the trials, mean decision time plus the time to move the eyes."""
    return float(mt.itr_bits_per_min(np.mean(correct), n_classes, np.mean(seconds) + gaze))


def choose_theta(confidence, decisions, labels, person, times=TIMES, thetas=THETAS):
    """The theta with the highest mean ITR over people (the first one in case of a tie).
    confidence, decisions: (trials, updates); labels, person: (trials,). Returns (theta, mean ITR for each theta)."""
    times, rows = np.asarray(times), np.arange(len(labels))
    mean_itr = []
    for theta in thetas:
        i = stop(confidence, theta)
        correct, seconds = decisions[rows, i] == labels, times[i]
        mean_itr.append(np.mean([person_itr(correct[person == p], seconds[person == p]) for p in np.unique(person)]))
    return thetas[int(np.argmax(mean_itr))], np.array(mean_itr)


def choose_window(decisions, labels, person, times=TIMES):
    """The fixed length of signal with the highest mean ITR over people (the shortest in case of a tie).
    Returns (index of the length, mean ITR for each length)."""
    correct = decisions == labels[:, None]
    mean_itr = [np.mean([person_itr(correct[person == p, j], t) for p in np.unique(person)]) for j, t in enumerate(times)]
    return int(np.argmax(mean_itr)), np.array(mean_itr)
