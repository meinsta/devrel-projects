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
    write_ratio: float,
    seed: int,
    output_dir: Path,
    preload_count: int,
    arrival_model: str,
    collection_name: str,
    read_top_k: int,
    write_batch_size: int,
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
            write_ratio=write_ratio,
            read_ratio=1.0 - write_ratio,
            write_batch_size=write_batch_size,
            read_top_k=read_top_k,
            preload_count=preload_count,
            arrival_model=arrival_model,
            output_dir=output_dir,
            dataset=dataset,
            collection_name=collection_name,
        )

        trial = Trial(config, client)
        result = await trial.execute()
        results.append(result)

        log.info(
            f"Trial {trial_num} complete: "
            f"write_p99={result.write_percentiles.p99:.1f}ms "
            f"read_p99={result.read_percentiles.p99:.1f}ms "
            f"freshness_p50={result.freshness_percentiles.p50:.1f}ms"
        )

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
    }

    for system in systems:
        trial_results = all_results.get(system, [])
        baselines = [
            r.baseline.ping_ms for r in trial_results if r.baseline is not None
        ]
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
@click.option("--write-ratio", default=0.70, help="Fraction of ops that are writes")
@click.option("--seed", default=42, help="Base random seed")
@click.option(
    "--output-dir", default="./results", type=click.Path(), help="Output directory"
)
@click.option("--preload-count", default=500000, help="Vectors to pre-load")
@click.option(
    "--arrival-model",
    default="uniform",
    type=click.Choice(["uniform", "poisson"]),
    help="Request arrival model",
)
@click.option("--collection-name", default="sift_write_bench", help="Collection name")
@click.option("--read-top-k", default=10, help="Search top-k")
@click.option("--write-batch-size", default=100, help="Vectors per write op")
@click.option("--env-file", default=".env", help="Path to .env file")
@click.option("--dry-run", is_flag=True, help="Validate credentials and exit")
def main(
    system: str,
    trials: int,
    duration: int,
    target_ops: int,
    write_ratio: float,
    seed: int,
    output_dir: str,
    preload_count: int,
    arrival_model: str,
    collection_name: str,
    read_top_k: int,
    write_batch_size: int,
    env_file: str,
    dry_run: bool,
) -> None:
    """Write-heavy vector database benchmark."""
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
                write_ratio=write_ratio,
                seed=seed,
                output_dir=out,
                preload_count=preload_count,
                arrival_model=arrival_model,
                collection_name=collection_name,
                read_top_k=read_top_k,
                write_batch_size=write_batch_size,
            )
        )
        all_results[s] = results

    save_run_metadata(
        out,
        systems,
        all_results,
        trials=trials,
        duration_s=duration,
        target_ops_per_sec=target_ops,
        write_ratio=write_ratio,
        read_ratio=1.0 - write_ratio,
        write_batch_size=write_batch_size,
        read_top_k=read_top_k,
        preload_count=preload_count,
        base_seed=seed,
        arrival_model=arrival_model,
        collection_name=collection_name,
    )

    # Archive everything
    archive_run(out, systems, duration, target_ops, write_ratio, trials)

    log.info(f"\nAll results written to {out}/")
    for s, results in all_results.items():
        for r in results:
            log.info(
                f"  {s} trial {r.trial_number}: "
                f"write_p99={r.write_percentiles.p99:.1f}ms "
                f"read_p99={r.read_percentiles.p99:.1f}ms "
                f"freshness_p50={r.freshness_percentiles.p50:.1f}ms"
            )


def archive_run(
    output_dir: Path,
    systems: list[str],
    duration: int,
    target_ops: int,
    write_ratio: float,
    trials: int,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sys_label = "_".join(s.replace("_cloud", "") for s in systems)
    archive_name = f"{ts}_{sys_label}_{trials}t_{duration}s_{target_ops}ops"
    archive_dir = Path("results/archive") / archive_name
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Copy all result files
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
