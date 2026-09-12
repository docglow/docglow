"""End-to-end column lineage for qualified stars, against the starshop example.

The unit tests in test_column_parser.py drive parse_column_lineage directly with
hand-written SQL. These run the whole pipeline over real committed dbt artifacts
instead, so a regression shows up the same way a user would meet it: as columns
missing from the lineage graph.

starshop exists for this. See examples/starshop/README.md — no other example
project selects a qualified star in an outermost SELECT, so before it, breaking
star expansion left every fixture green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docglow.lineage.analyzer import analyze_column_lineage
from docglow.lineage.column_parser import detect_dialect

Lineage = dict[str, dict[str, list[dict[str, str]]]]

STARSHOP = Path(__file__).parent.parent.parent / "examples" / "starshop"

DIM_COMPANY = "model.starshop.dim_company"
FCT_CONTRACTS = "model.starshop.fct_company_contracts"
STG_COMPANIES = "model.starshop.stg_companies"
STG_CONTRACTS = "model.starshop.stg_contracts"


def _load_starshop() -> Lineage:
    """Run column lineage over the committed starshop artifacts."""
    from docglow.artifacts.loader import load_artifacts
    from docglow.generator.pipeline import (
        PipelineContext,
        stage_filter_nodes,
        stage_transform_nodes,
        stage_transform_sources,
    )

    artifacts = load_artifacts(STARSHOP)
    ctx = PipelineContext(artifacts=artifacts, column_lineage_enabled=True)
    stage_transform_nodes(ctx)
    stage_filter_nodes(ctx)
    stage_transform_sources(ctx)
    return analyze_column_lineage(
        models=ctx.models,
        sources=ctx.sources,
        seeds=ctx.seeds,
        snapshots=ctx.snapshots,
        dialect=detect_dialect(artifacts.manifest.metadata.adapter_type),
        manifest_nodes=dict(artifacts.manifest.nodes),
        manifest_sources=dict(artifacts.manifest.sources),
    )


@pytest.fixture(scope="module")
def lineage() -> Lineage:
    return _load_starshop()


def _upstream_models(deps: list[dict[str, str]]) -> set[str]:
    return {d["source_model"] for d in deps if "source_model" in d}


class TestSingleQualifiedStar:
    """dim_company: `select md5(company_name) as company_key, renamed.* from renamed`."""

    def test_star_columns_are_traced(self, lineage: Lineage) -> None:
        # company_key is written out explicitly and survived even the bug; the
        # other four exist only because `renamed.*` expands.
        assert set(lineage[DIM_COMPANY]) == {
            "company_key",
            "company_id",
            "company_name",
            "country_code",
            "employee_count",
        }

    def test_star_columns_reach_the_source_model(self, lineage: Lineage) -> None:
        for column in ("company_id", "company_name", "country_code", "employee_count"):
            assert _upstream_models(lineage[DIM_COMPANY][column]) == {STG_COMPANIES}, (
                f"{column} should trace to stg_companies"
            )

    def test_no_literal_star_column(self, lineage: Lineage) -> None:
        # The original defect surfaced a literal '*' as an output column name.
        assert "*" not in lineage[DIM_COMPANY]


class TestMultiStarJoin:
    """fct_company_contracts: `select c.*, k.* from stg_companies c join stg_contracts k`."""

    def test_model_has_lineage_at_all(self, lineage: Lineage) -> None:
        # Before the fix this model produced no column lineage whatsoever.
        assert lineage.get(FCT_CONTRACTS), "multi-star join produced no column lineage"

    def test_each_star_resolves_against_its_own_source(self, lineage: Lineage) -> None:
        columns = lineage[FCT_CONTRACTS]
        for column in ("company_name", "country_code", "employee_count"):
            assert _upstream_models(columns[column]) == {STG_COMPANIES}
        for column in ("contract_id", "annual_value", "contract_status"):
            assert _upstream_models(columns[column]) == {STG_CONTRACTS}

    def test_colliding_name_collapses_to_the_first_source(self, lineage: Lineage) -> None:
        """company_id appears in both stars; lineage keeps the first source only.

        This is the deliberate choice in
        adr-2026-09-10-nested-schema-mapping-for-star-expansion: sqlglot's own
        lineage() resolves an ambiguous `id` to the first source, and the dbt
        catalog is keyed by column name so it cannot hold two entries anyway.
        The warehouse still emits a disambiguated `company_id_1` column, so the
        catalog has 8 columns here while lineage has 7 — that gap is intended,
        and this test exists so a future change to it is a decision, not a
        surprise.
        """
        columns = lineage[FCT_CONTRACTS]
        assert _upstream_models(columns["company_id"]) == {STG_COMPANIES}
        assert "company_id_1" not in columns

    def test_no_literal_star_column(self, lineage: Lineage) -> None:
        assert "*" not in lineage[FCT_CONTRACTS]
