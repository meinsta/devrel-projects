"""
Agentic RAG Example - Intelligent Multi-Step Search & Reasoning

This demonstrates the agentic approach:
1. Research Agent: Performs multiple strategic searches
2. Analysis Agent: Identifies gaps and performs follow-up searches  
3. Multi-perspective retrieval based on what's learned
4. Intelligent reasoning about what to search for next

Key differences from vanilla RAG:
- Multiple search iterations (not just one)
- Agents can reformulate queries based on findings
- Adaptive strategy based on question complexity
- Better coverage of relevant documents

Usage:
    python examples/3_agentic_rag/agentic_rag.py
    python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 10
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from datasets import load_dataset
from rich.console import Console
from rich.table import Table
from rich import box
from tqdm import tqdm
from crewai import Agent, Task, Crew, Process, LLM

# Add tools directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
from qdrant_tool import CustomQdrantTool

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


def create_agentic_workflow(qdrant_tool, question, state_name):
    """
    Create agents and tasks for agentic RAG.
    
    This is where the magic happens:
    - Multiple specialized agents
    - Each can perform searches based on what they learn
    - Iterative refinement
    """
    
    # Agent 1: Research Specialist
    # This agent understands it should search from multiple angles
    research_agent = Agent(
        role="Housing Law Research Specialist",
        goal=f"Find ALL relevant {state_name.title()} housing statutes through strategic multi-perspective search",
        backstory=f"""Expert researcher in {state_name.title()} housing law.
        
Your strategy:
1. Search the question directly
2. Identify key legal concepts and search for those
3. Search for related provisions that might be relevant
4. Use different phrasings to ensure comprehensive coverage

You perform 2-3 searches from different angles to ensure nothing is missed.""",
        tools=[qdrant_tool],
        verbose=False,
        llm=LLM(model="gpt-4o-mini", temperature=0)
    )
    
    # Agent 2: Legal Analyst
    # This agent analyzes findings and can request additional searches
    analyst_agent = Agent(
        role="Legal Analyst",
        goal="Analyze statutes and provide accurate Yes/No answer",
        backstory=f"""Expert in {state_name.title()} housing law analysis.

Your process:
1. Review all statutes found by the researcher
2. If you see gaps or ambiguities, perform targeted follow-up searches
3. Make your decision based on comprehensive evidence

Decision rules:
- Answer "Yes" ONLY if statutes explicitly support it
- Answer "No" if statutes are silent or contradict it
- Your FINAL answer must be: "Yes" or "No" (one word only)""",
        tools=[qdrant_tool],  # Analyst can also search!
        verbose=False,
        llm=LLM(model="gpt-4o-mini", temperature=0)
    )
    
    # Task 1: Multi-perspective research
    research_task = Task(
        description=f"""Find relevant statutes to answer: "{question}"

Search strategy:
1. Search the main question directly
2. Identify and search key legal terms
3. Search related concepts
4. Try alternative phrasings

Goal: Build comprehensive statute coverage (not just one search!)

Return: All relevant statutes with citations.""",
        agent=research_agent,
        expected_output="Comprehensive list of relevant statutes with citations and key excerpts"
    )
    
    # Task 2: Analysis with potential follow-up searches
    analysis_task = Task(
        description=f"""Analyze the statutes and answer: "{question}"

Process:
1. Review all statutes from research
2. If gaps exist, perform targeted follow-up searches
3. Make your final decision

Your answer MUST be exactly: "Yes" or "No" (one word, nothing else)""",
        agent=analyst_agent,
        expected_output="Yes or No",
        context=[research_task]  # Builds on research
    )
    
    return [research_agent, analyst_agent], [research_task, analysis_task]


def run_agentic_rag_demo(state_name, num_questions=5, k=5):
    """Run agentic RAG demo on housing law questions."""
    
    collection_name = COLLECTION_MAP[state_name.lower()]
    
    console.print("\n[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   AGENTIC RAG - Multi-Step Intelligent Search [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]\n")
    
    console.print(f"[bold]State:[/bold] {state_name.title()}")
    console.print(f"[bold]Collection:[/bold] {collection_name}")
    console.print(f"[bold]Strategy:[/bold] Multi-perspective search + Reasoning + Follow-ups\n")
    
    # Initialize Qdrant tool
    console.print("[cyan]Initializing agentic workflow...[/cyan]\n")
    
    qdrant_tool = CustomQdrantTool(
        qdrant_url=os.getenv('QDRANT_CLOUD_URL'),
        qdrant_api_key=os.getenv('QDRANT_API_KEY'),
        collection_name=collection_name,
        vector_name="fast-bge-small-en",
        limit=k,
        score_threshold=0.0
    )
    
    # Load questions
    test_questions = load_state_questions(state_name, limit=num_questions)
    
    # Run evaluation
    results = []
    correct_answers = 0
    
    console.print(f"[cyan]Running agentic RAG on {len(test_questions)} questions...[/cyan]")
    console.print("[dim]Note: Each question involves multiple agent interactions[/dim]\n")
    
    for i, question_data in enumerate(tqdm(test_questions, desc="Processing"), 1):
        question = question_data['question']
        golden_answer = question_data['answer']
        golden_statute_ids = set(question_data['golden_statute_ids'])
        
        try:
            # Create agentic workflow
            agents, tasks = create_agentic_workflow(qdrant_tool, question, state_name)
            
            # Run crew (this is where agents collaborate)
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=False
            )
            
            result = crew.kickoff()
            generated_answer = str(result).strip()
            
            # Extract Yes/No from response
            if 'yes' in generated_answer.lower() and 'no' not in generated_answer.lower():
                predicted = 'Yes'
            elif 'no' in generated_answer.lower() and 'yes' not in generated_answer.lower():
                predicted = 'No'
            else:
                predicted = generated_answer[:20]
            
            # Evaluate
            answer_correct = predicted.lower() == golden_answer.lower()
            
            if answer_correct:
                correct_answers += 1
            
            results.append({
                'question': question[:60] + "...",
                'golden': golden_answer,
                'predicted': predicted,
                'correct': answer_correct
            })
            
        except Exception as e:
            console.print(f"[red]Error on question {i}: {str(e)}[/red]")
            results.append({
                'question': question[:60] + "...",
                'golden': golden_answer,
                'predicted': 'Error',
                'correct': False
            })
    
    # Display results
    console.print("\n")
    
    table = Table(
        title=f"Results - Agentic RAG ({state_name.upper()})",
        box=box.DOUBLE_EDGE,
        title_style="bold cyan"
    )
    
    table.add_column("Metric", style="bold white", width=30)
    table.add_column("Value", style="bold green", justify="right")
    
    accuracy = (correct_answers / len(test_questions)) * 100 if test_questions else 0
    
    table.add_row("Questions Tested", str(len(test_questions)))
    table.add_row("", "")
    table.add_row("Answer Accuracy", f"{accuracy:.1f}% ({correct_answers}/{len(test_questions)})")
    table.add_row("", "")
    table.add_row("Strategy", "Multi-agent collaboration")
    table.add_row("Searches per Question", "~2-4 (adaptive)")
    
    console.print(table)
    console.print()
    
    # Show some examples
    console.print("\n[bold]Sample Results:[/bold]\n")
    
    for i, r in enumerate(results[:3], 1):
        status = "[green]✓[/green]" if r['correct'] else "[red]✗[/red]"
        console.print(f"{i}. {status} [dim]{r['question']}[/dim]")
        console.print(f"   Golden: [bold]{r['golden']}[/bold] | Predicted: [bold]{r['predicted']}[/bold]\n")
    
    console.print("\n[bold green]✓ Agentic RAG complete![/bold green]")
    console.print("[dim]💡 Compare this with examples/2_vanilla_rag/ to see the improvement.[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic RAG demo")
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
    
    run_agentic_rag_demo(args.state, num_questions=args.limit)

