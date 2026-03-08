"""Integration tests for the profiler engine against a real DuckDB database."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from docglow.profiler.engine import apply_profiles, profile_models

pytest.importorskip("sqlalchemy")
pytest.importorskip("duckdb")


@pytest.fixture()
def duckdb_path(tmp_path: Path) -> str:
    """Create a test DuckDB database with sample data."""
    import duckdb

    db_path = str(tmp_path / "test.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("""
        CREATE SCHEMA IF NOT EXISTS main;
        CREATE TABLE main.orders (
            order_id INTEGER,
            customer_id INTEGER,
            status VARCHAR,
            amount DECIMAL(10,2),
            order_date DATE,
            is_active BOOLEAN
        );
        INSERT INTO main.orders VALUES
            (1, 10, 'completed', 99.99, '2024-01-15', true),
            (2, 20, 'completed', 45.50, '2024-01-16', true),
            (3, 10, 'pending', 120.00, '2024-01-17', true),
            (4, 30, 'cancelled', NULL, '2024-01-18', false),
            (5, 20, 'completed', 75.25, '2024-01-19', true),
            (6, NULL, 'pending', 200.00, NULL, NULL),
            (7, 10, 'completed', 30.00, '2024-01-21', true),
            (8, 40, 'completed', 55.50, '2024-01-22', true),
            (9, 20, 'pending', 88.00, '2024-01-23', true),
            (10, 50, 'completed', 150.00, '2024-01-24', true);
    """)
    conn.close()
    return db_path


def _make_model(
    name: str = "orders",
    schema: str = "main",
    columns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "unique_id": f"model.test.{name}",
        "name": name,
        "schema": schema,
        "database": "test",
        "materialization": "table",
        "columns": columns or [],
        "catalog_stats": {"row_count": 10, "bytes": None, "has_stats": True},
        "description": "",
        "tags": [],
        "meta": {},
        "folder": "models",
        "path": f"models/{name}.sql",
        "depends_on": [],
        "referenced_by": [],
    }


class TestProfilerIntegration:
    def test_profile_numeric_columns(self, duckdb_path: str) -> None:
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "order_id", "data_type": "INTEGER"},
                {"name": "amount", "data_type": "DECIMAL(10,2)"},
            ]),
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        assert "model.test.orders" in profiles
        p = profiles["model.test.orders"]

        # order_id
        assert p["order_id"]["row_count"] == 10
        assert p["order_id"]["null_count"] == 0
        assert p["order_id"]["distinct_count"] == 10
        assert p["order_id"]["is_unique"] is True
        assert p["order_id"]["min"] == 1
        assert p["order_id"]["max"] == 10

        # amount (has one NULL)
        assert p["amount"]["null_count"] == 1
        assert p["amount"]["null_rate"] == 0.1

    def test_profile_string_columns(self, duckdb_path: str) -> None:
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "status", "data_type": "VARCHAR"},
            ]),
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        p = profiles["model.test.orders"]["status"]
        assert p["distinct_count"] == 3  # completed, pending, cancelled
        assert p["min_length"] is not None
        assert p["max_length"] is not None
        # Should have top_values since distinct_count <= 50
        assert p.get("top_values") is not None
        assert len(p["top_values"]) == 3

    def test_profile_date_columns(self, duckdb_path: str) -> None:
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "order_date", "data_type": "DATE"},
            ]),
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        p = profiles["model.test.orders"]["order_date"]
        assert p["null_count"] == 1  # one NULL date
        assert p["min"] is not None
        assert p["max"] is not None

    def test_profile_with_cache(self, duckdb_path: str, tmp_path: Path) -> None:
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "order_id", "data_type": "INTEGER"},
            ]),
        }
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First run - should profile
        profiles1 = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            cache_dir=cache_dir,
            use_cache=True,
        )
        assert "model.test.orders" in profiles1

        # Second run - should use cache
        profiles2 = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            cache_dir=cache_dir,
            use_cache=True,
        )
        assert profiles2 == profiles1

    def test_apply_profiles(self, duckdb_path: str) -> None:
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "order_id", "data_type": "INTEGER", "profile": None},
                {"name": "status", "data_type": "VARCHAR", "profile": None},
            ]),
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        updated = apply_profiles(models, profiles)

        # Original should be unchanged
        assert models["model.test.orders"]["columns"][0]["profile"] is None

        # Updated should have profiles
        cols = updated["model.test.orders"]["columns"]
        assert cols[0]["profile"] is not None
        assert cols[0]["profile"]["row_count"] == 10
        assert cols[1]["profile"] is not None

    def test_skip_ephemeral_models(self, duckdb_path: str) -> None:
        models = {
            "model.test.ephemeral": {
                **_make_model(name="ephemeral"),
                "materialization": "ephemeral",
                "columns": [{"name": "id", "data_type": "INTEGER"}],
            },
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        assert "model.test.ephemeral" not in profiles

    def test_profile_all_column_types(self, duckdb_path: str) -> None:
        """Profile all column types in one model."""
        models = {
            "model.test.orders": _make_model(columns=[
                {"name": "order_id", "data_type": "INTEGER"},
                {"name": "customer_id", "data_type": "INTEGER"},
                {"name": "status", "data_type": "VARCHAR"},
                {"name": "amount", "data_type": "DECIMAL(10,2)"},
                {"name": "order_date", "data_type": "DATE"},
                {"name": "is_active", "data_type": "BOOLEAN"},
            ]),
        }

        profiles = profile_models(
            models,
            adapter="duckdb",
            connection_params={"path": duckdb_path},
            use_cache=False,
        )

        p = profiles["model.test.orders"]
        assert len(p) == 6
        assert p["order_id"]["is_unique"] is True
        assert p["customer_id"]["is_unique"] is False
        assert p["status"]["distinct_count"] == 3
        assert p["is_active"]["distinct_count"] == 2
