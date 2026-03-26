"""Tests for SQL usage detection."""

from __future__ import annotations

from docglow.insights.sql_usage import detect_sql_usage


class TestDetectSqlUsage:
    def test_join_key(self) -> None:
        sql = "SELECT a.id, b.name FROM orders a JOIN users b ON a.user_id = b.id"
        result = detect_sql_usage(sql, ["id", "name", "user_id"])
        assert "join_key" in result.get("user_id", set())
        assert "join_key" in result.get("id", set())

    def test_group_by(self) -> None:
        sql = "SELECT status, count(*) FROM orders GROUP BY status"
        result = detect_sql_usage(sql, ["status"])
        assert "group_by" in result.get("status", set())

    def test_where_filter(self) -> None:
        sql = "SELECT * FROM orders WHERE status = 'paid'"
        result = detect_sql_usage(sql, ["status"])
        assert "filtered" in result.get("status", set())

    def test_aggregation(self) -> None:
        sql = "SELECT user_id, sum(amount) FROM orders GROUP BY user_id"
        result = detect_sql_usage(sql, ["user_id", "amount"])
        assert "aggregated" in result.get("amount", set())

    def test_selected_only(self) -> None:
        sql = "SELECT name, email FROM users"
        result = detect_sql_usage(sql, ["name", "email"])
        assert result.get("name") == {"selected_only"}
        assert result.get("email") == {"selected_only"}

    def test_multiple_usages(self) -> None:
        sql = "SELECT user_id, sum(amount) FROM orders WHERE status = 'active' GROUP BY user_id"
        result = detect_sql_usage(sql, ["user_id", "amount", "status"])
        assert "group_by" in result.get("user_id", set())
        assert "aggregated" in result.get("amount", set())
        assert "filtered" in result.get("status", set())

    def test_empty_sql(self) -> None:
        assert detect_sql_usage("", ["col"]) == {}
        assert detect_sql_usage("  ", ["col"]) == {}

    def test_unparseable_sql(self) -> None:
        result = detect_sql_usage("NOT VALID SQL !!!", ["col"])
        assert result == {} or all(v == {"selected_only"} for v in result.values())

    def test_case_insensitive(self) -> None:
        sql = "SELECT USER_ID FROM orders GROUP BY USER_ID"
        result = detect_sql_usage(sql, ["user_id"])
        assert "group_by" in result.get("user_id", set())
