"""
Inspect Qdrant collections for the three states in the housing law dataset.

This script shows you what's available in your Qdrant instance:
- Iowa Housing Statutes
- Idaho Housing Statutes  
- Wyoming Housing Statutes

Usage:
    python examples/1_data_exploration/inspect_collections.py
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from rich.console import Console
from rich.table import Table
from rich import box

load_dotenv()

console = Console()

# Collection names in Qdrant
COLLECTIONS = {
    'Iowa': 'iowa_statutes_baseline',
    'Idaho': 'housing_statutes_idaho',
    'Wyoming': 'housing_statutes_wyoming'
}


def inspect_collections():
    """Inspect all three state collections in Qdrant."""
    
    console.print("\n[bold cyan]🔍 Inspecting Qdrant Collections[/bold cyan]\n")
    
    # Connect to Qdrant
    qdrant_url = os.getenv('QDRANT_CLOUD_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        console.print("[red]Error: QDRANT_CLOUD_URL or QDRANT_API_KEY not set in .env file[/red]")
        return
    
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    # Create results table
    table = Table(
        title="Housing Law Collections",
        box=box.DOUBLE_EDGE,
        title_style="bold cyan"
    )
    
    table.add_column("State", style="bold white", width=12)
    table.add_column("Collection Name", style="cyan", width=30)
    table.add_column("Points", style="green", justify="right")
    table.add_column("Vectors", style="yellow")
    table.add_column("Status", style="bold")
    
    # Inspect each collection
    for state, collection_name in COLLECTIONS.items():
        try:
            collection_info = client.get_collection(collection_name)
            
            points_count = collection_info.points_count
            vectors_config = collection_info.config.params.vectors
            
            # Get vector names
            if hasattr(vectors_config, '__iter__') and not isinstance(vectors_config, str):
                vector_names = ', '.join(vectors_config.keys())
            else:
                vector_names = 'default'
            
            status = "[green]✓ Available[/green]"
            
            table.add_row(
                state,
                collection_name,
                f"{points_count:,}",
                vector_names,
                status
            )
            
        except Exception as e:
            table.add_row(
                state,
                collection_name,
                "N/A",
                "N/A",
                f"[red]✗ Error[/red]"
            )
            console.print(f"[dim]Error for {state}: {str(e)}[/dim]")
    
    console.print(table)
    console.print()


def show_sample_point(collection_name, state):
    """Show a sample point from a collection."""
    
    console.print(f"\n[bold cyan]📄 Sample Point from {state}[/bold cyan]\n")
    
    qdrant_url = os.getenv('QDRANT_CLOUD_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    try:
        # Get a random sample point
        points = client.scroll(
            collection_name=collection_name,
            limit=1
        )[0]
        
        if points:
            point = points[0]
            console.print(f"[bold]Point ID:[/bold] {point.id}")
            console.print(f"[bold]Payload:[/bold]")
            
            for key, value in point.payload.items():
                if key == 'text':
                    # Truncate long text
                    text_preview = value[:200] + "..." if len(value) > 200 else value
                    console.print(f"  [cyan]{key}:[/cyan] {text_preview}")
                else:
                    console.print(f"  [cyan]{key}:[/cyan] {value}")
            
            console.print()
    
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")


if __name__ == "__main__":
    # Inspect all collections
    inspect_collections()
    
    # Show sample from Wyoming
    console.print("\n" + "="*60)
    show_sample_point(COLLECTIONS['Wyoming'], 'Wyoming')

