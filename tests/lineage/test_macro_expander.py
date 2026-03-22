"""Tests for dbt macro expansion."""

from __future__ import annotations

from docglow.lineage.macro_expander import expand_macros


class TestSurrogateKey:
    def test_basic(self) -> None:
        sql = "SELECT {{ dbt_utils.surrogate_key(['col_a', 'col_b']) }} AS sk FROM t"
        result = expand_macros(sql)
        assert "CONCAT(col_a, col_b)" in result
        assert "{{" not in result

    def test_single_column(self) -> None:
        sql = """{{ dbt_utils.surrogate_key(["order_id"]) }}"""
        result = expand_macros(sql)
        assert "CONCAT(order_id)" in result

    def test_empty_list(self) -> None:
        sql = "{{ dbt_utils.surrogate_key([]) }}"
        result = expand_macros(sql)
        assert result == "NULL"


class TestStar:
    def test_with_ref(self) -> None:
        sql = "SELECT {{ dbt_utils.star(ref('stg_orders')) }} FROM stg_orders"
        result = expand_macros(sql)
        assert "*" in result
        assert "dbt_utils" not in result

    def test_with_except(self) -> None:
        sql = "SELECT {{ dbt_utils.star(ref('model'), except=['id']) }} FROM model"
        result = expand_macros(sql)
        assert "*" in result

    def test_with_source(self) -> None:
        sql = "SELECT {{ dbt_utils.star(source('raw', 'orders')) }} FROM raw.orders"
        result = expand_macros(sql)
        assert "*" in result


class TestDateTrunc:
    def test_dbt_date_trunc(self) -> None:
        result = expand_macros("{{ dbt.date_trunc('day', 'created_at') }}")
        assert result == "DATE_TRUNC('day', created_at)"

    def test_dbt_utils_date_trunc(self) -> None:
        result = expand_macros("{{ dbt_utils.date_trunc('month', 'order_date') }}")
        assert result == "DATE_TRUNC('month', order_date)"

    def test_unquoted_column(self) -> None:
        result = expand_macros("{{ dbt.date_trunc('week', updated_at) }}")
        assert result == "DATE_TRUNC('week', updated_at)"


class TestSafeCast:
    def test_basic(self) -> None:
        result = expand_macros("{{ dbt.safe_cast('amount', 'integer') }}")
        assert result == "CAST(amount AS integer)"

    def test_with_api_column(self) -> None:
        result = expand_macros(
            "{{ dbt.safe_cast('revenue', api.Column.translate_type('integer')) }}"
        )
        assert result == "CAST(revenue AS integer)"


class TestCurrentTimestamp:
    def test_dbt(self) -> None:
        result = expand_macros("{{ dbt.current_timestamp() }}")
        assert result == "CURRENT_TIMESTAMP"

    def test_dbt_utils(self) -> None:
        result = expand_macros("{{ dbt_utils.current_timestamp() }}")
        assert result == "CURRENT_TIMESTAMP"


class TestDatediff:
    def test_basic(self) -> None:
        result = expand_macros("{{ dbt.datediff('start_date', 'end_date', 'day') }}")
        assert result == "DATEDIFF('day', start_date, end_date)"


class TestDateadd:
    def test_basic(self) -> None:
        result = expand_macros("{{ dbt.dateadd('day', -7, 'created_at') }}")
        assert result == "DATEADD('day', -7, created_at)"


class TestTypeHelpers:
    def test_type_string(self) -> None:
        assert expand_macros("{{ type_string() }}") == "VARCHAR"
        assert expand_macros("{{ dbt.type_string() }}") == "VARCHAR"

    def test_type_int(self) -> None:
        assert expand_macros("{{ type_int() }}") == "INTEGER"

    def test_type_timestamp(self) -> None:
        assert expand_macros("{{ type_timestamp() }}") == "TIMESTAMP"

    def test_type_float(self) -> None:
        assert expand_macros("{{ type_float() }}") == "FLOAT"

    def test_type_numeric(self) -> None:
        assert expand_macros("{{ type_numeric() }}") == "NUMERIC"

    def test_type_boolean(self) -> None:
        assert expand_macros("{{ dbt.type_boolean() }}") == "BOOLEAN"


class TestUnrecognizedMacros:
    def test_unknown_macro_unchanged(self) -> None:
        """Unrecognized macros should NOT be modified by expand_macros."""
        sql = "SELECT {{ my_custom_macro('x') }} FROM t"
        result = expand_macros(sql)
        # The macro call should still be there (caller handles fallback)
        assert "{{ my_custom_macro('x') }}" in result

    def test_partial_expansion(self) -> None:
        """Only known macros are expanded; unknown ones stay."""
        sql = "SELECT {{ dbt.date_trunc('day', 'ts') }}, {{ unknown_func() }} FROM t"
        result = expand_macros(sql)
        assert "DATE_TRUNC('day', ts)" in result
        assert "{{ unknown_func() }}" in result


class TestStripJinjaIntegration:
    """Test that expand_macros works correctly in the strip_jinja pipeline."""

    def test_end_to_end(self) -> None:
        from docglow.lineage.analyzer import strip_jinja

        raw_sql = (
            "{{ config(materialized='table') }}\n"
            "SELECT\n"
            "  {{ dbt_utils.surrogate_key(['order_id', 'customer_id']) }} AS sk,\n"
            "  {{ dbt.date_trunc('day', 'created_at') }} AS created_day,\n"
            "  {{ my_unknown_macro() }} AS unknown_col\n"
            "FROM {{ ref('stg_orders') }}"
        )
        result = strip_jinja(raw_sql)

        assert "CONCAT(order_id, customer_id)" in result
        assert "DATE_TRUNC('day', created_at)" in result
        assert "NULL" in result  # unknown macro
        assert "stg_orders" in result  # ref resolved
        assert "config" not in result  # config removed
