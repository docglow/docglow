"""Tests for SQL identifier quoting in the profiler."""

import pytest

from docglow.profiler.queries import _quote


class TestQuote:
    def test_simple_column(self):
        assert _quote("user_id", "postgres") == '"user_id"'
        assert _quote("user_id", "duckdb") == '"user_id"'
        assert _quote("user_id", "snowflake") == '"user_id"'
        assert _quote("user_id", "bigquery") == "`user_id`"

    def test_column_with_double_quotes(self):
        """Embedded double quotes must be escaped for postgres/duckdb/snowflake."""
        assert _quote('col"name', "postgres") == '"col""name"'
        assert _quote('col"name', "duckdb") == '"col""name"'
        assert _quote('col"name', "snowflake") == '"col""name"'

    def test_column_with_backticks(self):
        """Embedded backticks must be escaped for bigquery."""
        assert _quote("col`name", "bigquery") == "`col``name`"

    def test_column_with_semicolon(self):
        """Semicolons are safe inside quoted identifiers."""
        assert _quote("col;drop", "postgres") == '"col;drop"'
        assert _quote("col;drop", "bigquery") == "`col;drop`"

    def test_column_with_null_byte_raises(self):
        """Null bytes in identifiers must be rejected."""
        with pytest.raises(ValueError, match="null byte"):
            _quote("col\x00name", "postgres")

        with pytest.raises(ValueError, match="null byte"):
            _quote("col\x00name", "bigquery")
