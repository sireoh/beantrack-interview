"""Migrations match the models, and SQLite runs in WAL mode."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import FastAPI
from sqlalchemy import text

from app.db.base import Base
from app.db.session import build_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_migrations_create_schema_matching_models(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"

    command.upgrade(_alembic_config(url), "head")

    engine = build_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_corrections_migration_upgrades_an_existing_database(tmp_path: Path) -> None:
    """0008 on a database that already has users and shows (not just an empty one)."""
    url = f"sqlite:///{(tmp_path / 'existing.db').as_posix()}"
    config = _alembic_config(url)
    command.upgrade(config, "0007")
    engine = build_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (discord_id, username, created_at, last_login, role)"
                " VALUES ('1', 'old-user', '2026-01-01', '2026-01-01', 'user')"
            )
        )
        connection.execute(
            text("INSERT INTO tvshows (imdb, title) VALUES ('tt0903747', 'Breaking Bad')")
        )

    command.upgrade(config, "head")

    with engine.begin() as connection:
        assert connection.execute(
            text("SELECT custom_display_enabled FROM users WHERE discord_id = '1'")
        ).scalar() == 1
        assert connection.execute(text("SELECT title FROM tvshows")).scalar() == "Breaking Bad"
        index_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'uq_show_corrections_one_pending'")
        ).scalar()
        assert isinstance(index_sql, str)
        assert "UNIQUE" in index_sql and "WHERE status = 'pending'" in index_sql
        connection.execute(
            text(
                "INSERT INTO show_corrections (imdb_id, submitted_by, new_title, status, created_at)"
                " VALUES ('tt0903747', '1', 'x', 'pending', '2026-01-01')"
            )
        )
    engine.dispose()


def test_corrections_downgrade_keeps_existing_user_data(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'existing.db').as_posix()}"
    config = _alembic_config(url)
    command.upgrade(config, "head")
    engine = build_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (discord_id, username, created_at, last_login, role)"
                " VALUES ('1', 'u', '2026-01-01', '2026-01-01', 'user')"
            )
        )
        connection.execute(text("INSERT INTO tvlists (tvlist_id, discord_id) VALUES ('L1', '1')"))
    engine.dispose()

    command.downgrade(config, "0007")

    engine = build_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM tvlists")).scalar() == 1
        columns = [row[1] for row in connection.execute(text("PRAGMA table_info(users)"))]
    engine.dispose()
    assert "custom_display_enabled" not in columns


def test_migrations_downgrade_cleanly(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    config = _alembic_config(url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = build_engine(url)
    with engine.connect() as connection:
        tables = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'")
        ).all()
    engine.dispose()
    assert tables == []


def test_connections_use_wal_and_busy_timeout(app: FastAPI) -> None:
    with app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
