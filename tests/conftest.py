from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database_uri(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    from pgserver.postgres_server import get_server

    server = get_server(tmp_path_factory.mktemp("postgres"), cleanup_mode="stop")
    try:
        uri: str = server.get_uri()
        with psycopg.connect(uri, autocommit=True) as connection:
            connection.execute((ROOT / "db/tests/auth-shim.sql").read_text())
            for migration in sorted((ROOT / "db/migrations").glob("*.sql")):
                connection.execute(migration.read_text())
        yield uri
    finally:
        server.cleanup()


@pytest.fixture
def db(database_uri: str) -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(database_uri) as connection:
        try:
            yield connection
        finally:
            connection.rollback()
