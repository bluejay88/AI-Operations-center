from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .settings import get_settings


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "sql" / "schema.sql"


def database_url(local: bool = False) -> str:
    settings = get_settings()
    return settings.local_database_url if local else settings.database_url


@contextmanager
def connect(local: bool = False) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url(local=local), row_factory=dict_row) as conn:
        yield conn


def init_db(local: bool = False) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()

