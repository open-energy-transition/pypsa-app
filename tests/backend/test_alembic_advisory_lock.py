"""Tests for the advisory-lock helper used by alembic env.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from pypsa_app.backend.alembic.lock import (
    MIGRATION_LOCK_KEY,
    advisory_lock,
)


class TestAdvisoryLockHelper:
    def test_lock_key_is_stable_integer(self) -> None:
        """MIGRATION_LOCK_KEY must be a deterministic int constant so all
        callers across containers acquire the *same* Postgres advisory lock."""
        assert isinstance(MIGRATION_LOCK_KEY, int)
        # bigint range — pg_advisory_lock takes a bigint
        assert -(2**63) <= MIGRATION_LOCK_KEY < 2**63

    def test_advisory_lock_acquires_and_releases(self) -> None:
        """The context manager must run pg_advisory_lock on entry and
        pg_advisory_unlock on exit, against the supplied connection."""
        conn = MagicMock()

        with advisory_lock(conn, MIGRATION_LOCK_KEY):
            pass

        executed_sql = [
            str(call.args[0]) for call in conn.execute.call_args_list
        ]
        assert any("pg_advisory_lock" in sql for sql in executed_sql), (
            f"expected pg_advisory_lock call, got: {executed_sql}"
        )
        assert any("pg_advisory_unlock" in sql for sql in executed_sql), (
            f"expected pg_advisory_unlock call, got: {executed_sql}"
        )

    def test_advisory_lock_releases_on_exception(self) -> None:
        """If the wrapped block raises, the lock must still be released —
        otherwise the next arriver hangs forever."""
        conn = MagicMock()

        with pytest.raises(RuntimeError, match="boom"):
            with advisory_lock(conn, MIGRATION_LOCK_KEY):
                raise RuntimeError("boom")

        executed_sql = [
            str(call.args[0]) for call in conn.execute.call_args_list
        ]
        assert any("pg_advisory_unlock" in sql for sql in executed_sql), (
            f"unlock must run on exception, got: {executed_sql}"
        )

    def test_advisory_lock_passes_key_as_bind_parameter(self) -> None:
        """The lock key must be bound, not f-string interpolated, to avoid
        SQL injection and to let sqlalchemy handle parameterization."""
        conn = MagicMock()
        with advisory_lock(conn, MIGRATION_LOCK_KEY):
            pass
        # First call is the lock — inspect its kwargs/args for bind params
        first_call = conn.execute.call_args_list[0]
        # sqlalchemy text() with bound params: execute(stmt, {"key": ...})
        # or execute(stmt.bindparams(key=...))
        sql = str(first_call.args[0])
        assert ":key" in sql or "$1" in sql or "%s" in sql or "?" in sql, (
            f"lock SQL must use a bind parameter for the key, got: {sql!r}"
        )


class TestEnvPyUsesAdvisoryLock:
    """The env.py module must call the advisory-lock helper around migrations."""

    def test_env_py_imports_and_uses_advisory_lock(self) -> None:
        from pathlib import Path
        env_path = Path(
            "src/pypsa_app/backend/alembic/env.py"
        ).resolve()
        source = env_path.read_text()
        assert "advisory_lock" in source, (
            "env.py must import and use the advisory_lock helper to serialize "
            "concurrent migration runs"
        )
