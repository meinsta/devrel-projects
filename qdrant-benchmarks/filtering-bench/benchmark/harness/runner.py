from __future__ import annotations

import asyncio
import json
import logging
import platform
import shutil
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv

from benchmark.clients.base_client import BaseVectorClient
from benchmark.clients.qdrant_cloud import QdrantCloudClient
from benchmark.clients.weaviate_cloud import WeaviateCloudClient
from benchmark.clients.zilliz_cloud import ZillizCloudClient
from benchmark.datasets.download_sift import load_sift
from benchmark.harness.trial import Trial, TrialConfig, TrialResult

log = logging.getLogger(__name__)

CLIENT_REGISTRY: dict[str, type[BaseVectorClient]] = {
    "qdrant_cloud": QdrantCloudClient,
    "zilliz_cloud": ZillizCloudClient,
    "weaviate_cloud": WeaviateCloudClient,
}

ALL_SYSTEMS = list(CLIENT_REGISTRY.keys())


def create_client(system: str) -> BaseVectorClient:
    if system not in CLIENT_REGISTRY:
        raise ValueError(f"Unknown system: {system}. Choose from: {ALL_SYSTEMS}")
    return CLIENT_REGISTRY[system]()


async def run_trials(
    system: str,
    trials: int,
    duration: int,
    target_ops: int,
    filtered_search_ratio: float,
    unfiltered_search_ratio: float,
    update_ratio: float,
    seed: int,
    output_dir: Path,
    preload_count: int,
    arrival_model: str,
    collection_name: str,
    read_top_k: int,
    filter_level_weights: list[float] | None,
) -> list[TrialResult]:
    dataset = load_sift()
    results: list[TrialResult] = []

    for trial_num in range(trials):
        trial_seed = seed + trial_num
        log.info(
            f"\n{'='*60}\n"
            f"Starting trial {trial_num}/{trials} for {system} (seed={trial_seed})\n"
            f"{'='*60}"
        )

        client = create_client(system)
        config = TrialConfig(
            system=system,
            trial_number=trial_num,
            seed=trial_seed,
            duration_s=duration,
            target_ops_per_sec=target_ops,
            filtered_search_ratio=filtered_search_ratio,
            unfiltered_search_ratio=unfiltered_search_ratio,
            update_ratio=update_ratio,
            read_top_k=read_top_k,
            preload_count=preload_count,
            arrival_model=arrival_model,
            output_dir=output_dir,
            dataset=dataset,
            collection_name=collection_name,
            filter_level_weights=filter_level_weights,
        )

        trial = Trial(config, client)
        result = await trial.execute()
        results.append(result)

        log.info(
            f"Trial {trial_num} complete: "
            f"filtered_p99={result.filtered_search_percentiles.p99:.1f}ms "
            f"unfiltered_p99={result.unfiltered_search_percentiles.p99:.1f}ms "
            f"update_p99={result.update_percentiles.p99:.1f}ms"
        )

        for level, pct in result.filter_level_percentiles.items():
            if pct.count > 0:
                log.info(f"  L{level}: p50={pct.p50:.1f}ms p99={pct.p99:.1f}ms (n={pct.count})")

        if trial_num < trials - 1:
            log.info("Pausing 10s between trials...")
            await asyncio.sleep(10)

    return results


def save_run_metadata(
    output_dir: Path,
    systems: list[str],
    all_results: dict[str, list[TrialResult]],
    **params: object,
) -> None:
    metadata = {
        "benchmark": "filtering_performance_under_load",
        "client_machine": {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "parameters": {k: v for k, v in params.items()},
        "systems": {},
        "dataset": {
            "name": "SIFT-1M",
            "dimensions": 128,
            "base_vectors": 1_000_000,
            "query_vectors": 10_000,
            "distance_metric": "euclidean",
            "source": "http://corpus-texmex.irisa.fr/",
        },
        "filter_complexity_levels": {
            "L1": "single tenant (~2% selectivity)",
            "L2": "tenant + region (~0.2%)",
            "L3": "tenant + geo + category + device (~0.004%)",
            "L4": "full geo + category hierarchy (~0.0004%)",
            "L5": "hierarchy + budget/quality ranges (~0.0001%)",
        },
    }

    for system in systems:
        trial_results = all_results.get(system, [])
        baselines = [r.baseline.ping_ms for r in trial_results if r.baseline is not None]
        metadata["systems"][system] = {
            "baseline_latency_ms": (
                sorted(baselines)[len(baselines) // 2] if baselines else None
            ),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "run_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)


@click.command()
@click.option(
    "--system",
    type=click.Choice(ALL_SYSTEMS + ["all"]),
    required=True,
    help="System to benchmark",
)
@click.option("--trials", default=5, help="Number of independent trials per system")
@click.option("--duration", default=300, help="Benchmark phase duration in seconds")
@click.option("--target-ops", default=1000, help="Target operations per second")
@click.option("--filtered-ratio", default=0.60, help="Fraction of ops that are filtered searches")
@click.option("--unfiltered-ratio", default=0.10, help="Fraction of ops that are unfiltered searches")
@click.option("--update-ratio", default=0.30, help="Fraction of ops that are metadata updates")
@click.option("--seed", default=42, help="Base random seed")
@click.option("--output-dir", default="./results", type=click.Path(), help="Output directory")
@click.option("--preload-count", default=500000, help="Vectors to pre-load with payloads")
@click.option(
    "--arrival-model",
    default="uniform",
    type=click.Choice(["uniform", "poisson"]),
    help="Request arrival model",
)
@click.option("--collection-name", default="sift_filter_bench", help="Collection name")
@click.option("--read-top-k", default=50, help="Search top-k (default 50 per Procurify requirement)")
@click.option("--env-file", default=".env", help="Path to .env file")
@click.option("--dry-run", is_flag=True, help="Validate credentials and exit")
def main(
    system: str,
    trials: int,
    duration: int,
    target_ops: int,
    filtered_ratio: float,
    unfiltered_ratio: float,
    update_ratio: float,
    seed: int,
    output_dir: str,
    preload_count: int,
    arrival_model: str,
    collection_name: str,
    read_top_k: int,
    env_file: str,
    dry_run: bool,
) -> None:
    """Filtering performance under load benchmark."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    load_dotenv(env_file)

    systems = ALL_SYSTEMS if system == "all" else [system]
    out = Path(output_dir)

    if dry_run:
        for s in systems:
            log.info(f"Dry run: validating {s}...")
            client = create_client(s)
            asyncio.run(_validate_client(client))
            log.info(f"  {s}: OK")
        return

    all_results: dict[str, list[TrialResult]] = {}

    for s in systems:
        results = asyncio.run(
            run_trials(
                system=s,
                trials=trials,
                duration=duration,
                target_ops=target_ops,
                filtered_search_ratio=filtered_ratio,
                unfiltered_search_ratio=unfiltered_ratio,
                update_ratio=update_ratio,
                seed=seed,
                output_dir=out,
                preload_count=preload_count,
                arrival_model=arrival_model,
                collection_name=collection_name,
                read_top_k=read_top_k,
                filter_level_weights=None,
            )
        )
        all_results[s] = results

    save_run_metadata(
        out, systems, all_results,
        trials=trials,
        duration_s=duration,
        target_ops_per_sec=target_ops,
        filtered_search_ratio=filtered_ratio,
        unfiltered_search_ratio=unfiltered_ratio,
        update_ratio=update_ratio,
        read_top_k=read_top_k,
        preload_count=preload_count,
        base_seed=seed,
        arrival_model=arrival_model,
        collection_name=collection_name,
    )

    archive_run(out, systems, duration, target_ops, trials)

    log.info(f"\nAll results written to {out}/")
    for s, results in all_results.items():
        for r in results:
            log.info(
                f"  {s} trial {r.trial_number}: "
                f"filtered_p99={r.filtered_search_percentiles.p99:.1f}ms "
                f"unfiltered_p99={r.unfiltered_search_percentiles.p99:.1f}ms "
                f"update_p99={r.update_percentiles.p99:.1f}ms"
            )


def archive_run(
    output_dir: Path,
    systems: list[str],
    duration: int,
    target_ops: int,
    trials: int,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sys_label = "_".join(s.replace("_cloud", "") for s in systems)
    archive_name = f"{ts}_{sys_label}_{trials}t_{duration}s_{target_ops}ops_filter"
    archive_dir = Path("results/archive") / archive_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    for f in output_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, archive_dir / f.name)
    log.info(f"Archived results to {archive_dir}")


async def _validate_client(client: BaseVectorClient) -> None:
    await client.connect()
    baseline = await client.measure_baseline_latency()
    log.info(f"  Baseline latency: {baseline.ping_ms:.1f}ms")
    await client.disconnect()


if __name__ == "__main__":
    main()
