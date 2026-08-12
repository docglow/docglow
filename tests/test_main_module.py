"""Test that docglow is runnable as ``python -m docglow``."""

from __future__ import annotations

import subprocess
import sys

from docglow import __version__


def test_python_m_docglow_reports_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "docglow", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
