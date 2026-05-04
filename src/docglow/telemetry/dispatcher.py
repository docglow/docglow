"""Telemetry dispatcher: the single integration point used by CLI commands.

Owns the gate logic ("should we send?"), payload assembly, and dispatch. CLI
commands use the :func:`record` context manager and remain ignorant of every
other module in this package.

Failures inside this module never raise into the caller.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docglow.telemetry import client, state
from docglow.telemetry.config import ENV_OPT_OUT, TelemetryConfig, parse_tristate
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
    """Return True iff telemetry should fire for this run.

    ``DOCGLOW_NO_TELEMETRY`` is re-checked here because ``config.enabled=False``
    is overloaded between "default off" and "user explicitly opted out", and
    only the env-var presence distinguishes the two -- consent="yes" should
    not beat an explicit opt-out.
    """
    environ = env if env is not None else os.environ
    if parse_tristate(environ.get(ENV_OPT_OUT)) is True:
        return False
    if config.enabled:
        return True
    return consent == "yes"


def _shape_from_resource_types(
    resource_types: Iterable[str],
    sources: int,
    macros: int,
    adapter_raw: object,
) -> ProjectShape:
    """Build a ProjectShape from a stream of resource_type strings + counts.

    Shared core for both the in-memory Manifest and on-disk manifest.json
    paths -- both end up doing the same counting and adapter normalisation.
    """
    models = seeds = tests = 0
    for rt in resource_types:
        if rt == "model":
            models += 1
        elif rt == "seed":
            seeds += 1
        elif rt == "test":
            tests += 1
    adapter_type: str | None = None
    if isinstance(adapter_raw, str) and adapter_raw:
        adapter_type = adapter_raw.lower()
    return ProjectShape(
        models=models,
        sources=sources,
        seeds=seeds,
        tests=tests,
        macros=macros,
        adapter_type=adapter_type,
    )


def project_shape_from_manifest(manifest: Manifest | None) -> ProjectShape:
    """Build an anonymous ProjectShape from an in-memory dbt Manifest."""
    if manifest is None:
        return ProjectShape()
    try:
        nodes = manifest.nodes.values() if hasattr(manifest, "nodes") else ()
        sources = len(manifest.sources) if hasattr(manifest, "sources") and manifest.sources else 0
        macros = len(manifest.macros) if hasattr(manifest, "macros") and manifest.macros else 0
        metadata = getattr(manifest, "metadata", None)
        adapter_raw = getattr(metadata, "adapter_type", None) if metadata is not None else None
        return _shape_from_resource_types(
            (getattr(n, "resource_type", "") for n in nodes),
            sources=sources,
            macros=macros,
            adapter_raw=adapter_raw,
        )
    except Exception as exc:
        logger.debug("telemetry: failed to derive ProjectShape from manifest: %s", exc)
        return ProjectShape()


def project_shape_from_manifest_path(target_dir: str | Path) -> ProjectShape:
    """Lightweight ``manifest.json`` reader for telemetry use.

    Reads only the fields we need without going through pydantic validation.
    Used by commands that don't otherwise hold a Manifest object so they can
    record a meaningful payload without paying for full artifact loading.
    """
    try:
        path = Path(target_dir) / "manifest.json"
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("telemetry: manifest.json peek failed: %s", exc)
        return ProjectShape()

    try:
        nodes = data.get("nodes", {}) or {}
        sources = len(data.get("sources", {}) or {})
        macros = len(data.get("macros", {}) or {})
        adapter_raw = (data.get("metadata") or {}).get("adapter_type")
        return _shape_from_resource_types(
            (n.get("resource_type", "") for n in nodes.values()),
            sources=sources,
            macros=macros,
            adapter_raw=adapter_raw,
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
    project_shape: ProjectShape | None = None,
    features_used: tuple[str, ...] = (),
    consent: state.ConsentValue | None = None,
    state_path: Path | None = None,
    send: bool = True,
) -> dict[str, object] | None:
    """Build and dispatch a telemetry event if telemetry is active.

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
        payload = build_event(
            instance_id=instance_id,
            command=command,
            result=result,
            duration_ms=duration_ms,
            project_shape=project_shape or ProjectShape(),
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
    shape_provider: Callable[[], ProjectShape] | None = None,
    features_used: tuple[str, ...] = (),
) -> Iterator[None]:
    """Time a command and record success/error on exit.

    ``shape_provider`` is invoked only when telemetry is active, so commands
    can pass an expensive thunk (e.g. reading manifest.json from disk) without
    paying for it on the disabled path.
    """
    started = time.monotonic()
    success = False
    try:
        yield
        success = True
    finally:
        try:
            duration_ms = int((time.monotonic() - started) * 1000)
            consent = state.get_consent()
            if not is_active(config, consent):
                return
            shape: ProjectShape | None = None
            if shape_provider is not None:
                try:
                    shape = shape_provider()
                except Exception:
                    shape = None
            record_command(
                config,
                command=command,
                result="success" if success else "error",
                duration_ms=duration_ms,
                project_shape=shape,
                features_used=features_used,
                consent=consent,
            )
        except Exception as exc:
            logger.debug("telemetry: record context exit failed: %s", exc)
