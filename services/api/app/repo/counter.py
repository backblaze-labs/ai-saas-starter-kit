"""Persistence adapter for the download counter.

Persistence belongs in the repo layer (AGENTS.md §3), so the file I/O that used
to live in `service/files.py` lives here behind a small interface.

Durability caveat: this writes a JSON file at `settings.download_count_file`.
On an ephemeral filesystem (Railway without a mounted volume) the count resets
on every redeploy, and with multiple replicas each process keeps its own file
and count. For production accuracy, mount a persistent volume or swap this
adapter for a shared store (Redis/DB). See docs/RELIABILITY.md.
"""

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)

_lock = Lock()


def _counter_path() -> Path:
    """Resolve the counter file path relative to the api service root."""
    p = Path(settings.download_count_file)
    if not p.is_absolute():
        # Anchor at services/api/ (three levels up: repo/ -> app/ -> api/).
        p = Path(__file__).resolve().parents[2] / p
    return p


def _load() -> int:
    """Read the persisted counter; return 0 if missing or unreadable."""
    try:
        with open(_counter_path()) as f:
            return int(json.load(f).get("count", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return 0


def _save(count: int) -> None:
    """Atomically persist the counter. Caller must hold the lock."""
    path = _counter_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp file in the same dir, then rename.
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"count": count}, f)
            os.replace(tmp, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
    except OSError as e:
        # Counter persistence failing shouldn't break downloads — log and move on.
        logger.warning("Failed to persist download counter: %s", e)


_count = _load()


def get_download_count() -> int:
    with _lock:
        return _count


def increment_download_count() -> None:
    global _count
    # Snapshot under the lock, then persist outside it: with handlers now on
    # the threadpool, holding the lock across the file write would serialize
    # every concurrent download behind disk I/O. `os.replace` is atomic so the
    # file is never corrupted; under a write race the persisted value may lag
    # the in-memory count (which stays correct) until the next increment.
    # Cross-restart/replica durability is tracked tech debt.
    with _lock:
        _count += 1
        snapshot = _count
    _save(snapshot)
