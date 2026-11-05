"""Tests for metric transforms and how metrics reach lineage, search, and --select."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docglow.artifacts.loader import load_artifacts
from docglow.artifacts.manifest import ManifestMetric, ManifestSemanticModel
from docglow.generator.data import build_docglow_data
from docglow.generator.layers import DEFAULT_LAYERS, LineageLayerConfig, resolve_node_layer
from docglow.generator.transforms.metrics import transform_metric

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"

SEMANTIC_MODELS = {
    "semantic_model.p.orders": ManifestSemanticModel(
        unique_id="semantic_model.p.orders",
        name="orders",
        depends_on={"nodes": ["model.p.orders"]},
        measures=[{"name": "order_total", "agg": "sum", "expr": "amount"}],
    ),
}


def _metric(type_: str, deps: list[str], **fields: Any) -> ManifestMetric:
    return ManifestMetric(
        unique_id=f"metric.p.{type_}_metric",
        name=f"{type_}_metric",
        type=type_,
        depends_on={"nodes": deps},
        **fields,
    )


class TestTransformMetric:
    def test_simple_metric_resolves_semantic_model_to_model(self) -> None:
        metric = _metric(
            "simple",
            ["semantic_model.p.orders"],
            type_params={"measure": {"name": "order_total", "filter": None}},
        )
        result = transform_metric(metric, SEMANTIC_MODELS)

        assert result["models"] == ["model.p.orders"]
        assert result["input_metrics"] == []
        assert result["semantic_models"] == ["orders"]
        assert result["definition"] == {
            "measure": {"name": "order_total", "agg": "sum", "expr": "amount"}
        }

    def test_ratio_metric_lists_input_metrics(self) -> None:
        metric = _metric(
            "ratio",
            ["metric.p.a", "metric.p.b"],
            type_params={
                "numerator": {"name": "a", "filter": None, "alias": None},
                "denominator": {"name": "b", "filter": None, "alias": None},
            },
        )
        result = transform_metric(metric, SEMANTIC_MODELS)

        assert result["models"] == []
        assert result["input_metrics"] == ["metric.p.a", "metric.p.b"]
        assert result["definition"] == {"numerator": {"name": "a"}, "denominator": {"name": "b"}}

    def test_derived_metric_keeps_expr_alias_and_offset(self) -> None:
        metric = _metric(
            "derived",
            ["metric.p.revenue"],
            type_params={
                "expr": "current - prev",
                "metrics": [
                    {"name": "revenue", "alias": "current", "offset_window": None},
                    {
                        "name": "revenue",
                        "alias": "prev",
                        "offset_window": {"count": 1, "granularity": "month"},
                    },
                ],
            },
        )
        definition = transform_metric(metric, SEMANTIC_MODELS)["definition"]

        assert definition["expr"] == "current - prev"
        assert definition["metrics"] == [
            {"name": "revenue", "alias": "current"},
            {"name": "revenue", "alias": "prev", "offset": "1 month"},
        ]

    def test_cumulative_window_and_metric_filter(self) -> None:
        metric = _metric(
            "cumulative",
            ["semantic_model.p.orders"],
            type_params={
                "measure": {"name": "order_total"},
                "cumulative_type_params": {"window": {"count": 7, "granularity": "day"}},
            },
            filter={"where_filters": [{"where_sql_template": "{{ Dimension('x') }} = 1"}]},
        )
        definition = transform_metric(metric, SEMANTIC_MODELS)["definition"]

        assert definition["window"] == "7 day"
        assert definition["filter"] == ["{{ Dimension('x') }} = 1"]

    def test_unknown_semantic_model_yields_no_models(self) -> None:
        metric = _metric("simple", ["semantic_model.p.missing"])
        result = transform_metric(metric, SEMANTIC_MODELS)

        assert result["models"] == []
        assert result["semantic_models"] == []
        assert result["definition"] == {}

    def test_pre_metricflow_metric_depends_on_model_directly(self) -> None:
        metric = _metric("count", ["model.p.orders"])
        assert transform_metric(metric, SEMANTIC_MODELS)["models"] == ["model.p.orders"]


def _build(tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
    target = tmp_path / "target"
    target.mkdir(exist_ok=True)
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        (target / name).write_text((FIXTURES_DIR / name).read_text())
    return build_docglow_data(load_artifacts(tmp_path), **kwargs)


class TestMetricsInSite:
    def test_metric_nodes_and_edges_in_lineage(self, tmp_path: Path) -> None:
        data = _build(tmp_path)
        nodes = {n["id"]: n for n in data["lineage"]["nodes"]}
        edges = {(e["source"], e["target"]) for e in data["lineage"]["edges"]}

        metric_nodes = [n for n in nodes.values() if n["resource_type"] == "metric"]
        assert len(metric_nodes) == len(data["metrics"]) == 19
        assert ("model.jaffle_shop.order_items", "metric.jaffle_shop.revenue") in edges
        assert ("metric.jaffle_shop.revenue", "metric.jaffle_shop.food_revenue_pct") in edges
        # No edge points at a semantic model, which has no lineage node.
        assert not any(src.startswith("semantic_model.") for src, _ in edges)

    def test_metrics_get_the_default_metric_layer(self, tmp_path: Path) -> None:
        data = _build(tmp_path)
        metric_rank = next(
            layer["rank"] for layer in data["lineage"]["layer_config"] if layer["name"] == "metric"
        )
        ranks = {n["layer"] for n in data["lineage"]["nodes"] if n["resource_type"] == "metric"}
        assert ranks == {metric_rank}

    def test_config_without_metric_layer_puts_metrics_last(self) -> None:
        layers = tuple(layer for layer in DEFAULT_LAYERS if layer.name != "metric")
        rank = resolve_node_layer(
            name="revenue",
            folder="",
            tags=[],
            meta={},
            resource_type="metric",
            schema="",
            config=LineageLayerConfig(layers=layers, rules=()),
        )
        assert rank == max(layer.rank for layer in layers)

    def test_metrics_are_searchable(self, tmp_path: Path) -> None:
        data = _build(tmp_path)
        entries = [e for e in data["search_index"] if e["resource_type"] == "metric"]
        assert {e["unique_id"] for e in entries} == set(data["metrics"])

    def test_select_keeps_only_metrics_reaching_selected_models(self, tmp_path: Path) -> None:
        data = _build(tmp_path, select="customers")

        assert set(data["metrics"]) == {
            "metric.jaffle_shop.lifetime_spend_pretax",
            "metric.jaffle_shop.count_lifetime_orders",
            # derived from the two above
            "metric.jaffle_shop.average_order_value",
        }
        lineage_metrics = {
            n["id"] for n in data["lineage"]["nodes"] if n["resource_type"] == "metric"
        }
        assert lineage_metrics == set(data["metrics"])

    def test_exclude_drops_edges_from_filtered_out_input_metrics(self, tmp_path: Path) -> None:
        # order_gross_profit = revenue (order_items) - order_cost (orders). With
        # order_items excluded, revenue goes but order_gross_profit stays.
        data = _build(tmp_path, exclude="order_items")
        ids = {n["id"] for n in data["lineage"]["nodes"]}

        assert "metric.jaffle_shop.revenue" not in data["metrics"]
        assert "metric.jaffle_shop.order_gross_profit" in data["metrics"]
        metric_edges = [e for e in data["lineage"]["edges"] if e["target"].startswith("metric.")]
        assert all(e["source"] in ids for e in metric_edges)


def _columns_metric(expr: str | None, **fields: Any) -> ManifestMetric:
    sm = ManifestSemanticModel(
        unique_id="semantic_model.p.accounts",
        name="accounts",
        depends_on={"nodes": ["model.p.accounts"]},
        measures=[{"name": "m", "agg": "count_distinct", "expr": expr}],
    )
    metric = _metric("simple", [sm.unique_id], type_params={"measure": {"name": "m"}, **fields})
    return transform_metric(metric, {sm.unique_id: sm}, dialect="databricks")


class TestMetricColumns:
    def test_measure_without_expr_reads_its_own_name(self) -> None:
        assert _columns_metric(None)["columns"] == [{"model": "model.p.accounts", "column": "m"}]

    def test_plain_column_expr(self) -> None:
        assert _columns_metric("account_id")["columns"] == [
            {"model": "model.p.accounts", "column": "account_id"}
        ]

    def test_sql_expr_lists_every_column_once(self) -> None:
        expr = "case when is_trial and lt_type = 'GL' then account_id end"
        columns = [c["column"] for c in _columns_metric(expr)["columns"]]
        assert columns == ["is_trial", "lt_type", "account_id"]

    def test_row_count_reads_no_column(self) -> None:
        assert _columns_metric("1")["columns"] == []
        assert _columns_metric("true")["columns"] == []

    def test_unparsable_expr_reads_no_column(self) -> None:
        assert _columns_metric("case when (")["columns"] == []

    def test_derived_metric_reads_columns_through_its_inputs(self) -> None:
        metric = _metric("derived", ["metric.p.a"], type_params={"expr": "a * 2"})
        assert transform_metric(metric, SEMANTIC_MODELS)["columns"] == []


class TestMetricColumnLineage:
    def test_metrics_join_column_lineage(self, tmp_path: Path) -> None:
        data = _build(tmp_path, column_lineage_enabled=True)
        cl = data["column_lineage"]

        assert cl["metric.jaffle_shop.revenue"] == {
            "revenue": [
                {
                    "source_model": "model.jaffle_shop.order_items",
                    "source_column": "product_price",
                    "transformation": "aggregated",
                }
            ]
        }
        # Derived metrics chain through their inputs' metric "columns".
        assert {
            (d["source_model"], d["source_column"])
            for d in cl["metric.jaffle_shop.order_gross_profit"]["order_gross_profit"]
        } == {
            ("metric.jaffle_shop.revenue", "revenue"),
            ("metric.jaffle_shop.order_cost", "order_cost"),
        }
        # A row count (expr: 1) reads no column, so it has no entry.
        assert "metric.jaffle_shop.orders" not in cl

    def test_metric_columns_exist_on_their_models(self, tmp_path: Path) -> None:
        data = _build(tmp_path, column_lineage_enabled=True)
        for metric in data["metrics"].values():
            for ref in metric["columns"]:
                names = [c["name"] for c in data["models"][ref["model"]]["columns"]]
                assert ref["column"] in names, (metric["name"], ref)

    def test_no_entries_when_column_lineage_is_off(self, tmp_path: Path) -> None:
        data = _build(tmp_path)
        assert data["column_lineage"] is None
        # The metric still lists the columns it reads.
        assert data["metrics"]["metric.jaffle_shop.revenue"]["columns"] == [
            {"model": "model.jaffle_shop.order_items", "column": "product_price"}
        ]

    def test_select_only_links_kept_metrics(self, tmp_path: Path) -> None:
        data = _build(tmp_path, column_lineage_enabled=True, select="customers")
        metric_keys = {k for k in data["column_lineage"] if k.startswith("metric.")}
        assert metric_keys <= set(data["metrics"])
        assert "metric.jaffle_shop.lifetime_spend_pretax" in metric_keys
