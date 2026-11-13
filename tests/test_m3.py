"""M3 code on synthetic data: folds of people, the network, adaptation without labels."""
import inspect
import pathlib
import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import adapt as ad  # noqa: E402
from ssvep import network as nw  # noqa: E402
from ssvep import wearable as wd  # noqa: E402


def _toy(n=96, seed=0):
    rng = np.random.default_rng(seed)
    y = np.arange(n) % 12
    t = np.arange(250) / 250.0
    x = rng.standard_normal((n, 3, 8, 250))
    x += 1.5 * np.sin(2 * np.pi * (9.25 + 0.5 * y)[:, None, None, None] * t)
    return nw.standardise(x), y


def test_folds_cover_everybody_once_and_never_mix():
    f = nw.folds(wd.DEVELOPMENT)
    assert len(f) == 4 and sorted(p for _, _, test in f for p in test) == sorted(wd.DEVELOPMENT)
    for train, val, test in f:
        assert (len(train), len(val), len(test)) == (43, 8, 17)
        assert not set(test) & (set(train) | set(val)) and not set(train) & set(val)
        assert not any(wd.is_lockbox(p) for p in train + val + test)


def test_network_size_and_output():
    model = nw.Net()
    assert nw.n_parameters(model) == 3572
    assert nw.predict(model, np.zeros((5, 3, 8, 250), dtype=np.float32)).shape == (5, 12)
    x = nw.standardise(np.random.default_rng(0).standard_normal((4, 3, 8, 250)) * 50 + 7)
    assert np.allclose(x.mean(axis=(-2, -1)), 0, atol=1e-5) and np.allclose(x.std(axis=(-2, -1)), 1, atol=1e-4)


def test_training_learns_and_is_repeatable():
    x, y = _toy()
    a, hist = nw.train(x, y, x, y, seed=1, max_epochs=12, patience=12)
    b, _ = nw.train(x, y, x, y, seed=1, max_epochs=12, patience=12)
    assert all(torch.equal(p, q) for p, q in zip(a.state_dict().values(), b.state_dict().values()))
    assert hist[-1][2] < hist[0][2]                                     # validation loss went down


def _split_state(model):
    stats = {k: v for k, v in model.state_dict().items() if "running" in k or "num_batches" in k}
    affine = {k: v for k, v in model.state_dict().items() if k.startswith("bn") and k.endswith(("weight", "bias"))}
    other = {k: v for k, v in model.state_dict().items() if k not in stats and k not in affine}
    return stats, affine, other


def test_adaptation_changes_only_what_it_should_and_takes_no_labels():
    x, y = _toy()
    model, _ = nw.train(x, y, x, y, seed=0, max_epochs=3, patience=3)
    new = nw.standardise(np.random.default_rng(5).standard_normal((72, 3, 8, 250)) * np.linspace(1, 3, 8)[:, None])
    s0, a0, o0 = _split_state(model)
    s1, a1, o1 = _split_state(ad.adapt_statistics(model, new))
    s2, a2, o2 = _split_state(ad.adapt_entropy(model, new))
    same = lambda p, q: all(torch.equal(p[k], q[k]) for k in p)        # noqa: E731
    assert not same(s0, s1) and same(a0, a1) and same(o0, o1)           # A1: statistics only
    assert same(s1, s2) and not same(a0, a2) and same(o0, o2)           # A2: + scale and shift only
    assert same(s0, _split_state(model)[0])                             # the source model is left as it was
    for fn in (ad.adapt_statistics, ad.adapt_entropy, ad.online):
        assert not {"y", "labels", "label", "targets"} & set(inspect.signature(fn).parameters)
    preds = ad.online(model, [new[:12], new[12:24]])
    assert len(preds) == 2 and preds[0].shape == (12,)
    assert np.array_equal(preds[0], nw.predict(model, new[:12]).argmax(axis=1))   # first block: before any adaptation


def test_entropy_steps_lower_the_entropy():
    x, y = _toy()
    model, _ = nw.train(x, y, x, y, seed=0, max_epochs=3, patience=3)
    new, _ = _toy(72, seed=9)
    before = ad.adapt_statistics(model, new)
    after = ad.adapt_entropy(model, new, lr=1e-2)
    h = lambda m: float(ad.entropy(torch.as_tensor(nw.predict(m, new))))   # noqa: E731
    assert h(after) < h(before)
