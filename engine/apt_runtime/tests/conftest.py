"""Opt-in real-Postgres fixtures for APT durable-store acceptance tests.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from uuid import uuid4

import pytest


@dataclass(frozen=True, slots=True)
class PostgresSandbox:
    """One isolated schema and DSN for a single acceptance test."""

    base_dsn: str
    dsn: str
    schema: str

    def dsn_for(self, application_name: str) -> str:
        """Return the sandbox DSN with a session name useful for lock tests."""

        from psycopg.conninfo import make_conninfo

        return make_conninfo(self.dsn, application_name=application_name)


@pytest.fixture(scope="session")
def apt_runtime_postgres_dsn():
    """Resolve an explicit DSN or an explicitly enabled disposable Postgres."""

    configured = os.environ.get("APT_RUNTIME_POSTGRES_DSN")
    if configured:
        yield configured
        return

    if os.environ.get("APT_RUNTIME_TEST_POSTGRES") != "1":
        pytest.skip(
            "set APT_RUNTIME_POSTGRES_DSN or APT_RUNTIME_TEST_POSTGRES=1 "
            "to run real-Postgres acceptance tests"
        )

    pytest.importorskip("psycopg")
    postgres_module = pytest.importorskip("testcontainers.postgres")
    container = postgres_module.PostgresContainer("postgres:16-alpine", driver=None)
    with container:
        yield container.get_connection_url(driver=None)


@pytest.fixture
def postgres_sandbox(apt_runtime_postgres_dsn: str):
    """Create and later drop a unique schema selected through libpq options."""

    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    schema = f"apt_runtime_test_{uuid4().hex}"
    with psycopg.connect(apt_runtime_postgres_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    isolated_dsn = make_conninfo(
        apt_runtime_postgres_dsn,
        options=f"-csearch_path={schema}",
    )
    sandbox = PostgresSandbox(
        base_dsn=apt_runtime_postgres_dsn,
        dsn=isolated_dsn,
        schema=schema,
    )
    try:
        yield sandbox
    finally:
        with psycopg.connect(apt_runtime_postgres_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
