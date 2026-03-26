"""Tests for template-based description generation."""

from __future__ import annotations

from docglow.insights.descriptions import apply_description, generate_description


class TestGenerateDescription:
    def test_primary_key(self) -> None:
        result = generate_description("order_id", "primary_key", "identifier", "fct_orders")
        assert "Unique identifier" in result
        assert "fct_orders" in result

    def test_foreign_key_entity(self) -> None:
        result = generate_description("user_id", "foreign_key", "identifier", "fct_orders")
        assert "user" in result
        assert "References" in result

    def test_foreign_key_key_suffix(self) -> None:
        result = generate_description("account_key", "foreign_key", "identifier", "fct_orders")
        assert "account" in result

    def test_timestamp_created(self) -> None:
        result = generate_description("created_at", "timestamp", "timestamp", "fct_orders")
        assert "creation" in result

    def test_timestamp_updated(self) -> None:
        result = generate_description("updated_at", "timestamp", "timestamp", "fct_orders")
        assert "last update" in result

    def test_metric(self) -> None:
        result = generate_description("total_revenue", "metric", "amount", "fct_orders")
        assert "Numeric measure" in result
        assert "total revenue" in result

    def test_categorical(self) -> None:
        result = generate_description("order_status", "categorical", "categorical", "fct_orders")
        assert "Category" in result

    def test_dimension(self) -> None:
        result = generate_description("customer_name", "dimension", "name", "fct_orders")
        assert "Descriptive attribute" in result

    def test_none_role(self) -> None:
        assert generate_description("mystery", None, None, "model") is None


class TestApplyDescription:
    def test_skip_preserves(self) -> None:
        assert apply_description("existing", "generated", "skip") == "existing"

    def test_replace_overwrites(self) -> None:
        assert apply_description("existing", "generated", "replace") == "generated"

    def test_replace_none_keeps(self) -> None:
        assert apply_description("existing", None, "replace") == "existing"

    def test_append_fills_blank(self) -> None:
        assert apply_description("", "generated", "append") == "generated"

    def test_append_keeps_existing(self) -> None:
        assert apply_description("existing", "generated", "append") == "existing"

    def test_append_none_generated(self) -> None:
        assert apply_description("", None, "append") == ""
