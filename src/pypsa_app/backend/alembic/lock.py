"""Postgres session-level advisory lock for serializing concurrent migrations.

`pg_advisory_lock(key)` blocks the second arriver until the first releases;
the second then sees the version table is current and runs upgrade head as a
no-op. The key is a deterministic int derived from a fixed app identifier so
every caller across processes and containers contends on the same lock.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text


def _compute_lock_key(identifier: bytes) -> int:
    digest = hashlib.sha256(identifier).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


MIGRATION_LOCK_KEY: int = _compute_lock_key(b"pypsa-app:alembic-migration")


@contextmanager
def advisory_lock(connection, key: int) -> Iterator[None]:
    connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
    try:
        yield
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
