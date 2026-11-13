"""The lockbox (34 people set aside in M0) is opened once. Small helpers that enforce it.

A marker file records the opening. It is written BEFORE the first lockbox person is decoded, so that an
opening cannot go unrecorded. Nothing here reads data.
"""
from __future__ import annotations

import pathlib

from . import wearable as wd

MARKER_NAME = "LOCKBOX_OPENED.txt"


class LockboxError(RuntimeError):
    """Raised when something would use the lockbox outside the single approved opening."""


def require_access(sid: int, opened: bool) -> None:
    """A lockbox person may be loaded only inside the opening."""
    if wd.is_lockbox(sid) and not opened:
        raise LockboxError(f"S{sid:03d} is a lockbox person; the lockbox has not been opened")


def check_disjoint(new, population, train, validation) -> None:
    """New people never appear among the people the methods were built on, and the population holds no lockbox person."""
    new, population, train, validation = set(new), set(population), set(train), set(validation)
    if new & population:
        raise LockboxError(f"new people inside the population: {sorted(new & population)}")
    if (train | validation) != population or train & validation:
        raise LockboxError("training and validation people must split the population")
    if any(wd.is_lockbox(s) for s in population):
        raise LockboxError("a lockbox person inside the population")


def state(marker) -> str:
    """'closed', 'started' (an opening began and did not finish) or 'complete'."""
    marker = pathlib.Path(marker)
    if not marker.exists():
        return "closed"
    return "complete" if "status: complete" in marker.read_text() else "started"


def begin(marker, commit: str, when: str, resume: bool = False) -> None:
    """Record the opening. Refuses if the lockbox was opened before. An opening that was interrupted before it
    finished (no result was written) may be resumed from the same commit only."""
    marker = pathlib.Path(marker)
    now = state(marker)
    if now == "closed":
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"The lockbox was opened.\nstarted: {when}\ncommit: {commit}\nstatus: started\n")
        return
    if now == "complete":
        raise LockboxError("the lockbox has already been opened; it is opened once")
    if not resume:
        raise LockboxError("an opening was started and did not finish; it can only be resumed, from the same commit")
    if f"commit: {commit}\n" not in marker.read_text():
        raise LockboxError("the interrupted opening was started from another commit")
    with marker.open("a") as f:
        f.write(f"resumed: {when}\n")


def finish(marker, when: str) -> None:
    with pathlib.Path(marker).open("a") as f:
        f.write(f"finished: {when}\nstatus: complete\n")
