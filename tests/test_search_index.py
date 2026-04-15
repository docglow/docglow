"""Unit tests for the search index builder."""

from __future__ import annotations

from docglow.generator.search_index import build_search_index


def _make_model(name: str, columns: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Description for {name}",
        "columns": columns or [],
        "tags": ["analytics"],
        "compiled_sql": "SELECT 1",
        "raw_sql": "SELECT 1",
    }


class TestBuildSearchIndex:
    def test_resource_entry_includes_expected_fields(self) -> None:
        models = {"model.proj.users": _make_model("users")}
        index = build_search_index(models, {}, {}, {})

        resource_entries = [e for e in index if e["resource_type"] != "column"]
        assert len(resource_entries) == 1
        entry = resource_entries[0]
        assert entry["id"] == "model.proj.users"
        assert entry["unique_id"] == "model.proj.users"
        assert entry["name"] == "users"
        assert entry["resource_type"] == "model"
        assert "column_name" not in entry
        assert "columns" not in entry
        assert "sql_snippet" not in entry

    def test_column_entries_emitted_per_column(self) -> None:
        models = {
            "model.proj.users": _make_model(
                "users",
                columns=[
                    {"name": "user_id", "description": "Primary key"},
                    {"name": "email", "description": "User email"},
                ],
            )
        }
        index = build_search_index(models, {}, {}, {})

        col_entries = [e for e in index if e["resource_type"] == "column"]
        assert len(col_entries) == 2

        names = {e["column_name"] for e in col_entries}
        assert names == {"user_id", "email"}

    def test_column_entry_fields(self) -> None:
        models = {
            "model.proj.orders": _make_model(
                "orders",
                columns=[{"name": "order_id", "description": "PK"}],
            )
        }
        index = build_search_index(models, {}, {}, {})

        col = next(e for e in index if e["resource_type"] == "column")
        assert col["id"] == "model.proj.orders::order_id"
        assert col["unique_id"] == "model.proj.orders"
        assert col["name"] == "order_id"
        assert col["column_name"] == "order_id"
        assert col["model_name"] == "orders"
        assert col["description"] == "PK"
        assert "columns" not in col
        assert "sql_snippet" not in col

    def test_column_entries_across_multiple_resource_types(self) -> None:
        models = {"model.proj.a": _make_model("a", [{"name": "col_a", "description": ""}])}
        sources = {"source.proj.b": _make_model("b", [{"name": "col_b", "description": ""}])}
        seeds = {"seed.proj.c": _make_model("c", [{"name": "col_c", "description": ""}])}
        snapshots = {"snapshot.proj.d": _make_model("d", [{"name": "col_d", "description": ""}])}
        index = build_search_index(models, sources, seeds, snapshots)

        col_entries = [e for e in index if e["resource_type"] == "column"]
        assert len(col_entries) == 4

        parent_ids = {e["unique_id"] for e in col_entries}
        assert parent_ids == {
            "model.proj.a",
            "source.proj.b",
            "seed.proj.c",
            "snapshot.proj.d",
        }

    def test_empty_column_name_skipped(self) -> None:
        models = {"model.proj.x": _make_model("x", columns=[{"name": "", "description": ""}])}
        index = build_search_index(models, {}, {}, {})

        col_entries = [e for e in index if e["resource_type"] == "column"]
        assert len(col_entries) == 0

    def test_no_columns_produces_no_column_entries(self) -> None:
        models = {"model.proj.empty": _make_model("empty", columns=[])}
        index = build_search_index(models, {}, {}, {})

        col_entries = [e for e in index if e["resource_type"] == "column"]
        assert len(col_entries) == 0

    def test_same_column_name_in_multiple_models(self) -> None:
        """Searching 'user_id' should return entries from every model that has it."""
        models = {
            "model.proj.users": _make_model("users", [{"name": "user_id", "description": ""}]),
            "model.proj.orders": _make_model("orders", [{"name": "user_id", "description": ""}]),
        }
        index = build_search_index(models, {}, {}, {})

        col_entries = [
            e for e in index if e["resource_type"] == "column" and e["column_name"] == "user_id"
        ]
        assert len(col_entries) == 2
        parent_models = {e["model_name"] for e in col_entries}
        assert parent_models == {"users", "orders"}
