"""Naming convention compliance checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from docglow.config import NamingRules


@dataclass(frozen=True)
class NamingViolation:
    unique_id: str
    name: str
    folder: str
    expected_pattern: str
    layer: str


@dataclass(frozen=True)
class NamingReport:
    total_checked: int
    compliant_count: int
    violations: list[NamingViolation]

    @property
    def compliance_rate(self) -> float:
        if self.total_checked == 0:
            return 1.0
        return self.compliant_count / self.total_checked


def _detect_layer(folder: str, path: str, rules: NamingRules) -> str | None:
    """Detect the dbt layer from folder structure using configured rule names.

    Matches layer names against individual path segments to avoid false
    positives (e.g. layer "int" won't match a folder named "internal").
    """
    segments = set((folder + "/" + path).lower().replace("\\", "/").split("/"))
    for layer_name in rules.layers():
        if layer_name in segments:
            return layer_name
    return None


def check_naming(
    models: dict[str, dict[str, Any]],
    rules: NamingRules | None = None,
) -> NamingReport:
    """Check model naming conventions against configured rules."""
    if rules is None:
        rules = NamingRules()

    violations: list[NamingViolation] = []
    total_checked = 0

    for uid, model in models.items():
        name = model.get("name", "")
        folder = model.get("folder", "")
        path = model.get("path", "")

        layer = _detect_layer(folder, path, rules)
        if layer is None:
            continue

        patterns = rules.patterns_for(layer)
        if not patterns:
            continue

        total_checked += 1

        if not any(re.match(p, name) for p in patterns):
            violations.append(
                NamingViolation(
                    unique_id=uid,
                    name=name,
                    folder=folder,
                    expected_pattern=" or ".join(patterns),
                    layer=layer,
                )
            )

    compliant = total_checked - len(violations)
    return NamingReport(
        total_checked=total_checked,
        compliant_count=compliant,
        violations=violations,
    )
