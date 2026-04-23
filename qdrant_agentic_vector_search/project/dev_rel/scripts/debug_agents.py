"""
Debug Version - See exactly what CrewAI agents are doing

This version has:
1. Verbose output enabled
2. Step-by-step logging
3. Error catching per question
4. Agent state inspection
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
from rich.panel import Panel
from tqdm import tqdm
from crewai import Agent, Task, Crew, Process, LLM
import traceback

# Add examples path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples', '3_agentic_rag', 'tools'))
from qdrant_tool import CustomQdrantTool

load_dotenv()

# Disable telemetry
os.environ["OTEL_SDK_DISABLED"] = "true"

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
    
    console.print(f"  [dim]→ Vanilla: Embedding question...[/dim]")
    question_embedding = list(embedding_model.embed([question]))[0].tolist()
    
    console.print(f"  [dim]→ Vanilla: Searching Qdrant...[/dim]")
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
    
    console.print(f"  [dim]→ Vanilla: Calling LLM...[/dim]")
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10
    )
    
    answer = response.choices[0].message.content.strip()
    console.print(f"  [dim]→ Vanilla: Got answer: {answer}[/dim]")
    return answer


def agentic_rag_answer_debug(question, question_num, qdrant_tool, state_name):
    """
    Debug version of agentic RAG - shows what's happening.
    
    Key: We create FRESH agents for EACH question to avoid state issues.
    """
    
    console.print(f"\n[bold yellow]🤖 Starting Agentic RAG for Question {question_num}[/bold yellow]")
    console.print(f"[dim]Question: {question[:60]}...[/dim]\n")
    
    try:
        console.print("  [dim]→ Creating fresh agents...[/dim]")
        
        # IMPORTANT: Create NEW agents each time (no state carryover)
        research_agent = Agent(
            role="Research Specialist",
            goal=f"Find relevant {state_name.title()} statutes through strategic search",
            backstory=f"""Expert researcher. Search from multiple angles:
1. Direct question
2. Key legal concepts
3. Related provisions

Do 2-3 searches maximum, then STOP.""",
            tools=[qdrant_tool],
            verbose=True,  # ENABLE VERBOSE
            allow_delegation=False,
            max_iter=5,  # Limit iterations
            llm=LLM(model="gpt-4o-mini", temperature=0)
        )
        
        analyst_agent = Agent(
            role="Legal Analyst",
            goal="Provide accurate Yes/No answer",
            backstory=f"""Analyze {state_name.title()} statutes and answer Yes/No.

Rules:
- Answer "Yes" ONLY if statutes explicitly support it
- Answer "No" if statutes are silent or don't support it
- Your FINAL answer must be ONLY: "Yes" or "No" (one word)

Do NOT search for more statutes. Use only what the researcher provided.""",
            tools=[],  # No tools - just analyzes
            verbose=True,  # ENABLE VERBOSE
            allow_delegation=False,
            max_iter=3,
            llm=LLM(model="gpt-4o-mini", temperature=0)
        )
        
        console.print("  [dim]→ Creating tasks...[/dim]")
        
        research_task = Task(
            description=f"""Find statutes to answer: "{question}"

Search strategy:
1. Search the main question directly
2. Search key legal terms
3. STOP after 2-3 searches

Return: List of relevant statutes with citations.""",
            agent=research_agent,
            expected_output="List of relevant statutes"
        )
        
        analysis_task = Task(
            description=f"""Answer: "{question}"

Based on the statutes found:
- If they support it: Answer "Yes"
- If they don't: Answer "No"

Your answer MUST be exactly one word: Yes or No""",
            agent=analyst_agent,
            expected_output="Yes or No",
            context=[research_task]
        )
        
        console.print("  [dim]→ Creating crew...[/dim]")
        
        # Create FRESH crew each time
        crew = Crew(
            agents=[research_agent, analyst_agent],
            tasks=[research_task, analysis_task],
            process=Process.sequential,
            verbose=True,  # ENABLE VERBOSE
            max_rpm=100,
            share_crew=False
        )
        
        console.print("  [bold cyan]→ Starting crew execution...[/bold cyan]\n")
        console.print("[dim]" + "="*60 + "[/dim]")
        
        # Execute
        result = crew.kickoff()
        
        console.print("[dim]" + "="*60 + "[/dim]\n")
        console.print(f"  [bold green]→ Crew completed![/bold green]")
        
        generated_answer = str(result).strip()
        console.print(f"  [dim]→ Raw result: {generated_answer}[/dim]")
        
        # Extract Yes/No
        if 'yes' in generated_answer.lower() and 'no' not in generated_answer.lower():
            final_answer = 'Yes'
        elif 'no' in generated_answer.lower() and 'yes' not in generated_answer.lower():
            final_answer = 'No'
        else:
            final_answer = generated_answer.split()[0] if generated_answer else 'No'
        
        console.print(f"  [bold green]→ Final answer: {final_answer}[/bold green]\n")
        return final_answer
        
    except Exception as e:
        console.print(f"\n[bold red]❌ ERROR in agentic RAG:[/bold red]")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[dim]Full traceback:[/dim]")
        traceback.print_exc()
        return 'Error'


def run_debug_comparison(state_name, num_questions=3):
    """Run comparison with full debug output."""
    
    collection_name = COLLECTION_MAP[state_name.lower()]
    
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]🔍 DEBUG MODE - Agentic RAG[/bold cyan]\n"
        f"[dim]State: {state_name.title()} | Questions: {num_questions}[/dim]\n"
        "[yellow]Verbose output enabled - you'll see everything![/yellow]",
        border_style="cyan"
    ))
    console.print()
    
    # Initialize clients
    console.print("[cyan]⚙️  Initializing systems...[/cyan]")
    
    qdrant_client = QdrantClient(
        url=os.getenv('QDRANT_CLOUD_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    console.print("  ✓ Qdrant client")
    
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    console.print("  ✓ Embedding model")
    
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    console.print("  ✓ OpenAI client")
    
    qdrant_tool = CustomQdrantTool(
        qdrant_url=os.getenv('QDRANT_CLOUD_URL'),
        qdrant_api_key=os.getenv('QDRANT_API_KEY'),
        collection_name=collection_name,
        vector_name="fast-bge-small-en",
        limit=5,
        score_threshold=0.0
    )
    console.print("  ✓ Qdrant tool\n")
    
    # Load questions
    console.print(f"[cyan]📚 Loading {state_name.title()} questions...[/cyan]")
    test_questions = load_state_questions(state_name, limit=num_questions)
    console.print(f"[green]✓ Loaded {len(test_questions)} questions[/green]\n")
    
    # Run comparison
    results = []
    
    console.print("[bold]Processing questions...[/bold]\n")
    console.print("="*80 + "\n")
    
    for i, question_data in enumerate(test_questions, 1):
        question = question_data['question']
        golden_answer = question_data['answer']
        
        console.print(f"[bold cyan]━━━ QUESTION {i}/{len(test_questions)} ━━━[/bold cyan]")
        console.print(f"[bold]{question}[/bold]")
        console.print(f"[dim]Golden answer: {golden_answer}[/dim]\n")
        
        # Vanilla RAG
        console.print("[bold blue]1️⃣  VANILLA RAG[/bold blue]")
        try:
            vanilla_answer = vanilla_rag_answer(
                question, collection_name, qdrant_client,
                embedding_model, openai_client, k=5
            )
            vanilla_correct = vanilla_answer.lower() == golden_answer.lower()
            vanilla_status = "✓ CORRECT" if vanilla_correct else "✗ WRONG"
            console.print(f"[{'green' if vanilla_correct else 'red'}]  → {vanilla_status}: {vanilla_answer}[/{'green' if vanilla_correct else 'red'}]\n")
        except Exception as e:
            console.print(f"[red]  → ERROR: {str(e)}[/red]\n")
            vanilla_answer = "Error"
            vanilla_correct = False
        
        # Agentic RAG
        console.print("[bold magenta]2️⃣  AGENTIC RAG[/bold magenta]")
        try:
            agentic_answer = agentic_rag_answer_debug(question, i, qdrant_tool, state_name)
            agentic_correct = agentic_answer.lower() == golden_answer.lower()
            agentic_status = "✓ CORRECT" if agentic_correct else "✗ WRONG"
            console.print(f"[{'green' if agentic_correct else 'red'}]  → {agentic_status}: {agentic_answer}[/{'green' if agentic_correct else 'red'}]\n")
        except Exception as e:
            console.print(f"[red]  → ERROR: {str(e)}[/red]\n")
            traceback.print_exc()
            agentic_answer = "Error"
            agentic_correct = False
        
        results.append({
            'question': question[:50] + "..." if len(question) > 50 else question,
            'golden': golden_answer,
            'vanilla': vanilla_answer,
            'vanilla_correct': vanilla_correct,
            'agentic': agentic_answer,
            'agentic_correct': agentic_correct
        })
        
        console.print("="*80 + "\n")
    
    # Summary
    console.print("\n[bold cyan]📊 SUMMARY[/bold cyan]\n")
    
    vanilla_correct_count = sum(1 for r in results if r['vanilla_correct'])
    agentic_correct_count = sum(1 for r in results if r['agentic_correct'])
    
    console.print(f"Vanilla RAG:  {vanilla_correct_count}/{len(results)} correct")
    console.print(f"Agentic RAG:  {agentic_correct_count}/{len(results)} correct\n")
    
    for i, r in enumerate(results, 1):
        v_icon = "✓" if r['vanilla_correct'] else "✗"
        a_icon = "✓" if r['agentic_correct'] else "✗"
        console.print(f"{i}. {r['question']}")
        console.print(f"   Golden: {r['golden']} | Vanilla: {v_icon} {r['vanilla']} | Agentic: {a_icon} {r['agentic']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug agentic RAG")
    parser.add_argument('--state', type=str, default='wyoming', choices=['wyoming', 'idaho', 'iowa'])
    parser.add_argument('--limit', type=int, default=3, help='Number of questions (keep small for debug)')
    
    args = parser.parse_args()
    
    # Check environment
    required_vars = ['OPENAI_API_KEY', 'QDRANT_CLOUD_URL', 'QDRANT_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        console.print(f"[red]Error: Missing: {', '.join(missing)}[/red]")
        exit(1)
    
    console.print("\n[bold yellow]⚠️  DEBUG MODE ACTIVE[/bold yellow]")
    console.print("[dim]You'll see all agent thoughts, actions, and observations.[/dim]")
    console.print("[dim]This is verbose! Use --limit 2 to keep it manageable.[/dim]\n")
    
    run_debug_comparison(args.state, num_questions=args.limit)

