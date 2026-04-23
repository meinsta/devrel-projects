"""
Data Ingestion Script - Load Housing Law Statutes to Qdrant

This script ingests statute data for three states (Iowa, Idaho, Wyoming) from the 
HousingQA dataset into Qdrant vector database with semantic embeddings.

Collections created:
- iowa_housing_statutes
- idaho_housing_statutes  
- wyoming_housing_statutes

Usage:
    python setup/01_ingest_data.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.table import Table
from rich import box
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

console = Console()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

STATES_TO_INGEST = {
    'iowa': 'iowa_housing_statutes',
    'idaho': 'idaho_housing_statutes',
    'wyoming': 'wyoming_housing_statutes'
}

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_NAME = "fast-bge-small-en"
VECTOR_SIZE = 384  # BGE-small produces 384-dimensional embeddings
BATCH_SIZE = 100


def load_statutes_for_state(state_name: str):
    """Load statutes from HousingQA dataset for a specific state."""
    console.print(f"\n[cyan]📥 Loading statutes for {state_name.title()}...[/cyan]")
    
    # Load the full statute corpus
    dataset = load_dataset(
        "reglab/housing_qa",
        "statutes",
        split="corpus",
        trust_remote_code=True
    )
    
    # Filter for this state
    state_statutes = [
        {
            'idx': item['idx'],
            'citation': item['citation'],
            'state': item['state'],
            'text': item['text'],
            'path': item.get('path', '')
        }
        for item in dataset
        if item['state'] and item['state'].lower() == state_name.lower()
    ]
    
    console.print(f"   ✓ Found [bold green]{len(state_statutes)}[/bold green] statutes")
    return state_statutes


def create_collection(client: QdrantClient, collection_name: str):
    """Create or recreate a Qdrant collection with named vectors."""
    console.print(f"\n[cyan]🗄️  Setting up collection: {collection_name}[/cyan]")
    
    # Check if collection exists
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if exists:
        console.print(f"   ⚠️  Collection exists. Deleting...")
        client.delete_collection(collection_name)
    
    # Create new collection with named vector
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            VECTOR_NAME: VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            )
        }
    )
    
    console.print(f"   ✓ Collection created: [bold green]{collection_name}[/bold green]")


def ingest_statutes(
    client: QdrantClient,
    collection_name: str,
    statutes: list,
    embedding_model: TextEmbedding
):
    """Embed and upload statutes to Qdrant."""
    console.print(f"\n[cyan]⚡ Embedding and uploading statutes...[/cyan]")
    
    total_batches = (len(statutes) + BATCH_SIZE - 1) // BATCH_SIZE
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        task = progress.add_task(
            f"Processing {len(statutes)} statutes...",
            total=len(statutes)
        )
        
        for batch_idx in range(0, len(statutes), BATCH_SIZE):
            batch = statutes[batch_idx:batch_idx + BATCH_SIZE]
            
            # Generate embeddings for batch
            texts = [s['text'] for s in batch]
            embeddings = list(embedding_model.embed(texts))
            
            # Create points
            points = []
            for i, statute in enumerate(batch):
                points.append(
                    PointStruct(
                        id=batch_idx + i,
                        vector={
                            VECTOR_NAME: embeddings[i].tolist()
                        },
                        payload={
                            'statute_idx': statute['idx'],
                            'citation': statute['citation'],
                            'state': statute['state'],
                            'text': statute['text'],
                            'path': statute['path']
                        }
                    )
                )
            
            # Upload batch
            client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            progress.update(task, advance=len(batch))
            
            # Small delay to avoid rate limits
            time.sleep(0.1)
    
    console.print(f"   ✓ Successfully ingested [bold green]{len(statutes)}[/bold green] statutes")


def verify_collection(client: QdrantClient, collection_name: str, expected_count: int):
    """Verify collection was created successfully."""
    console.print(f"\n[cyan]✓ Verifying collection: {collection_name}[/cyan]")
    
    info = client.get_collection(collection_name)
    actual_count = info.points_count
    
    if actual_count == expected_count:
        console.print(f"   ✓ Count matches: [bold green]{actual_count}[/bold green] points")
        return True
    else:
        console.print(f"   ⚠️  Count mismatch: expected {expected_count}, got {actual_count}")
        return False


def main():
    """Main ingestion workflow."""
    
    # Header
    console.print("\n" + "="*80)
    console.print(Panel.fit(
        "[bold white]Housing Law Statute Ingestion[/bold white]\n"
        "[dim]Loading statutes from HousingQA dataset into Qdrant[/dim]",
        border_style="cyan",
        box=box.DOUBLE
    ))
    console.print("="*80)
    
    # Check environment
    if not QDRANT_URL or not QDRANT_API_KEY:
        console.print("[red]❌ Error: QDRANT_CLOUD_URL and QDRANT_API_KEY must be set in .env[/red]")
        return
    
    # Initialize
    console.print("\n[bold]Initializing...[/bold]")
    console.print(f"[dim]Qdrant URL: {QDRANT_URL}[/dim]")
    console.print(f"[dim]Embedding Model: {EMBEDDING_MODEL_NAME}[/dim]")
    
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    
    # Process each state
    results = []
    
    for state_name, collection_name in STATES_TO_INGEST.items():
        console.print("\n" + "-"*80)
        console.print(f"[bold yellow]Processing: {state_name.upper()}[/bold yellow]")
        console.print("-"*80)
        
        try:
            # Load data
            statutes = load_statutes_for_state(state_name)
            
            # Create collection
            create_collection(client, collection_name)
            
            # Ingest
            ingest_statutes(client, collection_name, statutes, embedding_model)
            
            # Verify
            success = verify_collection(client, collection_name, len(statutes))
            
            results.append({
                'state': state_name,
                'collection': collection_name,
                'count': len(statutes),
                'success': success
            })
            
        except Exception as e:
            console.print(f"[red]❌ Error processing {state_name}: {e}[/red]")
            results.append({
                'state': state_name,
                'collection': collection_name,
                'count': 0,
                'success': False
            })
    
    # Summary
    console.print("\n" + "="*80)
    console.print("\n[bold]📊 Ingestion Summary[/bold]\n")
    
    summary_table = Table(box=box.ROUNDED, show_header=True)
    summary_table.add_column("State", style="cyan", width=12)
    summary_table.add_column("Collection", style="white", width=30)
    summary_table.add_column("Statutes", style="yellow", justify="right", width=10)
    summary_table.add_column("Status", style="bold", width=10)
    
    for result in results:
        status = "[green]✓ Success[/green]" if result['success'] else "[red]✗ Failed[/red]"
        summary_table.add_row(
            result['state'].title(),
            result['collection'],
            str(result['count']),
            status
        )
    
    console.print(summary_table)
    
    # Final message
    all_success = all(r['success'] for r in results)
    if all_success:
        console.print("\n[bold green]✅ All collections successfully created![/bold green]")
        console.print("\n[dim]Next steps:[/dim]")
        console.print("  1. Run: [cyan]python setup/02_verify_collections.py[/cyan]")
        console.print("  2. Try examples: [cyan]python examples/01_vanilla_rag.py[/cyan]")
    else:
        console.print("\n[bold red]⚠️  Some collections failed. Please check errors above.[/bold red]")
    
    console.print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

