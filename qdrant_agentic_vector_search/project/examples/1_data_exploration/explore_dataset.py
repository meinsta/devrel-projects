"""
Explore the HousingQA dataset questions.

This script loads the housing law questions from HuggingFace
and shows you what's available for each state.

Usage:
    python examples/1_data_exploration/explore_dataset.py
    python examples/1_data_exploration/explore_dataset.py --state wyoming
"""

import argparse
from datasets import load_dataset
from rich.console import Console
from rich.table import Table
from rich import box
from collections import defaultdict

console = Console()


def explore_questions(state_filter=None):
    """Explore questions in the HousingQA dataset."""
    
    console.print("\n[bold cyan]📚 Loading HousingQA Dataset...[/bold cyan]\n")
    
    # Load questions dataset
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    console.print(f"[green]✓ Loaded {len(questions_dataset)} questions[/green]\n")
    
    # Count questions by state
    state_counts = defaultdict(int)
    state_questions = defaultdict(list)
    
    for item in questions_dataset:
        state = item.get('state', 'Unknown')
        if state:
            state = state.lower()
            state_counts[state] += 1
            
            if not state_filter or state == state_filter.lower():
                state_questions[state].append({
                    'idx': item['idx'],
                    'question': item['question'],
                    'answer': item['answer'],
                    'num_statutes': len(item.get('statutes', []))
                })
    
    # Show summary table
    table = Table(
        title="Questions by State",
        box=box.DOUBLE_EDGE,
        title_style="bold cyan"
    )
    
    table.add_column("State", style="bold white")
    table.add_column("Questions", style="green", justify="right")
    table.add_column("Available in Demo", style="yellow")
    
    demo_states = ['iowa', 'idaho', 'wyoming']
    
    for state in sorted(state_counts.keys()):
        available = "✓ Yes" if state in demo_states else "✗ No"
        style = "green" if state in demo_states else "dim"
        
        table.add_row(
            state.title(),
            str(state_counts[state]),
            f"[{style}]{available}[/{style}]"
        )
    
    console.print(table)
    console.print()
    
    # Show sample questions if state filter is provided
    if state_filter:
        show_sample_questions(state_questions.get(state_filter.lower(), []), state_filter)


def show_sample_questions(questions, state):
    """Show sample questions for a state."""
    
    if not questions:
        console.print(f"[yellow]No questions found for {state}[/yellow]")
        return
    
    console.print(f"\n[bold cyan]📋 Sample Questions for {state.title()}[/bold cyan]\n")
    
    # Show first 5 questions
    for i, q in enumerate(questions[:5], 1):
        console.print(f"[bold]{i}. Question ID: {q['idx']}[/bold]")
        console.print(f"   [cyan]Q:[/cyan] {q['question']}")
        console.print(f"   [green]A:[/green] {q['answer']}")
        console.print(f"   [dim]Referenced statutes: {q['num_statutes']}[/dim]\n")
    
    if len(questions) > 5:
        console.print(f"[dim]... and {len(questions) - 5} more questions[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explore HousingQA dataset")
    parser.add_argument(
        '--state',
        type=str,
        help='Show sample questions for a specific state (e.g., wyoming, idaho, iowa)'
    )
    
    args = parser.parse_args()
    
    explore_questions(state_filter=args.state)
    
    if not args.state:
        console.print("\n[dim]💡 Tip: Run with --state wyoming to see sample questions[/dim]\n")

