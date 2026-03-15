"""Resolve SQLGlot table references to dbt unique_ids."""

from __future__ import annotations

from typing import Any


class TableResolver:
    """Maps SQL table references (e.g. 'analytics.stg_orders') to dbt unique_ids.

    Builds a lookup from the manifest's relation_name field and supports
    case-insensitive matching for adapters like Snowflake that uppercase identifiers.
    """

    def __init__(
        self,
        models: dict[str, dict[str, Any]],
        sources: dict[str, dict[str, Any]],
        seeds: dict[str, dict[str, Any]] | None = None,
        snapshots: dict[str, dict[str, Any]] | None = None,
        manifest_nodes: dict[str, Any] | None = None,
        manifest_sources: dict[str, Any] | None = None,
    ) -> None:
        self._exact: dict[str, str] = {}
        self._lower: dict[str, str] = {}
        self._short: dict[str, str] = {}  # schema.name -> unique_id

        self._index_from_manifest(manifest_nodes, manifest_sources)
        self._index_from_data(models, "model")
        self._index_from_data(sources, "source")
        if seeds:
            self._index_from_data(seeds, "seed")
        if snapshots:
            self._index_from_data(snapshots, "snapshot")

    def _index_from_manifest(
        self,
        nodes: dict[str, Any] | None,
        sources: dict[str, Any] | None,
    ) -> None:
        """Index relation_name from manifest nodes and sources."""
        if nodes:
            for uid, node in nodes.items():
                relation_name = getattr(node, "relation_name", None)
                if relation_name:
                    cleaned = _clean_relation_name(relation_name)
                    self._exact[cleaned] = uid
                    self._lower[cleaned.lower()] = uid

        if sources:
            for uid, source in sources.items():
                relation_name = getattr(source, "relation_name", None)
                if relation_name:
                    cleaned = _clean_relation_name(relation_name)
                    self._exact[cleaned] = uid
                    self._lower[cleaned.lower()] = uid

    def _index_from_data(
        self,
        data: dict[str, dict[str, Any]],
        resource_type: str,
    ) -> None:
        """Index from transformed docglow data dicts (schema + name)."""
        for uid, item in data.items():
            schema = item.get("schema", "")
            name = item.get("name", "")
            database = item.get("database", "")

            if schema and name:
                short_ref = f"{schema}.{name}"
                self._short[short_ref.lower()] = uid

                if database:
                    full_ref = f"{database}.{schema}.{name}"
                    self._lower[full_ref.lower()] = uid

            # For models/seeds/snapshots: index by bare name (for {{ ref('name') }})
            if resource_type in ("model", "seed", "snapshot") and name:
                self._short.setdefault(name.lower(), uid)

            # For sources: index by source_name.table_name (for {{ source('src', 'tbl') }})
            if resource_type == "source":
                source_name = item.get("source_name", "")
                if source_name and name:
                    src_ref = f"{source_name}.{name}"
                    self._short.setdefault(src_ref.lower(), uid)

    def resolve(self, table_reference: str) -> str | None:
        """Resolve a SQL table reference to a dbt unique_id.

        Tries exact match first, then case-insensitive, then schema.name shorthand.

        Args:
            table_reference: Table reference from SQLGlot (e.g. "db.schema.table"
                or "schema.table").

        Returns:
            The dbt unique_id if found, None otherwise.
        """
        cleaned = _clean_relation_name(table_reference)

        # Exact match
        if cleaned in self._exact:
            return self._exact[cleaned]

        # Case-insensitive match
        lower = cleaned.lower()
        if lower in self._lower:
            return self._lower[lower]

        # Short reference (schema.name)
        if lower in self._short:
            return self._short[lower]

        # Try just the last two parts (schema.name) from a fully qualified reference
        parts = lower.split(".")
        if len(parts) >= 2:
            short = f"{parts[-2]}.{parts[-1]}"
            if short in self._short:
                return self._short[short]

        return None


def _clean_relation_name(name: str) -> str:
    """Remove quoting characters from a relation name.

    dbt's relation_name often includes backticks, double quotes, or brackets
    depending on the adapter. Strip those for matching.
    """
    return name.replace('"', "").replace("`", "").replace("[", "").replace("]", "")
