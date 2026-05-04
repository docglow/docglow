"""CLI entry point for docglow."""

import logging

import click
from rich.console import Console
from rich.logging import RichHandler

from docglow import __version__
from docglow.commands.cloud import cloud_group, login, logout, setup, status
from docglow.commands.generate import generate
from docglow.commands.health import health
from docglow.commands.init import init
from docglow.commands.mcp import mcp_server
from docglow.commands.profile import profile
from docglow.commands.publish import publish
from docglow.commands.serve import serve
from docglow.commands.telemetry import telemetry as telemetry_group

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def _parse_connection(adapter: str, connection: str) -> dict[str, str]:
    """Parse a connection string into params dict."""
    if adapter == "duckdb":
        return {"path": connection}
    if adapter in ("postgres", "postgresql"):
        return {"dsn": connection}
    if adapter == "snowflake":
        return {"dsn": connection}
    return {"dsn": connection}


@click.group()
@click.version_option(version=__version__, prog_name="docglow")
def cli() -> None:
    """docglow: Next-generation dbt documentation site generator."""


cli.add_command(generate)
cli.add_command(serve)
cli.add_command(health)
cli.add_command(profile)
cli.add_command(publish)
cli.add_command(login)
cli.add_command(logout)
cli.add_command(status)
cli.add_command(setup)
cli.add_command(cloud_group)
cli.add_command(mcp_server)
cli.add_command(init)
cli.add_command(telemetry_group)
