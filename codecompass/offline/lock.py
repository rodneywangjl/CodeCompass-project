"""Single-writer file lock with wait/timeout (plan D7, spec C8)."""

from __future__ import annotations

from contextlib import contextmanager

from filelock import FileLock, Timeout


class LockTimeout(Exception):
    """Raised when the index lock cannot be acquired within the timeout."""


@contextmanager
def acquire_lock(lock_path, timeout_seconds: float = 120):
    """Hold an exclusive lock; wait up to *timeout_seconds* or raise LockTimeout."""
    lock = FileLock(str(lock_path), timeout=timeout_seconds)
    try:
        lock.acquire()
    except Timeout as e:
        raise LockTimeout(
            f"index is locked (waited {timeout_seconds}s): {lock_path}") from e
    try:
        yield
    finally:
        lock.release()
