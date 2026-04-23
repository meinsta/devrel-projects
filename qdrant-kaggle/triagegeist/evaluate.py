"""Evaluation metrics and bias analysis for triage predictions."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
)

from triagegeist.config import DEMOGRAPHIC_COLS, ESI_LABELS, RESULTS_DIR


def evaluate_predictions(
    y_true: pd.Series,
    y_pred: pd.Series,
    save: bool = True,
) -> dict:
    """Compute triage prediction metrics."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "f1_macro": f1_score(y_true, y_pred, average="macro"),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted"),
        "cohen_kappa": cohen_kappa_score(y_true, y_pred, weights="quadratic"),
        "within_1_level": float(np.mean(np.abs(y_true - y_pred) <= 1)),
    }

    print(f"accuracy:       {metrics['accuracy']:.3f}")
    print(f"f1 (macro):     {metrics['f1_macro']:.3f}")
    print(f"f1 (weighted):  {metrics['f1_weighted']:.3f}")
    print(f"cohen kappa:    {metrics['cohen_kappa']:.3f}")
    print(f"within 1 level: {metrics['within_1_level']:.3f}")
    print()
    print(classification_report(
        y_true, y_pred,
        target_names=[f"ESI-{k} ({v})" for k, v in ESI_LABELS.items()],
    ))

    if save:
        with open(RESULTS_DIR / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

    return metrics


def plot_confusion_matrix(
    y_true: pd.Series,
    y_pred: pd.Series,
    save: bool = True,
) -> plt.Figure:
    """Plot confusion matrix for triage acuity predictions."""
    labels = sorted(y_true.unique())
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
                xticklabels=[f"ESI-{l}" for l in labels],
                yticklabels=[f"ESI-{l}" for l in labels])
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].set_title("Confusion Matrix (counts)")

    sns.heatmap(cm_pct, annot=True, fmt=".2f", cmap="Blues", ax=axes[1],
                xticklabels=[f"ESI-{l}" for l in labels],
                yticklabels=[f"ESI-{l}" for l in labels])
    axes[1].set_xlabel("Predicted")
    axes[1].set_ylabel("Actual")
    axes[1].set_title("Confusion Matrix (row-normalized)")

    plt.tight_layout()
    if save:
        fig.savefig(RESULTS_DIR / "confusion_matrix.png", dpi=150, bbox_inches="tight")
    return fig


def bias_analysis(
    df: pd.DataFrame,
    y_true_col: str = "triage_acuity",
    y_pred_col: str = "predicted_acuity",
    save: bool = True,
) -> dict:
    """Analyze prediction fairness across demographic groups.

    For each demographic dimension, compute per-group accuracy, F1,
    and over/under-triage rates. Over-triage means predicted acuity
    is more severe (lower number) than actual.
    """
    results = {}

    for demo_col in DEMOGRAPHIC_COLS:
        if demo_col not in df.columns:
            continue

        group_metrics = []
        for group_val, group_df in df.groupby(demo_col):
            if len(group_df) < 10:
                continue

            y_true = group_df[y_true_col]
            y_pred = group_df[y_pred_col]
            diff = y_pred - y_true  # positive = under-triage, negative = over-triage

            group_metrics.append({
                "group": str(group_val),
                "n": len(group_df),
                "accuracy": accuracy_score(y_true, y_pred),
                "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
                "over_triage_rate": float(np.mean(diff < 0)),
                "under_triage_rate": float(np.mean(diff > 0)),
                "exact_match_rate": float(np.mean(diff == 0)),
                "mean_error": float(diff.mean()),
            })

        results[demo_col] = group_metrics
        _print_bias_table(demo_col, group_metrics)

    if save:
        with open(RESULTS_DIR / "bias_analysis.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

    return results


def _print_bias_table(demo_col: str, group_metrics: list[dict]):
    print(f"\n{'='*60}")
    print(f"bias analysis: {demo_col}")
    print(f"{'='*60}")
    print(f"{'group':<20} {'n':>6} {'acc':>6} {'f1':>6} {'over':>6} {'under':>6}")
    print("-" * 60)
    for g in sorted(group_metrics, key=lambda x: -x["n"]):
        print(
            f"{g['group']:<20} {g['n']:>6} "
            f"{g['accuracy']:>6.3f} {g['f1_weighted']:>6.3f} "
            f"{g['over_triage_rate']:>6.3f} {g['under_triage_rate']:>6.3f}"
        )


def plot_bias_summary(
    bias_results: dict,
    save: bool = True,
) -> plt.Figure:
    """Plot accuracy disparity across demographic groups."""
    n_dims = len(bias_results)
    if n_dims == 0:
        return None

    fig, axes = plt.subplots(1, n_dims, figsize=(5 * n_dims, 5))
    if n_dims == 1:
        axes = [axes]

    for ax, (demo_col, groups) in zip(axes, bias_results.items()):
        groups_sorted = sorted(groups, key=lambda x: -x["accuracy"])
        names = [g["group"] for g in groups_sorted]
        accs = [g["accuracy"] for g in groups_sorted]
        colors = ["#e74c3c" if g["under_triage_rate"] > 0.3 else "#3498db" for g in groups_sorted]

        bars = ax.barh(names, accs, color=colors)
        ax.set_xlim(0, 1)
        ax.set_xlabel("Accuracy")
        ax.set_title(f"Accuracy by {demo_col}")
        ax.axvline(x=np.mean(accs), color="gray", linestyle="--", alpha=0.5)

    plt.tight_layout()
    if save:
        fig.savefig(RESULTS_DIR / "bias_summary.png", dpi=150, bbox_inches="tight")
    return fig
