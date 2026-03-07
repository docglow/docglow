"""Static site generator — orchestrates artifact loading, transformation, and bundling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from docs_plus_plus.artifacts.loader import load_artifacts
from docs_plus_plus.generator.bundle import bundle_site
from docs_plus_plus.generator.data import build_datum_data

logger = logging.getLogger(__name__)


def generate_site(
    project_dir: Path,
    target_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    static: bool = False,
    profiling_enabled: bool = False,
    profiling_adapter: str | None = None,
    profiling_connection: dict[str, Any] | None = None,
    profiling_sample_size: int | None = None,
    profiling_cache: bool = True,
    ai_enabled: bool = False,
    title: str | None = None,
    select: str | None = None,
    exclude: str | None = None,
) -> Path:
    """Generate the docs-plus-plus static site.

    Args:
        project_dir: Path to the dbt project root.
        target_dir: Path to the dbt target directory.
        output_dir: Where to write the generated site. Defaults to target/datum.
        static: If True, bundle everything into a single index.html.
        profiling_enabled: Whether column profiling data is included.
        profiling_adapter: Database adapter (duckdb, postgres, snowflake).
        profiling_connection: Connection params for the adapter.
        profiling_sample_size: Max rows to sample per model.
        profiling_cache: Whether to cache profiling results.
        ai_enabled: Whether to enable the AI chat panel.
        title: Custom site title.
        select: Only include models matching this pattern.
        exclude: Exclude models matching this pattern.

    Returns:
        Path to the output directory.
    """
    resolved_output = output_dir or (project_dir / "target" / "datum")
    resolved_output.mkdir(parents=True, exist_ok=True)

    logger.info("Loading dbt artifacts...")
    artifacts = load_artifacts(project_dir, target_dir)

    logger.info("Building data payload...")
    datum_data = build_datum_data(
        artifacts,
        profiling_enabled=profiling_enabled,
        ai_enabled=ai_enabled,
        select=select,
        exclude=exclude,
    )

    # Run profiling if enabled
    if profiling_enabled and profiling_adapter and profiling_connection:
        _run_profiling(
            datum_data,
            adapter=profiling_adapter,
            connection_params=profiling_connection,
            sample_size=profiling_sample_size,
            cache_dir=resolved_output if profiling_cache else None,
        )

    if title:
        datum_data["metadata"]["project_name"] = title

    logger.info("Bundling site...")
    bundle_site(datum_data, resolved_output, static=static)

    file_count = len(list(resolved_output.iterdir()))
    logger.info("Site generated at %s (%d files)", resolved_output, file_count)

    return resolved_output


def _run_profiling(
    datum_data: dict[str, Any],
    adapter: str,
    connection_params: dict[str, Any],
    sample_size: int | None,
    cache_dir: Path | None,
) -> None:
    """Run profiling and apply results to datum_data models in-place."""
    from docs_plus_plus.profiler.engine import apply_profiles, profile_models

    logger.info("Running column profiling...")
    profiles = profile_models(
        datum_data["models"],
        adapter=adapter,
        connection_params=connection_params,
        sample_size=sample_size,
        cache_dir=cache_dir,
    )

    if profiles:
        datum_data["models"] = apply_profiles(datum_data["models"], profiles)
        datum_data["metadata"]["profiling_enabled"] = True
