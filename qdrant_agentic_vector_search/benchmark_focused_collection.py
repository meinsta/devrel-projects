"""
Benchmark Retrieval on Focused Test Collection

Tests vanilla Qdrant search (dense, sparse, hybrid) on the focused collection:
- 181 California questions
- 40 golden passages
- 500 noise statutes
- Total: 540 statutes

Metrics:
- Recall@K: Percentage of questions where golden passage is in top K results
- MRR: Mean Reciprocal Rank of the golden passage
"""

import os
import time
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box

load_dotenv()

console = Console()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = "california_housing_test_focused"

# Embedding models
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"

# Search parameters
TOP_K = [1, 3, 5, 10]

def load_test_questions():
    """Load California test questions with golden passage IDs."""
    console.print("\n[cyan]Loading test questions...[/cyan]")
    
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    test_questions = []
    for item in questions_dataset:
        if item['state'] and item['state'].lower() == 'california':
            statute_ids = []
            if 'statutes' in item and item['statutes']:
                statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
            
            test_questions.append({
                'idx': item['idx'],
                'question': item['question'],
                'answer': item['answer'],
                'golden_statute_ids': statute_ids
            })
    
    console.print(f"  ✓ Loaded [bold green]{len(test_questions)}[/bold green] test questions\n")
    return test_questions

def dense_search(client, query, dense_model, k=10):
    """Perform dense vector search."""
    # Embed query
    query_embedding = list(dense_model.embed([query]))[0]
    
    # Search
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding.tolist(),
        using="dense",
        limit=k
    )
    
    return results.points

def sparse_search(client, query, sparse_model, k=10):
    """Perform sparse vector search."""
    # Embed query
    query_embedding = list(sparse_model.embed([query]))[0]
    
    # Search
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.SparseVector(
            indices=query_embedding.indices.tolist(),
            values=query_embedding.values.tolist()
        ),
        using="sparse",
        limit=k
    )
    
    return results.points

def hybrid_search(client, query, dense_model, sparse_model, k=10):
    """Perform hybrid search with RRF fusion."""
    # Get dense results
    dense_results = dense_search(client, query, dense_model, k=k*2)
    
    # Get sparse results
    sparse_results = sparse_search(client, query, sparse_model, k=k*2)
    
    # RRF fusion
    rrf_k = 60
    scores = {}
    
    for rank, result in enumerate(dense_results, start=1):
        statute_idx = result.payload['statute_idx']
        scores[statute_idx] = scores.get(statute_idx, 0) + 1 / (rrf_k + rank)
    
    for rank, result in enumerate(sparse_results, start=1):
        statute_idx = result.payload['statute_idx']
        scores[statute_idx] = scores.get(statute_idx, 0) + 1 / (rrf_k + rank)
    
    # Sort by score and return top K statute IDs
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [statute_idx for statute_idx, _ in ranked[:k]]

def calculate_metrics(results_map, questions):
    """Calculate Recall@K and MRR for each search method."""
    metrics = {}
    
    for method_name, method_results in results_map.items():
        method_metrics = {}
        
        for k in TOP_K:
            recalls = []
            reciprocal_ranks = []
            
            for question in questions:
                golden_ids = set(question['golden_statute_ids'])
                retrieved_ids = method_results[question['idx']][:k]
                
                # Recall@K: Did we retrieve ANY golden passage in top K?
                recall = 1 if any(rid in golden_ids for rid in retrieved_ids) else 0
                recalls.append(recall)
                
                # MRR: Position of first golden passage
                for rank, rid in enumerate(retrieved_ids, start=1):
                    if rid in golden_ids:
                        reciprocal_ranks.append(1 / rank)
                        break
                else:
                    reciprocal_ranks.append(0)
            
            method_metrics[f'recall@{k}'] = sum(recalls) / len(recalls) * 100
            method_metrics[f'mrr@{k}'] = sum(reciprocal_ranks) / len(reciprocal_ranks)
        
        metrics[method_name] = method_metrics
    
    return metrics

def run_benchmark(client, questions, dense_model, sparse_model):
    """Run benchmark on all search methods."""
    console.print("[cyan]Running benchmark on all search methods...[/cyan]\n")
    
    results_map = {
        'Dense': {},
        'Sparse': {},
        'Hybrid': {}
    }
    
    start_time = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        console=console
    ) as progress:
        
        # Dense search
        task = progress.add_task("[cyan]Dense search...", total=len(questions))
        for q in questions:
            results = dense_search(client, q['question'], dense_model, k=max(TOP_K))
            results_map['Dense'][q['idx']] = [r.payload['statute_idx'] for r in results]
            progress.advance(task)
        
        # Sparse search
        task = progress.add_task("[cyan]Sparse search...", total=len(questions))
        for q in questions:
            results = sparse_search(client, q['question'], sparse_model, k=max(TOP_K))
            results_map['Sparse'][q['idx']] = [r.payload['statute_idx'] for r in results]
            progress.advance(task)
        
        # Hybrid search
        task = progress.add_task("[cyan]Hybrid search...", total=len(questions))
        for q in questions:
            results = hybrid_search(client, q['question'], dense_model, sparse_model, k=max(TOP_K))
            results_map['Hybrid'][q['idx']] = results
            progress.advance(task)
    
    elapsed = time.time() - start_time
    
    console.print(f"\n  ✓ Completed in [bold green]{elapsed:.1f}s[/bold green]\n")
    
    return results_map

def print_results(metrics):
    """Print benchmark results in a table."""
    console.print("\n" + "="*80)
    console.print("[bold cyan]BENCHMARK RESULTS - Focused Test Collection[/bold cyan]")
    console.print("="*80 + "\n")
    
    # Recall table
    console.print("[bold]Recall@K[/bold] (% of questions where golden passage found in top K)\n")
    
    recall_table = Table(box=box.ROUNDED, show_header=True)
    recall_table.add_column("Search Method", style="cyan", width=15)
    for k in TOP_K:
        recall_table.add_column(f"@{k}", justify="right", style="green", width=10)
    
    for method_name, method_metrics in metrics.items():
        row = [method_name]
        for k in TOP_K:
            recall = method_metrics[f'recall@{k}']
            row.append(f"{recall:.1f}%")
        recall_table.add_row(*row)
    
    console.print(recall_table)
    
    # MRR table
    console.print("\n[bold]MRR@K[/bold] (Mean Reciprocal Rank)\n")
    
    mrr_table = Table(box=box.ROUNDED, show_header=True)
    mrr_table.add_column("Search Method", style="cyan", width=15)
    for k in TOP_K:
        mrr_table.add_column(f"@{k}", justify="right", style="yellow", width=10)
    
    for method_name, method_metrics in metrics.items():
        row = [method_name]
        for k in TOP_K:
            mrr = method_metrics[f'mrr@{k}']
            row.append(f"{mrr:.3f}")
        mrr_table.add_row(*row)
    
    console.print(mrr_table)
    console.print("\n" + "="*80 + "\n")

def main():
    console.print("\n" + "="*80)
    console.print("[bold cyan]BENCHMARK: VANILLA QDRANT SEARCH[/bold cyan]")
    console.print(f"Collection: {COLLECTION_NAME}")
    console.print("="*80)
    
    # Load questions
    questions = load_test_questions()
    
    # Initialize
    console.print("[cyan]Initializing Qdrant and embedding models...[/cyan]")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    console.print(f"  ✓ Connected to Qdrant")
    
    # Verify collection exists
    info = client.get_collection(COLLECTION_NAME)
    console.print(f"  ✓ Collection has {info.points_count:,} points")
    
    dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    console.print(f"  ✓ Loaded dense model")
    
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    console.print(f"  ✓ Loaded sparse model\n")
    
    # Run benchmark
    results_map = run_benchmark(client, questions, dense_model, sparse_model)
    
    # Calculate metrics
    console.print("[cyan]Calculating metrics...[/cyan]")
    metrics = calculate_metrics(results_map, questions)
    
    # Print results
    print_results(metrics)
    
    console.print("[bold green]✅ Benchmark complete![/bold green]\n")

if __name__ == "__main__":
    main()





