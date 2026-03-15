"""Resolve Jinja ref() and source() calls in dbt manifest raw_code.

Produces a modified manifest with compiled_code populated for models
that only use ref(), source(), config(), and simple var() calls.
Complex Jinja (if/for/macro blocks, custom macros) is handled on a
best-effort basis.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def build_ref_map(manifest: dict) -> dict[str, str]:
    """Build model name -> relation_name mapping from manifest nodes."""
    ref_map: dict[str, str] = {}
    for uid, node in manifest.get("nodes", {}).items():
        name = node.get("name", "")
        relation = node.get("relation_name", "")
        if name and relation:
            ref_map[name] = relation
            # Also map by unique_id for cross-project refs
            ref_map[uid] = relation
    return ref_map


def build_source_map(manifest: dict) -> dict[str, str]:
    """Build (source_name, table_name) -> relation_name mapping."""
    source_map: dict[str, str] = {}
    for uid, src in manifest.get("sources", {}).items():
        source_name = src.get("source_name", "")
        table_name = src.get("name", "")
        relation = src.get("relation_name", "")
        if source_name and table_name and relation:
            key = f"{source_name}.{table_name}"
            source_map[key] = relation
    return source_map


def build_var_map(manifest: dict) -> dict[str, str]:
    """Extract project-level vars from manifest metadata."""
    var_map: dict[str, str] = {}
    project = manifest.get("metadata", {})
    if "vars" in project:
        for k, v in project["vars"].items():
            if isinstance(v, str | int | float | bool):
                var_map[k] = str(v)
    return var_map


def resolve_ref(match: re.Match, ref_map: dict[str, str]) -> str:
    """Replace {{ ref('model_name') }} with relation_name."""
    args = match.group(1).strip()
    # Handle ref('model_name') and ref('package', 'model_name')
    names = re.findall(r"""['"]([^'"]+)['"]""", args)
    if len(names) == 1:
        model_name = names[0]
    elif len(names) == 2:
        model_name = names[1]  # second arg is the model name
    else:
        return match.group(0)  # Can't parse, leave as-is

    relation = ref_map.get(model_name)
    if relation:
        return relation
    return match.group(0)


def resolve_source(match: re.Match, source_map: dict[str, str]) -> str:
    """Replace {{ source('source_name', 'table_name') }} with relation_name."""
    args = match.group(1).strip()
    names = re.findall(r"""['"]([^'"]+)['"]""", args)
    if len(names) != 2:
        return match.group(0)

    key = f"{names[0]}.{names[1]}"
    relation = source_map.get(key)
    if relation:
        return relation
    return match.group(0)


def strip_config_block(sql: str) -> str:
    """Remove {{ config(...) }} blocks."""
    return re.sub(r"\{\{\s*config\s*\(.*?\)\s*\}\}", "", sql, flags=re.DOTALL)


def strip_jinja_comments(sql: str) -> str:
    """Remove {# ... #} Jinja comments."""
    return re.sub(r"\{#.*?#\}", "", sql, flags=re.DOTALL)


def resolve_simple_vars(sql: str, var_map: dict[str, str]) -> str:
    """Replace {{ var('name', 'default') }} with the value or default."""

    def replace_var(match: re.Match) -> str:
        args = match.group(1).strip()
        parts = re.findall(r"""['"]([^'"]+)['"]""", args)
        if len(parts) >= 1:
            var_name = parts[0]
            if var_name in var_map:
                return f"'{var_map[var_name]}'"
            # Use default if provided
            if len(parts) >= 2:
                return f"'{parts[1]}'"
        # Try numeric defaults
        numeric = re.findall(r",\s*(\d+(?:\.\d+)?)\s*\)", args)
        if numeric:
            return numeric[0]
        return match.group(0)

    return re.sub(r"\{\{\s*var\s*\((.*?)\)\s*\}\}", replace_var, sql, flags=re.DOTALL)


def resolve_this(sql: str, relation_name: str) -> str:
    """Replace {{ this }} with the model's own relation_name."""
    return re.sub(r"\{\{\s*this\s*\}\}", relation_name, sql)


def strip_simple_jinja_blocks(sql: str) -> str:
    """Best-effort removal of simple if/for/set blocks.

    Handles patterns like:
      {% if ... %} ... {% endif %}
      {% for ... %} ... {% endfor %}
      {% set ... %}
      {% do ... %}
    """
    # Remove {% set var = value %}
    sql = re.sub(r"\{%[-]?\s*set\s+\w+\s*=.*?%\}", "", sql, flags=re.DOTALL)

    # Remove {% do ... %}
    sql = re.sub(r"\{%[-]?\s*do\s+.*?%\}", "", sql, flags=re.DOTALL)

    # Simple if blocks: keep the content inside, strip the tags
    # This is a heuristic — we keep the "then" branch and strip else
    # Pattern: {% if ... %} CONTENT {% else %} ELSE_CONTENT {% endif %}
    # We keep CONTENT
    sql = re.sub(
        r"\{%[-]?\s*if\s+.*?%\}(.*?)\{%[-]?\s*else\s*%\}.*?\{%[-]?\s*endif\s*[-]?%\}",
        r"\1",
        sql,
        flags=re.DOTALL,
    )
    # Pattern without else: {% if ... %} CONTENT {% endif %}
    sql = re.sub(
        r"\{%[-]?\s*if\s+.*?%\}(.*?)\{%[-]?\s*endif\s*[-]?%\}",
        r"\1",
        sql,
        flags=re.DOTALL,
    )

    # For loops: keep the body (it'll have ref/source already resolved)
    sql = re.sub(
        r"\{%[-]?\s*for\s+.*?%\}(.*?)\{%[-]?\s*endfor\s*[-]?%\}",
        r"\1",
        sql,
        flags=re.DOTALL,
    )

    return sql


def resolve_env_vars(sql: str) -> str:
    """Replace {{ env_var('NAME', 'default') }} with the default or placeholder."""

    def replace_env(match: re.Match) -> str:
        args = match.group(1).strip()
        parts = re.findall(r"""['"]([^'"]+)['"]""", args)
        if len(parts) >= 2:
            return f"'{parts[1]}'"  # Use default
        return "'ENV_PLACEHOLDER'"

    return re.sub(r"\{\{\s*env_var\s*\((.*?)\)\s*\}\}", replace_env, sql, flags=re.DOTALL)


def resolve_target_vars(sql: str) -> str:
    """Replace {{ target.name }}, {{ target.schema }}, etc."""
    sql = re.sub(r"\{\{\s*target\.name\s*\}\}", "'resolved_target'", sql)
    sql = re.sub(r"\{\{\s*target\.schema\s*\}\}", "'analytics'", sql)
    sql = re.sub(r"\{\{\s*target\.database\s*\}\}", "'analytics'", sql)
    sql = re.sub(r"\{\{\s*target\.\w+\s*\}\}", "'target_value'", sql)
    return sql


def has_unresolved_jinja(sql: str) -> bool:
    """Check if any Jinja expressions remain."""
    return bool(re.search(r"\{\{.*?\}\}|\{%.*?%\}", sql, flags=re.DOTALL))


def resolve_model(
    node: dict,
    ref_map: dict[str, str],
    source_map: dict[str, str],
    var_map: dict[str, str],
) -> tuple[str, bool]:
    """Resolve a single model's raw_code into compiled_code.

    Returns (compiled_sql, success).
    """
    raw = node.get("raw_code", "") or ""
    if not raw.strip():
        return "", False

    relation_name = node.get("relation_name", "")

    sql = raw
    sql = strip_jinja_comments(sql)
    sql = strip_config_block(sql)
    sql = resolve_env_vars(sql)
    sql = resolve_target_vars(sql)
    sql = resolve_simple_vars(sql, var_map)
    sql = resolve_this(sql, relation_name)

    # Resolve ref() calls
    sql = re.sub(
        r"\{\{\s*ref\s*\((.*?)\)\s*\}\}",
        lambda m: resolve_ref(m, ref_map),
        sql,
        flags=re.DOTALL,
    )

    # Resolve source() calls
    sql = re.sub(
        r"\{\{\s*source\s*\((.*?)\)\s*\}\}",
        lambda m: resolve_source(m, source_map),
        sql,
        flags=re.DOTALL,
    )

    # Strip remaining simple Jinja blocks
    sql = strip_simple_jinja_blocks(sql)

    # Clean up any remaining Jinja tags we couldn't resolve
    # (custom macros, adapter calls, etc.)
    remaining_jinja = re.findall(r"\{\{.*?\}\}|\{%.*?%\}", sql, flags=re.DOTALL)
    unresolved_count = len(remaining_jinja)

    # Strip unresolved Jinja expressions (replace with empty string)
    sql = re.sub(r"\{\{.*?\}\}", "", sql, flags=re.DOTALL)
    sql = re.sub(r"\{%.*?%\}", "", sql, flags=re.DOTALL)

    # Clean up multiple blank lines
    sql = re.sub(r"\n{3,}", "\n\n", sql)

    success = unresolved_count == 0
    return sql.strip(), success


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: resolve_refs.py <manifest.json> [output.json] [--select model_name]")
        sys.exit(1)

    manifest_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    )

    # Optional: select a specific model and its upstream
    select_model = None
    for i, arg in enumerate(sys.argv):
        if arg == "--select" and i + 1 < len(sys.argv):
            select_model = sys.argv[i + 1]

    with open(manifest_path) as f:
        manifest = json.load(f)

    ref_map = build_ref_map(manifest)
    source_map = build_source_map(manifest)
    var_map = build_var_map(manifest)

    # Determine which models to resolve
    if select_model:
        # Find the full unique_id
        target_uid = None
        for uid in manifest["nodes"]:
            if (
                uid.endswith(f".{select_model}")
                and manifest["nodes"][uid]["resource_type"] == "model"
            ):
                target_uid = uid
                break

        if not target_uid:
            print(f"Model '{select_model}' not found in manifest")
            sys.exit(1)

        # Get all upstream
        def get_upstream(node_id: str, parent_map: dict, visited: set | None = None) -> set:
            if visited is None:
                visited = set()
            if node_id in visited:
                return visited
            visited.add(node_id)
            for p in parent_map.get(node_id, []):
                get_upstream(p, parent_map, visited)
            return visited

        upstream = get_upstream(target_uid, manifest.get("parent_map", {}))
        model_uids = {uid for uid in upstream if uid.startswith("model.")}
        print(f"Selected {len(model_uids)} models upstream of {select_model}")
    else:
        model_uids = {
            uid for uid, node in manifest["nodes"].items() if node["resource_type"] == "model"
        }

    # Resolve each model
    total = 0
    resolved_clean = 0
    resolved_partial = 0
    failed = 0

    for uid in sorted(model_uids):
        node = manifest["nodes"].get(uid)
        if not node:
            continue

        total += 1
        compiled_sql, success = resolve_model(node, ref_map, source_map, var_map)

        if compiled_sql:
            node["compiled_code"] = compiled_sql
            if success:
                resolved_clean += 1
            else:
                resolved_partial += 1
        else:
            failed += 1

    clean_pct = resolved_clean * 100 // total
    partial_pct = resolved_partial * 100 // total
    total_ok = resolved_clean + resolved_partial
    total_pct = total_ok * 100 // total
    print(f"\nResults ({total} models):")
    print(f"  Clean resolve (no Jinja):   {resolved_clean} ({clean_pct}%)")
    print(f"  Partial (Jinja stripped):   {resolved_partial} ({partial_pct}%)")
    print(f"  Failed (empty SQL):         {failed}")
    print(f"  Total with compiled_code:   {total_ok} ({total_pct}%)")

    # Write output
    if output_path:
        with open(output_path, "w") as f:
            json.dump(manifest, f, separators=(",", ":"))
        print(f"\nWritten to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        # Overwrite in place
        default_out = manifest_path.parent / "manifest_resolved.json"
        with open(default_out, "w") as f:
            json.dump(manifest, f, separators=(",", ":"))
        print(f"\nWritten to {default_out} ({default_out.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
