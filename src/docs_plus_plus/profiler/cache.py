"""Profile caching to avoid re-profiling unchanged models."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CACHE_FILENAME = "profiles.json"


def _schema_hash(columns: list[dict[str, Any]], row_count: int | None) -> str:
    """Generate a hash of a model's schema for change detection."""
    sig = json.dumps(
        {
            "columns": [(c.get("name", ""), c.get("data_type", "")) for c in columns],
            "row_count": row_count,
        },
        sort_keys=True,
    )
    return hashlib.sha256(sig.encode()).hexdigest()[:16]


def load_cache(cache_dir: Path) -> dict[str, Any]:
    """Load the profile cache from disk."""
    cache_path = cache_dir / CACHE_FILENAME
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load profile cache: %s", e)
        return {}


def save_cache(cache_dir: Path, cache: dict[str, Any]) -> None:
    """Save the profile cache to disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / CACHE_FILENAME
    cache_path.write_text(json.dumps(cache, indent=2))


def is_cached(
    cache: dict[str, Any],
    model_id: str,
    columns: list[dict[str, Any]],
    row_count: int | None,
) -> bool:
    """Check if a model's profile is cached and still valid."""
    entry = cache.get(model_id)
    if entry is None:
        return False
    current_hash = _schema_hash(columns, row_count)
    return entry.get("schema_hash") == current_hash


def get_cached_profiles(
    cache: dict[str, Any],
    model_id: str,
) -> dict[str, dict[str, Any]] | None:
    """Get cached column profiles for a model."""
    entry = cache.get(model_id)
    if entry is None:
        return None
    return entry.get("profiles")


def update_cache(
    cache: dict[str, Any],
    model_id: str,
    columns: list[dict[str, Any]],
    row_count: int | None,
    profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return a new cache dict with updated profiles for a model."""
    return {
        **cache,
        model_id: {
            "schema_hash": _schema_hash(columns, row_count),
            "profiles": profiles,
        },
    }
