"""Publish command implementation for docglow Cloud."""

from __future__ import annotations

import logging
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from docglow.cloud.client import (
    LEGACY_UPLOAD_LIMIT_BYTES,
    CloudApiError,
    CloudClient,
    CloudUploadUrlUnsupportedError,
)
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
            result = _upload_and_finalize(client, tarball_path)
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


def _upload_and_finalize(client: CloudClient, tarball_path: Path) -> dict[str, Any]:
    """Upload the tarball to Cloud and record the publish.

    Three steps, because the artifact cannot travel through the API: the hosting
    platform rejects request bodies over ~4.5 MB at the edge, and a real dbt
    project's artifacts exceed that compressed. So the CLI asks for a storage URL,
    uploads straight to storage, and then records the publish over a small JSON
    call.
    """
    size = tarball_path.stat().st_size

    try:
        upload = client.create_upload_url()
    except CloudUploadUrlUnsupportedError:
        return _publish_inline_fallback(client, tarball_path, size)

    # The server owns this number; validating against it rather than a local copy
    # means the limit can change without shipping a new CLI. Checking before the
    # upload turns a multi-minute transfer that was always going to fail into an
    # immediate error.
    max_bytes = upload.get("max_bytes")
    if isinstance(max_bytes, int) and size > max_bytes:
        raise CloudApiError(
            f"Artifacts are {size / (1024 * 1024):.1f} MB, over the "
            f"{max_bytes / (1024 * 1024):.0f} MB limit for your workspace. "
            "Contact support@docglow.com if you need a higher limit."
        )

    logger.info("Uploading artifacts to docglow Cloud...")
    _upload_with_progress(client, upload["upload_url"], tarball_path, size)

    return client.finalize_publish(expected_version=upload.get("expected_version"))


def _upload_with_progress(
    client: CloudClient, upload_url: str, tarball_path: Path, size: int
) -> None:
    """Upload with a progress bar when the terminal can show one.

    The upload is now a visible multi-minute step on a slow uplink rather than one
    opaque request, so silence reads as a hang. `rich` is already a dependency; if
    importing it fails for any reason, fall back to a plain upload rather than
    letting a cosmetic feature break publishing.
    """
    try:
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            TimeRemainingColumn,
            TransferSpeedColumn,
        )
    except ImportError:  # pragma: no cover - rich is a hard dependency
        client.upload_artifacts(upload_url, tarball_path)
        return

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Uploading artifacts", total=size)
        client.upload_artifacts(
            upload_url,
            tarball_path,
            on_progress=lambda advanced: progress.advance(task, advanced),
        )


def _publish_inline_fallback(client: CloudClient, tarball_path: Path, size: int) -> dict[str, Any]:
    """Publish via the deprecated inline endpoint, for a Cloud that predates it.

    Only worth attempting for a small tarball. Above the platform's request-body
    ceiling the fallback is guaranteed to fail with an opaque 413, so say what is
    actually wrong instead of letting the user watch a doomed upload.
    """
    if size > LEGACY_UPLOAD_LIMIT_BYTES:
        raise CloudApiError(
            f"This docglow Cloud server does not support large uploads yet, and "
            f"your artifacts are {size / (1024 * 1024):.1f} MB (the inline upload "
            f"limit is {LEGACY_UPLOAD_LIMIT_BYTES / (1024 * 1024):.0f} MB). "
            "Upgrade the server, or contact support@docglow.com."
        )

    logger.info("Uploading artifacts to docglow Cloud (legacy inline upload)...")
    return client.publish(tarball_path)


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
