"""Qdrant site agent CLI."""

import typer
from rich.console import Console

app = typer.Typer(help="AI agents for editing and creating Qdrant website content.")
console = Console()


@app.command()
def eval(
    content_dir: str = typer.Argument(
        ..., help="Path to content directory or single .md file to evaluate"
    ),
    reference_dir: str = typer.Option(
        None, "--reference", "-r",
        help="Path to reference content for benchmarking (defaults to qdrant blog)"
    ),
    model: str = typer.Option(
        "claude-sonnet-4-20250514", "--model", "-m",
        help="Model to use for evaluation"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Evaluate content quality against Qdrant's voice and style."""
    from qdrant_site_agent.eval import run_eval
    run_eval(content_dir, reference_dir, model, verbose)


@app.command()
def benchmark(
    site_dir: str = typer.Option(
        None, "--site-dir", "-d",
        help="Path to qdrant-landing content dir"
    ),
    model: str = typer.Option(
        "claude-sonnet-4-20250514", "--model", "-m",
    ),
    sample: int = typer.Option(10, "--sample", "-n", help="Number of posts to sample"),
):
    """Analyze existing Qdrant content to establish quality baseline."""
    from qdrant_site_agent.benchmark import run_benchmark
    run_benchmark(site_dir, model, sample)
