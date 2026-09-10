"""Tests for the column lineage SQL parser."""

from __future__ import annotations

from typing import Any

import pytest
from sqlglot.schema import MappingSchema

from docglow.lineage.column_parser import (
    ColumnDependency,
    _extract_output_columns,
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
        assert detect_dialect("athena") == "presto"
        assert detect_dialect("sqlserver") == "tsql"
        assert detect_dialect("fabric") == "tsql"
        assert detect_dialect("oracle") == "oracle"
        assert detect_dialect("starburst") == "trino"

    def test_case_insensitive(self) -> None:
        assert detect_dialect("Snowflake") == "snowflake"
        assert detect_dialect("BIGQUERY") == "bigquery"

    def test_unknown_adapter(self) -> None:
        assert detect_dialect("unknown_db") is None

    def test_none_adapter(self) -> None:
        assert detect_dialect(None) is None


class TestParseColumnLineage:
    """Tests for SQL parsing and column dependency extraction."""

    def test_simple_select_passthrough_columns(self) -> None:
        """Simple column references are classified as 'passthrough'."""
        sql = "SELECT id, name FROM users"
        result = parse_column_lineage(sql)
        assert "id" in result
        assert "name" in result
        assert any(d.source_column == "id" for d in result["id"])
        assert any(d.source_column == "name" for d in result["name"])
        # Phase 1: simple column refs are passthrough, not direct
        assert all(d.transformation == "passthrough" for d in result["id"])
        assert all(d.transformation == "passthrough" for d in result["name"])

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
        assert all(d.transformation == "derived" for d in deps)

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

    def test_select_star_from_cte_with_no_schema_or_known_columns(self) -> None:
        """SELECT * FROM cte resolves from the CTE's own definition alone.

        No external schema and no catalog known_columns are provided —
        qualify()'s infer_schema resolves the star structurally from the
        CTE body itself.
        """
        sql = """
        WITH renamed AS (
            SELECT id AS user_id, name FROM raw_users
        )
        SELECT * FROM renamed
        """
        result = parse_column_lineage(sql)
        assert "user_id" in result
        assert "name" in result
        assert any(
            d.source_table == "raw_users" and d.source_column == "id" for d in result["user_id"]
        )

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

    def test_expression_alongside_star_preserves_lineage(self) -> None:
        """Explicit expressions must survive expansion of a neighboring star."""
        sql = """
        WITH renamed AS (
            SELECT company, part_num
            FROM epicor_part
        )
        SELECT
            MD5(company || part_num) AS sk_with_star,
            *
        FROM renamed
        """
        result = parse_column_lineage(
            sql,
            known_columns=["sk_with_star", "company", "part_num"],
            dialect="trino",
        )

        assert "sk_with_star" in result
        assert {
            (dep.source_table, dep.source_column, dep.transformation)
            for dep in result["sk_with_star"]
        } == {
            ("epicor_part", "company", "derived"),
            ("epicor_part", "part_num", "derived"),
        }
        assert "company" in result
        assert "part_num" in result

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

    def test_unknown_transformation_for_unparseable(self) -> None:
        """When the expression is None (unparseable), classify as 'unknown'."""
        # COUNT(*) produces no column-level dependencies but the parser may
        # encounter None expressions in edge cases.  We test via the internal
        # helper directly.
        from docglow.lineage.column_parser import _classify_transformation

        assert _classify_transformation(None) == "unknown"

    def test_passthrough_simple_column(self) -> None:
        """A bare exp.Column reference is 'passthrough'."""
        from sqlglot import exp

        from docglow.lineage.column_parser import _classify_transformation

        col = exp.Column(this=exp.to_identifier("id"))
        assert _classify_transformation(col) == "passthrough"

    def test_passthrough_aliased_column(self) -> None:
        """An aliased column (SELECT a AS b) is still 'passthrough'."""
        from sqlglot import exp

        from docglow.lineage.column_parser import _classify_transformation

        alias = exp.Alias(
            this=exp.Column(this=exp.to_identifier("a")),
            alias=exp.to_identifier("b"),
        )
        assert _classify_transformation(alias) == "passthrough"

    def test_aggregation_still_aggregated(self) -> None:
        """Aggregate functions remain 'aggregated'."""
        from sqlglot import exp

        from docglow.lineage.column_parser import _classify_transformation

        agg = exp.Sum(this=exp.Column(this=exp.to_identifier("amount")))
        assert _classify_transformation(agg) == "aggregated"

    def test_window_function_derived(self) -> None:
        """Window functions should be classified as 'derived'."""
        sql = "SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn FROM users"
        result = parse_column_lineage(sql)
        if "rn" in result:
            assert all(d.transformation == "derived" for d in result["rn"])

    def test_case_expression_still_derived(self) -> None:
        """CASE expressions remain 'derived'."""
        sql = """
        SELECT
            CASE WHEN status = 'active' THEN 1 ELSE 0 END AS is_active
        FROM users
        """
        result = parse_column_lineage(sql)
        assert "is_active" in result
        assert all(d.transformation == "derived" for d in result["is_active"])

    def test_direct_no_longer_appears_in_output(self) -> None:
        """'direct' should never appear in new lineage output."""
        sql = (
            "SELECT id, name, CONCAT(a, b) AS full, SUM(x) AS total FROM t GROUP BY id, name, full"
        )
        result = parse_column_lineage(sql)
        for deps in result.values():
            for dep in deps:
                assert dep.transformation != "direct", f"'direct' found in output for {dep}"

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
                "database": "jaffle_shop",
                "columns": [
                    {"name": "id", "data_type": "INT"},
                    {"name": "name", "data_type": "VARCHAR"},
                ],
            }
        }
        sources: dict[str, dict[str, object]] = {}
        schema = build_schema_mapping(models, sources)
        assert "jaffle_shop" in schema
        assert schema["jaffle_shop"]["public"]["users"]["id"] == "INT"
        assert schema["jaffle_shop"]["public"]["users"]["name"] == "VARCHAR"

    def test_empty_data_type_defaults_to_varchar(self) -> None:
        models = {
            "model.proj.t": {
                "name": "t",
                "schema": "s",
                "database": "db",
                "columns": [{"name": "col", "data_type": ""}],
            }
        }
        schema = build_schema_mapping(models, {})
        assert schema["db"]["s"]["t"]["col"] == "VARCHAR"

    def test_sources_included(self) -> None:
        sources = {
            "source.proj.raw.events": {
                "name": "events",
                "schema": "raw",
                "database": "jaffle_shop",
                "columns": [{"name": "event_id", "data_type": "BIGINT"}],
            }
        }
        schema = build_schema_mapping({}, sources)
        assert "events" in schema["jaffle_shop"]["raw"]

    def test_bare_name_indexed(self) -> None:
        """Models with full database/schema/table info nest to depth 3.

        Bare-name indexing (for Jinja-stripped SQL) is no longer
        build_schema_mapping's job — that's TableResolver's `_short` index
        (see tests/lineage/test_table_resolver.py). This mapping exists
        solely to drive SQLGlot's qualify()/star-expansion, so it only ever
        holds fully qualified database.schema.table paths.
        """
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "database": "jaffle_shop",
                "columns": [{"name": "id", "data_type": "INT"}],
            }
        }
        schema = build_schema_mapping(models, {})
        assert schema["jaffle_shop"]["public"]["users"]["id"] == "INT"

    def test_source_name_indexed(self) -> None:
        """Sources nest under database.schema.table like models do.

        source_name.table_name indexing (for resolving `source()` refs) is
        TableResolver's job, not build_schema_mapping's — see
        tests/lineage/test_table_resolver.py.
        """
        sources = {
            "source.proj.ecom.orders": {
                "name": "orders",
                "schema": "raw",
                "database": "ecom_db",
                "source_name": "ecom",
                "columns": [{"name": "id", "data_type": "INT"}],
            }
        }
        schema = build_schema_mapping({}, sources)
        assert schema["ecom_db"]["raw"]["orders"]["id"] == "INT"

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

    def test_nested_database_schema_table_column_shape(self) -> None:
        """Schema mapping should be subscriptable as a depth-3 nested dict.

        {database: {schema: {table: {column: type}}}} lets SQLGlot's
        qualify() expand qualified stars (e.g. renamed.*, a.* / b.*).
        """
        models = {
            "model.proj.orders": {
                "name": "orders",
                "schema": "main",
                "database": "jaffle_shop",
                "columns": [{"name": "order_id", "data_type": "INT"}],
            }
        }
        schema = build_schema_mapping(models, {})
        assert schema["jaffle_shop"]["main"]["orders"]["order_id"] == "INT"
        assert MappingSchema(schema).depth() == 3

    def test_node_missing_database_is_omitted(self) -> None:
        """A node missing `database` must be dropped, not inserted at a shorter depth."""
        models = {
            "model.proj.orders": {
                "name": "orders",
                "schema": "main",
                "database": "",
                "columns": [{"name": "order_id", "data_type": "INT"}],
            },
            "model.proj.customers": {
                "name": "customers",
                "schema": "main",
                "database": "jaffle_shop",
                "columns": [{"name": "customer_id", "data_type": "INT"}],
            },
        }
        schema = build_schema_mapping(models, {})
        assert "" not in schema
        assert schema["jaffle_shop"]["main"]["customers"]["customer_id"] == "INT"

    def test_node_missing_schema_is_omitted(self) -> None:
        """A node missing `schema` must be dropped, not inserted at a shorter depth."""
        models = {
            "model.proj.orders": {
                "name": "orders",
                "schema": "",
                "database": "jaffle_shop",
                "columns": [{"name": "order_id", "data_type": "INT"}],
            },
            "model.proj.customers": {
                "name": "customers",
                "schema": "main",
                "database": "jaffle_shop",
                "columns": [{"name": "customer_id", "data_type": "INT"}],
            },
        }
        schema = build_schema_mapping(models, {})
        assert "" not in schema["jaffle_shop"]
        assert schema["jaffle_shop"]["main"]["customers"]["customer_id"] == "INT"

    def test_omitted_node_does_not_break_mapping_schema(self) -> None:
        """A malformed node must not make MappingSchema raise SchemaError."""
        models = {
            "model.proj.orders": {
                "name": "orders",
                "schema": "main",
                "database": "",
                "columns": [{"name": "order_id", "data_type": "INT"}],
            },
            "model.proj.customers": {
                "name": "customers",
                "schema": "main",
                "database": "jaffle_shop",
                "columns": [{"name": "customer_id", "data_type": "INT"}],
            },
        }
        schema = build_schema_mapping(models, {})
        MappingSchema(schema)

    def test_same_named_tables_in_different_schemas_coexist(self) -> None:
        """Two tables named `orders` in different schemas must not collide."""
        models = {
            "model.proj.staging_orders": {
                "name": "orders",
                "schema": "staging",
                "database": "jaffle_shop",
                "columns": [{"name": "raw_order_id", "data_type": "INT"}],
            },
            "model.proj.marts_orders": {
                "name": "orders",
                "schema": "marts",
                "database": "jaffle_shop",
                "columns": [{"name": "order_id", "data_type": "BIGINT"}],
            },
        }
        schema = build_schema_mapping(models, {})

        staging_orders = schema["jaffle_shop"]["staging"]["orders"]
        marts_orders = schema["jaffle_shop"]["marts"]["orders"]

        assert staging_orders == {"raw_order_id": "INT"}
        assert marts_orders == {"order_id": "BIGINT"}
        assert staging_orders != marts_orders


class TestQualifiedStarGuard:
    """A qualified star (e.g. renamed.*) must never surface as a literal '*'."""

    def test_unresolvable_qualified_star_has_no_star_key(self) -> None:
        result = parse_column_lineage("SELECT renamed.* FROM renamed", schema={})
        assert "*" not in result

    def test_extract_output_columns_skips_qualified_stars(self) -> None:
        import sqlglot

        select = sqlglot.parse_one("SELECT a.*, b.* FROM tbl_a a JOIN tbl_b b ON a.id = b.id")
        assert _extract_output_columns(select) == []

    def test_qualified_star_expands_via_nested_schema(self) -> None:
        """A qualified star (renamed.*) expands to real columns via qualify()."""
        sql = """
        WITH renamed AS (SELECT id, company FROM raw.src)
        SELECT md5(company) AS sk, renamed.* FROM renamed
        """
        schema = {"raw": {"public": {"src": {"id": "INT", "company": "VARCHAR"}}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"sk", "id", "company"}

        assert {(d.source_table, d.source_column) for d in result["id"]} == {("raw.src", "id")}
        assert {(d.source_table, d.source_column) for d in result["company"]} == {
            ("raw.src", "company")
        }
        assert {(d.source_table, d.source_column, d.transformation) for d in result["sk"]} == {
            ("raw.src", "company", "derived")
        }

    def test_qualified_star_against_plain_table(self) -> None:
        """A qualified star (a.*) against a plain (non-CTE) table expands fully."""
        sql = "SELECT a.* FROM raw.public.a AS a"
        schema = {"raw": {"public": {"a": {"id": "INT", "name": "VARCHAR"}}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "name"}
        assert {(d.source_table, d.source_column) for d in result["id"]} == {("raw.public.a", "id")}
        assert {(d.source_table, d.source_column) for d in result["name"]} == {
            ("raw.public.a", "name")
        }

    def test_qualified_star_falls_back_to_known_columns(self) -> None:
        """When the star's source table isn't in the schema mapping, fall back
        to the known_columns parameter (e.g. from the catalog) instead of
        silently dropping the star."""
        sql = "SELECT a.* FROM raw.a AS a"
        schema = {"other": {"public": {"z": {"x": "INT"}}}}

        result = parse_column_lineage(sql, schema=schema, known_columns=["id", "name"])

        assert set(result.keys()) == {"id", "name"}

    def test_qualified_star_against_zero_column_source(self) -> None:
        """A qualified star against a source with zero columns yields no '*' key
        and does not raise."""
        sql = "SELECT a.* FROM raw.public.a AS a"
        schema = {"raw": {"public": {"a": {}}}}

        result = parse_column_lineage(sql, schema=schema)

        assert "*" not in result

    def test_multi_star_two_way_join_resolves_each_source(self) -> None:
        """SELECT a.*, b.* FROM a JOIN b resolves both stars independently —
        never collapses to {} even though each source contributes a star."""
        sql = """
        SELECT a.*, b.*
        FROM raw.public.a AS a
        JOIN raw.public.b AS b ON a.id = b.id
        """
        schema = {
            "raw": {
                "public": {
                    "a": {"id": "INT", "x": "VARCHAR"},
                    "b": {"id": "INT", "y": "VARCHAR"},
                }
            }
        }

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "x", "y"}
        assert {(d.source_table, d.source_column) for d in result["x"]} == {("raw.public.a", "x")}
        assert {(d.source_table, d.source_column) for d in result["y"]} == {("raw.public.b", "y")}

    def test_duplicate_star_column_collapses_to_first_source(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When both sides of a join contribute a column with the same name
        (e.g. both have `id`), the output collapses to a single `id` key
        resolving to the first-seen source, and a DEBUG log names it."""
        sql = """
        SELECT a.*, b.*
        FROM raw.public.a AS a
        JOIN raw.public.b AS b ON a.id = b.id
        """
        schema = {
            "raw": {
                "public": {
                    "a": {"id": "INT", "x": "VARCHAR"},
                    "b": {"id": "INT", "y": "VARCHAR"},
                }
            }
        }

        with caplog.at_level("DEBUG", logger="docglow.lineage.column_parser"):
            result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "x", "y"}
        assert {(d.source_table, d.source_column) for d in result["id"]} == {("raw.public.a", "id")}

        debug_messages = [r.message for r in caplog.records if r.levelname == "DEBUG"]
        assert any("id" in message for message in debug_messages)

    def test_multi_star_three_way_join_resolves_each_source(self) -> None:
        """A three-way join with a star per side reports columns from all
        three sources."""
        sql = """
        SELECT a.*, b.*, c.*
        FROM raw.public.a AS a
        JOIN raw.public.b AS b ON a.id = b.id
        JOIN raw.public.c AS c ON a.id = c.id
        """
        schema = {
            "raw": {
                "public": {
                    "a": {"id": "INT", "x": "VARCHAR"},
                    "b": {"id": "INT", "y": "VARCHAR"},
                    "c": {"id": "INT", "z": "VARCHAR"},
                }
            }
        }

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "x", "y", "z"}
        assert {(d.source_table, d.source_column) for d in result["x"]} == {("raw.public.a", "x")}
        assert {(d.source_table, d.source_column) for d in result["y"]} == {("raw.public.b", "y")}
        assert {(d.source_table, d.source_column) for d in result["z"]} == {("raw.public.c", "z")}

    def test_half_resolvable_join_reports_resolvable_side(self) -> None:
        """When one side of a join is in schema and the other side's table is
        absent from both schema and known_columns, the resolvable side's
        columns are still reported and no exception is raised."""
        sql = """
        SELECT a.*, b.*
        FROM raw.a AS a
        JOIN missing.b AS b ON a.id = b.id
        """
        schema = {"raw": {"a": {"id": "INT", "x": "VARCHAR"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "x"}
        assert {(d.source_table, d.source_column) for d in result["id"]} == {("raw.a", "id")}
        assert {(d.source_table, d.source_column) for d in result["x"]} == {("raw.a", "x")}

    def test_fully_unresolvable_join_returns_empty_dict(self) -> None:
        """When neither side of a join can be resolved (both tables absent
        from schema, no known_columns), the result is {} with no '*' key and
        no exception is raised."""
        sql = """
        SELECT a.*, b.*
        FROM missing.a AS a
        JOIN missing.b AS b ON a.id = b.id
        """
        schema = {"raw": {"other": {"id": "INT"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert result == {}
        assert "*" not in result

    def test_qualified_star_exclude_drops_excluded_column(self) -> None:
        """`a.* EXCLUDE (x)` on the resolvable side of a half-resolvable join
        must drop `x`, not just the columns qualify() itself expands."""
        sql = """
        SELECT a.* EXCLUDE (x), b.*
        FROM raw.a AS a
        JOIN missing.b AS b ON a.id = b.id
        """
        schema = {"raw": {"a": {"id": "INT", "x": "VARCHAR"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id"}
        assert "x" not in result

    def test_bare_star_exclude_still_drops_excluded_column(self) -> None:
        """Regression: bare `SELECT * EXCLUDE (x)` behaviour is unchanged."""
        sql = "SELECT * EXCLUDE (x) FROM raw.a"
        schema = {"raw": {"a": {"id": "INT", "x": "INT"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id"}
        assert "x" not in result

    def test_exclude_nonexistent_column_returns_all_real_columns(self) -> None:
        """Excluding a column name that isn't actually a column is a no-op."""
        sql = """
        SELECT a.* EXCLUDE (nonexistent), b.*
        FROM raw.a AS a
        JOIN missing.b AS b ON a.id = b.id
        """
        schema = {"raw": {"a": {"id": "INT", "x": "VARCHAR"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert set(result.keys()) == {"id", "x"}

    def test_exclude_every_column_yields_empty_result_with_no_star_key(self) -> None:
        """Excluding every column of the only resolvable source leaves nothing
        to report — and must never surface a literal '*' key."""
        sql = """
        SELECT a.* EXCLUDE (id, x), b.*
        FROM raw.a AS a
        JOIN missing.b AS b ON a.id = b.id
        """
        schema = {"raw": {"a": {"id": "INT", "x": "VARCHAR"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert result == {}
        assert "*" not in result

    def test_unparseable_exclude_sql_returns_empty_dict_without_raising(self) -> None:
        """SQL SQLGlot can't parse at all (EXCLUDE or otherwise) falls back to
        the existing unparseable-SQL path — {} without raising."""
        sql = "SELECT ((( FROM"
        schema = {"raw": {"a": {"id": "INT"}}}

        result = parse_column_lineage(sql, schema=schema)

        assert result == {}

    def test_column_trace_timeout_omits_only_that_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A per-column trace that exceeds the timeout is omitted from the
        result while other columns that trace successfully are still
        returned."""
        import time

        from docglow.lineage import column_parser

        # Shrink the timeout so the test doesn't need to sleep for seconds.
        monkeypatch.setattr(column_parser._trace_column_in_executor, "__defaults__", (0.1,))

        from sqlglot.lineage import lineage as real_lineage

        def fake_lineage(column: str, sql: str, schema: Any, dialect: str | None) -> Any:
            if column == "slow":
                time.sleep(0.3)
            return real_lineage(column=column, sql=sql, schema=schema, dialect=dialect)

        monkeypatch.setattr("sqlglot.lineage.lineage", fake_lineage)

        sql = "SELECT id, slow FROM users"
        result = parse_column_lineage(sql)

        assert "id" in result
        assert "slow" not in result

    def test_unparseable_sql_returns_empty_dict(self) -> None:
        """SQL that SQLGlot cannot parse at all returns {} without raising,
        before qualify() is ever reached."""
        result = parse_column_lineage(
            "SELECT FROM FROM WHERE (((", schema={"a": {"b": {"c": {"d": "INT"}}}}
        )

        assert result == {}
