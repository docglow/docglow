"""Opt-in anonymous telemetry for docglow.

This package implements the CLI side of the telemetry pipeline described in
GitHub issue #24 and the implementation plan
``docglow-private-docs/planning/2026-04-29-001-feat-opt-in-telemetry-plan.md``.

Discipline mirrors :mod:`docglow.cloud_hint`: every code path here must be
safe to run in any environment, must never raise into a calling CLI command,
and must default to *no* network activity until the user explicitly opts in.
"""

from docglow.telemetry.config import TelemetryConfig, resolve_telemetry_config

__all__ = ["TelemetryConfig", "resolve_telemetry_config"]
