"""Colored logging configuration using Rich."""

import logging
import sys
from rich.logging import RichHandler
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

# Create console for rich output
console = Console()


def setup_logging(level: int = logging.INFO):
    """
    Set up colored logging with Rich.
    
    Args:
        level: Logging level (default: INFO)
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Add Rich handler with colors and formatting
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
        show_level=True,
    )
    
    # Set format
    rich_handler.setFormatter(
        logging.Formatter("%(message)s", datefmt="[%X]")
    )
    
    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(rich_handler)
    
    # Suppress verbose logging from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def print_header(title: str, emoji: str = "🚀"):
    """Print a beautiful header panel."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{emoji} {title}[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def print_success(message: str, emoji: str = "✅"):
    """Print a success message."""
    console.print(f"[bold green]{emoji} {message}[/bold green]")


def print_error(message: str, emoji: str = "❌"):
    """Print an error message."""
    console.print(f"[bold red]{emoji} {message}[/bold red]")


def print_warning(message: str, emoji: str = "⚠️"):
    """Print a warning message."""
    console.print(f"[bold yellow]{emoji} {message}[/bold yellow]")


def print_info(message: str, emoji: str = "ℹ️"):
    """Print an info message."""
    console.print(f"[bold blue]{emoji} {message}[/bold blue]")


def print_step(step_num: int, total_steps: int, description: str):
    """Print a step indicator."""
    console.print(
        f"\n[bold cyan][{step_num}/{total_steps}][/bold cyan] [bold]{description}[/bold]"
    )


def print_progress_bar(current: int, total: int, description: str = ""):
    """Print a progress bar."""
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(description, total=total)
        progress.update(task, completed=current)


def print_table(data: list, title: str = ""):
    """Print a table."""
    from rich.table import Table
    
    if not data:
        return
    
    table = Table(title=title, box=box.ROUNDED, border_style="cyan")
    
    # Add columns from first row keys
    if isinstance(data[0], dict):
        for key in data[0].keys():
            table.add_column(str(key), style="cyan")
        
        # Add rows
        for row in data:
            table.add_row(*[str(v) for v in row.values()])
    else:
        # Simple list of lists
        if len(data) > 0:
            for i, col in enumerate(data[0]):
                table.add_column(f"Column {i+1}", style="cyan")
            for row in data:
                table.add_row(*[str(v) for v in row])
    
    console.print(table)



