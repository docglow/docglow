"""Build telemetry event payloads.

Pure functions only -- no I/O, no global state. Callers gather the inputs
(``ProjectShape`` from a manifest, command + result + duration_ms from the
dispatcher) and pass them in. The builder returns a v1 payload dict matching
the schema documented in ``docs/telemetry.md``.

The module uses an explicit allow-list for fields. New fields require an
intentional code change here, never an accidental kwargs passthrough -- this
is the load-bearing safeguard against leaking model names, paths, or other
identifying data through a manifest field nobody noticed.
"""

from __future__ import annotations

import platform as _platform
import sys
from dataclasses import dataclass
from typing import Any, Literal

import docglow as _docglow

SCHEMA_VERSION = 1

CommandName = Literal["generate", "health", "serve"]
ResultName = Literal["success", "error"]


@dataclass(frozen=True)
class ProjectShape:
    """Anonymized shape of a dbt project, derived from the manifest.

    Only counts and the adapter type. No names, no paths, no SQL, no columns.
    """

    models: int = 0
    sources: int = 0
    seeds: int = 0
    tests: int = 0
    macros: int = 0
    adapter_type: str | None = None


def _platform_short() -> str:
    """Return a coarse platform name: 'linux', 'darwin', 'windows', or 'other'."""
    system = _platform.system().lower()
    if system in ("linux", "darwin", "windows"):
        return system
    return "other"


def _python_version_short() -> str:
    """Return ``major.minor.micro`` -- no implementation/build suffixes."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def build_event(
    *,
    instance_id: str,
    command: CommandName,
    result: ResultName,
    duration_ms: int,
    project_shape: ProjectShape | None,
    features_used: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a v1 telemetry event payload.

    Returns a JSON-serialisable dict. The shape is fixed; new fields require
    a deliberate edit here and a corresponding update to ``docs/telemetry.md``
    and the snapshot test.
    """
    shape = project_shape or ProjectShape()
    return {
        "schema_version": SCHEMA_VERSION,
        "instance_id": instance_id,
        "command": command,
        "result": result,
        "duration_ms": int(duration_ms),
        "docglow_version": _docglow.__version__,
        "python_version": _python_version_short(),
        "platform": _platform_short(),
        "adapter_type": shape.adapter_type,
        "project_shape": {
            "models": shape.models,
            "sources": shape.sources,
            "seeds": shape.seeds,
            "tests": shape.tests,
            "macros": shape.macros,
        },
        "features_used": list(features_used),
    }
