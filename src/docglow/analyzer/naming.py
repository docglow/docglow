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


def _detect_layer(folder: str, path: str) -> str | None:
    """Detect the dbt layer from folder structure."""
    combined = (folder + "/" + path).lower()
    if "staging" in combined or "/stg" in combined:
        return "staging"
    if "intermediate" in combined or "/int" in combined:
        return "intermediate"
    if "marts" in combined:
        # Check for fact vs dimension based on name prefix later
        return "marts"
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

        layer = _detect_layer(folder, path)
        if layer is None:
            continue

        total_checked += 1

        if layer == "staging":
            if not re.match(rules.staging, name):
                violations.append(
                    NamingViolation(
                        unique_id=uid,
                        name=name,
                        folder=folder,
                        expected_pattern=rules.staging,
                        layer=layer,
                    )
                )
        elif layer == "intermediate":
            if not re.match(rules.intermediate, name):
                violations.append(
                    NamingViolation(
                        unique_id=uid,
                        name=name,
                        folder=folder,
                        expected_pattern=rules.intermediate,
                        layer=layer,
                    )
                )
        elif layer == "marts":
            # Marts models should start with fct_ or dim_
            matches_fact = re.match(rules.marts_fact, name)
            matches_dim = re.match(rules.marts_dimension, name)
            if not matches_fact and not matches_dim:
                violations.append(
                    NamingViolation(
                        unique_id=uid,
                        name=name,
                        folder=folder,
                        expected_pattern=f"{rules.marts_fact} or {rules.marts_dimension}",
                        layer=layer,
                    )
                )

    compliant = total_checked - len(violations)
    return NamingReport(
        total_checked=total_checked,
        compliant_count=compliant,
        violations=violations,
    )
