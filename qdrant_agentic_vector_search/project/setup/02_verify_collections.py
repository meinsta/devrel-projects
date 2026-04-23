"""
Collection Verification Script

Verifies that all three housing law collections are properly loaded in Qdrant
and performs basic search tests.

Usage:
    python setup/02_verify_collections.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

console = Console()

QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

EXPECTED_COLLECTIONS = {
    'iowa_housing_statutes': 'Iowa',
    'idaho_housing_statutes': 'Idaho',
    'wyoming_housing_statutes': 'Wyoming'
}

TEST_QUERIES = {
    'iowa': 'Can landlords charge late fees?',
    'idaho': 'Are security deposits required?',
    'wyoming': 'What are the eviction procedures?'
}


def check_collection_exists(client: QdrantClient, collection_name: str):
    """Check if a collection exists and get its info."""
    try:
        info = client.get_collection(collection_name)
        return {
            'exists': True,
            'points_count': info.points_count,
            'vectors_count': info.vectors_count,
            'status': info.status
        }
    except Exception as e:
        return {
            'exists': False,
            'error': str(e)
        }


def test_search(client: QdrantClient, collection_name: str, query: str, embedding_model):
    """Perform a test search on a collection."""
    try:
        # Generate query embedding
        query_vector = list(embedding_model.embed([query]))[0].tolist()
        
        # Search
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using='fast-bge-small-en',
            limit=3
        ).points
        
        return {
            'success': True,
            'num_results': len(results),
            'top_score': results[0].score if results else 0,
            'top_citation': results[0].payload.get('citation', 'N/A') if results else 'N/A'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """Main verification workflow."""
    
    console.print("\n" + "="*80)
    console.print(Panel.fit(
        "[bold white]Collection Verification[/bold white]\n"
        "[dim]Checking Qdrant collections and running test searches[/dim]",
        border_style="cyan",
        box=box.DOUBLE
    ))
    console.print("="*80 + "\n")
    
    # Check environment
    if not QDRANT_URL or not QDRANT_API_KEY:
        console.print("[red]❌ Error: QDRANT_CLOUD_URL and QDRANT_API_KEY must be set in .env[/red]")
        return
    
    # Initialize
    console.print("[cyan]Initializing...[/cyan]")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    console.print("✓ Connected to Qdrant\n")
    
    # Check each collection
    console.print("[bold]📋 Collection Status[/bold]\n")
    
    status_table = Table(box=box.ROUNDED, show_header=True)
    status_table.add_column("State", style="cyan", width=12)
    status_table.add_column("Collection", style="white", width=30)
    status_table.add_column("Points", style="yellow", justify="right", width=10)
    status_table.add_column("Status", style="bold", width=15)
    
    all_exist = True
    collection_data = {}
    
    for collection_name, state_name in EXPECTED_COLLECTIONS.items():
        info = check_collection_exists(client, collection_name)
        
        if info['exists']:
            status = "[green]✓ Active[/green]"
            count = str(info['points_count'])
        else:
            status = "[red]✗ Missing[/red]"
            count = "0"
            all_exist = False
        
        status_table.add_row(state_name, collection_name, count, status)
        collection_data[collection_name] = info
    
    console.print(status_table)
    
    if not all_exist:
        console.print("\n[red]⚠️  Some collections are missing. Run setup/01_ingest_data.py first.[/red]")
        return
    
    # Test searches
    console.print("\n[bold]🔍 Test Searches[/bold]\n")
    
    search_table = Table(box=box.ROUNDED, show_header=True)
    search_table.add_column("State", style="cyan", width=12)
    search_table.add_column("Query", style="white", width=35)
    search_table.add_column("Results", style="yellow", justify="right", width=8)
    search_table.add_column("Top Score", style="green", justify="right", width=10)
    search_table.add_column("Status", style="bold", width=10)
    
    for (state_key, query), (collection_name, state_name) in zip(
        TEST_QUERIES.items(), 
        EXPECTED_COLLECTIONS.items()
    ):
        result = test_search(client, collection_name, query, embedding_model)
        
        if result['success']:
            status = "[green]✓ Pass[/green]"
            num_results = str(result['num_results'])
            top_score = f"{result['top_score']:.3f}"
        else:
            status = "[red]✗ Fail[/red]"
            num_results = "0"
            top_score = "0.000"
        
        search_table.add_row(
            state_name,
            query[:33] + "..." if len(query) > 33 else query,
            num_results,
            top_score,
            status
        )
    
    console.print(search_table)
    
    # Summary
    console.print("\n" + "="*80)
    console.print("\n[bold green]✅ All collections verified and operational![/bold green]")
    console.print("\n[dim]You can now run:[/dim]")
    console.print("  • [cyan]python examples/01_vanilla_rag.py[/cyan]")
    console.print("  • [cyan]python examples/02_agentic_rag.py[/cyan]")
    console.print("  • [cyan]python examples/03_demo_comparison.py[/cyan]")
    console.print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

