"""Wandb logging for agent trajectories."""

import os
from typing import Any


def log_trajectory(trajectory, run_name: str = "asteroid", project: str = "asteroid") -> None:
    """Log a trajectory to wandb."""
    try:
        import wandb
    except ImportError:
        return

    if not os.getenv("WANDB_API_KEY"):
        return

    if wandb.run is None:
        wandb.init(project=project, name=run_name, reinit=True)

    wandb.log({
        "turns": len(trajectory.turns),
        "tool_calls": trajectory.tool_call_count,
        "total_tokens": trajectory.total_tokens,
        "total_latency": trajectory.total_latency,
        "has_answer": bool(trajectory.final_answer and not trajectory.final_answer.startswith("[")),
        "tokens_per_turn": trajectory.total_tokens / max(1, len(trajectory.turns)),
        "tools_per_turn": trajectory.tool_call_count / max(1, len(trajectory.turns)),
    })


def log_eval_results(results: list[dict], run_name: str = "asteroid-eval", project: str = "asteroid") -> None:
    """Log evaluation results to wandb."""
    try:
        import wandb
    except ImportError:
        return

    if not os.getenv("WANDB_API_KEY"):
        return

    if wandb.run is None:
        wandb.init(project=project, name=run_name, reinit=True)

    scores = [r.get("score", 0.0) for r in results]
    turns = [r.get("turns", 0) for r in results]
    tool_calls = [r.get("tool_calls", 0) for r in results]
    tokens = [r.get("total_tokens", 0) for r in results]

    wandb.log({
        "eval/n_questions": len(results),
        "eval/mean_score": sum(scores) / max(1, len(scores)),
        "eval/mean_turns": sum(turns) / max(1, len(turns)),
        "eval/mean_tool_calls": sum(tool_calls) / max(1, len(tool_calls)),
        "eval/mean_tokens": sum(tokens) / max(1, len(tokens)),
        "eval/score_pass_rate": sum(1 for s in scores if s > 0.5) / max(1, len(scores)),
    })

    table = wandb.Table(columns=["question", "score", "turns", "tool_calls", "tokens", "answer"])
    for r in results:
        table.add_data(
            r.get("question", "")[:200],
            r.get("score", 0.0),
            r.get("turns", 0),
            r.get("tool_calls", 0),
            r.get("total_tokens", 0),
            r.get("answer", "")[:300],
        )
    wandb.log({"eval/results": table})
