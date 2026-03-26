"""Tests for role inference, semantic type, and confidence scoring."""

from __future__ import annotations

from docglow.insights.inference import compute_confidence, infer_role, infer_semantic_type


class TestInferSemanticType:
    def test_identifier(self) -> None:
        assert infer_semantic_type("user_id", "") == "identifier"
        assert infer_semantic_type("order_key", "") == "identifier"
        assert infer_semantic_type("id", "") == "identifier"

    def test_timestamp(self) -> None:
        assert infer_semantic_type("created_at", "") == "timestamp"
        assert infer_semantic_type("order_date", "") == "timestamp"
        assert infer_semantic_type("updated_timestamp", "") == "timestamp"

    def test_boolean(self) -> None:
        assert infer_semantic_type("is_active", "") == "boolean"
        assert infer_semantic_type("has_email", "") == "boolean"

    def test_amount(self) -> None:
        assert infer_semantic_type("total_amount", "") == "amount"
        assert infer_semantic_type("order_total", "") == "amount"
        assert infer_semantic_type("unit_price", "") == "amount"

    def test_count(self) -> None:
        assert infer_semantic_type("order_count", "") == "count"
        assert infer_semantic_type("item_qty", "") == "count"

    def test_categorical(self) -> None:
        assert infer_semantic_type("order_status", "") == "categorical"
        assert infer_semantic_type("account_type", "") == "categorical"
        assert infer_semantic_type("status", "") == "categorical"

    def test_name(self) -> None:
        assert infer_semantic_type("customer_name", "") == "name"
        assert infer_semantic_type("name", "") == "name"

    def test_percentage(self) -> None:
        assert infer_semantic_type("completion_rate", "") == "percentage"
        assert infer_semantic_type("tax_pct", "") == "percentage"

    def test_data_type_fallback(self) -> None:
        assert infer_semantic_type("some_col", "BOOLEAN") == "boolean"
        assert infer_semantic_type("some_col", "TIMESTAMP_LTZ") == "timestamp"

    def test_no_match(self) -> None:
        assert infer_semantic_type("foobar", "VARCHAR") is None


class TestInferRole:
    def test_primary_key(self) -> None:
        tests = [
            {"test_type": "unique", "status": "pass"},
            {"test_type": "not_null", "status": "pass"},
        ]
        assert infer_role("id", "INTEGER", tests, set(), "identifier") == "primary_key"

    def test_foreign_key_from_test(self) -> None:
        tests = [{"test_type": "relationships", "status": "pass"}]
        assert infer_role("user_id", "INTEGER", tests, set(), "identifier") == "foreign_key"

    def test_foreign_key_from_join(self) -> None:
        assert infer_role("user_id", "INTEGER", [], {"join_key"}, "identifier") == "foreign_key"

    def test_timestamp(self) -> None:
        assert infer_role("created_at", "TIMESTAMP", [], set(), "timestamp") == "timestamp"

    def test_metric_from_aggregation(self) -> None:
        assert infer_role("amount", "DECIMAL", [], {"aggregated"}, None) == "metric"

    def test_metric_from_semantic(self) -> None:
        assert infer_role("total_amount", "DECIMAL", [], set(), "amount") == "metric"

    def test_categorical(self) -> None:
        tests = [{"test_type": "accepted_values", "status": "pass"}]
        assert infer_role("status", "VARCHAR", tests, set(), "categorical") == "categorical"

    def test_dimension_from_group_by(self) -> None:
        assert infer_role("region", "VARCHAR", [], {"group_by"}, None) == "dimension"

    def test_no_role(self) -> None:
        assert infer_role("mystery_col", "VARCHAR", [], set(), None) is None


class TestComputeConfidence:
    def test_base_score(self) -> None:
        assert compute_confidence("dimension", [], set(), None) == 0.5

    def test_none_role(self) -> None:
        assert compute_confidence(None, [], set(), None) == 0.0

    def test_test_bonus(self) -> None:
        tests = [{"test_type": "unique"}, {"test_type": "not_null"}]
        score = compute_confidence("primary_key", tests, set(), None)
        assert score == 0.7  # 0.5 + 0.2

    def test_sql_bonus(self) -> None:
        score = compute_confidence("foreign_key", [], {"join_key"}, None)
        assert score == 0.7  # 0.5 + 0.2

    def test_naming_bonus(self) -> None:
        score = compute_confidence("timestamp", [], set(), "timestamp")
        assert score == 0.6  # 0.5 + 0.1

    def test_all_bonuses(self) -> None:
        tests = [{"test_type": "unique"}, {"test_type": "not_null"}]
        score = compute_confidence("primary_key", tests, {"join_key"}, "identifier")
        assert score >= 0.99  # 0.5 + 0.2 + 0.2 + 0.1 ≈ 1.0

    def test_capped_at_one(self) -> None:
        tests = [{"test_type": "unique"}, {"test_type": "not_null"}]
        score = compute_confidence("primary_key", tests, {"join_key"}, "identifier")
        assert score <= 1.0
