"""docglow.yml health settings must reach the scorer (#67).

`load_config` parsed the `health:` section, but neither `docglow generate` nor
`docglow health` passed it on, so every project was scored with the defaults.
These tests drive both commands end to end against the fixture artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from docglow.cli import cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"

DOCUMENTATION_ONLY = """\
health:
  weights:
    documentation: 1.0
    testing: 0.0
    freshness: 0.0
    complexity: 0.0
    naming: 0.0
    orphans: 0.0
"""

STRICT_THRESHOLDS_AND_NAMING = """\
health:
  complexity:
    high_sql_lines: 1
  naming_rules:
    staging: "^never_matches_"
"""


@pytest.fixture(autouse=True)
def _quiet_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCGLOW_NO_TELEMETRY", "1")
    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")


def _project(tmp_path: Path, docglow_yml: str | None) -> Path:
    target = tmp_path / "target"
    target.mkdir(parents=True)
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        (target / name).write_text((FIXTURES_DIR / name).read_text())
    if docglow_yml is not None:
        (tmp_path / "docglow.yml").write_text(docglow_yml)
    return tmp_path


def _health_via_generate(project: Path) -> dict[str, Any]:
    output = project / "site"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "--project-dir",
            str(project),
            "--output-dir",
            str(output),
            "--skip-column-lineage",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data: dict[str, Any] = json.loads((output / "docglow-data.json").read_text())
    return data["health"]


def _health_via_health_command(project: Path) -> dict[str, Any]:
    result = CliRunner().invoke(
        cli,
        ["health", "--project-dir", str(project), "--format", "json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    health: dict[str, Any] = json.loads(result.output[result.output.index("{") :])
    return health


ENTRY_POINTS = pytest.mark.parametrize(
    "run_health",
    [_health_via_generate, _health_via_health_command],
    ids=["generate", "health"],
)


@ENTRY_POINTS
def test_custom_weights_change_overall_score(tmp_path: Path, run_health: Any) -> None:
    default = run_health(_project(tmp_path / "default", None))
    configured = run_health(_project(tmp_path / "configured", DOCUMENTATION_ONLY))

    # With all weight on documentation, overall is the documentation score.
    assert configured["score"]["overall"] == configured["score"]["documentation"]
    assert configured["score"]["overall"] != default["score"]["overall"]
    assert configured["config"]["weights"] == {
        "documentation": 1.0,
        "testing": 0.0,
        "freshness": 0.0,
        "complexity": 0.0,
        "naming": 0.0,
        "orphans": 0.0,
    }


@ENTRY_POINTS
def test_complexity_threshold_and_naming_rules_apply(tmp_path: Path, run_health: Any) -> None:
    default = run_health(_project(tmp_path / "default", None))
    configured = run_health(_project(tmp_path / "configured", STRICT_THRESHOLDS_AND_NAMING))

    assert configured["config"]["complexity_thresholds"]["high_sql_lines"] == 1
    assert configured["config"]["naming_rules"] == [
        {"layer": "staging", "patterns": ["^never_matches_"]}
    ]
    # Every model has more than one line of SQL, and no staging model matches.
    assert configured["score"]["complexity"] < default["score"]["complexity"]
    assert configured["score"]["naming"] < default["score"]["naming"]
    assert configured["score"]["overall"] < default["score"]["overall"]


@ENTRY_POINTS
def test_no_docglow_yml_scores_with_defaults(tmp_path: Path, run_health: Any) -> None:
    health = run_health(_project(tmp_path, None))

    assert health["config"]["weights"] == {
        "documentation": 0.25,
        "testing": 0.25,
        "freshness": 0.15,
        "complexity": 0.15,
        "naming": 0.10,
        "orphans": 0.10,
    }
