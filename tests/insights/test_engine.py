"""Integration tests for the column insights engine."""

from __future__ import annotations

from typing import Any

import pytest

from docglow.insights.engine import enrich_columns


@pytest.fixture()
def sample_data() -> dict[str, Any]:
    """Minimal docglow data payload for testing."""
    return {
        "metadata": {"project_name": "test"},
        "models": {
            "model.test.fct_orders": {
                "unique_id": "model.test.fct_orders",
                "name": "fct_orders",
                "compiled_sql": (
                    "SELECT o.order_id, o.user_id, o.status, sum(oi.amount) as total_amount "
                    "FROM orders o "
                    "JOIN order_items oi ON o.order_id = oi.order_id "
                    "WHERE o.status = 'completed' "
                    "GROUP BY o.order_id, o.user_id, o.status"
                ),
                "raw_sql": "",
                "columns": [
                    {
                        "name": "order_id",
                        "description": "Primary key for orders",
                        "data_type": "INTEGER",
                        "tests": [
                            {"test_type": "unique", "status": "pass"},
                            {"test_type": "not_null", "status": "pass"},
                        ],
                        "meta": {},
                        "tags": [],
                        "profile": None,
                    },
                    {
                        "name": "user_id",
                        "description": "",
                        "data_type": "INTEGER",
                        "tests": [{"test_type": "relationships", "status": "pass"}],
                        "meta": {},
                        "tags": [],
                        "profile": None,
                    },
                    {
                        "name": "status",
                        "description": "",
                        "data_type": "VARCHAR",
                        "tests": [
                            {
                                "test_type": "accepted_values",
                                "status": "pass",
                                "config": {"values": ["completed", "pending"]},
                            }
                        ],
                        "meta": {},
                        "tags": [],
                        "profile": None,
                    },
                    {
                        "name": "total_amount",
                        "description": "",
                        "data_type": "DECIMAL",
                        "tests": [],
                        "meta": {},
                        "tags": [],
                        "profile": None,
                    },
                    {
                        "name": "created_at",
                        "description": "",
                        "data_type": "TIMESTAMP",
                        "tests": [],
                        "meta": {},
                        "tags": [],
                        "profile": None,
                    },
                ],
            },
        },
        "sources": {
            "source.test.raw.orders": {
                "unique_id": "source.test.raw.orders",
                "name": "orders",
                "source_name": "raw",
                "columns": [
                    {
                        "name": "order_id",
                        "description": "",
                        "data_type": "INTEGER",
                        "tests": [],
                        "meta": {},
                        "tags": [],
                    },
                ],
            },
        },
        "seeds": {},
        "snapshots": {},
    }


class TestEnrichColumns:
    def test_primary_key_detected(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        assert cols["order_id"]["insights"]["role"] == "primary_key"

    def test_foreign_key_detected(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        assert cols["user_id"]["insights"]["role"] == "foreign_key"

    def test_categorical_detected(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        assert cols["status"]["insights"]["role"] == "categorical"

    def test_metric_detected(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        assert cols["total_amount"]["insights"]["role"] == "metric"

    def test_timestamp_detected(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        assert cols["created_at"]["insights"]["role"] == "timestamp"

    def test_description_append_fills_blank(self, sample_data: dict) -> None:
        enrich_columns(sample_data, description_mode="append")
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        # user_id had empty description, should be filled
        assert cols["user_id"]["description"] != ""
        # order_id had existing description, should be preserved
        assert cols["order_id"]["description"] == "Primary key for orders"

    def test_description_replace(self, sample_data: dict) -> None:
        enrich_columns(sample_data, description_mode="replace")
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        # order_id had existing description, should be replaced with generated
        assert "Unique identifier" in cols["order_id"]["description"]

    def test_description_skip(self, sample_data: dict) -> None:
        enrich_columns(sample_data, description_mode="skip")
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        # All descriptions unchanged
        assert cols["order_id"]["description"] == "Primary key for orders"
        assert cols["user_id"]["description"] == ""

    def test_insights_shape(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        col = sample_data["models"]["model.test.fct_orders"]["columns"][0]
        insights = col["insights"]
        assert "role" in insights
        assert "semantic_type" in insights
        assert "sql_usage" in insights
        assert "confidence" in insights
        assert "generated_description" in insights
        assert isinstance(insights["sql_usage"], list)
        assert isinstance(insights["confidence"], float)

    def test_sources_enriched(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        col = sample_data["sources"]["source.test.raw.orders"]["columns"][0]
        assert "insights" in col
        assert col["insights"]["semantic_type"] == "identifier"

    def test_empty_models(self) -> None:
        data: dict[str, Any] = {
            "metadata": {},
            "models": {},
            "sources": {},
            "seeds": {},
            "snapshots": {},
        }
        result = enrich_columns(data)
        assert result is data  # returns same dict

    def test_confidence_scores(self, sample_data: dict) -> None:
        enrich_columns(sample_data)
        cols = {c["name"]: c for c in sample_data["models"]["model.test.fct_orders"]["columns"]}
        # Primary key with tests + naming should have high confidence
        assert cols["order_id"]["insights"]["confidence"] >= 0.7
        # Timestamp with naming match but no tests
        assert cols["created_at"]["insights"]["confidence"] >= 0.5
