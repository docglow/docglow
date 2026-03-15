"""Tests for the column lineage SQL parser."""

from __future__ import annotations

import pytest

from docglow.lineage.column_parser import (
    ColumnDependency,
    build_schema_mapping,
    detect_dialect,
    parse_column_lineage,
)


class TestDetectDialect:
    """Tests for adapter_type -> dialect mapping."""

    def test_known_adapters(self) -> None:
        assert detect_dialect("bigquery") == "bigquery"
        assert detect_dialect("snowflake") == "snowflake"
        assert detect_dialect("postgres") == "postgres"
        assert detect_dialect("postgresql") == "postgres"
        assert detect_dialect("redshift") == "redshift"
        assert detect_dialect("duckdb") == "duckdb"
        assert detect_dialect("databricks") == "databricks"

    def test_case_insensitive(self) -> None:
        assert detect_dialect("Snowflake") == "snowflake"
        assert detect_dialect("BIGQUERY") == "bigquery"

    def test_unknown_adapter(self) -> None:
        assert detect_dialect("unknown_db") is None

    def test_none_adapter(self) -> None:
        assert detect_dialect(None) is None


class TestParseColumnLineage:
    """Tests for SQL parsing and column dependency extraction."""

    def test_simple_select_direct_columns(self) -> None:
        sql = "SELECT id, name FROM users"
        result = parse_column_lineage(sql)
        assert "id" in result
        assert "name" in result
        assert any(d.source_column == "id" for d in result["id"])
        assert any(d.source_column == "name" for d in result["name"])

    def test_aliased_column(self) -> None:
        sql = "SELECT id AS user_id FROM users"
        result = parse_column_lineage(sql)
        assert "user_id" in result
        deps = result["user_id"]
        assert any(d.source_column == "id" for d in deps)

    def test_expression_derived(self) -> None:
        sql = "SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM users"
        result = parse_column_lineage(sql)
        assert "full_name" in result
        deps = result["full_name"]
        assert all(d.transformation == "derived" for d in deps)

    def test_aggregation(self) -> None:
        sql = "SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id"
        result = parse_column_lineage(sql)
        assert "total" in result
        total_deps = result["total"]
        assert any(
            d.source_column == "amount" and d.transformation == "aggregated" for d in total_deps
        )

    def test_count_aggregation(self) -> None:
        sql = "SELECT customer_id, COUNT(*) AS order_count FROM orders GROUP BY customer_id"
        result = parse_column_lineage(sql)
        assert "customer_id" in result

    def test_join_columns_from_multiple_tables(self) -> None:
        sql = """
        SELECT o.id, o.amount, c.name AS customer_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        """
        result = parse_column_lineage(sql)
        assert "id" in result
        assert "customer_name" in result
        customer_deps = result["customer_name"]
        assert any(d.source_column == "name" for d in customer_deps)

    def test_cte_passthrough(self) -> None:
        sql = """
        WITH staged AS (
            SELECT id, name FROM raw_users
        )
        SELECT id, name FROM staged
        """
        result = parse_column_lineage(sql)
        assert "id" in result
        assert "name" in result
        # Should trace through the CTE to the base table
        id_deps = result["id"]
        assert any(d.source_table == "raw_users" for d in id_deps)

    def test_case_expression_derived(self) -> None:
        sql = """
        SELECT
            id,
            CASE WHEN status = 'active' THEN 1 ELSE 0 END AS is_active
        FROM users
        """
        result = parse_column_lineage(sql)
        assert "is_active" in result
        deps = result["is_active"]
        assert any(d.transformation == "derived" for d in deps)

    def test_empty_sql_returns_empty(self) -> None:
        assert parse_column_lineage("") == {}
        assert parse_column_lineage("   ") == {}

    def test_invalid_sql_returns_empty(self) -> None:
        result = parse_column_lineage("THIS IS NOT SQL AT ALL ;;; {{{")
        # Should not raise, just return empty or partial results
        assert isinstance(result, dict)

    def test_dialect_snowflake(self) -> None:
        sql = "SELECT id, name FROM my_schema.users"
        result = parse_column_lineage(sql, dialect="snowflake")
        assert "id" in result

    def test_dialect_bigquery(self) -> None:
        sql = "SELECT id, name FROM `project.dataset.users`"
        result = parse_column_lineage(sql, dialect="bigquery")
        assert "id" in result

    def test_with_schema_for_star_expansion(self) -> None:
        schema = {"users": {"id": "INT", "name": "VARCHAR", "email": "VARCHAR"}}
        sql = "SELECT * FROM users"
        result = parse_column_lineage(sql, schema=schema)
        # With schema provided, * should be expanded
        # At minimum we should get no errors
        assert isinstance(result, dict)

    def test_subquery(self) -> None:
        sql = """
        SELECT sub.id, sub.total
        FROM (
            SELECT id, SUM(amount) AS total
            FROM orders
            GROUP BY id
        ) sub
        """
        result = parse_column_lineage(sql)
        assert "id" in result

    def test_select_star_from_cte_with_known_columns(self) -> None:
        """SELECT * FROM cte should be rewritten using known_columns."""
        sql = """
        WITH renamed AS (
            SELECT id AS user_id, name FROM raw_users
        )
        SELECT * FROM renamed
        """
        result = parse_column_lineage(sql, known_columns=["user_id", "name"])
        assert "user_id" in result
        assert "name" in result
        assert any(
            d.source_table == "raw_users" and d.source_column == "id" for d in result["user_id"]
        )

    def test_select_star_with_schema_resolves_inner_ctes(self) -> None:
        """Schema mapping should help resolve SELECT * inside CTEs."""
        schema = {
            "base_table": {
                "id": "INT",
                "val": "VARCHAR",
            }
        }
        sql = """
        WITH src AS (
            SELECT * FROM base_table
        )
        SELECT id, val FROM src
        """
        result = parse_column_lineage(sql, schema=schema)
        assert "id" in result
        assert any(d.source_table == "base_table" for d in result["id"])

    def test_dependency_is_frozen_dataclass(self) -> None:
        sql = "SELECT id FROM users"
        result = parse_column_lineage(sql)
        if result:
            dep = result["id"][0]
            assert isinstance(dep, ColumnDependency)
            with pytest.raises(AttributeError):
                dep.source_column = "other"  # type: ignore[misc]


class TestBuildSchemaMapping:
    """Tests for building SQLGlot schema from docglow data."""

    def test_basic_schema_building(self) -> None:
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "columns": [
                    {"name": "id", "data_type": "INT"},
                    {"name": "name", "data_type": "VARCHAR"},
                ],
            }
        }
        sources: dict[str, dict[str, object]] = {}
        schema = build_schema_mapping(models, sources)
        assert "public.users" in schema
        assert schema["public.users"]["id"] == "INT"
        assert schema["public.users"]["name"] == "VARCHAR"

    def test_empty_data_type_defaults_to_varchar(self) -> None:
        models = {
            "model.proj.t": {
                "name": "t",
                "schema": "s",
                "columns": [{"name": "col", "data_type": ""}],
            }
        }
        schema = build_schema_mapping(models, {})
        assert schema["s.t"]["col"] == "VARCHAR"

    def test_sources_included(self) -> None:
        sources = {
            "source.proj.raw.events": {
                "name": "events",
                "schema": "raw",
                "columns": [{"name": "event_id", "data_type": "BIGINT"}],
            }
        }
        schema = build_schema_mapping({}, sources)
        assert "raw.events" in schema

    def test_bare_name_indexed(self) -> None:
        """Models should be indexed by bare name for Jinja-stripped SQL."""
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "columns": [{"name": "id", "data_type": "INT"}],
            }
        }
        schema = build_schema_mapping(models, {})
        assert "users" in schema
        assert schema["users"]["id"] == "INT"

    def test_source_name_indexed(self) -> None:
        """Sources should be indexed by source_name.table_name."""
        sources = {
            "source.proj.ecom.orders": {
                "name": "orders",
                "schema": "raw",
                "source_name": "ecom",
                "columns": [{"name": "id", "data_type": "INT"}],
            }
        }
        schema = build_schema_mapping({}, sources)
        assert "ecom.orders" in schema

    def test_no_columns_skipped(self) -> None:
        models = {
            "model.proj.empty": {
                "name": "empty",
                "schema": "public",
                "columns": [],
            }
        }
        schema = build_schema_mapping(models, {})
        assert "public.empty" not in schema
