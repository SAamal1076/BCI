"""M3: shared helpers. The 1 s sub-band trials of pipeline B2 are cached once per development person."""
import os
import pathlib
import sys
import tempfile

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ssvep import pipeline as pp  # noqa: E402
from ssvep import wearable as wd  # noqa: E402

PIPELINE, N, FS = "B2", 250, wd.FS
PEOPLE = wd.DEVELOPMENT
SEEDS = (0, 1, 2)
DEFAULT_CACHE = pathlib.Path(tempfile.gettempdir()) / "m3_cache"
RES = ROOT / "results" / "m3"


def _prepare_one(job):
    sid, raw, cache = job
    assert not wd.is_lockbox(sid)
    sub = pp.subbands(wd.load_subject(raw, sid), N, PIPELINE, wd.RESP_START, FS)     # (band, e, block, target, ch, n)
    sub = sub - sub.mean(axis=-1, keepdims=True)
    np.save(cache / f"S{sid:03d}.npy", sub.transpose(1, 2, 3, 0, 4, 5).astype(np.float32))
    return sid


def prepare(raw, cache, jobs=2):
    """Write the cache (once): one file per development person, [electrode, block, target, band, channel, sample]."""
    cache = pathlib.Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    todo = [(sid, raw, cache) for sid in PEOPLE if not (cache / f"S{sid:03d}.npy").exists()]
    if todo:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs) as pool:
            pool.map(_prepare_one, todo, chunksize=1)
    return cache


def load(cache, sid, electrode):
    """Trials of one person and one headband: (block, target, band, channel, sample), float32."""
    assert not wd.is_lockbox(sid)
    return np.load(pathlib.Path(cache) / f"S{sid:03d}.npy")[electrode]


def labelled(cache, people, electrode, blocks=range(10)):
    """All trials of the given people as network input: x (trials, band, ch, n) not yet standardised, y."""
    x = np.concatenate([load(cache, sid, electrode)[list(blocks)].reshape(-1, 3, 8, N) for sid in people])
    y = np.tile(np.arange(wd.N_TARGETS), len(x) // wd.N_TARGETS)
    return x, y
