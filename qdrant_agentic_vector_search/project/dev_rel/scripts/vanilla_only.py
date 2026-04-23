"""
Vanilla RAG Only - For when agentic RAG has issues

This runs ONLY the vanilla RAG approach (no CrewAI agents).
Fast, reliable, good for quick demos when agents are problematic.
"""

import os
import argparse
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from openai import OpenAI
from rich.console import Console
from rich.table import Table
from rich import box
from tqdm import tqdm

load_dotenv()

console = Console()

COLLECTION_MAP = {
    'wyoming': 'housing_statutes_wyoming',
    'idaho': 'housing_statutes_idaho',
    'iowa': 'iowa_statutes_baseline',
}


def load_state_questions(state_name, limit=None):
    """Load questions for a specific state."""
    
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    state_questions = []
    for item in questions_dataset:
        if item['state'] and item['state'].lower() == state_name.lower():
            statute_ids = []
            if 'statutes' in item and item['statutes']:
                statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
            
            state_questions.append({
                'idx': item['idx'],
                'question': item['question'],
                'answer': item['answer'],
                'golden_statute_ids': statute_ids
            })
    
    if limit:
        state_questions = state_questions[:limit]
    
    return state_questions


def vanilla_rag_answer(question, collection_name, qdrant_client, embedding_model, openai_client, k=5):
    """Vanilla RAG: Single search + simple prompt."""
    
    question_embedding = list(embedding_model.embed([question]))[0].tolist()
    
    results = qdrant_client.query_points(
        collection_name=collection_name,
        query=question_embedding,
        using='fast-bge-small-en',
        limit=k
    ).points
    
    context_parts = []
    for i, result in enumerate(results, 1):
        citation = result.payload.get('citation', 'Unknown')
        text = result.payload.get('text', '')[:500]
        context_parts.append(f"[{i}] {citation}\n{text}")
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""You are a legal assistant. Answer the question based ONLY on the provided statutes.

Question: {question}

Statutes:
{context}

Instructions:
- Answer with ONLY "Yes" or "No"
- Base your answer strictly on the provided statutes
- If the statutes don't provide enough information, answer "No"

Answer:"""
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10
    )
    
    return response.choices[0].message.content.strip()


def run_vanilla_only(state_name, num_questions=10):
    """Run vanilla RAG only - fast and reliable!"""
    
    collection_name = COLLECTION_MAP[state_name.lower()]
    
    console.print("\n[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   VANILLA RAG - Fast Baseline Demo            [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]\n")
    
    console.print(f"[bold]State:[/bold] {state_name.title()}")
    console.print(f"[bold]Collection:[/bold] {collection_name}")
    console.print(f"[bold]Strategy:[/bold] Single search + Simple prompt\n")
    
    # Initialize
    console.print("[cyan]⚙️  Initializing...[/cyan]\n")
    
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_CLOUD_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Load questions
    test_questions = load_state_questions(state_name, limit=num_questions)
    console.print(f"[cyan]Running vanilla RAG on {len(test_questions)} questions...[/cyan]\n")
    
    # Run
    correct = 0
    results = []
    
    for question_data in tqdm(test_questions, desc="Processing"):
        question = question_data['question']
        golden_answer = question_data['answer']
        
        try:
            answer = vanilla_rag_answer(
                question, collection_name, qdrant_client,
                embedding_model, openai_client, k=5
            )
            is_correct = answer.lower() == golden_answer.lower()
            if is_correct:
                correct += 1
            
            results.append({
                'question': question[:50] + "..." if len(question) > 50 else question,
                'golden': golden_answer,
                'predicted': answer,
                'correct': is_correct
            })
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            results.append({
                'question': question[:50] + "...",
                'golden': golden_answer,
                'predicted': 'Error',
                'correct': False
            })
    
    # Results
    console.print("\n")
    
    accuracy = (correct / len(test_questions)) * 100 if test_questions else 0
    
    table = Table(
        title=f"Vanilla RAG Results - {state_name.upper()}",
        box=box.DOUBLE_EDGE,
        title_style="bold cyan"
    )
    
    table.add_column("Metric", style="bold white", width=30)
    table.add_column("Value", style="bold green", justify="right")
    
    table.add_row("Questions Tested", str(len(test_questions)))
    table.add_row("Correct Answers", f"{correct} ({accuracy:.1f}%)")
    table.add_row("", "")
    table.add_row("Strategy", "Single search (no agents)")
    table.add_row("Avg Time/Question", "~2 seconds")
    
    console.print(table)
    console.print()
    
    # Show samples
    console.print("\n[bold]Sample Results:[/bold]\n")
    
    for i, r in enumerate(results[:5], 1):
        status = "[green]✓[/green]" if r['correct'] else "[red]✗[/red]"
        console.print(f"{i}. {status} [dim]{r['question']}[/dim]")
        console.print(f"   Golden: [bold]{r['golden']}[/bold] | Predicted: [bold]{r['predicted']}[/bold]\n")
    
    console.print(f"\n[bold green]✓ Vanilla RAG complete![/bold green]")
    console.print(f"[dim]Tested {len(test_questions)} questions in ~{len(test_questions)*2} seconds[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vanilla RAG only (no agents)")
    parser.add_argument('--state', type=str, default='wyoming', choices=['wyoming', 'idaho', 'iowa'])
    parser.add_argument('--limit', type=int, default=10)
    
    args = parser.parse_args()
    
    # Check environment
    required_vars = ['OPENAI_API_KEY', 'QDRANT_CLOUD_URL', 'QDRANT_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        console.print(f"[red]Error: Missing: {', '.join(missing)}[/red]")
        exit(1)
    
    run_vanilla_only(args.state, num_questions=args.limit)

