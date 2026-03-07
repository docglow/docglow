"""Tests for the column profiling engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from docs_plus_plus.profiler.cache import (
    is_cached,
    load_cache,
    save_cache,
    update_cache,
)
from docs_plus_plus.profiler.queries import (
    ColumnSpec,
    build_column_specs,
    build_stats_query,
    build_top_values_query,
    classify_column,
)
from docs_plus_plus.profiler.stats import parse_stats_row, parse_top_values_rows


class TestColumnClassification:
    def test_numeric_types(self) -> None:
        assert classify_column("INTEGER") == "numeric"
        assert classify_column("BIGINT") == "numeric"
        assert classify_column("FLOAT") == "numeric"
        assert classify_column("DECIMAL(10,2)") == "numeric"
        assert classify_column("NUMBER") == "numeric"

    def test_string_types(self) -> None:
        assert classify_column("VARCHAR") == "string"
        assert classify_column("TEXT") == "string"
        assert classify_column("VARCHAR(255)") == "string"
        assert classify_column("CHAR(10)") == "string"

    def test_date_types(self) -> None:
        assert classify_column("DATE") == "date"
        assert classify_column("TIMESTAMP") == "date"
        assert classify_column("TIMESTAMP WITH TIME ZONE") == "date"

    def test_boolean_types(self) -> None:
        assert classify_column("BOOLEAN") == "boolean"
        assert classify_column("BOOL") == "boolean"

    def test_unknown_type(self) -> None:
        assert classify_column("BINARY") == "other"
        assert classify_column("") == "other"

    def test_case_insensitive(self) -> None:
        assert classify_column("integer") == "numeric"
        assert classify_column("Varchar") == "string"


class TestQueryGeneration:
    def test_stats_query_numeric(self) -> None:
        cols = [ColumnSpec("price", "DECIMAL(10,2)", "numeric")]
        sql = build_stats_query("main", "orders", cols, adapter="duckdb")
        assert "COUNT(*) AS _row_count" in sql
        assert '"price__non_null_count"' in sql
        assert '"price__distinct_count"' in sql
        assert '"price__min"' in sql
        assert '"price__max"' in sql
        assert '"price__mean"' in sql
        assert '"price__median"' in sql
        assert '"price__stddev"' in sql
        assert '"main"."orders"' in sql

    def test_stats_query_string(self) -> None:
        cols = [ColumnSpec("status", "VARCHAR", "string")]
        sql = build_stats_query("main", "orders", cols, adapter="duckdb")
        assert '"status__min_length"' in sql
        assert '"status__max_length"' in sql
        assert '"status__avg_length"' in sql

    def test_stats_query_date(self) -> None:
        cols = [ColumnSpec("created_at", "TIMESTAMP", "date")]
        sql = build_stats_query("main", "events", cols, adapter="duckdb")
        assert '"created_at__min"' in sql
        assert '"created_at__max"' in sql

    def test_stats_query_with_sampling(self) -> None:
        cols = [ColumnSpec("id", "INTEGER", "numeric")]
        sql = build_stats_query("main", "big_table", cols, adapter="duckdb", sample_size=1000)
        assert "USING SAMPLE 1000 ROWS" in sql

    def test_stats_query_postgres_sampling(self) -> None:
        cols = [ColumnSpec("id", "INTEGER", "numeric")]
        sql = build_stats_query("public", "t", cols, adapter="postgres", sample_size=5000)
        assert "LIMIT 5000" in sql

    def test_stats_query_postgres_median(self) -> None:
        cols = [ColumnSpec("price", "NUMERIC", "numeric")]
        sql = build_stats_query("public", "t", cols, adapter="postgres")
        assert "PERCENTILE_CONT" in sql

    def test_top_values_query(self) -> None:
        sql = build_top_values_query("main", "orders", "status", adapter="duckdb")
        assert '"status" AS value' in sql
        assert "COUNT(*) AS frequency" in sql
        assert "ORDER BY frequency DESC" in sql
        assert "LIMIT 10" in sql

    def test_multiple_columns(self) -> None:
        cols = [
            ColumnSpec("id", "INTEGER", "numeric"),
            ColumnSpec("name", "VARCHAR", "string"),
            ColumnSpec("created", "DATE", "date"),
        ]
        sql = build_stats_query("main", "users", cols, adapter="duckdb")
        assert '"id__min"' in sql
        assert '"name__min_length"' in sql
        assert '"created__min"' in sql


class TestStatsParser:
    def test_parse_numeric_column(self) -> None:
        row = {
            "_row_count": 100,
            "price__non_null_count": 95,
            "price__distinct_count": 50,
            "price__min": 1.5,
            "price__max": 99.99,
            "price__mean": 45.0,
            "price__median": 42.0,
            "price__stddev": 20.0,
        }
        cols = [ColumnSpec("price", "DECIMAL", "numeric")]
        result = parse_stats_row(row, cols)

        assert "price" in result
        p = result["price"]
        assert p["row_count"] == 100
        assert p["null_count"] == 5
        assert p["null_rate"] == 0.05
        assert p["distinct_count"] == 50
        assert p["is_unique"] is False
        assert p["min"] == 1.5
        assert p["max"] == 99.99
        assert p["mean"] == 45.0
        assert p["median"] == 42.0
        assert p["stddev"] == 20.0

    def test_parse_string_column(self) -> None:
        row = {
            "_row_count": 50,
            "name__non_null_count": 50,
            "name__distinct_count": 50,
            "name__min_length": 2,
            "name__max_length": 30,
            "name__avg_length": 12.5,
        }
        cols = [ColumnSpec("name", "VARCHAR", "string")]
        result = parse_stats_row(row, cols)

        p = result["name"]
        assert p["is_unique"] is True
        assert p["min_length"] == 2
        assert p["max_length"] == 30
        assert p["avg_length"] == 12.5

    def test_parse_top_values(self) -> None:
        rows = [
            {"value": "active", "frequency": 80},
            {"value": "inactive", "frequency": 20},
        ]
        result = parse_top_values_rows(rows)
        assert len(result) == 2
        assert result[0]["value"] == "active"
        assert result[0]["frequency"] == 80

    def test_zero_rows(self) -> None:
        row = {
            "_row_count": 0,
            "id__non_null_count": 0,
            "id__distinct_count": 0,
        }
        cols = [ColumnSpec("id", "INTEGER", "numeric")]
        result = parse_stats_row(row, cols)
        assert result["id"]["null_rate"] == 0.0
        assert result["id"]["is_unique"] is False


class TestCache:
    def test_save_and_load(self, tmp_path: Path) -> None:
        cache = {"model1": {"schema_hash": "abc123", "profiles": {"col1": {"null_rate": 0.1}}}}
        save_cache(tmp_path, cache)
        loaded = load_cache(tmp_path)
        assert loaded == cache

    def test_load_missing(self, tmp_path: Path) -> None:
        loaded = load_cache(tmp_path)
        assert loaded == {}

    def test_is_cached(self) -> None:
        columns = [{"name": "id", "data_type": "INTEGER"}]
        cache: dict[str, Any] = {}
        cache = update_cache(cache, "m1", columns, 100, {"id": {"null_rate": 0.0}})

        assert is_cached(cache, "m1", columns, 100)
        assert not is_cached(cache, "m1", columns, 200)  # different row count
        assert not is_cached(cache, "m2", columns, 100)  # different model

    def test_update_is_immutable(self) -> None:
        cache: dict[str, Any] = {"existing": {"schema_hash": "x"}}
        new_cache = update_cache(cache, "new_model", [], None, {})
        assert "existing" in new_cache
        assert "new_model" in new_cache
        assert "new_model" not in cache  # original unchanged


class TestBuildColumnSpecs:
    def test_from_column_dicts(self) -> None:
        columns = [
            {"name": "id", "data_type": "INTEGER"},
            {"name": "name", "data_type": "VARCHAR"},
            {"name": "created", "data_type": "TIMESTAMP"},
        ]
        specs = build_column_specs(columns)
        assert len(specs) == 3
        assert specs[0].category == "numeric"
        assert specs[1].category == "string"
        assert specs[2].category == "date"
