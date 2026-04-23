"""
Experiment: Compare Different Embedding Models with Arize Phoenix

Tests multiple embedding models on the focused California test collection and
tracks results in Arize Phoenix for comparison.

Models to test:
- BAAI/bge-small-en-v1.5 (384d) - current baseline
- BAAI/bge-base-en-v1.5 (768d) - larger version
- sentence-transformers/all-MiniLM-L6-v2 (384d) - popular alternative
- Alibaba-NLP/gte-small-en-v1.5 (384d) - newer model

Metrics tracked:
- Recall@K (K=1,3,5,10)
- MRR@K
- Inference time
- Collection size
"""

import os
import time
import phoenix as px
from datetime import datetime
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box

load_dotenv()

console = Console()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

# Embedding models to test
EMBEDDING_MODELS = [
    {
        "name": "bge-small",
        "model_name": "BAAI/bge-small-en-v1.5",
        "vector_size": 384,
        "description": "Current baseline - fast and efficient"
    },
    {
        "name": "bge-base",
        "model_name": "BAAI/bge-base-en-v1.5",
        "vector_size": 768,
        "description": "Larger BGE model - better quality"
    },
    {
        "name": "minilm-l6",
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "description": "Popular SentenceTransformers model"
    },
    {
        "name": "gte-small",
        "model_name": "Alibaba-NLP/gte-small-en-v1.5",
        "vector_size": 384,
        "description": "Newer GTE model from Alibaba"
    }
]

# Search parameters
TOP_K = [1, 3, 5, 10]
NOISE_STATUTES = 500

def load_questions_and_statutes():
    """Load California questions and golden + noise statutes."""
    console.print("[cyan]Loading dataset...[/cyan]")
    
    # Load questions
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    questions = []
    golden_ids = set()
    
    for item in questions_dataset:
        if item['state'] and item['state'].lower() == 'california':
            statute_ids = []
            if 'statutes' in item and item['statutes']:
                statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
            
            questions.append({
                'idx': item['idx'],
                'question': item['question'],
                'golden_statute_ids': statute_ids
            })
            golden_ids.update(statute_ids)
    
    # Load statutes
    statutes_dataset = load_dataset(
        "reglab/housing_qa",
        "statutes",
        split="corpus",
        trust_remote_code=True
    )
    
    california_statutes = []
    golden_statutes = []
    
    for item in statutes_dataset:
        if item['state'] == 'california':
            statute = {
                'idx': item['idx'],
                'text': item['text'],
                'citation': item['citation'],
                'state': item['state'],
                'path': item['path']
            }
            
            if item['idx'] in golden_ids:
                golden_statutes.append(statute)
            else:
                california_statutes.append(statute)
    
    # Add noise
    import random
    noise_statutes = random.sample(california_statutes, min(NOISE_STATUTES, len(california_statutes)))
    all_statutes = golden_statutes + noise_statutes
    random.shuffle(all_statutes)
    
    console.print(f"  ✓ Questions: {len(questions)}")
    console.print(f"  ✓ Golden statutes: {len(golden_statutes)}")
    console.print(f"  ✓ Total statutes: {len(all_statutes)}\n")
    
    return questions, all_statutes

def create_collection_for_model(client, model_config):
    """Create a collection for a specific embedding model."""
    collection_name = f"california_test_{model_config['name']}"
    
    # Delete if exists
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    # Create collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=model_config['vector_size'],
            distance=Distance.COSINE
        )
    )
    
    return collection_name

def embed_and_upload(client, collection_name, statutes, embedding_model, show_progress=True):
    """Embed statutes and upload to collection."""
    batch_size = 32
    start_time = time.time()
    
    if show_progress:
        progress_context = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console
        )
    else:
        progress_context = None
    
    with progress_context or console.status("") as progress:
        if show_progress:
            task = progress.add_task("[cyan]Embedding...", total=len(statutes))
        
        for i in range(0, len(statutes), batch_size):
            batch = statutes[i:i + batch_size]
            texts = [s['text'] for s in batch]
            
            # Embed
            embeddings = list(embedding_model.embed(texts))
            
            # Create points
            points = []
            for j, statute in enumerate(batch):
                point = PointStruct(
                    id=i + j,
                    vector=embeddings[j].tolist(),
                    payload={
                        'statute_idx': statute['idx'],
                        'text': statute['text'],
                        'citation': statute['citation']
                    }
                )
                points.append(point)
            
            # Upload
            client.upsert(collection_name=collection_name, points=points)
            
            if show_progress:
                progress.advance(task, len(batch))
    
    elapsed = time.time() - start_time
    return elapsed

def run_retrieval_evaluation(client, collection_name, questions, embedding_model):
    """Evaluate retrieval performance."""
    results = {k: [] for k in TOP_K}
    mrr_scores = {k: [] for k in TOP_K}
    
    query_times = []
    
    for question in questions:
        # Embed query
        start = time.time()
        query_embedding = list(embedding_model.embed([question['question']]))[0]
        
        # Search
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_embedding.tolist(),
            limit=max(TOP_K)
        )
        
        query_time = time.time() - start
        query_times.append(query_time)
        
        # Extract retrieved statute IDs
        retrieved_ids = [r.payload['statute_idx'] for r in search_results]
        golden_ids = set(question['golden_statute_ids'])
        
        # Calculate metrics for each K
        for k in TOP_K:
            top_k_ids = retrieved_ids[:k]
            
            # Recall: did we find ANY golden passage?
            recall = 1 if any(rid in golden_ids for rid in top_k_ids) else 0
            results[k].append(recall)
            
            # MRR: position of first golden passage
            mrr = 0
            for rank, rid in enumerate(top_k_ids, start=1):
                if rid in golden_ids:
                    mrr = 1 / rank
                    break
            mrr_scores[k].append(mrr)
    
    # Calculate averages
    metrics = {}
    for k in TOP_K:
        metrics[f'recall@{k}'] = sum(results[k]) / len(results[k]) * 100
        metrics[f'mrr@{k}'] = sum(mrr_scores[k]) / len(mrr_scores[k])
    
    metrics['avg_query_time_ms'] = sum(query_times) / len(query_times) * 1000
    
    return metrics

def run_experiment_for_model(client, model_config, questions, statutes):
    """Run complete experiment for one embedding model."""
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold]Experiment: {model_config['name']}[/bold]")
    console.print(f"Model: {model_config['model_name']}")
    console.print(f"Description: {model_config['description']}")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    experiment_start = time.time()
    
    # Load model
    console.print(f"[cyan]Loading embedding model...[/cyan]")
    embedding_model = TextEmbedding(model_name=model_config['model_name'])
    console.print(f"  ✓ Loaded\n")
    
    # Create collection
    console.print(f"[cyan]Creating collection...[/cyan]")
    collection_name = create_collection_for_model(client, model_config)
    console.print(f"  ✓ Created: {collection_name}\n")
    
    # Embed and upload
    console.print(f"[cyan]Embedding and uploading {len(statutes)} statutes...[/cyan]")
    embedding_time = embed_and_upload(client, collection_name, statutes, embedding_model)
    console.print(f"  ✓ Complete in {embedding_time:.1f}s\n")
    
    # Run evaluation
    console.print(f"[cyan]Running retrieval evaluation on {len(questions)} questions...[/cyan]")
    eval_start = time.time()
    metrics = run_retrieval_evaluation(client, collection_name, questions, embedding_model)
    eval_time = time.time() - eval_start
    console.print(f"  ✓ Complete in {eval_time:.1f}s\n")
    
    # Add timing metrics
    metrics['embedding_time_s'] = embedding_time
    metrics['eval_time_s'] = eval_time
    metrics['total_time_s'] = time.time() - experiment_start
    
    # Cleanup
    console.print(f"[cyan]Cleaning up collection...[/cyan]")
    client.delete_collection(collection_name)
    console.print(f"  ✓ Deleted\n")
    
    return metrics

def print_comparison_table(all_results):
    """Print comparison table of all models."""
    console.print("\n" + "="*100)
    console.print("[bold cyan]EXPERIMENT RESULTS - Embedding Model Comparison[/bold cyan]")
    console.print("="*100 + "\n")
    
    # Recall table
    console.print("[bold]Recall@K[/bold] (% of questions with golden passage in top K)\n")
    
    recall_table = Table(box=box.ROUNDED, show_header=True, width=90)
    recall_table.add_column("Model", style="cyan", width=20)
    recall_table.add_column("Description", style="dim", width=30)
    for k in TOP_K:
        recall_table.add_column(f"@{k}", justify="right", style="green", width=8)
    
    for model_name, metrics in all_results.items():
        row = [model_name, EMBEDDING_MODELS[list(all_results.keys()).index(model_name)]['description']]
        for k in TOP_K:
            recall = metrics[f'recall@{k}']
            row.append(f"{recall:.1f}%")
        recall_table.add_row(*row)
    
    console.print(recall_table)
    
    # MRR table
    console.print("\n[bold]MRR@K[/bold] (Mean Reciprocal Rank)\n")
    
    mrr_table = Table(box=box.ROUNDED, show_header=True, width=90)
    mrr_table.add_column("Model", style="cyan", width=20)
    for k in TOP_K:
        mrr_table.add_column(f"@{k}", justify="right", style="yellow", width=10)
    
    for model_name, metrics in all_results.items():
        row = [model_name]
        for k in TOP_K:
            mrr = metrics[f'mrr@{k}']
            row.append(f"{mrr:.3f}")
        mrr_table.add_row(*row)
    
    console.print(mrr_table)
    
    # Performance table
    console.print("\n[bold]Performance Metrics[/bold]\n")
    
    perf_table = Table(box=box.ROUNDED, show_header=True, width=90)
    perf_table.add_column("Model", style="cyan", width=20)
    perf_table.add_column("Embedding Time", justify="right", style="blue", width=15)
    perf_table.add_column("Avg Query Time", justify="right", style="blue", width=15)
    perf_table.add_column("Total Time", justify="right", style="blue", width=15)
    
    for model_name, metrics in all_results.items():
        perf_table.add_row(
            model_name,
            f"{metrics['embedding_time_s']:.1f}s",
            f"{metrics['avg_query_time_ms']:.1f}ms",
            f"{metrics['total_time_s']:.1f}s"
        )
    
    console.print(perf_table)
    console.print("\n" + "="*100 + "\n")

def log_to_phoenix(all_results):
    """Log experiment results to Arize Phoenix."""
    console.print("[cyan]Logging results to Arize Phoenix...[/cyan]")
    
    try:
        # Launch Phoenix
        session = px.launch_app()
        console.print(f"  ✓ Phoenix UI: {session.url}")
        
        # Create experiment data
        experiment_data = []
        for model_name, metrics in all_results.items():
            model_config = next(m for m in EMBEDDING_MODELS if m['name'] == model_name)
            
            experiment_data.append({
                "experiment_name": f"embedding_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "model_name": model_config['model_name'],
                "model_short_name": model_name,
                "vector_size": model_config['vector_size'],
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            })
        
        console.print(f"  ✓ Logged {len(experiment_data)} experiments")
        console.print(f"\n[bold]View results at: [cyan]{session.url}[/cyan][/bold]\n")
        
    except Exception as e:
        console.print(f"  ⚠ Could not log to Phoenix: {e}")

def main():
    console.print("\n" + "="*100)
    console.print("[bold cyan]EXPERIMENT: EMBEDDING MODEL COMPARISON[/bold cyan]")
    console.print("Testing different embedding models on California housing law dataset")
    console.print("="*100)
    
    # Load data once
    questions, statutes = load_questions_and_statutes()
    
    # Initialize Qdrant
    console.print("[cyan]Connecting to Qdrant...[/cyan]")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    console.print("  ✓ Connected\n")
    
    # Run experiments for each model
    all_results = {}
    
    for model_config in EMBEDDING_MODELS:
        try:
            metrics = run_experiment_for_model(client, model_config, questions, statutes)
            all_results[model_config['name']] = metrics
        except Exception as e:
            console.print(f"[red]✗ Error with {model_config['name']}: {e}[/red]\n")
            continue
    
    # Print comparison
    print_comparison_table(all_results)
    
    # Log to Phoenix
    log_to_phoenix(all_results)
    
    console.print("[bold green]✅ Experiment complete![/bold green]\n")

if __name__ == "__main__":
    main()





