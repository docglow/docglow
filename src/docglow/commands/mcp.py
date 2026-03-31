"""MCP server command for docglow CLI."""

from pathlib import Path

import click


@click.command("mcp-server")
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
def mcp_server(project_dir: Path, target_dir: Path | None) -> None:
    """Start an MCP server for AI editor integration.

    Runs a Model Context Protocol server on stdio that exposes
    your dbt project to AI editors like Claude Code, Cursor, and Copilot.

    Configure in your editor's MCP settings:

        "docglow": {
          "command": "docglow",
          "args": ["mcp-server", "--project-dir", "/path/to/dbt/project"]
        }
    """
    from docglow.mcp.server import run_server

    run_server(project_dir, target_dir)
