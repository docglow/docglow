"""``docglow telemetry`` -- inspect and toggle telemetry consent.

The CLI surface that lets users see exactly what telemetry will do and
control it without editing config files. Output is the canonical reference
for "what is the resolved state" -- the same logic the dispatcher uses.
"""

from __future__ import annotations

import os
import sys

import click

from docglow.telemetry import state
from docglow.telemetry.config import (
    ENV_ENDPOINT_OVERRIDE,
    ENV_OPT_IN,
    ENV_OPT_OUT,
    resolve_telemetry_config,
)
from docglow.telemetry.dispatcher import is_active

DOCS_URL = "https://docs.docglow.com/telemetry"


@click.group()
def telemetry() -> None:
    """Inspect and control opt-in anonymous telemetry."""


@telemetry.command()
def status() -> None:
    """Show the current telemetry state."""
    config = resolve_telemetry_config(None)
    consent = state.get_consent()
    instance_id = state.get_instance_id()
    active = is_active(config, consent)

    click.echo("docglow telemetry status")
    click.echo("------------------------")
    click.echo(f"  Active: {'yes' if active else 'no'}")
    click.echo(f"  Instance ID: {instance_id}")
    click.echo(f"  Endpoint: {config.endpoint}")
    click.echo(f"  Recorded consent: {consent}")
    click.echo()
    click.echo("Resolution:")
    click.echo(f"  {ENV_OPT_OUT}: {os.environ.get(ENV_OPT_OUT, '(unset)')}")
    click.echo(f"  {ENV_OPT_IN}: {os.environ.get(ENV_OPT_IN, '(unset)')}")
    click.echo(f"  {ENV_ENDPOINT_OVERRIDE}: {os.environ.get(ENV_ENDPOINT_OVERRIDE, '(unset)')}")
    click.echo()
    click.echo(f"What is collected: {DOCS_URL}")


@telemetry.command()
def enable() -> None:
    """Opt in to anonymous telemetry."""
    state.set_consent("yes")
    click.echo("Anonymous telemetry enabled.")
    click.echo(f"What is collected: {DOCS_URL}")
    click.echo("Disable anytime with `docglow telemetry disable` or DOCGLOW_NO_TELEMETRY=1.")


@telemetry.command()
def disable() -> None:
    """Opt out of telemetry."""
    state.set_consent("no")
    click.echo("Telemetry disabled. No events will be sent.")


def _can_prompt() -> bool:
    """Return True iff we're in an interactive context where prompting is appropriate."""
    if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if os.environ.get(ENV_OPT_OUT):
        # Don't prompt if the user has already forced telemetry off via env.
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


PROMPT_MESSAGE = (
    "\n[bold]Help improve docglow with anonymous telemetry?[/bold]\n"
    "We collect counts (models, sources, tests) and your dbt adapter type "
    "to prioritise features.\n"
    f"Full details: {DOCS_URL}\n"
    "  - No model names, column names, SQL, file paths, or credentials.\n"
    "  - Disable anytime with `docglow telemetry disable` or "
    "[bold]DOCGLOW_NO_TELEMETRY=1[/bold].\n"
)


def maybe_prompt_for_consent(console: object | None = None) -> state.ConsentValue:
    """Prompt the user for telemetry consent if appropriate, return resolved value.

    Returns the recorded consent ("yes", "no", or "unset"). Records "no"
    automatically when the prompt is suppressed -- this means we never
    prompt twice and never block non-interactive runs.

    Pass ``console`` (a rich Console) to render styled output; falls back to
    plain ``click.echo`` if missing or rendering fails. Never raises.
    """
    try:
        current = state.get_consent()
        if current != "unset":
            return current

        if not _can_prompt():
            # Record an implicit "no" so we never re-prompt this user.
            state.set_consent("no")
            return "no"

        try:
            if console is not None and hasattr(console, "print"):
                console.print(PROMPT_MESSAGE)
            else:
                click.echo(PROMPT_MESSAGE)
            answer = click.confirm("Enable anonymous telemetry?", default=False)
        except Exception:
            answer = False

        consent: state.ConsentValue = "yes" if answer else "no"
        state.set_consent(consent)
        return consent
    except Exception:
        return "unset"
