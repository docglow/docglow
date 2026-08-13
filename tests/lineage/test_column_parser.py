"""Tests for the column lineage SQL parser."""

from __future__ import annotations

import pytest

from docglow.lineage.column_parser import (
    ColumnDependency,
    _table_to_string,
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
        assert detect_dialect("fabricspark") == "spark"
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

    def test_qualified_star_with_known_columns(self) -> None:
        sql = "SELECT base.* FROM base"
        result = parse_column_lineage(sql, known_columns=["id", "name"])
        assert set(result.keys()) == {"id", "name"}
        assert "*" not in result

    def test_qualified_star_with_expression_preserves_outputs(self) -> None:
        sql = """
        WITH base AS (
            SELECT source_id AS id, source_date AS adjustment_date
            FROM source_table
        )
        SELECT base.*, current_timestamp() AS updated_at
        FROM base
        """
        result = parse_column_lineage(
            sql,
            known_columns=["id", "adjustment_date", "updated_at"],
            dialect="spark",
        )
        assert "id" in result
        assert "adjustment_date" in result
        assert "*" not in result
        assert all(key != "*" for key in result)

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


class TestTableToString:
    @pytest.mark.parametrize(
        ("adapter_type", "sql", "expected"),
        [
            ("fabricspark", "SELECT * FROM schema_name.table_name", "schema_name.table_name"),
            (
                "fabricspark",
                "SELECT * FROM lakehouse_name.schema_name.table_name",
                "lakehouse_name.schema_name.table_name",
            ),
            (
                "fabricspark",
                "SELECT * FROM `workspace_name`.`lakehouse_name`.`schema_name`.`table_name`",
                "workspace_name.lakehouse_name.schema_name.table_name",
            ),
            ("fabric", "SELECT * FROM schema_name.table_name", "schema_name.table_name"),
            (
                "fabric",
                "SELECT * FROM warehouse_name.schema_name.table_name",
                "warehouse_name.schema_name.table_name",
            ),
            (
                "fabric",
                "SELECT * FROM [server_name].[warehouse_name].[dbo].[orders]",
                "server_name.warehouse_name.dbo.orders",
            ),
        ],
    )
    def test_preserves_full_relation_parts_for_fabric_adapters(
        self,
        adapter_type: str,
        sql: str,
        expected: str,
    ) -> None:
        import sqlglot
        from sqlglot import exp

        dialect = detect_dialect(adapter_type)
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        table = parsed.find(exp.Table)

        assert table is not None
        assert _table_to_string(table, adapter_type=adapter_type) == expected

    @pytest.mark.parametrize(
        ("adapter_type", "dialect", "sql", "expected"),
        [
            (
                "spark",
                "spark",
                "SELECT * FROM catalog_name.schema_name.table_name",
                "catalog_name.schema_name.table_name",
            ),
            (
                "databricks",
                "databricks",
                "SELECT * FROM catalog_name.schema_name.table_name",
                "catalog_name.schema_name.table_name",
            ),
            (
                "snowflake",
                "snowflake",
                "SELECT * FROM database_name.schema_name.table_name",
                "database_name.schema_name.table_name",
            ),
            (
                "bigquery",
                "bigquery",
                "SELECT * FROM `project_name.dataset_name.table_name`",
                "project_name.dataset_name.table_name",
            ),
            (
                "postgres",
                "postgres",
                "SELECT * FROM schema_name.table_name",
                "schema_name.table_name",
            ),
            (
                "sqlserver",
                "tsql",
                "SELECT * FROM [server_name].[database_name].[dbo].[orders]",
                "server_name.database_name.orders",
            ),
        ],
    )
    def test_non_fabric_adapters_keep_existing_relation_conversion(
        self,
        adapter_type: str,
        dialect: str,
        sql: str,
        expected: str,
    ) -> None:
        import sqlglot
        from sqlglot import exp

        parsed = sqlglot.parse_one(sql, dialect=dialect)
        table = parsed.find(exp.Table)

        assert table is not None
        assert _table_to_string(table, adapter_type=adapter_type) == expected


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
