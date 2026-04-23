"""
Create a Focused Test Collection for California Housing Law

This creates a smaller, focused collection with:
- All 181 California questions
- All 40 golden passages (correct reference statutes)
- ~500 noise statutes (random California statutes for realistic search)

Total: ~540 statutes (manageable size, fast testing, all golden passages present)
"""

import os
import random
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding, SparseTextEmbedding
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

load_dotenv()

console = Console()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = "california_housing_test_focused"

# Embedding models
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"
DENSE_VECTOR_SIZE = 384

# Dataset parameters
NOISE_STATUTES = 500  # Number of random statutes to add as noise

def print_header():
    console.print("\n" + "="*80)
    console.print("[bold cyan]CREATE FOCUSED TEST COLLECTION[/bold cyan]")
    console.print("California Housing Law - Questions + Golden Passages + Noise")
    console.print("="*80 + "\n")

def load_questions_and_golden_ids():
    """Load California questions and extract all golden statute IDs."""
    console.print("[cyan]Step 1: Loading California questions...[/cyan]")
    
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    california_questions = []
    all_golden_ids = set()
    
    for item in questions_dataset:
        if item['state'] and item['state'].lower() == 'california':
            statute_ids = []
            if 'statutes' in item and item['statutes']:
                statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
            
            california_questions.append({
                'idx': item['idx'],
                'question': item['question'],
                'answer': item['answer'],
                'golden_statute_ids': statute_ids
            })
            all_golden_ids.update(statute_ids)
    
    console.print(f"  ✓ Found [bold green]{len(california_questions)}[/bold green] California questions")
    console.print(f"  ✓ Unique golden statute IDs: [bold green]{len(all_golden_ids)}[/bold green]\n")
    
    return california_questions, all_golden_ids

def load_statutes(golden_ids, noise_count):
    """Load golden statutes + random noise statutes."""
    console.print("[cyan]Step 2: Loading statutes corpus...[/cyan]")
    
    statutes_dataset = load_dataset(
        "reglab/housing_qa",
        "statutes",
        split="corpus",
        trust_remote_code=True
    )
    
    console.print(f"  → Total statutes in dataset: {len(statutes_dataset):,}")
    
    # Filter California statutes
    california_statutes = []
    golden_statutes = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:,}/{task.total:,}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing statutes...", total=len(statutes_dataset))
        
        for item in statutes_dataset:
            if item['state'] == 'california':
                statute = {
                    'idx': item['idx'],
                    'citation': item['citation'],
                    'state': item['state'],
                    'text': item['text'],
                    'path': item['path'],
                    'is_golden': item['idx'] in golden_ids
                }
                
                california_statutes.append(statute)
                
                if statute['is_golden']:
                    golden_statutes.append(statute)
            
            progress.advance(task)
    
    console.print(f"  ✓ California statutes: [bold green]{len(california_statutes):,}[/bold green]")
    console.print(f"  ✓ Golden statutes found: [bold green]{len(golden_statutes)}[/bold green]")
    
    # Add random noise statutes
    non_golden = [s for s in california_statutes if not s['is_golden']]
    noise_statutes = random.sample(non_golden, min(noise_count, len(non_golden)))
    
    console.print(f"  ✓ Noise statutes sampled: [bold green]{len(noise_statutes)}[/bold green]\n")
    
    # Combine golden + noise
    final_statutes = golden_statutes + noise_statutes
    random.shuffle(final_statutes)  # Shuffle so golden aren't all at the start
    
    console.print(f"[bold]Total statutes for collection: [green]{len(final_statutes)}[/green][/bold]")
    console.print(f"  • Golden: {len(golden_statutes)}")
    console.print(f"  • Noise: {len(noise_statutes)}\n")
    
    return final_statutes, golden_statutes

def create_collection(client):
    """Create Qdrant collection with hybrid vectors."""
    console.print("[cyan]Step 3: Creating Qdrant collection...[/cyan]")
    
    # Delete if exists
    try:
        client.delete_collection(COLLECTION_NAME)
        console.print(f"  ⚠ Deleted existing collection")
    except:
        pass
    
    # Create with hybrid vectors
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(
                    on_disk=False
                )
            )
        }
    )
    
    console.print(f"  ✓ Collection created: [bold green]{COLLECTION_NAME}[/bold green]\n")

def embed_and_upload(client, statutes, dense_model, sparse_model):
    """Embed statutes and upload to Qdrant."""
    console.print("[cyan]Step 4: Embedding and uploading statutes...[/cyan]")
    
    batch_size = 32
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing...", total=len(statutes))
        
        for i in range(0, len(statutes), batch_size):
            batch = statutes[i:i + batch_size]
            texts = [s['text'] for s in batch]
            
            # Generate embeddings
            dense_embeddings = list(dense_model.embed(texts))
            sparse_embeddings = list(sparse_model.embed(texts))
            
            # Create points
            points = []
            for j, statute in enumerate(batch):
                point = PointStruct(
                    id=i + j,
                    vector={
                        "dense": dense_embeddings[j].tolist(),
                        "sparse": models.SparseVector(
                            indices=sparse_embeddings[j].indices.tolist(),
                            values=sparse_embeddings[j].values.tolist()
                        )
                    },
                    payload={
                        'statute_idx': statute['idx'],
                        'citation': statute['citation'],
                        'state': statute['state'],
                        'text': statute['text'],
                        'path': statute['path'],
                        'is_golden': statute['is_golden']
                    }
                )
                points.append(point)
            
            # Upload batch
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            progress.advance(task, len(batch))
    
    console.print(f"  ✓ Upload complete!\n")

def verify_collection(client, expected_count, golden_count):
    """Verify collection contents."""
    console.print("[cyan]Step 5: Verifying collection...[/cyan]")
    
    info = client.get_collection(COLLECTION_NAME)
    actual_count = info.points_count
    
    console.print(f"  • Total points: [bold green]{actual_count}[/bold green] (expected: {expected_count})")
    console.print(f"  • Golden passages in dataset: [bold green]{golden_count}[/bold green]")
    
    if actual_count == expected_count:
        console.print(f"  ✓ [bold green]Verification passed![/bold green]\n")
    else:
        console.print(f"  ⚠ [yellow]Count mismatch: expected {expected_count}, got {actual_count}[/yellow]\n")

def main():
    print_header()
    
    # Step 1: Load questions and golden IDs
    questions, golden_ids = load_questions_and_golden_ids()
    
    # Step 2: Load statutes (golden + noise)
    statutes, golden_statutes = load_statutes(golden_ids, NOISE_STATUTES)
    
    # Step 3: Initialize Qdrant and models
    console.print("[cyan]Initializing Qdrant and embedding models...[/cyan]")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    console.print(f"  ✓ Connected to Qdrant")
    
    dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    console.print(f"  ✓ Loaded dense model: {DENSE_MODEL_NAME}")
    
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    console.print(f"  ✓ Loaded sparse model: {SPARSE_MODEL_NAME}\n")
    
    # Step 4: Create collection
    create_collection(client)
    
    # Step 5: Embed and upload
    embed_and_upload(client, statutes, dense_model, sparse_model)
    
    # Step 6: Verify
    verify_collection(client, len(statutes), len(golden_statutes))
    
    # Summary
    console.print("="*80)
    console.print("[bold green]✅ FOCUSED TEST COLLECTION CREATED![/bold green]")
    console.print("="*80)
    console.print(f"\nCollection: [bold cyan]{COLLECTION_NAME}[/bold cyan]")
    console.print(f"Questions: {len(questions)}")
    console.print(f"Total Statutes: {len(statutes)} (Golden: {len(golden_statutes)}, Noise: {len(statutes) - len(golden_statutes)})")
    console.print(f"\nNext step: Run benchmark script to test retrieval")
    console.print("="*80 + "\n")

if __name__ == "__main__":
    main()

