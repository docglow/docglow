"""Publish command implementation for docglow Cloud."""

from __future__ import annotations

import logging
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from docglow.cloud.client import CloudApiError, CloudClient
from docglow.cloud.config import CloudConfig
from docglow.config import CONFIG_FILENAMES

logger = logging.getLogger(__name__)

ARTIFACT_FILES = [
    "manifest.json",
    "catalog.json",
    "run_results.json",
    "sources.json",
    "profiles.json",
]


def run_publish(
    config: CloudConfig,
    project_dir: Path,
    target_dir: Path | None = None,
    *,
    no_wait: bool = False,
) -> dict[str, Any]:
    """Publish dbt artifacts to docglow Cloud.

    Args:
        config: Cloud configuration with token and API URL.
        project_dir: Path to the dbt project root.
        target_dir: Path to the target directory containing artifacts.
        no_wait: If True, return immediately after upload without waiting.

    Returns:
        Publish result dict with status, site_url, health info.

    Raises:
        CloudApiError: If the API returns an error.
        FileNotFoundError: If no artifacts are found.
    """
    resolved_target = target_dir or (project_dir / "target")

    if not resolved_target.exists():
        raise FileNotFoundError(
            f"Target directory not found: {resolved_target}. "
            "Run 'dbt build' first to generate artifacts."
        )

    # Find available artifacts
    found_artifacts = _find_artifacts(resolved_target)
    if not found_artifacts:
        raise FileNotFoundError(
            f"No dbt artifacts found in {resolved_target}. "
            "Expected at least manifest.json and catalog.json."
        )

    logger.info("Found %d artifact files", len(found_artifacts))

    # Ship the author's docglow.yml (from the project root) alongside the dbt
    # artifacts so Cloud renders custom layer rules + ERD preference. Optional —
    # absence just means Cloud uses defaults.
    config_file = _find_config_file(project_dir)
    bundle = found_artifacts + ([config_file] if config_file else [])

    # Create tarball
    tarball_path = _create_tarball(bundle)

    try:
        client = CloudClient(config)
        try:
            # Upload
            logger.info("Uploading artifacts to docglow Cloud...")
            result = client.publish(tarball_path)
            data = result.get("data", result)
            publish_id = data.get("publish_id", "")

            if no_wait:
                logger.info("Upload complete. Publish ID: %s", publish_id)
                return result

            # Poll for completion
            logger.info("Processing...")
            status = _poll_status(client, publish_id)
            return status
        finally:
            client.close()
    finally:
        tarball_path.unlink(missing_ok=True)


def _find_artifacts(target_dir: Path) -> list[Path]:
    """Find dbt artifact files in the target directory."""
    found: list[Path] = []
    for name in ARTIFACT_FILES:
        path = target_dir / name
        if path.exists():
            found.append(path)
    return found


def _find_config_file(project_dir: Path) -> Path | None:
    """Return the project's docglow config file (root), or None if absent.

    Shipped from the project root (not target/) so Cloud renders the project's
    own layer rules + ERD preference instead of OSS defaults. First match wins;
    absence is fine (Cloud falls back to defaults).
    """
    for name in CONFIG_FILENAMES:
        path = project_dir / name
        if path.exists():
            return path
    return None


def _create_tarball(artifacts: list[Path]) -> Path:
    """Create a compressed tarball of artifact files."""
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp.close()
    tarball_path = Path(tmp.name)

    with tarfile.open(tarball_path, "w:gz") as tar:
        for artifact in artifacts:
            tar.add(artifact, arcname=artifact.name)

    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    logger.info("Created artifacts tarball: %.1f MB", size_mb)

    return tarball_path


def _poll_status(
    client: CloudClient,
    publish_id: str,
    *,
    timeout: int = 300,
    interval: int = 3,
) -> dict[str, Any]:
    """Poll publish status until complete or timeout."""
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        response = client.get_publish_status(publish_id)
        data = response.get("data", response)
        status: dict[str, Any] = data if isinstance(data, dict) else response
        state = status.get("status", "")

        if state == "complete":
            return status
        if state == "failed":
            error_msg = status.get("error_message", "Unknown error")
            raise CloudApiError(f"Publish failed: {error_msg}")

        time.sleep(interval)

    raise CloudApiError(f"Publish timed out after {timeout}s (ID: {publish_id})")
