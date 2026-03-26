"""Column insights engine — orchestrates inference for all models."""

from __future__ import annotations

import logging
from typing import Any

from docglow.insights.descriptions import apply_description, generate_description
from docglow.insights.inference import compute_confidence, infer_role, infer_semantic_type
from docglow.insights.sql_usage import detect_sql_usage

logger = logging.getLogger(__name__)


def enrich_columns(
    docglow_data: dict[str, Any],
    *,
    description_mode: str = "append",
    dialect: str | None = None,
) -> dict[str, Any]:
    """Enrich all columns in the docglow data with inferred insights.

    Mutates column dicts in-place (consistent with existing patterns
    like profiling and column backfill).

    Args:
        docglow_data: The full data dict from build_docglow_data().
        description_mode: How to handle generated descriptions:
            "append" (fill blanks), "replace" (overwrite), "skip" (hands off).
        dialect: SQL dialect for sqlglot parsing.

    Returns:
        The same docglow_data dict (for chaining).
    """
    total_columns = 0
    enriched_columns = 0

    # Enrich models, seeds, snapshots (have compiled SQL)
    for collection_name in ("models", "seeds", "snapshots"):
        collection = docglow_data.get(collection_name, {})
        for uid, model_data in collection.items():
            columns = model_data.get("columns", [])
            if not columns:
                continue

            # Detect SQL usage once per model
            sql = model_data.get("compiled_sql", "") or model_data.get("raw_sql", "")
            column_names = [c["name"] for c in columns]
            sql_usage = detect_sql_usage(sql, column_names, dialect) if sql else {}

            model_name = model_data.get("name", uid.split(".")[-1])

            for col in columns:
                total_columns += 1
                col_usage = sql_usage.get(col["name"], set())
                col_tests = col.get("tests", [])

                semantic_type = infer_semantic_type(col["name"], col.get("data_type", ""))
                role = infer_role(
                    col["name"], col.get("data_type", ""), col_tests, col_usage, semantic_type
                )
                confidence = compute_confidence(role, col_tests, col_usage, semantic_type)
                generated_desc = generate_description(col["name"], role, semantic_type, model_name)

                # Apply description
                col["description"] = apply_description(
                    col.get("description", ""), generated_desc, description_mode
                )

                # Add insights metadata
                col["insights"] = {
                    "role": role,
                    "semantic_type": semantic_type,
                    "sql_usage": sorted(col_usage),
                    "confidence": round(confidence, 2),
                    "generated_description": generated_desc,
                }

                if role is not None:
                    enriched_columns += 1

    # Enrich sources (no SQL, but can infer from tests + naming)
    for uid, source_data in docglow_data.get("sources", {}).items():
        columns = source_data.get("columns", [])
        for col in columns:
            total_columns += 1
            col_tests = col.get("tests", [])

            semantic_type = infer_semantic_type(col["name"], col.get("data_type", ""))
            role = infer_role(
                col["name"], col.get("data_type", ""), col_tests, set(), semantic_type
            )
            confidence = compute_confidence(role, col_tests, set(), semantic_type)
            generated_desc = generate_description(
                col["name"], role, semantic_type, source_data.get("name", "")
            )

            col["description"] = apply_description(
                col.get("description", ""), generated_desc, description_mode
            )

            col["insights"] = {
                "role": role,
                "semantic_type": semantic_type,
                "sql_usage": [],
                "confidence": round(confidence, 2),
                "generated_description": generated_desc,
            }

            if role is not None:
                enriched_columns += 1

    logger.info(
        "Column insights: enriched %d/%d columns with inferred roles",
        enriched_columns,
        total_columns,
    )

    return docglow_data
