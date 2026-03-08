#!/usr/bin/env python3
"""Build frontend and copy assets into the Python package for distribution."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
STATIC_DIR = PROJECT_ROOT / "src" / "docglow" / "static"


def main() -> None:
    # Build frontend
    print("Building frontend...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Frontend build failed:", result.stderr)
        sys.exit(1)
    print("Frontend build complete.")

    # Clear static dir (except .gitignore)
    if STATIC_DIR.exists():
        for item in STATIC_DIR.iterdir():
            if item.name == ".gitignore":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    # Copy dist/ contents to static/
    for item in DIST_DIR.iterdir():
        dest = STATIC_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    file_count = sum(1 for _ in STATIC_DIR.rglob("*") if _.is_file() and _.name != ".gitignore")
    print(f"Copied {file_count} files to {STATIC_DIR}")


if __name__ == "__main__":
    main()
