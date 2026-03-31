"""Cloud commands (login, logout, status, setup) for docglow CLI."""

import click


@click.command()
@click.option("--token", type=str, default=None, help="API token for non-interactive auth")
def login(token: str | None) -> None:
    """Authenticate with docglow.dev."""
    from docglow.cli import console
    from docglow.cloud.auth import store_token

    if token:
        store_token(token)
        console.print("[bold green]Token saved successfully.[/bold green]")
        return

    console.print("Interactive browser login is not yet available.")
    console.print("Use [bold]docglow login --token YOUR_TOKEN[/bold] instead.")
    console.print("Get your token at [bold]https://app.docglow.dev/settings/tokens[/bold]")


@click.command()
def logout() -> None:
    """Remove stored docglow.dev credentials."""
    from docglow.cli import console
    from docglow.cloud.auth import clear_token

    clear_token()
    console.print("[bold green]Logged out successfully.[/bold green]")


@click.command()
@click.option("--token", envvar="DOCGLOW_TOKEN", default=None)
@click.option("--verbose", is_flag=True)
def status(token: str | None, verbose: bool) -> None:
    """Check docglow Cloud publish status and site health."""
    from docglow.cli import _setup_logging, console

    _setup_logging(verbose)

    try:
        from docglow.cloud.client import CloudApiError, CloudClient
        from docglow.cloud.config import load_cloud_config
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] Cloud features require httpx. "
            "Install with: [bold]pip install docglow\\[cloud][/bold]"
        )
        raise SystemExit(1)

    config = load_cloud_config()
    if token:
        from dataclasses import replace

        config = replace(config, token=token)

    if not config.token:
        console.print(
            "[bold red]Error:[/bold red] No API token found. "
            "Set DOCGLOW_TOKEN env var or run [bold]docglow login[/bold]."
        )
        raise SystemExit(1)

    client = CloudClient(config)
    try:
        info = client.get_workspace_info()
        console.print(f"\n[bold]Workspace:[/bold] {info.get('name', 'Unknown')}")
        console.print(f"  Slug: {info.get('slug', '')}")
        console.print(f"  Tier: {info.get('subscription_tier', 'free')}")
        if info.get("latest_health_score") is not None:
            console.print(f"  Health: {info['latest_health_score']}")
        if info.get("site_url"):
            console.print(f"  Site: {info['site_url']}")
    except CloudApiError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
    finally:
        client.close()


@click.command()
def setup() -> None:
    """Interactive setup wizard for docglow Cloud."""
    from docglow.cli import console
    from docglow.cloud.config import load_cloud_config, save_cloud_config

    config = load_cloud_config()

    console.print("[bold]docglow Cloud Setup[/bold]\n")

    if config.token:
        console.print("  Token: [green]configured[/green]")
    else:
        console.print("  Token: [yellow]not set[/yellow]")
        token = click.prompt("  Enter your API token", default="", show_default=False)
        if token:
            save_cloud_config(token=token)

    workspace = click.prompt(
        "  Workspace slug",
        default=config.workspace_slug or "",
        show_default=bool(config.workspace_slug),
    )
    project = click.prompt(
        "  Project slug",
        default=config.project_slug or "",
        show_default=bool(config.project_slug),
    )

    save_cloud_config(workspace_slug=workspace, project_slug=project)
    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("  Config saved to ~/.docglow/config.json")
