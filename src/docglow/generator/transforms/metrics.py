"""Transform dbt (MetricFlow) metrics into Docglow metric dicts."""

from __future__ import annotations

from typing import Any

from docglow.artifacts.manifest import ManifestMetric, ManifestSemanticModel


def transform_metric(
    metric: ManifestMetric,
    semantic_models: dict[str, ManifestSemanticModel],
) -> dict[str, Any]:
    """Transform a manifest metric into a DocglowMetric dict.

    A simple / cumulative / conversion metric depends on a semantic model,
    which docglow does not show as a node of its own; ``models`` resolves it to
    the model the semantic model is built on, so lineage can draw
    model → metric. Derived and ratio metrics depend on other metrics, listed
    in ``input_metrics``.
    """
    deps = metric.depends_on.nodes
    sm_ids = [d for d in deps if d.startswith("semantic_model.")]
    sms = [semantic_models[d] for d in sm_ids if d in semantic_models]

    models: list[str] = []
    for dep in deps:
        if dep.startswith("semantic_model."):
            sm = semantic_models.get(dep)
            targets = sm.depends_on.nodes if sm else []
        elif dep.startswith("metric."):
            continue
        else:
            # Pre-MetricFlow metrics (dbt < 1.6) depend on models directly.
            targets = [dep]
        for target in targets:
            if target not in models:
                models.append(target)

    return {
        "unique_id": metric.unique_id,
        "name": metric.name,
        "description": metric.description,
        "label": metric.label,
        "type": metric.type,
        "depends_on": deps,
        "tags": list(metric.tags),
        "package_name": metric.package_name,
        "models": models,
        "input_metrics": [d for d in deps if d.startswith("metric.")],
        "semantic_models": [sm.name for sm in sms],
        "definition": _definition(metric, sms),
    }


def _definition(metric: ManifestMetric, sms: list[ManifestSemanticModel]) -> dict[str, Any]:
    """The parts of ``type_params`` a reader needs, with empty keys dropped.

    ``type_params`` carries every field for every metric type, mostly null, so
    copying it verbatim would bloat the payload for projects with hundreds of
    metrics.
    """
    params = metric.type_params
    definition: dict[str, Any] = {}

    measure = params.get("measure")
    if isinstance(measure, dict) and measure.get("name"):
        definition["measure"] = _measure(measure, sms)
    else:
        # dbt 1.10+ simple metrics can aggregate an expression directly.
        agg_params = params.get("metric_aggregation_params")
        if isinstance(agg_params, dict) and agg_params.get("agg"):
            definition["measure"] = _drop_empty(
                {"agg": agg_params.get("agg"), "expr": params.get("expr")}
            )

    for side in ("numerator", "denominator"):
        ref = params.get(side)
        if isinstance(ref, dict) and ref.get("name"):
            definition[side] = _metric_input(ref)

    inputs = params.get("metrics")
    if isinstance(inputs, list) and inputs:
        definition["metrics"] = [_metric_input(i) for i in inputs if isinstance(i, dict)]
        expr = params.get("expr")
        if expr:
            definition["expr"] = expr

    cumulative = params.get("cumulative_type_params")
    window = cumulative.get("window") if isinstance(cumulative, dict) else None
    grain_to_date = cumulative.get("grain_to_date") if isinstance(cumulative, dict) else None
    window = window or params.get("window")
    grain_to_date = grain_to_date or params.get("grain_to_date")
    if window:
        definition["window"] = _window(window)
    if grain_to_date:
        definition["grain_to_date"] = _granularity(grain_to_date)

    conversion = params.get("conversion_type_params")
    if isinstance(conversion, dict):
        definition["conversion"] = _drop_empty(
            {
                "base_measure": _name(conversion.get("base_measure")),
                "conversion_measure": _name(conversion.get("conversion_measure")),
                "entity": conversion.get("entity"),
                "calculation": conversion.get("calculation"),
                "window": _window(conversion.get("window")),
            }
        )

    filters = _filters(metric.filter)
    if filters:
        definition["filter"] = filters

    return definition


def _measure(ref: dict[str, Any], sms: list[ManifestSemanticModel]) -> dict[str, Any]:
    """A measure reference, with its aggregation and expression looked up."""
    name = ref.get("name")
    found: dict[str, object] = {}
    for sm in sms:
        found = next((m for m in sm.measures if m.get("name") == name), {})
        if found:
            break
    return _drop_empty(
        {
            "name": name,
            "agg": found.get("agg"),
            "expr": found.get("expr"),
            "filter": _filters(ref.get("filter")),
        }
    )


def _metric_input(ref: dict[str, Any]) -> dict[str, Any]:
    """A metric used as an input to a derived or ratio metric."""
    return _drop_empty(
        {
            "name": ref.get("name"),
            "alias": ref.get("alias"),
            "offset": _window(ref.get("offset_window")) or _granularity(ref.get("offset_to_grain")),
            "filter": _filters(ref.get("filter")),
        }
    )


def _filters(value: object) -> list[str]:
    """``{"where_filters": [{"where_sql_template": ...}]}`` → the SQL templates."""
    if not isinstance(value, dict):
        return []
    where = value.get("where_filters")
    if not isinstance(where, list):
        return []
    return [
        str(f["where_sql_template"])
        for f in where
        if isinstance(f, dict) and f.get("where_sql_template")
    ]


def _window(value: object) -> str | None:
    """``{"count": 7, "granularity": "day"}`` → ``"7 day"``."""
    if not isinstance(value, dict) or value.get("count") is None:
        return None
    granularity = value.get("granularity") or value.get("time_granularity") or ""
    return f"{value['count']} {_granularity(granularity) or ''}".strip()


def _granularity(value: object) -> str | None:
    """A granularity, either a plain string or ``{"name": ...}`` in some versions."""
    if isinstance(value, dict):
        value = value.get("name")
    return str(value) if value else None


def _name(value: object) -> str | None:
    return str(value["name"]) if isinstance(value, dict) and value.get("name") else None


def _drop_empty(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v not in (None, "", [], {})}
