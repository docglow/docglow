"""Tests for BYOK (Bring Your Own Key) via env var and CLI flag."""

import os
from pathlib import Path
from unittest.mock import patch

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
    def test_ai_key_none_when_ai_disabled(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=False)
        assert data["ai_key"] is None

    def test_ai_key_from_explicit_param(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        data = build_docglow_data(artifacts, ai_enabled=True, ai_key="sk-test-123")
        assert data["ai_key"] == "sk-test-123"

    def test_ai_key_from_env_var(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env-456"}):
            data = build_docglow_data(artifacts, ai_enabled=True)
        assert data["ai_key"] == "sk-env-456"

    def test_explicit_key_takes_precedence(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env-456"}):
            data = build_docglow_data(artifacts, ai_enabled=True, ai_key="sk-explicit-789")
        assert data["ai_key"] == "sk-explicit-789"

    def test_ai_key_none_when_no_key_available(self, tmp_path):
        artifacts = _load_fixtures(tmp_path)
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if set
            os.environ.pop("ANTHROPIC_API_KEY", None)
            data = build_docglow_data(artifacts, ai_enabled=True)
        assert data["ai_key"] is None
