"""
Side-by-Side Comparison: Vanilla RAG vs Agentic RAG

This demo runs BOTH approaches on the same questions to show the difference.

Perfect for dev rel presentations and videos:
- See both approaches in action
- Compare accuracy metrics
- Understand when agents add value

Usage:
    python demos/compare_vanilla_vs_agentic.py
    python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 5
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from openai import OpenAI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from tqdm import tqdm
from crewai import Agent, Task, Crew, Process, LLM

# Add examples path (scripts/ is two levels deep: dev_rel/scripts/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples', '3_agentic_rag', 'tools'))
from qdrant_tool import CustomQdrantTool

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


def agentic_rag_answer(question, qdrant_tool, state_name):
    """Agentic RAG: Multi-step search with reasoning."""
    
    research_agent = Agent(
        role="Research Specialist",
        goal=f"Find relevant {state_name.title()} statutes through strategic search",
        backstory=f"""Expert researcher. Search from multiple angles:
1. Direct question
2. Key legal concepts
3. Related provisions""",
        tools=[qdrant_tool],
        verbose=False,
        llm=LLM(model="gpt-4o-mini", temperature=0)
    )
    
    analyst_agent = Agent(
        role="Legal Analyst",
        goal="Provide accurate Yes/No answer",
        backstory=f"""Analyze statutes and answer. Can perform follow-up searches if needed.
Answer MUST be: "Yes" or "No" (one word)""",
        tools=[qdrant_tool],
        verbose=False,
        llm=LLM(model="gpt-4o-mini", temperature=0)
    )
    
    research_task = Task(
        description=f"""Find statutes for: "{question}"
Search from multiple perspectives.""",
        agent=research_agent,
        expected_output="Relevant statutes"
    )
    
    analysis_task = Task(
        description=f"""Answer: "{question}"
Your answer MUST be: "Yes" or "No" (one word)""",
        agent=analyst_agent,
        expected_output="Yes or No",
        context=[research_task]
    )
    
    crew = Crew(
        agents=[research_agent, analyst_agent],
        tasks=[research_task, analysis_task],
        process=Process.sequential,
        verbose=False
    )
    
    result = crew.kickoff()
    generated_answer = str(result).strip()
    
    # Extract Yes/No
    if 'yes' in generated_answer.lower() and 'no' not in generated_answer.lower():
        return 'Yes'
    elif 'no' in generated_answer.lower() and 'yes' not in generated_answer.lower():
        return 'No'
    else:
        return generated_answer[:20]


def run_comparison(state_name, num_questions=5):
    """Run side-by-side comparison."""
    
    collection_name = COLLECTION_MAP[state_name.lower()]
    
    # Header
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]Vanilla RAG vs Agentic RAG[/bold cyan]\n"
        f"[dim]State: {state_name.title()} | Questions: {num_questions}[/dim]",
        border_style="cyan"
    ))
    console.print()
    
    # Initialize clients for vanilla RAG
    console.print("[cyan]⚙️  Initializing systems...[/cyan]\n")
    
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_CLOUD_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Initialize tool for agentic RAG
    qdrant_tool = CustomQdrantTool(
        qdrant_url=os.getenv('QDRANT_CLOUD_URL'),
        qdrant_api_key=os.getenv('QDRANT_API_KEY'),
        collection_name=collection_name,
        vector_name="fast-bge-small-en",
        limit=5,
        score_threshold=0.0
    )
    
    # Load questions
    console.print(f"[cyan]📚 Loading {state_name.title()} questions...[/cyan]")
    test_questions = load_state_questions(state_name, limit=num_questions)
    console.print(f"[green]✓ Loaded {len(test_questions)} questions[/green]\n")
    
    # Run comparison
    vanilla_correct = 0
    agentic_correct = 0
    comparisons = []
    
    console.print("[bold]Running comparison...[/bold]\n")
    
    for i, question_data in enumerate(tqdm(test_questions, desc="Processing"), 1):
        question = question_data['question']
        golden_answer = question_data['answer']
        
        # Vanilla RAG
        try:
            vanilla_answer = vanilla_rag_answer(
                question, collection_name, qdrant_client,
                embedding_model, openai_client, k=5
            )
            vanilla_is_correct = vanilla_answer.lower() == golden_answer.lower()
            if vanilla_is_correct:
                vanilla_correct += 1
        except Exception as e:
            vanilla_answer = "Error"
            vanilla_is_correct = False
        
        # Agentic RAG
        try:
            agentic_answer = agentic_rag_answer(question, qdrant_tool, state_name)
            agentic_is_correct = agentic_answer.lower() == golden_answer.lower()
            if agentic_is_correct:
                agentic_correct += 1
        except Exception as e:
            agentic_answer = "Error"
            agentic_is_correct = False
        
        comparisons.append({
            'question': question[:50] + "..." if len(question) > 50 else question,
            'golden': golden_answer,
            'vanilla': vanilla_answer,
            'vanilla_correct': vanilla_is_correct,
            'agentic': agentic_answer,
            'agentic_correct': agentic_is_correct
        })
    
    # Display results
    console.print("\n")
    console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]                COMPARISON RESULTS              [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]\n")
    
    # Accuracy comparison
    vanilla_accuracy = (vanilla_correct / len(test_questions)) * 100 if test_questions else 0
    agentic_accuracy = (agentic_correct / len(test_questions)) * 100 if test_questions else 0
    improvement = agentic_accuracy - vanilla_accuracy
    
    table = Table(box=box.DOUBLE_EDGE)
    table.add_column("Approach", style="bold white", width=20)
    table.add_column("Correct", style="green", justify="right")
    table.add_column("Accuracy", style="cyan", justify="right")
    table.add_column("Strategy", style="dim")
    
    table.add_row(
        "Vanilla RAG",
        f"{vanilla_correct}/{len(test_questions)}",
        f"{vanilla_accuracy:.1f}%",
        "Single search"
    )
    
    table.add_row(
        "Agentic RAG",
        f"{agentic_correct}/{len(test_questions)}",
        f"{agentic_accuracy:.1f}%",
        "Multi-step reasoning"
    )
    
    console.print(table)
    console.print()
    
    # Show improvement
    if improvement > 0:
        console.print(f"[bold green]✓ Agentic RAG improvement: +{improvement:.1f} percentage points[/bold green]\n")
    elif improvement < 0:
        console.print(f"[yellow]⚠ Vanilla RAG performed better by {abs(improvement):.1f} points[/yellow]\n")
    else:
        console.print(f"[blue]Both approaches achieved the same accuracy[/blue]\n")
    
    # Show detailed comparison
    console.print("\n[bold]Detailed Question-by-Question Comparison:[/bold]\n")
    
    for i, comp in enumerate(comparisons, 1):
        console.print(f"[bold]{i}. {comp['question']}[/bold]")
        console.print(f"   [dim]Golden Answer: {comp['golden']}[/dim]")
        
        vanilla_icon = "[green]✓[/green]" if comp['vanilla_correct'] else "[red]✗[/red]"
        agentic_icon = "[green]✓[/green]" if comp['agentic_correct'] else "[red]✗[/red]"
        
        console.print(f"   {vanilla_icon} Vanilla: [bold]{comp['vanilla']}[/bold]")
        console.print(f"   {agentic_icon} Agentic: [bold]{comp['agentic']}[/bold]")
        
        # Highlight when agentic gets it right but vanilla doesn't
        if comp['agentic_correct'] and not comp['vanilla_correct']:
            console.print(f"   [green]→ Agentic RAG wins on this question![/green]")
        
        console.print()
    
    # Summary insights
    console.print("\n[bold cyan]Key Insights:[/bold cyan]\n")
    console.print("• [bold]Vanilla RAG:[/bold] Fast single-shot retrieval, but limited by initial search quality")
    console.print("• [bold]Agentic RAG:[/bold] Slower but more thorough, can find documents vanilla misses")
    console.print("• [bold]Best for:[/bold] Complex questions where initial search may miss key documents\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Vanilla vs Agentic RAG")
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
        default=5,
        help='Number of questions to test (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Check environment
    required_vars = ['OPENAI_API_KEY', 'QDRANT_CLOUD_URL', 'QDRANT_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        console.print(f"[red]Error: Missing environment variables: {', '.join(missing)}[/red]")
        console.print("[yellow]Create a .env file with these variables[/yellow]")
        exit(1)
    
    run_comparison(args.state, num_questions=args.limit)

