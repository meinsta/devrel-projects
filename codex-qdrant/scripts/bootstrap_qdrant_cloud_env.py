#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone


DEFAULT_COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "codex-memory")
DEFAULT_EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "fastembed")
DEFAULT_EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


def _run_json(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"Command failed: {' '.join(command)}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse JSON from {' '.join(command)}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object from {' '.join(command)}")
    return data


def _build_cluster_url(cluster_json: dict) -> str:
    endpoint = cluster_json.get("state", {}).get("endpoint", {})
    url = str(endpoint.get("url", "")).rstrip("/")
    rest_port = endpoint.get("restPort") or 6333
    if not url:
        raise SystemExit("Cluster does not expose a REST endpoint yet. Wait until it is healthy.")
    if url.endswith(f":{rest_port}"):
        return url
    return f"{url}:{rest_port}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve Qdrant Cloud runtime env vars from qcloud."
    )
    parser.add_argument(
        "--cluster-id",
        default=os.environ.get("QDRANT_CLUSTER_ID"),
        help="Qdrant Cloud cluster ID",
    )
    parser.add_argument(
        "--key-name",
        default=os.environ.get(
            "QCLOUD_KEY_NAME",
            f"codex-memory-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        ),
        help="Cluster API key name to create",
    )
    parser.add_argument(
        "--access-type",
        choices=("manage", "read-only"),
        default=os.environ.get("QCLOUD_KEY_ACCESS_TYPE", "manage"),
        help="Cluster API key access type",
    )
    parser.add_argument(
        "--emit",
        choices=("shell", "json"),
        default=os.environ.get("BOOTSTRAP_EMIT", "shell"),
        help="Output format",
    )
    args = parser.parse_args()

    if not args.cluster_id:
        raise SystemExit("Set QDRANT_CLUSTER_ID or pass --cluster-id.")

    if not shutil.which("qcloud"):
        raise SystemExit("qcloud is required but was not found in PATH.")

    cluster = _run_json(["qcloud", "cluster", "describe", args.cluster_id, "--json"])
    key = _run_json(
        [
            "qcloud",
            "cluster",
            "key",
            "create",
            args.cluster_id,
            "--name",
            args.key_name,
            "--access-type",
            args.access_type,
            "--wait",
            "--json",
        ]
    )

    qdrant_api_key = str(key.get("key", ""))
    if not qdrant_api_key:
        raise SystemExit(
            "qcloud did not return a cluster API key. Retry the command and capture the one-time key."
        )

    exports = {
        "QDRANT_CLUSTER_ID": args.cluster_id,
        "QDRANT_URL": _build_cluster_url(cluster),
        "QDRANT_API_KEY": qdrant_api_key,
        "COLLECTION_NAME": DEFAULT_COLLECTION_NAME,
        "EMBEDDING_PROVIDER": DEFAULT_EMBEDDING_PROVIDER,
        "EMBEDDING_MODEL": DEFAULT_EMBEDDING_MODEL,
        "QCLOUD_KEY_NAME": args.key_name,
    }

    print(
        f"Created cluster key '{args.key_name}' for cluster {args.cluster_id}.",
        file=sys.stderr,
    )

    if args.emit == "json":
        print(json.dumps(exports))
        return

    for key_name, value in exports.items():
        print(f"export {key_name}={shlex.quote(value)}")


if __name__ == "__main__":
    import shutil

    main()
