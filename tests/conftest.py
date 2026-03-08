"""Shared test fixtures for docglow."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture()
def manifest_path(fixtures_dir: Path) -> Path:
    """Path to the fixture manifest.json."""
    return fixtures_dir / "manifest.json"


@pytest.fixture()
def catalog_path(fixtures_dir: Path) -> Path:
    """Path to the fixture catalog.json."""
    return fixtures_dir / "catalog.json"


@pytest.fixture()
def run_results_path(fixtures_dir: Path) -> Path:
    """Path to the fixture run_results.json."""
    return fixtures_dir / "run_results.json"


@pytest.fixture()
def sources_path(fixtures_dir: Path) -> Path:
    """Path to the fixture sources.json."""
    return fixtures_dir / "sources.json"
