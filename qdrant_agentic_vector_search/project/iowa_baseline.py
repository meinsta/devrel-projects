"""
Iowa Housing Statute Retrieval - Baseline System

Using BGE-large embeddings (via FastEmbed) with Qdrant vector search to build a simple
baseline retrieval system for Iowa housing statutes from the HousingQA dataset.
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from datasets import load_dataset
from fastembed import TextEmbedding
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import box
import random
import uuid
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Initialize rich console with color palette
console = Console()

QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = "iowa_statutes_baseline"


def get_embeddings_batch(embedding_model, texts):
    """Generates embeddings for a batch of texts using FastEmbed.
    
    Args:
        embedding_model: FastEmbed TextEmbedding model
        texts: A list of strings to embed
        
    Returns:
        A list of embedding vectors (as lists)
    """
    try:
        embeddings = list(embedding_model.embed(texts))
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        print(f"Error getting embeddings: {e}")
        raise


def load_iowa_data(num_questions=None, corpus_size=None):
    """Load Iowa questions and statutes from HousingQA dataset.
    
    Args:
        num_questions: Number of test questions to use (None = all Iowa questions)
        corpus_size: Total number of statutes to index (None = all Iowa statutes)
        
    Returns:
        tuple: (test_questions, test_statutes, golden_statute_ids)
    """
    console.print("\n[bold blue]📚 Loading HousingQA dataset...[/bold blue]")
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Loading questions...", total=None)
        questions_dataset = load_dataset(
            "reglab/housing_qa",
            "questions",
            split="test",
            trust_remote_code=True
        )
        progress.update(task, completed=True)
        
        task = progress.add_task("[cyan]Loading statutes corpus...", total=None)
        statutes_dataset = load_dataset(
            "reglab/housing_qa", 
            "statutes", 
            split="corpus",
            trust_remote_code=True
        )
        progress.update(task, completed=True)
    
    console.print(f"✓ Total questions: [bold green]{len(questions_dataset):,}[/bold green]")
    console.print(f"✓ Total statutes: [bold green]{len(statutes_dataset):,}[/bold green]")
    
    # Filter Iowa questions
    console.print("\n[cyan]Filtering Iowa data...[/cyan]")
    iowa_questions = []
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:,}/{task.total:,}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing questions...", total=len(questions_dataset))
        
        for item in questions_dataset:
            if item['state'] and item['state'].lower() == 'iowa':
                # Extract statute indices
                statute_ids = []
                if 'statutes' in item and item['statutes']:
                    statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
                
                iowa_questions.append({
                    'idx': item['idx'],
                    'question': item['question'],
                    'answer': item['answer'],
                    'golden_statute_ids': statute_ids
                })
            progress.advance(task)
    
    # Create statute lookup and filter Iowa statutes
    statute_lookup = {}
    iowa_statutes = []
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:,}/{task.total:,}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing statutes...", total=len(statutes_dataset))
        
        for item in statutes_dataset:
            statute = {
                'idx': item['idx'],
                'citation': item['citation'],
                'state': item['state'],
                'text': item['text'],
                'path': item['path']
            }
            statute_lookup[item['idx']] = statute
            
            if item['state'] == 'iowa':
                iowa_statutes.append(statute)
            
            progress.advance(task)
    
    console.print(f"\n✓ Iowa questions: [bold teal]{len(iowa_questions)}[/bold teal]")
    console.print(f"✓ Iowa statutes: [bold teal]{len(iowa_statutes):,}[/bold teal]")
    
    # Select test questions (all if num_questions is None)
    if num_questions is None:
        test_questions = iowa_questions
    else:
        test_questions = iowa_questions[:num_questions]
    
    # Collect golden statute IDs
    golden_statute_ids = set()
    for q in test_questions:
        golden_statute_ids.update(q['golden_statute_ids'])
    
    # Get golden statutes
    golden_statutes = [statute_lookup[sid] for sid in golden_statute_ids if sid in statute_lookup]
    
    # Use all Iowa statutes if corpus_size is None, otherwise add random distractors
    if corpus_size is None:
        test_statutes = iowa_statutes
        random.shuffle(test_statutes)
        random_statutes = [s for s in test_statutes if s['idx'] not in golden_statute_ids]
    else:
        # Add random distractors to reach corpus_size
        available_for_random = [s for s in iowa_statutes if s['idx'] not in golden_statute_ids]
        num_random_needed = corpus_size - len(golden_statutes)
        num_random_needed = min(num_random_needed, len(available_for_random))
        
        random_statutes = random.sample(available_for_random, num_random_needed) if num_random_needed > 0 else []
        
        # Combine and shuffle
        test_statutes = golden_statutes + random_statutes
        random.shuffle(test_statutes)
    
    # Create composition table
    table = Table(title="📊 Test Corpus Composition", box=box.ROUNDED, title_style="bold #8547FF")  # Violet
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green", justify="right")
    
    table.add_row("Test Questions", str(len(test_questions)))
    table.add_row("Total Statutes Indexed", f"{len(test_statutes):,}")
    table.add_row("Golden (Relevant)", str(len(golden_statutes)))
    table.add_row("Random (Distractors)", f"{len(random_statutes):,}")
    table.add_row("Relevant Ratio", f"{len(golden_statutes)/len(test_statutes)*100:.2f}%")
    
    console.print("\n", table)
    
    return test_questions, test_statutes, golden_statute_ids


def index_statutes(qdrant_client, embedding_model, statutes):
    """Index statutes in Qdrant with BGE embeddings.
    
    Args:
        qdrant_client: Qdrant client
        embedding_model: FastEmbed TextEmbedding model
        statutes: List of statute dictionaries
    """
    console.print(f"\n[bold #DC244C]🔨 Indexing {len(statutes):,} statutes with {EMBEDDING_MODEL}[/bold #DC244C]")
    
    # Delete collection if exists
    try:
        qdrant_client.delete_collection(COLLECTION_NAME)
        console.print(f"[dim]Deleted existing collection: {COLLECTION_NAME}[/dim]")
    except:
        pass
    
    # Generate embeddings in batches to avoid memory issues
    texts = [s['text'] for s in statutes]
    batch_size = 64  # Process 64 statutes at a time (small model is faster)
    all_embeddings = []
    
    console.print("[cyan]Generating embeddings...[/cyan]")
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches", unit="batch"):
        batch_texts = texts[i:i + batch_size]
        batch_embeddings = get_embeddings_batch(embedding_model, batch_texts)
        all_embeddings.extend(batch_embeddings)
    
    console.print(f"✓ Generated [bold green]{len(all_embeddings):,}[/bold green] embeddings")
    
    # Create collection
    vector_size = len(all_embeddings[0])
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE
        )
    )
    console.print(f"✓ Created collection (vector size: [bold blue]{vector_size}[/bold blue])")
    
    # Upload points in batches with progress
    upload_batch_size = 100  # Upload 100 at a time
    
    console.print("[cyan]Uploading to Qdrant...[/cyan]")
    for i in tqdm(range(0, len(statutes), upload_batch_size), desc="Uploading batches", unit="batch"):
        batch_statutes = statutes[i:i + upload_batch_size]
        batch_embeddings = all_embeddings[i:i + upload_batch_size]
        
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    'idx': statute['idx'],
                    'citation': statute['citation'],
                    'state': statute['state'],
                    'path': statute['path'],
                    'text': statute['text']
                }
            )
            for statute, embedding in zip(batch_statutes, batch_embeddings)
        ]
        
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
    
    console.print(f"[bold green]✓ Indexed {len(statutes):,} statutes successfully![/bold green]")


def evaluate_retrieval(qdrant_client, embedding_model, test_questions, golden_ids, k=5):
    """Evaluate retrieval system on test questions.
    
    Args:
        qdrant_client: Qdrant client
        embedding_model: FastEmbed TextEmbedding model
        test_questions: List of test question dictionaries
        golden_ids: Set of all golden statute IDs
        k: Number of results to retrieve
        
    Returns:
        dict: Average metrics across all questions
    """
    console.print(Panel.fit(
        "[bold white]🎯 EVALUATING RETRIEVAL SYSTEM[/bold white]",
        border_style="#8547FF",  # Violet
        box=box.DOUBLE
    ))
    
    all_metrics = []
    
    for i, question in enumerate(test_questions, 1):
        question_golden_ids = set(question['golden_statute_ids'])
        
        console.print(f"\n[bold #038585]━━━ TEST {i}/{len(test_questions)} ━━━[/bold #038585]")
        console.print(Panel(
            f"[bold white]{question['question']}[/bold white]",
            title=f"[#DC244C]Question {i}[/#DC244C]",
            border_style="#2F6FF0"  # Blue
        ))
        console.print(f"[dim]Golden statutes needed: {list(question_golden_ids)}[/dim]")
        
        # Embed the question
        question_embedding = get_embeddings_batch(embedding_model, [question['question']])[0]
        
        # Search using query_points (search is deprecated)
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=question_embedding,
            limit=k
        ).points
        
        # Evaluate
        retrieved_ids = [result.payload['idx'] for result in results]
        relevant_retrieved = [rid for rid in retrieved_ids if rid in question_golden_ids]
        
        # Calculate metrics
        R = len(question_golden_ids)  # R = number of golden docs for this question
        
        # Precision@R: Check precision at position R (more fair than fixed @5)
        retrieved_top_r = retrieved_ids[:R]
        relevant_in_top_r = [rid for rid in retrieved_top_r if rid in question_golden_ids]
        precision_at_r = len(relevant_in_top_r) / R if R > 0 else 0
        
        # Precision@k (for reference)
        precision_at_k = len(relevant_retrieved) / k if k > 0 else 0
        
        # Recall@k
        recall = len(relevant_retrieved) / len(question_golden_ids) if question_golden_ids else 0
        
        # Hit@k: Binary - did we find at least one relevant document?
        hit_at_k = 1 if len(relevant_retrieved) > 0 else 0
        
        # MRR: position of first relevant result
        mrr = 0
        for pos, rid in enumerate(retrieved_ids, 1):
            if rid in question_golden_ids:
                mrr = 1.0 / pos
                break
        
        # Print results
        results_table = Table(title=f"Top {k} Results", box=box.SIMPLE, title_style="bold cyan")
        results_table.add_column("#", style="dim", width=3)
        results_table.add_column("Status", width=15)
        results_table.add_column("Score", justify="right", style="yellow", width=8)
        results_table.add_column("Citation", style="white")
        
        for pos, result in enumerate(results, 1):
            is_golden_this_q = result.payload['idx'] in question_golden_ids
            is_golden_other_q = result.payload['idx'] in golden_ids and not is_golden_this_q
            
            if is_golden_this_q:
                marker = "[bold green]✓ GOLDEN[/bold green]"
            elif is_golden_other_q:
                marker = "[yellow]~ OTHER Q[/yellow]"
            else:
                marker = "[dim]✗ RANDOM[/dim]"
            
            results_table.add_row(
                str(pos),
                marker,
                f"{result.score:.4f}",
                result.payload['citation'][:60]
            )
        
        console.print("\n", results_table)
        
        # Metrics table
        metrics_table = Table(box=box.ROUNDED, show_header=False, border_style="#038585")  # Teal
        metrics_table.add_column("Metric", style="bold cyan", width=20)
        metrics_table.add_column("Value", style="bold green" if hit_at_k else "bold red")
        
        metrics_table.add_row(f"Hit@{k}", "[bold green]YES ✓[/bold green]" if hit_at_k else "[bold red]NO ✗[/bold red]")
        metrics_table.add_row(f"Precision@R (R={R})", f"{precision_at_r:.2%} ({len(relevant_in_top_r)}/{R})")
        metrics_table.add_row(f"Recall@{k}", f"{recall:.2%} ({len(relevant_retrieved)}/{len(question_golden_ids)})")
        metrics_table.add_row("MRR", f"{mrr:.4f}")
        
        console.print("\n", metrics_table)
        
        all_metrics.append({
            'hit_at_k': hit_at_k,
            'precision_at_r': precision_at_r,
            'R': R,
            'recall': recall,
            'mrr': mrr,
            'relevant_retrieved': len(relevant_retrieved)
        })
    
    # Calculate averages
    avg_hit = sum(m['hit_at_k'] for m in all_metrics) / len(all_metrics)
    avg_precision_at_r = sum(m['precision_at_r'] for m in all_metrics) / len(all_metrics)
    avg_recall = sum(m['recall'] for m in all_metrics) / len(all_metrics)
    avg_mrr = sum(m['mrr'] for m in all_metrics) / len(all_metrics)
    avg_r = sum(m['R'] for m in all_metrics) / len(all_metrics)
    
    # Final results
    final_table = Table(
        title="🏆 OVERALL RESULTS",
        box=box.DOUBLE_EDGE,
        title_style="bold #8547FF",  # Violet
        border_style="#DC244C"  # Amaranth
    )
    final_table.add_column("Metric", style="bold cyan", width=22)
    final_table.add_column("Value", style="bold green", justify="right")
    
    final_table.add_row("Questions Tested", str(len(test_questions)))
    final_table.add_row("Avg R (golden docs/q)", f"{avg_r:.1f}")
    final_table.add_row("", "")  # Separator
    final_table.add_row(f"Hit@{k}", f"{avg_hit:.2%} ({int(avg_hit * len(all_metrics))}/{len(test_questions)} questions)")
    final_table.add_row(f"Precision@R (avg)", f"{avg_precision_at_r:.2%}")
    final_table.add_row(f"Recall@{k}", f"{avg_recall:.2%}")
    final_table.add_row(f"MRR@{k}", f"{avg_mrr:.4f}")
    
    console.print("\n", final_table)
    
    return {
        'avg_hit': avg_hit,
        'avg_precision_at_r': avg_precision_at_r,
        'avg_recall': avg_recall,
        'avg_mrr': avg_mrr
    }


def main():
    """Main function to run the baseline retrieval system."""
    
    # Banner
    console.print(Panel.fit(
        "[bold white]Iowa Housing Statute Retrieval[/bold white]\n"
        "[dim]Baseline Dense Retrieval System[/dim]",
        border_style="#DC244C",  # Amaranth
        box=box.DOUBLE
    ))
    
    # Initialize clients
    console.print("\n[bold blue]🚀 Initializing...[/bold blue]")
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"[cyan]Loading {EMBEDDING_MODEL}...", total=None)
        embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
        progress.update(task, completed=True)
        
        task = progress.add_task("[cyan]Connecting to Qdrant Cloud...", total=None)
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
        progress.update(task, completed=True)
    
    console.print("[bold green]✓ Initialization complete![/bold green]")
    
    # Load data - use all Iowa questions and statutes
    test_questions, test_statutes, golden_ids = load_iowa_data(num_questions=None, corpus_size=None)
    
    # Index statutes
    index_statutes(qdrant_client, embedding_model, test_statutes)
    
    # Evaluate
    metrics = evaluate_retrieval(qdrant_client, embedding_model, test_questions, golden_ids, k=5)
    
    console.print("\n[bold green]✓ Baseline evaluation complete![/bold green]")
    console.print("[dim]Results saved to collection:[/dim]", COLLECTION_NAME)


if __name__ == "__main__":
    main()

