"""Tests for histogram query building and parsing."""

import pytest

from docglow.profiler.queries import build_histogram_query
from docglow.profiler.stats import parse_histogram_rows


class TestBuildHistogramQuery:
    def test_duckdb_query_structure(self):
        sql = build_histogram_query("main", "orders", "amount", adapter="duckdb")
        assert "WIDTH_BUCKET" in sql
        assert '"amount"' in sql
        assert '"main"."orders"' in sql
        assert "10" in sql  # default bins

    def test_custom_bins(self):
        sql = build_histogram_query("main", "orders", "amount", adapter="duckdb", num_bins=5)
        assert ", 5)" in sql

    def test_postgres_query(self):
        sql = build_histogram_query("public", "orders", "total", adapter="postgres")
        assert "DOUBLE PRECISION" in sql
        assert "WIDTH_BUCKET" in sql


class TestParseHistogramRows:
    def test_basic_histogram(self):
        rows = [
            {"bucket": 1, "freq": 10},
            {"bucket": 2, "freq": 20},
            {"bucket": 3, "freq": 5},
        ]
        bins = parse_histogram_rows(rows, col_min=0.0, col_max=30.0, num_bins=3)
        assert len(bins) == 3
        assert bins[0] == {"low": 0.0, "high": 10.0, "count": 10}
        assert bins[1] == {"low": 10.0, "high": 20.0, "count": 20}
        assert bins[2] == {"low": 20.0, "high": 30.0, "count": 5}

    def test_missing_buckets_filled_with_zero(self):
        rows = [
            {"bucket": 1, "freq": 10},
            {"bucket": 3, "freq": 5},
        ]
        bins = parse_histogram_rows(rows, col_min=0.0, col_max=30.0, num_bins=3)
        assert len(bins) == 3
        assert bins[1]["count"] == 0  # bucket 2 missing

    def test_empty_range_returns_empty(self):
        bins = parse_histogram_rows([], col_min=5.0, col_max=5.0, num_bins=10)
        assert bins == []

    def test_none_bounds_returns_empty(self):
        bins = parse_histogram_rows([], col_min=None, col_max=None, num_bins=10)
        assert bins == []

    def test_ten_bins_default(self):
        rows = [{"bucket": i, "freq": i * 10} for i in range(1, 11)]
        bins = parse_histogram_rows(rows, col_min=0.0, col_max=100.0)
        assert len(bins) == 10
        assert bins[0]["low"] == 0.0
        assert bins[9]["high"] == 100.0
