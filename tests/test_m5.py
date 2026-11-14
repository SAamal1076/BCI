"""M5 on synthetic signals: the stream gives the scores of the fixed-window code, confidence, stopping rule."""
import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import network as nw  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import stream as sm  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F, START = wd.FS, wd.TARGET_FREQS, wd.RESP_START
TIMES = (0.3, 0.6, 1.0, 2.0)


def _epochs(n_per_class, seed, amplitude=0.6):
    """Whole trials (trials, 8, 710): correlated 1/f noise, mains pick-up, and from the start of the response a
    sine at the target frequency (with its second harmonic) that has one spatial pattern and a phase per class."""
    rng = np.random.default_rng(seed)
    n, k = wd.N_SAMPLES, len(F)
    gain = 1 / np.maximum(np.fft.rfftfreq(n, 1 / FS), 1.0) ** 0.75
    pink = lambda shape: np.fft.irfft(np.fft.rfft(rng.standard_normal(shape), axis=-1) * gain, n=n, axis=-1)   # noqa: E731
    trials = n_per_class * k
    x = np.einsum("cs,tsn->tcn", rng.standard_normal((8, 2)), pink((trials, 2, n))) + 0.5 * pink((trials, 8, n))
    t = np.arange(n) / FS
    x += 2.0 * np.sin(2 * np.pi * 50.03 * t + rng.uniform(0, 6.28, (trials, 1, 1)))
    labels = np.tile(np.arange(k), n_per_class)
    pattern = np.random.default_rng(99).standard_normal(8)                  # the same in every call
    tr_ = np.arange(n - START) / FS
    for i, f in enumerate(F):
        resp = np.sin(2 * np.pi * f * tr_ + 0.5 * np.pi * i) + 0.4 * np.sin(4 * np.pi * f * tr_ + 0.5 * np.pi * i)
        x[labels == i, :, START:] += amplitude * pattern[:, None] * resp
    return x, labels


def _templates(times):
    """Mean response per class of a separate set of 'other people', for each length of signal."""
    x, labels = _epochs(8, seed=1)
    out = {}
    for t in times:
        n = sm.n_samples(t)
        sub = sm.preprocess(x, n)
        out[n] = np.stack([sub[:, labels == i].mean(axis=1) for i in range(len(F))], axis=1)
    return out


def _replay(decoder, epoch, piece=25):
    decoder.reset()
    updates, pushes = [], []
    for i, part in enumerate(sm.pieces(epoch, piece)):
        got = decoder.push(part)
        updates += got
        pushes += [i] * len(got)
    return updates, pushes


def test_stream_gives_the_scores_of_the_fixed_window_code():
    x, labels = _epochs(1, seed=2)
    templates = _templates(TIMES)
    decoder = sm.StreamDecoder(templates, times=TIMES)
    weights = pp.weights("B2")
    correct = 0
    for trial in range(6):
        updates, pushes = _replay(decoder, x[trial])
        assert [u[0] for u in updates] == list(TIMES)
        # an update comes with the piece that completes its signal, not before: 0.3 s needs 160 + 75 samples = 10 pieces
        assert pushes == [int(np.ceil((START + sm.n_samples(t)) / 25)) - 1 for t in TIMES]
        for t, fbcca, tmpl in updates:
            n = sm.n_samples(t)
            bases = dc.reference_bases(F, n, FS, 3)
            ref_f, ref_t = sm.window_scores(x[trial:trial + 1], n, bases, weights, templates[n])
            assert np.allclose(fbcca, ref_f[0], atol=1e-10, rtol=0) and np.allclose(tmpl, ref_t[0], atol=1e-10, rtol=0)
        correct += updates[-1][2].argmax() == labels[trial]
        assert len(decoder.seconds) == len(TIMES) and all(a > 0 and b > 0 for a, b in decoder.seconds)
    assert correct >= 5                                                    # the synthetic response is decodable at 2 s
    batch_f, batch_t = sm.window_scores(x[:6], 250, dc.reference_bases(F, 250, FS, 3), weights, templates[250])
    one = [sm.window_scores(x[i:i + 1], 250, dc.reference_bases(F, 250, FS, 3), weights, templates[250]) for i in range(6)]
    assert np.allclose(batch_f, np.concatenate([o[0] for o in one]), atol=1e-10) and np.allclose(batch_t, np.concatenate([o[1] for o in one]), atol=1e-10)


def test_a_sample_that_has_not_arrived_changes_nothing():
    x, _ = _epochs(1, seed=3)
    templates = _templates(TIMES)
    decoder = sm.StreamDecoder(templates, times=TIMES)
    base, _ = _replay(decoder, x[0])
    for j, t in enumerate(TIMES[:-1]):                                    # change everything after the signal of update j
        y = x[0].copy()
        y[:, START + sm.n_samples(t):] += 50.0
        changed, _ = _replay(decoder, y)
        assert np.array_equal(changed[j][1], base[j][1]) and np.array_equal(changed[j][2], base[j][2])
        assert not np.array_equal(changed[j + 1][1], base[j + 1][1])      # and the later update does see it
    for piece in (10, 60, 710):                                           # the size of the pieces does not matter
        other, _ = _replay(decoder, x[0], piece)
        assert all(np.array_equal(a[1], b[1]) and np.array_equal(a[2], b[2]) for a, b in zip(other, base))
    fbcca_only, _ = _replay(sm.StreamDecoder(None, times=TIMES), x[0])
    assert all(u[2] is None for u in fbcca_only) and np.array_equal(fbcca_only[1][1], base[1][1])


def test_probabilities_and_their_scale():
    rng = np.random.default_rng(4)
    labels = rng.integers(0, 12, 6000)
    scores = 0.08 * rng.standard_normal((6000, 12))
    scores[np.arange(6000), labels] += 0.12                               # a decoder that is right about half the time
    b = sm.fit_scale(scores, labels)
    p = sm.probabilities(scores, b)
    assert np.allclose(p.sum(axis=-1), 1.0) and (p >= 0).all() and 5 < b < 200
    conf, right = p.max(axis=-1), p.argmax(axis=-1) == labels
    assert 0.3 < right.mean() < 0.8
    gap = [abs(right[(conf >= a) & (conf < a + 0.2)].mean() - conf[(conf >= a) & (conf < a + 0.2)].mean()) for a in (0.2, 0.4, 0.6, 0.8)]
    assert max(gap) < 0.06                                                # the confidence can be believed
    too_sure = sm.probabilities(scores, 4 * b)                            # a wrong scale cannot
    assert too_sure.max(axis=-1).mean() - right.mean() > 0.15
    flat = sm.fit_scale(0.08 * rng.standard_normal((3000, 12)), rng.integers(0, 12, 3000))
    assert sm.probabilities(scores, flat).max(axis=-1).mean() < 0.15      # scores that say nothing: about 1/12 each


def test_stopping_rule():
    rng = np.random.default_rng(5)
    conf = rng.uniform(0.1, 1.0, (500, 18))
    last = None
    for theta in sm.THETAS:
        i = sm.stop(conf, theta)
        assert i.min() >= 0 and i.max() <= 17
        first = np.array([np.flatnonzero(row >= theta)[0] if (row >= theta).any() else 17 for row in conf])
        assert np.array_equal(i, first)
        assert last is None or (i >= last).all()                           # a higher theta never decides earlier
        last = i
    assert (sm.stop(conf, 1.01) == 17).all()                               # never confident: decided at the last update
    assert (sm.stop(np.full((3, 18), 0.999), 0.5) == 0).all()              # confident at once: decided at the first
    assert sm.TIMES[0] == 0.3 and sm.TIMES[-1] == 2.0 and len(sm.TIMES) == 18 and np.allclose(np.diff(sm.TIMES), 0.1)


def test_itr_and_the_two_choices():
    assert np.isclose(sm.person_itr(np.ones(10), np.full(10, 1.0)), 60 / 1.5 * np.log2(12))
    assert sm.person_itr(np.arange(12) == 0, np.full(12, 1.0)) == 0.0     # chance level: no information
    assert sm.person_itr(np.ones(10), np.full(10, 0.5)) > sm.person_itr(np.ones(10), np.full(10, 1.0))
    rng = np.random.default_rng(6)
    labels, person = np.tile(np.arange(12), 20), np.repeat(np.arange(4), 60)
    # accuracy rises with the length of signal: 0.2 at 0.3 s, 0.95 from 1.0 s on; the best fixed length is in between
    p_right = np.clip(np.linspace(0.2, 1.4, 18), 0, 0.95)
    right = rng.uniform(size=(240, 18)) < p_right
    decisions = np.where(right, labels[:, None], (labels[:, None] + 1) % 12)
    j, by_window = sm.choose_window(decisions, labels, person)
    assert j == int(np.argmax(by_window)) and 3 < j < 14 and len(by_window) == 18
    conf = np.where(right, 0.9, 0.3) + 0.05 * rng.uniform(size=(240, 18))  # a confidence that knows when it is right
    theta, by_theta = sm.choose_theta(conf, decisions, labels, person)
    assert theta in sm.THETAS and theta == sm.THETAS[int(np.argmax(by_theta))] and len(by_theta) == len(sm.THETAS)
    assert by_theta.max() > by_window.max()                               # stopping when right beats any fixed length
    blind = rng.uniform(size=(240, 18))                                   # a confidence that knows nothing does not
    assert sm.choose_theta(blind, decisions, labels, person)[1].max() < by_theta.max()


def test_people_of_a_fold_do_not_overlap():
    folds = nw.folds(wd.DEVELOPMENT)
    tested = sorted(p for _, _, test in folds for p in test)
    assert tested == sorted(wd.DEVELOPMENT)                                # everyone is a test person once
    for train, val, test in folds:
        assert not set(train) & set(val) and not set(train) & set(test) and not set(val) & set(test)
        assert (len(train), len(val), len(test)) == (43, 8, 17)
        assert not any(wd.is_lockbox(p) for p in train + val + test)
