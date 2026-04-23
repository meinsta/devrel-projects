"""LLM-based content quality evaluation."""

import json
import os
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

EVAL_PROMPT = """You are a content quality evaluator for Qdrant's technical blog and website.

Score the following content on these dimensions (1-10 each):

1. **Voice Match**: Does it sound like a senior engineer who cares about production? Confident but not arrogant, shows rather than tells.
2. **Technical Depth**: Specific numbers, real architecture details, code snippets. Not hand-wavy.
3. **Readability**: Short paragraphs, clear subheadings, scannable. Flesch-Kincaid grade 10-14.
4. **CTA Clarity**: Does it end with a clear, specific next step?
5. **Opening Quality**: Does it lead with the technical problem (good) or filler like "In today's rapidly evolving..." (bad)?
6. **Code/Diagram Ratio**: At least 1 code block or diagram per 500 words?
7. **Jargon Balance**: Technical enough for engineers, but doesn't over-explain basics or drown in acronyms?

Return JSON only:
{
  "scores": {
    "voice_match": <int>,
    "technical_depth": <int>,
    "readability": <int>,
    "cta_clarity": <int>,
    "opening_quality": <int>,
    "code_ratio": <int>,
    "jargon_balance": <int>
  },
  "overall": <float>,
  "grade": "<A/B/C/D/F with +/->",
  "strengths": ["<strength1>", "<strength2>"],
  "weaknesses": ["<weakness1>", "<weakness2>"],
  "suggestions": ["<actionable suggestion1>", "<actionable suggestion2>"]
}

Content to evaluate:
---
{content}
---"""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
                return fm or {}, parts[2].strip()
            except yaml.YAMLError:
                pass
    return {}, text


def _call_llm(prompt: str, model: str) -> dict:
    """Call Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        raise SystemExit(1)

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    # Extract JSON from response
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def _collect_files(path: str) -> list[Path]:
    """Collect .md files from path."""
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(p.rglob("*.md"))


def run_eval(content_dir: str, reference_dir: str | None, model: str, verbose: bool):
    """Evaluate content quality."""
    files = _collect_files(content_dir)
    if not files:
        console.print(f"[red]No .md files found in {content_dir}[/red]")
        return

    console.print(f"[cyan]Evaluating {len(files)} file(s) with {model}[/cyan]\n")

    results = []
    for f in files:
        text = f.read_text()
        fm, body = _parse_frontmatter(text)
        if not body.strip():
            continue

        title = fm.get("title", f.stem)
        console.print(f"  Evaluating: [bold]{title}[/bold]")

        prompt = EVAL_PROMPT.format(content=text)
        try:
            result = _call_llm(prompt, model)
            result["file"] = str(f)
            result["title"] = title
            results.append(result)
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    if not results:
        return

    # Summary table
    table = Table(title="Content Quality Evaluation")
    table.add_column("Title", style="bold")
    table.add_column("Grade", justify="center")
    table.add_column("Overall", justify="center")
    table.add_column("Voice", justify="center")
    table.add_column("Depth", justify="center")
    table.add_column("Read", justify="center")
    table.add_column("CTA", justify="center")
    table.add_column("Opening", justify="center")

    for r in results:
        s = r["scores"]
        grade_color = "green" if r["grade"].startswith("A") else "yellow" if r["grade"].startswith("B") else "red"
        table.add_row(
            r["title"][:40],
            f"[{grade_color}]{r['grade']}[/{grade_color}]",
            f"{r['overall']:.1f}",
            str(s["voice_match"]),
            str(s["technical_depth"]),
            str(s["readability"]),
            str(s["cta_clarity"]),
            str(s["opening_quality"]),
        )

    console.print()
    console.print(table)

    # Average
    avg = sum(r["overall"] for r in results) / len(results)
    console.print(f"\n[cyan]Average score: {avg:.1f}/10[/cyan]")

    if verbose:
        for r in results:
            console.print(f"\n[bold]{r['title']}[/bold]")
            console.print(f"  Strengths: {', '.join(r['strengths'])}")
            console.print(f"  Weaknesses: {', '.join(r['weaknesses'])}")
            for s in r["suggestions"]:
                console.print(f"  → {s}")

    # Save results
    out = Path("eval_runs")
    out.mkdir(exist_ok=True)
    outfile = out / "latest.json"
    outfile.write_text(json.dumps(results, indent=2))
    console.print(f"\n[dim]Results saved to {outfile}[/dim]")
