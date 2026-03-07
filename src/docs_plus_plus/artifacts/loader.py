"""Load and validate dbt artifacts from the target directory."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from docs_plus_plus.artifacts.catalog import Catalog
from docs_plus_plus.artifacts.manifest import Manifest
from docs_plus_plus.artifacts.run_results import RunResults
from docs_plus_plus.artifacts.sources import SourceFreshness

logger = logging.getLogger(__name__)


class ArtifactLoadError(Exception):
    """Raised when a required artifact cannot be loaded."""


@dataclass(frozen=True)
class LoadedArtifacts:
    """Container for all loaded dbt artifacts."""

    manifest: Manifest
    catalog: Catalog
    run_results: RunResults | None
    source_freshness: SourceFreshness | None


def _resolve_target_dir(project_dir: Path, target_dir: Path | None) -> Path:
    """Resolve the target directory path."""
    if target_dir is not None:
        if target_dir.is_absolute():
            return target_dir
        return project_dir / target_dir
    return project_dir / "target"


def _load_json(path: Path) -> dict:
    """Load and parse a JSON file with clear error messages."""
    if not path.exists():
        raise ArtifactLoadError(f"File not found: {path}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ArtifactLoadError(f"Cannot read file {path}: {e}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ArtifactLoadError(
            f"Invalid JSON in {path.name}: {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e

    if not isinstance(data, dict):
        raise ArtifactLoadError(f"Expected a JSON object in {path.name}, got {type(data).__name__}")

    return data


def _load_optional_json(path: Path, artifact_name: str) -> dict | None:
    """Load an optional artifact, returning None with a warning if missing."""
    if not path.exists():
        logger.warning("%s not found at %s — skipping", artifact_name, path)
        return None

    try:
        return _load_json(path)
    except ArtifactLoadError as e:
        logger.warning("Could not load %s: %s — skipping", artifact_name, e)
        return None


def load_artifacts(
    project_dir: Path,
    target_dir: Path | None = None,
) -> LoadedArtifacts:
    """Load all dbt artifacts from the target directory.

    Args:
        project_dir: Path to the dbt project root.
        target_dir: Path to the target directory. Defaults to project_dir/target.

    Returns:
        LoadedArtifacts containing all parsed artifacts.

    Raises:
        ArtifactLoadError: If required artifacts (manifest, catalog) cannot be loaded.
    """
    resolved_target = _resolve_target_dir(project_dir, target_dir)

    if not resolved_target.exists():
        raise ArtifactLoadError(
            f"Target directory not found: {resolved_target}. "
            "Have you run 'dbt docs generate'?"
        )

    # Required artifacts
    manifest_data = _load_json(resolved_target / "manifest.json")
    catalog_data = _load_json(resolved_target / "catalog.json")

    manifest = Manifest.model_validate(manifest_data)
    catalog = Catalog.model_validate(catalog_data)

    _log_artifact_info("manifest.json", manifest.metadata.dbt_schema_version)
    _log_artifact_info("catalog.json", catalog.metadata.dbt_schema_version)

    # Optional artifacts
    run_results_data = _load_optional_json(
        resolved_target / "run_results.json", "run_results.json"
    )
    run_results = (
        RunResults.model_validate(run_results_data) if run_results_data is not None else None
    )

    sources_data = _load_optional_json(resolved_target / "sources.json", "sources.json")
    source_freshness = (
        SourceFreshness.model_validate(sources_data) if sources_data is not None else None
    )

    _log_summary(manifest, catalog, run_results, source_freshness)

    return LoadedArtifacts(
        manifest=manifest,
        catalog=catalog,
        run_results=run_results,
        source_freshness=source_freshness,
    )


def _log_artifact_info(filename: str, schema_version: str) -> None:
    """Log artifact schema version for debugging."""
    logger.info("Loaded %s (schema: %s)", filename, schema_version)


def _log_summary(
    manifest: Manifest,
    catalog: Catalog,
    run_results: RunResults | None,
    source_freshness: SourceFreshness | None,
) -> None:
    """Log a summary of loaded artifacts."""
    model_count = sum(
        1 for n in manifest.nodes.values() if n.resource_type == "model"
    )
    test_count = sum(
        1 for n in manifest.nodes.values() if n.resource_type == "test"
    )
    source_count = len(manifest.sources)
    catalog_node_count = len(catalog.nodes) + len(catalog.sources)
    result_count = len(run_results.results) if run_results else 0
    freshness_count = len(source_freshness.results) if source_freshness else 0

    logger.info(
        "Artifacts loaded: %d models, %d tests, %d sources, "
        "%d catalog entries, %d run results, %d freshness results",
        model_count,
        test_count,
        source_count,
        catalog_node_count,
        result_count,
        freshness_count,
    )
