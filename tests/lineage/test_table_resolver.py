"""Tests for the table name resolver."""

from __future__ import annotations

from unittest.mock import MagicMock

from docglow.lineage.table_resolver import TableResolver


def _make_manifest_node(relation_name: str | None) -> MagicMock:
    """Create a mock manifest node with a relation_name."""
    node = MagicMock()
    node.relation_name = relation_name
    return node


class TestTableResolver:
    """Tests for resolving SQL table references to dbt unique_ids."""

    def test_resolve_from_data_schema_name(self) -> None:
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "database": "mydb",
            }
        }
        resolver = TableResolver(models=models, sources={})
        assert resolver.resolve("public.users") == "model.proj.users"

    def test_resolve_fully_qualified(self) -> None:
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "database": "mydb",
            }
        }
        resolver = TableResolver(models=models, sources={})
        assert resolver.resolve("mydb.public.users") == "model.proj.users"

    def test_resolve_case_insensitive(self) -> None:
        """Snowflake uppercases identifiers — matching should be case-insensitive."""
        models = {
            "model.proj.users": {
                "name": "users",
                "schema": "public",
                "database": "mydb",
            }
        }
        resolver = TableResolver(models=models, sources={})
        assert resolver.resolve("PUBLIC.USERS") == "model.proj.users"
        assert resolver.resolve("MYDB.PUBLIC.USERS") == "model.proj.users"

    def test_resolve_from_manifest_relation_name(self) -> None:
        models: dict[str, dict[str, object]] = {
            "model.proj.orders": {"name": "orders", "schema": "analytics", "database": "prod"}
        }
        manifest_nodes = {"model.proj.orders": _make_manifest_node('"prod"."analytics"."orders"')}
        resolver = TableResolver(
            models=models,
            sources={},
            manifest_nodes=manifest_nodes,
        )
        # Should match after stripping quotes
        assert resolver.resolve("prod.analytics.orders") == "model.proj.orders"

    def test_resolve_source(self) -> None:
        sources = {
            "source.proj.raw.events": {
                "name": "events",
                "schema": "raw",
                "database": "warehouse",
            }
        }
        resolver = TableResolver(models={}, sources=sources)
        assert resolver.resolve("raw.events") == "source.proj.raw.events"

    def test_resolve_with_backticks(self) -> None:
        """BigQuery uses backtick quoting."""
        manifest_nodes = {"model.proj.users": _make_manifest_node("`project.dataset.users`")}
        resolver = TableResolver(
            models={
                "model.proj.users": {
                    "name": "users",
                    "schema": "dataset",
                    "database": "project",
                }
            },
            sources={},
            manifest_nodes=manifest_nodes,
        )
        assert resolver.resolve("project.dataset.users") == "model.proj.users"

    def test_resolve_unresolvable_returns_none(self) -> None:
        resolver = TableResolver(models={}, sources={})
        assert resolver.resolve("nonexistent.table") is None

    def test_resolve_seeds(self) -> None:
        seeds = {
            "seed.proj.countries": {
                "name": "countries",
                "schema": "public",
                "database": "mydb",
            }
        }
        resolver = TableResolver(models={}, sources={}, seeds=seeds)
        assert resolver.resolve("public.countries") == "seed.proj.countries"

    def test_resolve_snapshots(self) -> None:
        snapshots = {
            "snapshot.proj.orders_snapshot": {
                "name": "orders_snapshot",
                "schema": "snapshots",
                "database": "mydb",
            }
        }
        resolver = TableResolver(models={}, sources={}, snapshots=snapshots)
        assert resolver.resolve("snapshots.orders_snapshot") == "snapshot.proj.orders_snapshot"

    def test_resolve_prefers_exact_match(self) -> None:
        """When multiple matches exist, exact match should win."""
        manifest_nodes = {"model.proj.users": _make_manifest_node("analytics.users")}
        models = {"model.proj.users": {"name": "users", "schema": "analytics", "database": ""}}
        resolver = TableResolver(
            models=models,
            sources={},
            manifest_nodes=manifest_nodes,
        )
        assert resolver.resolve("analytics.users") == "model.proj.users"

    def test_short_reference_from_long(self) -> None:
        """Given 'db.schema.table', should try 'schema.table' as fallback."""
        models = {
            "model.proj.orders": {
                "name": "orders",
                "schema": "public",
                "database": "",
            }
        }
        resolver = TableResolver(models=models, sources={})
        # Full reference with unknown db should fall back to schema.name
        assert resolver.resolve("unknown_db.public.orders") == "model.proj.orders"
