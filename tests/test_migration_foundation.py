from pathlib import Path

import pytest

from scripts.ci_migration_smoke import EXPECTED_URL, validated_test_database_url
from scripts.schema_inventory import inventory_fingerprint, normalize_database_url


def test_migration_smoke_accepts_only_exact_disposable_database():
    assert validated_test_database_url(EXPECTED_URL) == EXPECTED_URL
    for unsafe in (
        None,
        "postgresql+asyncpg://ci:ci_test@localhost:55433/hist_soc_migration_test",
        "postgresql+asyncpg://ci:ci_test@127.0.0.1:5432/hist_soc_migration_test",
        "postgresql+asyncpg://ci:ci_test@127.0.0.1:55433/production",
        "postgresql+asyncpg://owner:secret@example.com/production",
    ):
        with pytest.raises(RuntimeError, match="Refusing"):
            validated_test_database_url(unsafe)


def test_inventory_url_normalization_and_driver_guard():
    normalized = normalize_database_url("postgresql://user:secret@db.example/test")
    assert normalized.startswith("postgresql+asyncpg://")
    with pytest.raises(ValueError, match="Only postgresql"):
        normalize_database_url("sqlite:///test.db")


def test_inventory_fingerprint_is_deterministic_and_sensitive():
    first = {
        "database": "staging",
        "server_version": "17.1",
        "tables": [{"name": "a"}],
        "extensions": [],
    }
    reordered = {
        "extensions": [],
        "tables": [{"name": "a"}],
        "database": "production",
        "server_version": "17.2",
    }
    changed = {"extensions": [], "tables": [{"name": "b"}]}
    assert inventory_fingerprint(first) == inventory_fingerprint(reordered)
    assert inventory_fingerprint(first) != inventory_fingerprint(changed)


def test_initial_revision_is_explicit_empty_database_bootstrap():
    source = Path(
        "migrations/versions/0001_empty_database_orm_bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "Base.metadata.create_all" not in source
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert "restricted to an empty PostgreSQL database" in source
    assert source.count("op.create_table(") == 36
    assert "empty-database bootstrap only" in source.casefold()


def test_runtime_image_contains_migration_assets():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY alembic.ini ./" in dockerfile
    assert "COPY migrations ./migrations" in dockerfile
