"""Benchmark column lineage performance against a real dbt project.

Usage:
    python scripts/bench_column_lineage.py /path/to/dbt/project
    python scripts/bench_column_lineage.py /path/to/dbt/project --no-cache
    python scripts/bench_column_lineage.py /path/to/dbt/project --select fct_orders+
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any


def _setup_pipeline_context(
    project_dir: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    Any,
    str | None,
]:
    """Run pipeline stages up through transform to get model/source dicts.

    Returns (models, sources, seeds, snapshots, manifest, dialect).
    """
    from docglow.artifacts.loader import load_artifacts
    from docglow.generator.pipeline import (
        PipelineContext,
        stage_filter_nodes,
        stage_transform_nodes,
        stage_transform_sources,
    )
    from docglow.lineage.column_parser import detect_dialect

    artifacts = load_artifacts(project_dir)

    ctx = PipelineContext(
        artifacts=artifacts,
        column_lineage_enabled=True,
    )

    # Run the transform stages that build the model/source dicts
    stage_transform_nodes(ctx)
    stage_filter_nodes(ctx)
    stage_transform_sources(ctx)

    dialect = detect_dialect(artifacts.manifest.metadata.adapter_type)

    return ctx.models, ctx.sources, ctx.seeds, ctx.snapshots, artifacts.manifest, dialect


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark column lineage performance")
    parser.add_argument("project_dir", type=Path, help="Path to dbt project root")
    parser.add_argument("--no-cache", action="store_true", help="Clear cache before running")
    parser.add_argument(
        "--select", type=str, default=None, help="Subset pattern (e.g. fct_orders+)"
    )
    parser.add_argument("--workers", type=int, default=None, help="Max parallel workers")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    project_dir = args.project_dir.resolve()
    cache_path = project_dir / "target" / ".bench-column-lineage-cache.json"

    if args.no_cache and cache_path.exists():
        cache_path.unlink()
        print(f"Cleared cache: {cache_path}")

    # Phase 1: Load and transform artifacts
    print(f"\nLoading artifacts from {project_dir}...")
    t0 = time.perf_counter()
    models, sources, seeds, snapshots, manifest, dialect = _setup_pipeline_context(project_dir)
    t_load = time.perf_counter() - t0

    total_columns = sum(len(m.get("columns", [])) for m in models.values())

    print(f"  Models:    {len(models)}")
    print(f"  Sources:   {len(sources)}")
    print(f"  Seeds:     {len(seeds)}")
    print(f"  Snapshots: {len(snapshots)}")
    print(f"  Columns:   {total_columns}")
    print(f"  Dialect:   {dialect}")
    print(f"  Load time: {t_load:.1f}s")

    # Phase 2: Compute subset if requested
    subset = None
    if args.select:
        from docglow.lineage.analyzer import compute_column_lineage_subset

        subset = compute_column_lineage_subset(
            pattern=args.select,
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
        )
        print(f"\n  Subset:    {len(subset)} models (pattern: {args.select})")

    # Phase 3: Run column lineage analysis (the thing we're benchmarking)
    from docglow.lineage.analyzer import analyze_column_lineage

    print("\nRunning column lineage analysis...")
    t1 = time.perf_counter()
    result = analyze_column_lineage(
        models=models,
        sources=sources,
        seeds=seeds,
        snapshots=snapshots,
        dialect=dialect,
        manifest_nodes=dict(manifest.nodes),
        manifest_sources=dict(manifest.sources),
        cache_path=cache_path,
        subset=subset,
        max_workers=args.workers,
    )
    t_lineage = time.perf_counter() - t1

    # Phase 4: Report results
    total_deps = sum(
        len(deps) for model_lineage in result.values() for deps in model_lineage.values()
    )
    traced_columns = sum(len(cols) for cols in result.values())

    print(f"\n{'=' * 50}")
    print("  RESULTS")
    print(f"{'=' * 50}")
    print(f"  Models with lineage:  {len(result)}")
    print(f"  Columns traced:       {traced_columns}")
    print(f"  Total dependencies:   {total_deps}")
    print(f"  Lineage time:         {t_lineage:.1f}s")
    print(f"  Total time:           {t_load + t_lineage:.1f}s")

    if len(models) > 0:
        print(f"  Avg per model:        {t_lineage / len(models) * 1000:.0f}ms")
    if traced_columns > 0:
        print(f"  Avg per column:       {t_lineage / traced_columns * 1000:.0f}ms")

    print(f"  Cache:                {cache_path}")
    print()


if __name__ == "__main__":
    main()
