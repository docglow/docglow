"""Telemetry dispatcher: the single integration point used by CLI commands.

Owns the gate logic ("should we send?"), payload assembly, and dispatch. CLI
commands call ``record_command`` (or use the ``record`` context manager) and
remain ignorant of every other module in this package.

Gate logic, in order:

    1. ``DOCGLOW_NO_TELEMETRY=1`` -- force off (re-checked here defensively
       even though it is also folded into ``TelemetryConfig.enabled``).
    2. ``config.enabled`` -- env opt-in or yml flag says yes.
    3. ``consent == 'yes'`` -- the user accepted the first-run prompt.

Anything that fails any of these returns silently. Failures inside this
module never raise into the caller.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from docglow.telemetry import client, state
from docglow.telemetry.config import (
    ENV_OPT_OUT,
    TelemetryConfig,
    _parse_tristate,
)
from docglow.telemetry.payload import (
    CommandName,
    ProjectShape,
    ResultName,
    build_event,
)

if TYPE_CHECKING:
    from docglow.artifacts.manifest import Manifest

logger = logging.getLogger(__name__)


def is_active(
    config: TelemetryConfig,
    consent: state.ConsentValue,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True iff telemetry should fire for this run."""
    environ = env if env is not None else os.environ
    if _parse_tristate(environ.get(ENV_OPT_OUT)) is True:
        return False
    if config.enabled:
        return True
    return consent == "yes"


def project_shape_from_manifest(manifest: Manifest | None) -> ProjectShape:
    """Build an anonymous ProjectShape from an in-memory dbt Manifest.

    Returns a zero-shape if the manifest is None or any field access fails.
    """
    if manifest is None:
        return ProjectShape()
    try:
        nodes = manifest.nodes.values() if hasattr(manifest, "nodes") else []
        models = sum(1 for n in nodes if getattr(n, "resource_type", "") == "model")
        seeds = sum(1 for n in nodes if getattr(n, "resource_type", "") == "seed")
        tests = sum(1 for n in nodes if getattr(n, "resource_type", "") == "test")
        sources = len(manifest.sources) if hasattr(manifest, "sources") and manifest.sources else 0
        macros = len(manifest.macros) if hasattr(manifest, "macros") and manifest.macros else 0
        adapter_type: str | None = None
        metadata = getattr(manifest, "metadata", None)
        if metadata is not None:
            raw = getattr(metadata, "adapter_type", None)
            if isinstance(raw, str) and raw:
                adapter_type = raw.lower()
        return ProjectShape(
            models=models,
            sources=sources,
            seeds=seeds,
            tests=tests,
            macros=macros,
            adapter_type=adapter_type,
        )
    except Exception as exc:
        logger.debug("telemetry: failed to derive ProjectShape from manifest: %s", exc)
        return ProjectShape()


def project_shape_from_manifest_path(target_dir: str | Path) -> ProjectShape:
    """Lightweight manifest.json reader for telemetry use.

    Reads only the fields we need (node resource_types, source/macro counts,
    adapter_type) without going through pydantic validation. Used by CLI
    commands that don't otherwise hold a Manifest object so they can record
    a meaningful payload without paying for full artifact loading.

    Returns ProjectShape() on any failure -- this must never break the
    calling command.
    """
    import json

    try:
        path = Path(target_dir) / "manifest.json"
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.debug("telemetry: manifest.json peek failed: %s", exc)
        return ProjectShape()

    try:
        nodes = data.get("nodes", {}) or {}
        models = sum(1 for n in nodes.values() if n.get("resource_type") == "model")
        seeds = sum(1 for n in nodes.values() if n.get("resource_type") == "seed")
        tests = sum(1 for n in nodes.values() if n.get("resource_type") == "test")
        sources = len(data.get("sources", {}) or {})
        macros = len(data.get("macros", {}) or {})
        adapter_type = None
        metadata = data.get("metadata") or {}
        raw = metadata.get("adapter_type")
        if isinstance(raw, str) and raw:
            adapter_type = raw.lower()
        return ProjectShape(
            models=models,
            sources=sources,
            seeds=seeds,
            tests=tests,
            macros=macros,
            adapter_type=adapter_type,
        )
    except Exception as exc:
        logger.debug("telemetry: manifest.json parse failed: %s", exc)
        return ProjectShape()


def record_command(
    config: TelemetryConfig,
    *,
    command: CommandName,
    result: ResultName,
    duration_ms: int,
    manifest: Manifest | None = None,
    project_shape: ProjectShape | None = None,
    features_used: tuple[str, ...] = (),
    consent: state.ConsentValue | None = None,
    state_path: Path | None = None,
    send: bool = True,
) -> dict[str, object] | None:
    """Build and dispatch a telemetry event if telemetry is active.

    Pass ``project_shape`` directly when the caller already has it, or
    ``manifest`` (an in-memory Manifest) for the dispatcher to derive shape.
    If both are None the payload reports a zero shape -- still valid for
    commands like ``serve`` that don't necessarily have a manifest at hand.

    Returns the payload that was (or would have been) sent, or None when
    telemetry is inactive. Useful for tests; production callers ignore the
    return value.

    Never raises.
    """
    try:
        resolved_consent = consent if consent is not None else state.get_consent(state_path)
        if not is_active(config, resolved_consent):
            return None

        instance_id = state.get_instance_id(state_path)
        if project_shape is None:
            project_shape = project_shape_from_manifest(manifest)
        payload = build_event(
            instance_id=instance_id,
            command=command,
            result=result,
            duration_ms=duration_ms,
            project_shape=project_shape,
            features_used=features_used,
        )
        if send:
            client.send(payload, config.endpoint)
        return payload
    except Exception as exc:
        logger.debug("telemetry: record_command failed: %s", exc)
        return None


@contextmanager
def record(
    config: TelemetryConfig,
    *,
    command: CommandName,
    manifest_provider: Callable[[], Manifest | None] | None = None,
    features_used: tuple[str, ...] = (),
) -> Iterator[None]:
    """Context manager that times a command and records success/error on exit.

    ``manifest_provider`` is an optional zero-arg callable returning the
    Manifest (or None). Called inside the ``finally`` block so it picks up
    a manifest that was loaded mid-command, even on error.
    """
    started = time.monotonic()
    success = False
    try:
        yield
        success = True
    finally:
        try:
            duration_ms = int((time.monotonic() - started) * 1000)
            manifest = None
            if manifest_provider is not None:
                try:
                    manifest = manifest_provider()
                except Exception:
                    manifest = None
            record_command(
                config,
                command=command,
                result="success" if success else "error",
                duration_ms=duration_ms,
                manifest=manifest,
                features_used=features_used,
            )
        except Exception as exc:
            logger.debug("telemetry: record context exit failed: %s", exc)
