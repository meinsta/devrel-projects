"""
Vanilla RAG Example - Simple Single-Shot Retrieval + Generation

This demonstrates the traditional RAG approach:
1. User asks a question
2. System performs ONE vector search
3. Retrieved documents go to LLM
4. LLM generates answer

No iteration, no reasoning, no follow-up searches.

Usage:
    python examples/2_vanilla_rag/simple_rag.py
    python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 10
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

# Map state names to collection names
COLLECTION_MAP = {
    'wyoming': 'housing_statutes_wyoming',
    'idaho': 'housing_statutes_idaho',
    'iowa': 'iowa_statutes_baseline',
}


def load_state_questions(state_name, limit=None):
    """Load questions for a specific state."""
    
    console.print(f"[cyan]Loading {state_name.title()} questions...[/cyan]")
    
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
    
    console.print(f"[green]✓ Loaded {len(state_questions)} questions[/green]\n")
    return state_questions


def vanilla_rag_answer(question, collection_name, qdrant_client, embedding_model, openai_client, k=5):
    """
    Simple vanilla RAG: ONE search + simple prompt.
    
    This is the baseline approach - no intelligence, no iteration.
    """
    
    # Step 1: Embed the question (no reformulation, no thinking)
    question_embedding = list(embedding_model.embed([question]))[0].tolist()
    
    # Step 2: Single vector search (one shot!)
    results = qdrant_client.query_points(
        collection_name=collection_name,
        query=question_embedding,
        using='fast-bge-small-en',  # Named vector
        limit=k
    ).points
    
    # Step 3: Extract context from retrieved documents
    retrieved_statute_ids = []
    context_parts = []
    
    for i, result in enumerate(results, 1):
        statute_idx = result.payload.get('statute_idx')
        if statute_idx:
            retrieved_statute_ids.append(statute_idx)
        
        citation = result.payload.get('citation', 'Unknown')
        text = result.payload.get('text', '')[:500]  # Limit length
        
        context_parts.append(f"[{i}] {citation}\n{text}")
    
    context = "\n\n".join(context_parts)
    
    # Step 4: Simple prompt (no reasoning, just answer)
    prompt = f"""You are a legal assistant. Answer the question based ONLY on the provided statutes.

Question: {question}

Statutes:
{context}

Instructions:
- Answer with ONLY "Yes" or "No"
- Base your answer strictly on the provided statutes
- If the statutes don't provide enough information, answer "No"

Answer:"""
    
    # Step 5: LLM call (single shot, no follow-up)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10
    )
    
    answer = response.choices[0].message.content.strip()
    
    # Deduplicate statute IDs
    unique_statute_ids = list(dict.fromkeys(retrieved_statute_ids))
    
    return {
        'answer': answer,
        'retrieved_statute_ids': unique_statute_ids,
        'num_retrieved': len(unique_statute_ids),
        'context': context[:500] + "..." if len(context) > 500 else context
    }


def run_vanilla_rag_demo(state_name, num_questions=5, k=5):
    """Run vanilla RAG demo on housing law questions."""
    
    collection_name = COLLECTION_MAP[state_name.lower()]
    
    console.print("\n[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   VANILLA RAG - Simple Single-Shot Approach   [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]\n")
    
    console.print(f"[bold]State:[/bold] {state_name.title()}")
    console.print(f"[bold]Collection:[/bold] {collection_name}")
    console.print(f"[bold]Strategy:[/bold] One search → Simple prompt → Answer\n")
    
    # Initialize clients
    console.print("[cyan]Initializing...[/cyan]")
    
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_CLOUD_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Load questions
    test_questions = load_state_questions(state_name, limit=num_questions)
    
    # Run evaluation
    results = []
    correct_answers = 0
    retrieval_hits = 0
    
    console.print(f"[cyan]Running vanilla RAG on {len(test_questions)} questions...[/cyan]\n")
    
    for i, question_data in enumerate(tqdm(test_questions, desc="Processing"), 1):
        question = question_data['question']
        golden_answer = question_data['answer']
        golden_statute_ids = set(question_data['golden_statute_ids'])
        
        # Run vanilla RAG
        result = vanilla_rag_answer(
            question,
            collection_name,
            qdrant_client,
            embedding_model,
            openai_client,
            k=k
        )
        
        # Evaluate
        predicted_answer = result['answer']
        answer_correct = predicted_answer.lower() == golden_answer.lower()
        
        if answer_correct:
            correct_answers += 1
        
        # Check retrieval quality
        retrieved_ids = set(result['retrieved_statute_ids'])
        hit = len(retrieved_ids & golden_statute_ids) > 0
        
        if hit:
            retrieval_hits += 1
        
        results.append({
            'question': question[:60] + "...",
            'golden': golden_answer,
            'predicted': predicted_answer,
            'correct': answer_correct,
            'retrieval_hit': hit
        })
    
    # Display results
    console.print("\n")
    
    table = Table(
        title=f"Results - Vanilla RAG ({state_name.upper()})",
        box=box.DOUBLE_EDGE,
        title_style="bold cyan"
    )
    
    table.add_column("Metric", style="bold white", width=30)
    table.add_column("Value", style="bold green", justify="right")
    
    accuracy = (correct_answers / len(test_questions)) * 100 if test_questions else 0
    hit_rate = (retrieval_hits / len(test_questions)) * 100 if test_questions else 0
    
    table.add_row("Questions Tested", str(len(test_questions)))
    table.add_row("", "")
    table.add_row("Answer Accuracy", f"{accuracy:.1f}% ({correct_answers}/{len(test_questions)})")
    table.add_row("Retrieval Hit@5", f"{hit_rate:.1f}% ({retrieval_hits}/{len(test_questions)})")
    table.add_row("", "")
    table.add_row("Strategy", "Single search (no iteration)")
    
    console.print(table)
    console.print()
    
    # Show some examples
    console.print("\n[bold]Sample Results:[/bold]\n")
    
    for i, r in enumerate(results[:3], 1):
        status = "[green]✓[/green]" if r['correct'] else "[red]✗[/red]"
        console.print(f"{i}. {status} [dim]{r['question']}[/dim]")
        console.print(f"   Golden: [bold]{r['golden']}[/bold] | Predicted: [bold]{r['predicted']}[/bold]\n")
    
    console.print("\n[dim]💡 This is the baseline. See examples/3_agentic_rag/ for the improved approach.[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vanilla RAG demo")
    parser.add_argument(
        '--state',
        type=str,
        default='wyoming',
        choices=['wyoming', 'idaho', 'iowa'],
        help='State to query (default: wyoming)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of questions to test (default: 10)'
    )
    
    args = parser.parse_args()
    
    # Check environment
    if not os.getenv('OPENAI_API_KEY'):
        console.print("[red]Error: OPENAI_API_KEY not set in .env file[/red]")
        exit(1)
    
    if not os.getenv('QDRANT_CLOUD_URL'):
        console.print("[red]Error: QDRANT_CLOUD_URL not set in .env file[/red]")
        exit(1)
    
    run_vanilla_rag_demo(args.state, num_questions=args.limit)

