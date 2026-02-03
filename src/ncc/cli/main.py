"""
Main CLI entry point for Network Command Center.

Provides the root command and orchestrates all subcommands.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ncc import __version__
from ncc.core.config import config
from ncc.core.logging import setup_logging, logger

console = Console()


class NCCContext:
    """Context object for passing state between CLI commands."""
    
    def __init__(self):
        self.config = config
        self.silent = False
        self.debug = False


pass_context = click.make_pass_decorator(NCCContext, ensure=True)


@click.group()
@click.version_option(version=__version__, prog_name="ncc")
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode"
)
@click.option(
    "--workers",
    is_flag=False,
    help="Number of parallel tasks"
)
@click.option(
    "--username",
    is_flag=False,
    help="Username for device authentication"
)
@click.option(
    "--password",
    is_flag=False,
    help="Password for device authentication"
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    help="Path to log file"
)

@pass_context
def cli(
    ctx: NCCContext,
    debug: bool,
    workers: int,
    username: Optional[str],
    password: Optional[str],
    log_file: Optional[Path]
):
    """
    Network Command Center (NCC) - Network management and automation tool.
    
    NCC provides comprehensive network device inventory management, discovery,
    diagnostics, and automation capabilities through both CLI and web interfaces.
    """
    ctx.debug = debug
    ctx.workers = workers
    ctx.username = username
    ctx.password = password
    
    # Configure logging
    log_level = "DEBUG" if debug else config.log_level
    setup_logging(level=log_level, log_file=log_file)
    
    if debug:
        logger.debug("Debug mode enabled")
        logger.debug(f"Configuration: {ctx.config.model_dump()}")


@cli.command()
@pass_context
def info(ctx: NCCContext):
    """Display NCC version and configuration information."""
    console.print(f"[bold cyan]Network Command Center (NCC)[/bold cyan] v{__version__}")
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Database: {ctx.config.database_url}")
    console.print(f"  Log Level: {ctx.config.log_level}")
    console.print(f"  Debug: {ctx.debug}")


@cli.command()
def init():
    """Initialize NCC database and configuration."""
    from ncc.core.database import init_db
    
    console.print("[bold cyan]Initializing NCC...[/bold cyan]")
    
    try:
        init_db()
        console.print("[green]✓[/green] Database initialized successfully")
        
        # Create default config directory
        config_dir = Path.home() / ".config" / "ncc"
        config_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Configuration directory: {config_dir}")
        
        # Create templates directory
        template_dir = Path.home() / ".config" / "ncc" / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Templates directory: {template_dir}")
        
        console.print()
        console.print("[bold green]NCC initialized successfully![/bold green]")
        console.print("Run [bold]ncc --help[/bold] to see available commands")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.exception("Failed to initialize NCC")
        sys.exit(1)


# Import and register subcommands
from ncc.backup.backup import backup
cli.add_command(backup)


if __name__ == "__main__":
    cli()
