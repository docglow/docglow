"""Tests for BYOK (Bring Your Own Key) — key is never embedded in output."""

from pathlib import Path

from docglow.artifacts.loader import load_artifacts
from docglow.generator.data import build_docglow_data

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures(tmp_path: Path) -> dict:
    target = tmp_path / "target"
    target.mkdir()
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        src = FIXTURES_DIR / name
        if src.exists():
            (target / name).write_text(src.read_text())
    artifacts = load_artifacts(tmp_path)
    return artifacts


class TestByok:
    def test_ai_key_always_none_when_ai_disabled(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=False)
        assert data["ai_key"] is None

    def test_ai_key_never_embedded_when_ai_enabled(self, tmp_path):
        """Even with AI enabled, the key must never appear in the output."""
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=True)
        assert data["ai_key"] is None

    def test_ai_context_present_when_ai_enabled(self, tmp_path):
        """AI context (project metadata for chat) should be present."""
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=True)
        assert data["ai_context"] is not None
        assert "project_name" in data["ai_context"]

    def test_ai_context_absent_when_ai_disabled(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=False)
        assert data["ai_context"] is None
