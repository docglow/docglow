"""Template-based description generation for columns."""

from __future__ import annotations

# Map of role -> template function
_TIMESTAMP_EVENTS: dict[str, str] = {
    "created": "creation",
    "updated": "last update",
    "deleted": "deletion",
    "completed": "completion",
    "started": "start",
    "ended": "end",
    "closed": "closure",
    "opened": "opening",
    "submitted": "submission",
    "approved": "approval",
    "rejected": "rejection",
    "expired": "expiration",
    "published": "publishing",
    "modified": "modification",
    "canceled": "cancellation",
    "exported": "export",
    "imported": "import",
    "activated": "activation",
}


def _humanize(name: str) -> str:
    """Convert snake_case to human-readable: order_total_cents → order total cents."""
    return name.replace("_", " ")


def _extract_entity(column_name: str) -> str:
    """Extract entity name from a foreign key column: user_id → user."""
    lower = column_name.lower()
    for suffix in ("_id", "_key", "_fk"):
        if lower.endswith(suffix):
            return _humanize(column_name[: -len(suffix)])
    return _humanize(column_name)


def _extract_event(column_name: str) -> str:
    """Extract event description from a timestamp column."""
    lower = column_name.lower()
    # Strip common suffixes
    for suffix in ("_at", "_dttm", "_date", "_time", "_timestamp", "_ts"):
        if lower.endswith(suffix):
            stem = column_name[: -len(suffix)].lower()
            # Check known event mappings
            for key, event in _TIMESTAMP_EVENTS.items():
                if stem.endswith(key) or stem == key:
                    return event
            return _humanize(stem)
    return _humanize(column_name)


def generate_description(
    column_name: str,
    role: str | None,
    semantic_type: str | None,
    model_name: str,
) -> str | None:
    """Generate a template-based description for a column.

    Returns None if no description can be generated.
    """
    if role is None:
        return None

    if role == "primary_key":
        return f"Unique identifier for each record in {model_name}."

    if role == "foreign_key":
        entity = _extract_entity(column_name)
        return f"References a related {entity} record."

    if role == "timestamp":
        event = _extract_event(column_name)
        return f"Timestamp recording when the {event} occurred."

    if role == "metric":
        return f"Numeric measure: {_humanize(column_name)}."

    if role == "categorical":
        return f"Category or classification: {_humanize(column_name)}."

    if role == "dimension":
        return f"Descriptive attribute: {_humanize(column_name)}."

    return None


def apply_description(
    existing: str,
    generated: str | None,
    mode: str,
) -> str:
    """Apply a generated description according to the configured mode.

    Modes:
        append: Use generated description only when existing is empty.
        replace: Always use generated description (if available).
        skip: Never modify the existing description.
    """
    if mode == "skip":
        return existing

    if mode == "replace":
        return generated if generated is not None else existing

    # Default: "append" — fill blanks only
    if not existing and generated:
        return generated

    return existing
