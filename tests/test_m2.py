"""M2 code on synthetic signals: pipeline candidates, template decoder, leakage rules, statistics."""
import pathlib
import sys

import numpy as np
import pytest
from scipy import signal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ssvep import decoders as dc  # noqa: E402
from ssvep import pipeline as pp  # noqa: E402
from ssvep import spectral as sp  # noqa: E402
from ssvep import stats as st  # noqa: E402
from ssvep import transfer as tr  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

FS, F = 250.0, wd.TARGET_FREQS
NEAR = np.isin(F, (12.25, 12.75))


def _noise(n_trials, seed=0, independent=1.0):
    """8 channels of 1/f noise, no response and no mains: two sources common to all channels plus an
    independent part. A small independent part gives strongly correlated channels, as on the scalp."""
    rng = np.random.default_rng(seed)
    n = wd.N_SAMPLES
    gain = 1 / np.maximum(np.fft.rfftfreq(n, 1 / FS), 1.0) ** 0.75

    def pink(shape):
        return np.fft.irfft(np.fft.rfft(rng.standard_normal(shape), axis=-1) * gain, n=n, axis=-1)

    common = np.einsum("cs,tsn->tcn", rng.standard_normal((8, 2)), pink((n_trials, 2, n)))
    return common + independent * pink((n_trials, 8, n))


# ----------------------------------------------------------------------------- pipeline
def test_b2_filters_pass_the_band_and_stop_the_mains():
    for band, low in enumerate((6.0, 14.0, 22.0)):
        sos = pp.design_b2(band)
        f, h = signal.sosfreqz(sos, worN=[low + 4, 30.0, 44.0, 50.0, 60.0], fs=FS)
        gain = 20 * np.log10(np.abs(h))
        # the design rule reaches 31 to 35 dB at the 50 Hz edge (as the reference filters do at theirs);
        # the filter is applied forward and backward, which doubles these figures
        assert np.all(gain[:3] > -1.0) and gain[3] < -30.0 and gain[4] < -60.0
        assert np.all(np.abs(np.roots(np.poly(np.concatenate([np.roots(s[3:]) for s in sos])))) < 1)


def test_shared_removal_takes_out_a_common_mains():
    rng = np.random.default_rng(1)
    t = np.arange(wd.N_SAMPLES) / FS
    mains = 60 * rng.uniform(0.5, 1.5, (20, 8, 1)) * np.sin(2 * np.pi * 50.03 * t + rng.uniform(0, 6, (20, 1, 1)))
    x = 0.1 * rng.standard_normal((20, 8, wd.N_SAMPLES))
    out = pp.remove_mains_shared(x + mains, FS)
    assert sp.amplitude(x + mains, [50.03], FS).min() > 20 and sp.amplitude(out, [50.03], FS).max() < 0.05


def test_shared_removal_makes_no_decision_bias_on_noise_but_the_per_channel_one_does():
    """With strongly correlated channels the per-channel removal (B) pulls CCA decisions to 12.25 and 12.75 Hz
    (4th harmonic at 49 and 51 Hz) although there is no mains and no response; the shared removal does not.
    With weakly correlated channels neither does."""
    weak = _noise(300, independent=1.0)
    bases = dc.reference_bases(F, 250, FS, 5)
    assert NEAR[dc.cca_corr(pp.subbands(weak, 250, "B", wd.RESP_START)[0], bases).argmax(axis=-1)].mean() < 0.15
    x, n = _noise(400, independent=0.01), 250
    bases = dc.reference_bases(F, n, FS, 5)
    share = {}
    for name in ("B", "B1"):
        sub = pp.subbands(x, n, name, wd.RESP_START)[0]
        share[name] = NEAR[dc.cca_corr(sub, bases).argmax(axis=-1)].mean()
    assert share["B"] > 0.30 and share["B1"] < 0.15


def test_b1_treats_all_channels_alike():
    """Rotating the channels before or after the pipeline gives the same result (not true for B)."""
    x = _noise(5, seed=3)
    q = np.linalg.qr(np.random.default_rng(4).standard_normal((8, 8)))[0]
    a = pp.subbands(np.einsum("ij,tjn->tin", q, x), 250, "B1", wd.RESP_START)
    b = np.einsum("ij,btjn->btin", q, pp.subbands(x, 250, "B1", wd.RESP_START))
    assert np.allclose(a, b, atol=1e-9)


@pytest.mark.parametrize("name", pp.NAMES)
def test_candidates_use_no_sample_after_the_window(name):
    x = _noise(3, seed=5)
    y = x.copy()
    y[..., wd.RESP_START + 250:] += 100.0
    a, b = pp.subbands(x, 250, name, wd.RESP_START), pp.subbands(y, 250, name, wd.RESP_START)
    assert a.shape == (pp.N_BANDS[name], 3, 8, 250) and np.array_equal(a, b)
    assert len(pp.weights(name)) == pp.N_BANDS[name]


# ----------------------------------------------------------------------------- template decoder
def test_cca_filters_agree_with_cca_corr_and_give_that_correlation():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4, 8, 250))
    bases = dc.reference_bases(F, 250, FS, 3)
    rho, w = tr.cca_filters(x, bases)
    assert np.allclose(rho, dc.cca_corr(x, bases))
    xc = x - x.mean(axis=-1, keepdims=True)
    for t, k in ((0, 0), (2, 7)):
        y = w[t, k] @ xc[t]
        fit = bases[k] @ (bases[k].T @ y)
        assert np.isclose(np.corrcoef(y, fit)[0, 1], rho[t, k])


def test_combined_template_limits():
    p, i = np.ones((2, 3)), np.zeros((2, 3))
    assert tr.combined_template(p, None, 0, 2.0) is p
    assert np.allclose(tr.combined_template(p, i, 2, 2.0), 0.5)
    assert np.allclose(tr.combined_template(p, i, 4, 0.0), i)
    assert np.allclose(tr.combined_template(p, i, 1, 1e9), p)


def _phase_coded_trials(rng, n_trials, amp, n=250):
    """Trials whose response has the right frequency for every class but a class-specific spatial pattern and
    phase, so that a template carries information that the sine-cosine reference does not."""
    t = np.arange(n) / FS
    patterns = rng.standard_normal((12, 8))
    clean = np.array([np.outer(patterns[k], np.sin(2 * np.pi * F[k] * t + k)) for k in range(12)])
    labels = np.tile(np.arange(12), n_trials)
    x = amp * clean[labels] + rng.standard_normal((len(labels), 8, n))
    return x[None], clean[None], labels


def test_a_good_template_helps_and_a_wrong_one_does_not():
    rng = np.random.default_rng(2)
    x, clean, labels = _phase_coded_trials(rng, 10, 0.12)
    bases = dc.reference_bases(F, 250, FS, 3)
    part = tr.trial_part(x, bases)
    acc_cca = (part[0][0].argmax(axis=-1) == labels).mean()
    acc_template = (tr.ecca_scores(part, clean, bases, [1.0]).argmax(axis=-1) == labels).mean()
    wrong = np.roll(clean, 3, axis=1)                                   # templates given to the wrong classes
    acc_wrong = (tr.ecca_scores(part, wrong, bases, [1.0]).argmax(axis=-1) == labels).mean()
    assert acc_template > acc_cca + 0.15 and acc_wrong < acc_template - 0.15


def test_features_have_the_documented_shapes():
    rng = np.random.default_rng(3)
    x, clean, _ = _phase_coded_trials(rng, 2, 1.0)
    x, clean = np.repeat(x, 3, axis=0), np.repeat(clean, 3, axis=0)
    bases = dc.reference_bases(F, 250, FS, 3)
    feats = tr.ecca_features(tr.trial_part(x, bases), clean, bases)
    assert all(f.shape == (3, 24, 12) for f in feats)
    assert tr.ecca_scores(tr.trial_part(x, bases), clean, bases, [1.0, 0.5, 0.25]).shape == (24, 12)


# ----------------------------------------------------------------------------- leakage rules
def test_test_person_never_enters_the_population_template():
    rng = np.random.default_rng(4)
    means = rng.standard_normal((6, 2, 4))                              # 6 people
    total = means.sum(axis=0)
    marked = means.copy()
    marked[2] += 1e6                                                    # marker in person 3
    p_clean = tr.leave_one_out_mean(total, means[2], 6)
    p_marked = tr.leave_one_out_mean(marked.sum(axis=0), marked[2], 6)
    assert np.allclose(p_clean, p_marked, atol=1e-6)
    assert np.allclose(p_clean, np.delete(means, 2, axis=0).mean(axis=0))
    assert not np.allclose(tr.leave_one_out_mean(marked.sum(axis=0), marked[1], 6), p_clean)   # positive control


def test_calibration_and_test_blocks_never_overlap():
    for k in (0, 1, 2, 4, 6):
        cal, test = tr.split_blocks(k)
        assert cal == tuple(range(k)) and test == (6, 7, 8, 9) and not set(cal) & set(test)
    with pytest.raises(ValueError):
        tr.split_blocks(7)


# ----------------------------------------------------------------------------- statistics
def test_crossover_effect_cancels_the_period_effect():
    rng = np.random.default_rng(5)
    first = np.arange(40) < 22                                          # 22 people had the treatment first
    tau, period = -0.15, -0.05                                          # treatment effect, second-period effect
    base = rng.uniform(0.3, 0.9, 40)
    treated = base + tau + np.where(first, 0.0, period)
    control = base + np.where(first, period, 0.0)
    d = treated - control
    assert np.isclose(st.crossover_effect(d, first), tau)
    assert not np.isclose(d.mean(), tau)                                # the plain mean is biased by the period
    noise = 0.05 * rng.standard_normal(40)
    assert st.crossover_test(d + noise, first) < 0.001
    only_period = np.where(first, -period, period) + noise              # no treatment effect at all
    assert st.crossover_test(only_period, first) > 0.05


def test_noninferiority_and_bootstrap():
    rng = np.random.default_rng(6)
    ref = rng.uniform(0.5, 0.9, 34)
    noise = 0.03 * rng.standard_normal(34)
    assert st.noninferiority_test(ref - 0.01 + noise, ref, 0.05) < 0.01
    assert st.noninferiority_test(ref - 0.10 + noise, ref, 0.05) > 0.5
    lo, hi = st.bootstrap_ci(ref)
    assert lo < ref.mean() < hi and st.bootstrap_ci(ref) == (lo, hi)
