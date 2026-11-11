"""SQLAlchemy engine, session factory and declarative Base."""

import sqlite3
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, create_engine, event, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    """
    Turn on SQLite foreign keys.

    SQLite ignores foreign keys unless asked; ON DELETE CASCADE needs this.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """
    Timezone-aware UTC datetimes.

    SQLite does not store tzinfo, so a plain DateTime(timezone=True) comes back
    naive and the API would emit timestamps without a "Z". This type stores UTC
    and always returns aware UTC values, on every database.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:  # treat naive input as UTC
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def init_db() -> None:
    """
    Create the SQLite folder (if needed) and all tables. Called at startup.

    Alembic is the production path; create_all is enough for this project.
    """
    import_module("app.models")  # registers the tables on Base

    if _is_sqlite:
        db_path = make_url(settings.database_url).database
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _reset_if_outdated()
    Base.metadata.create_all(engine)
    _add_missing_columns()


class OutdatedDatabaseError(RuntimeError):
    pass


def _reset_if_outdated() -> None:
    """
    Results gained `model_key` and a new unique rule (scan, method, model).
    SQLite cannot change a unique rule in place, so an older database is
    rebuilt when it holds no scans, and otherwise startup stops with advice
    instead of failing later on the second ML result of a scan.
    """
    inspector = inspect(engine)
    if "scan_results" not in inspector.get_table_names():
        return
    if "model_key" in {c["name"] for c in inspector.get_columns("scan_results")}:
        return
    with engine.connect() as conn:
        scans = conn.execute(text("SELECT COUNT(*) FROM scans")).scalar() or 0
    if scans:
        raise OutdatedDatabaseError(
            f"The database at {settings.database_url} was made by an older version "
            f"and holds {scans} scan(s). Back it up or delete it (and data/media), then start again."
        )
    Base.metadata.drop_all(engine)


# Columns added after the first release. create_all does not alter existing
# tables, so a database made by an older version gets them here.
_ADDED_COLUMNS = {"scan_results": {"mask_key": "VARCHAR"}}


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
