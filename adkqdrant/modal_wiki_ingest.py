"""
Modal App for Wikipedia Parquet Ingestion with Multiple Configs

GPU-accelerated embedding with parallel processing.
Each config runs on a separate parquet file for comparison.

Usage:
    # Single config
    modal run modal_wiki_ingest.py::ingest_parquet --config openai_256_mrl --parquet-url s3://...

    # Multiple configs in parallel (each on different parquet)
    modal run modal_wiki_ingest.py::run_experiment_suite

    # View results
    modal run modal_wiki_ingest.py::show_results
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
import json

import modal

# =============================================================================
# Modal App Configuration
# =============================================================================

app = modal.App("wiki-parquet-ingest")

# Volumes for data and results
data_volume = modal.Volume.from_name("wiki-parquet-data", create_if_missing=True)
results_volume = modal.Volume.from_name("wiki-ingest-results", create_if_missing=True)

# Base image with core dependencies
base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Qdrant
        "qdrant-client>=1.12.0",
        # Embeddings
        "openai>=1.50.0",
        # Data processing
        "pyarrow>=15.0.0",
        "pandas>=2.2.0",
        "datasets>=2.20.0",  # HuggingFace datasets
        # Utils
        "tqdm>=4.66.0",
        "python-dotenv>=1.0.0",
    )
)

# GPU image with FastEmbed + ColBERT
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "qdrant-client>=1.12.0",
        "fastembed>=0.4.0",  # Includes LateInteractionTextEmbedding for ColBERT
        "openai>=1.50.0",
        "pyarrow>=15.0.0",
        "pandas>=2.2.0",
        "datasets>=2.20.0",
        "tqdm>=4.66.0",
        "python-dotenv>=1.0.0",
        "torch>=2.2.0",
    )
)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class IngestConfig:
    """Configuration for a single ingestion run"""
    name: str
    embedding_provider: str  # openai, cohere, fastembed
    embedding_model: str
    dimensions: int
    use_mrl: bool = False
    use_quantization: bool = False
    quantization_type: Optional[str] = None
    use_sparse: bool = False
    batch_size: int = 1000
    defer_indexing: bool = True
    on_disk: bool = True
    shard_number: int = 2


@dataclass
class IngestMetrics:
    """Metrics from ingestion run"""
    experiment_id: str
    config_name: str
    config: Dict[str, Any]
    parquet_file: str
    collection_name: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "running"
    total_rows: int = 0
    total_vectors: int = 0
    total_batches: int = 0
    embedding_time_ms: float = 0
    upsert_time_ms: float = 0
    total_time_ms: float = 0
    vectors_per_second: float = 0
    search_latency_p50_ms: Optional[float] = None
    search_latency_p95_ms: Optional[float] = None
    estimated_size_mb: float = 0
    errors: List[str] = field(default_factory=list)


# Predefined configurations
CONFIGS: Dict[str, IngestConfig] = {
    "openai_256_mrl": IngestConfig(
        name="OpenAI 256d MRL",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        dimensions=256,
        use_mrl=True,
        batch_size=100,  # Reduced for Wikipedia's long articles
    ),
    "openai_512_mrl": IngestConfig(
        name="OpenAI 512d MRL",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        dimensions=512,
        use_mrl=True,
        batch_size=1500,
    ),
    "openai_1536": IngestConfig(
        name="OpenAI 1536d",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        dimensions=1536,
        use_mrl=False,
        batch_size=500,
    ),
    "openai_256_quantized": IngestConfig(
        name="OpenAI 256d INT8",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        dimensions=256,
        use_mrl=True,
        use_quantization=True,
        quantization_type="int8",
        batch_size=2000,
    ),
    "cohere_256_mrl": IngestConfig(
        name="Cohere 256d MRL",
        embedding_provider="cohere",
        embedding_model="embed-english-v3.0",
        dimensions=256,
        use_mrl=True,
        batch_size=96,
    ),
    "cohere_1024": IngestConfig(
        name="Cohere 1024d",
        embedding_provider="cohere",
        embedding_model="embed-english-v3.0",
        dimensions=1024,
        use_mrl=False,
        batch_size=96,
    ),
    "fastembed_bge_384": IngestConfig(
        name="FastEmbed BGE-small 384d",
        embedding_provider="fastembed",
        embedding_model="BAAI/bge-small-en-v1.5",
        dimensions=384,
        batch_size=500,
    ),
    "fastembed_bge_768": IngestConfig(
        name="FastEmbed BGE-base 768d",
        embedding_provider="fastembed",
        embedding_model="BAAI/bge-base-en-v1.5",
        dimensions=768,
        batch_size=200,
    ),
}


# =============================================================================
# Embedding Functions
# =============================================================================

def embed_openai(texts: List[str], model: str, dimensions: int, use_mrl: bool, api_key: str) -> List[List[float]]:
    """Embed with OpenAI"""
    import openai
    client = openai.OpenAI(api_key=api_key)

    kwargs = {"model": model, "input": texts}
    if use_mrl:
        kwargs["dimensions"] = dimensions

    response = client.embeddings.create(**kwargs)
    return [d.embedding for d in response.data]


def embed_cohere(texts: List[str], model: str, dimensions: int, use_mrl: bool, api_key: str) -> List[List[float]]:
    """Embed with Cohere"""
    import cohere
    client = cohere.ClientV2(api_key=api_key)

    kwargs = {"model": model, "texts": texts, "input_type": "search_document"}
    if use_mrl:
        kwargs["output_dimension"] = dimensions

    response = client.embed(**kwargs)
    return [list(e) for e in response.embeddings]


def embed_fastembed(texts: List[str], model: str, embedder=None) -> List[List[float]]:
    """Embed with FastEmbed (GPU)"""
    from fastembed import TextEmbedding
    if embedder is None:
        embedder = TextEmbedding(model)
    return [list(e) for e in embedder.embed(texts)]


# =============================================================================
# Main Ingestion Function (CPU - for OpenAI/Cohere)
# =============================================================================

@app.function(
    image=base_image,
    volumes={
        "/data": data_volume,
        "/results": results_volume,
    },
    timeout=3600 * 4,  # 4 hours
    secrets=[
        modal.Secret.from_name("qdrant"),
        modal.Secret.from_name("openai"),
    ],
    cpu=4,
    memory=8192,
)
def ingest_parquet_cpu(
    config_name: str,
    parquet_path: str,
    text_column: str = "text",
    collection_suffix: str = "",
) -> Dict:
    """
    Ingest parquet file with OpenAI or Cohere embeddings.

    Args:
        config_name: Name of config from CONFIGS
        parquet_path: Path to parquet file (in /data volume or URL)
        text_column: Column containing text to embed
        collection_suffix: Optional suffix for collection name
    """
    import time
    import uuid
    import pyarrow.parquet as pq
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        ScalarQuantization, ScalarType, HnswConfigDiff,
    )

    config = CONFIGS[config_name]
    experiment_id = uuid.uuid4().hex[:12]
    collection_name = f"wiki_{config_name}_{experiment_id}"
    if collection_suffix:
        collection_name += f"_{collection_suffix}"

    metrics = IngestMetrics(
        experiment_id=experiment_id,
        config_name=config.name,
        config=asdict(config),
        parquet_file=parquet_path,
        collection_name=collection_name,
        started_at=datetime.utcnow().isoformat(),
    )

    # Get secrets
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    cohere_key = os.environ.get("COHERE_API_KEY")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=300)

    total_start = time.time()

    try:
        # Create collection
        vectors_config = VectorParams(
            size=config.dimensions,
            distance=Distance.COSINE,
            on_disk=config.on_disk,
        )

        quantization = None
        if config.use_quantization and config.quantization_type == "int8":
            quantization = ScalarQuantization(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )

        hnsw_config = HnswConfigDiff(m=0) if config.defer_indexing else None

        try:
            client.delete_collection(collection_name)
        except:
            pass

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            quantization_config=quantization,
            hnsw_config=hnsw_config,
            shard_number=config.shard_number,
        )

        print(f"[{config.name}] Created collection: {collection_name}")

        # Read parquet
        parquet_file = pq.ParquetFile(parquet_path)
        metrics.total_rows = parquet_file.metadata.num_rows

        total_embedding_time = 0
        total_upsert_time = 0
        batch_count = 0
        vector_count = 0

        for batch in parquet_file.iter_batches(batch_size=config.batch_size, columns=[text_column]):
            texts = [str(t) for t in batch[text_column].to_pylist() if t]
            if not texts:
                continue

            batch_count += 1

            # Embed
            embed_start = time.time()
            if config.embedding_provider == "openai":
                vectors = embed_openai(texts, config.embedding_model, config.dimensions, config.use_mrl, openai_key)
            else:
                vectors = embed_cohere(texts, config.embedding_model, config.dimensions, config.use_mrl, cohere_key)
            embed_time = (time.time() - embed_start) * 1000
            total_embedding_time += embed_time

            # Create points
            points = [
                PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vec,
                    payload={"text": text[:1000], "batch": batch_count},
                )
                for text, vec in zip(texts, vectors)
            ]

            # Upsert
            upsert_start = time.time()
            client.upsert(collection_name=collection_name, points=points, wait=True)
            upsert_time = (time.time() - upsert_start) * 1000
            total_upsert_time += upsert_time

            vector_count += len(points)

            if batch_count % 10 == 0:
                print(f"  [{config.name}] Batch {batch_count}: {vector_count:,} vectors - "
                      f"Embed: {embed_time:.0f}ms, Upsert: {upsert_time:.0f}ms")

        # Re-enable indexing
        if config.defer_indexing and vector_count > 0:
            print(f"  [{config.name}] Re-enabling HNSW...")
            index_start = time.time()
            client.update_collection(
                collection_name=collection_name,
                hnsw_config=HnswConfigDiff(m=16),
            )
            while True:
                info = client.get_collection(collection_name)
                if info.status.value == "green":
                    break
                time.sleep(1)
            print(f"  [{config.name}] Indexing done in {(time.time() - index_start):.1f}s")

        total_time = (time.time() - total_start) * 1000

        # Metrics
        metrics.total_vectors = vector_count
        metrics.total_batches = batch_count
        metrics.embedding_time_ms = total_embedding_time
        metrics.upsert_time_ms = total_upsert_time
        metrics.total_time_ms = total_time
        metrics.vectors_per_second = vector_count / (total_time / 1000) if total_time > 0 else 0

        bytes_per_float = 1 if config.use_quantization else 4
        metrics.estimated_size_mb = (config.dimensions * bytes_per_float * vector_count) / (1024 * 1024)

        # Search test
        if vector_count > 0:
            test_result = client.scroll(collection_name=collection_name, limit=5, with_payload=True)
            test_texts = [p.payload.get("text", "")[:200] for p in test_result[0]]

            if test_texts and config.embedding_provider == "openai":
                test_vecs = embed_openai(test_texts, config.embedding_model, config.dimensions, config.use_mrl, openai_key)
            elif test_texts and config.embedding_provider == "cohere":
                test_vecs = embed_cohere(test_texts, config.embedding_model, config.dimensions, config.use_mrl, cohere_key)
            else:
                test_vecs = []

            latencies = []
            for vec in test_vecs:
                start = time.time()
                client.query_points(collection_name=collection_name, query=vec, limit=10)
                latencies.append((time.time() - start) * 1000)

            if latencies:
                latencies.sort()
                metrics.search_latency_p50_ms = latencies[len(latencies) // 2]
                metrics.search_latency_p95_ms = latencies[int(len(latencies) * 0.95)]

        metrics.status = "completed"
        metrics.completed_at = datetime.utcnow().isoformat()

        print(f"\n[{config.name}] COMPLETED:")
        print(f"  Vectors: {metrics.total_vectors:,}")
        print(f"  Throughput: {metrics.vectors_per_second:.1f} vec/s")
        print(f"  Search P50: {metrics.search_latency_p50_ms}ms")

    except Exception as e:
        metrics.status = "failed"
        metrics.errors.append(str(e))
        metrics.completed_at = datetime.utcnow().isoformat()
        print(f"[{config.name}] FAILED: {e}")

    # Save results
    result_path = f"/results/{experiment_id}.json"
    with open(result_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)

    return asdict(metrics)


# =============================================================================
# GPU Ingestion Function (for FastEmbed)
# =============================================================================

@app.function(
    image=gpu_image,
    gpu="T4",
    volumes={
        "/data": data_volume,
        "/results": results_volume,
    },
    timeout=3600 * 4,
    secrets=[modal.Secret.from_name("qdrant")],
)
def ingest_parquet_gpu(
    config_name: str,
    parquet_path: str,
    text_column: str = "text",
    collection_suffix: str = "",
) -> Dict:
    """
    Ingest parquet file with GPU-accelerated FastEmbed.
    """
    import time
    import uuid
    import pyarrow.parquet as pq
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, HnswConfigDiff,
    )

    config = CONFIGS[config_name]
    experiment_id = uuid.uuid4().hex[:12]
    collection_name = f"wiki_{config_name}_{experiment_id}"

    metrics = IngestMetrics(
        experiment_id=experiment_id,
        config_name=config.name,
        config=asdict(config),
        parquet_file=parquet_path,
        collection_name=collection_name,
        started_at=datetime.utcnow().isoformat(),
    )

    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=300)
    embedder = TextEmbedding(config.embedding_model)

    total_start = time.time()

    try:
        # Create collection
        vectors_config = VectorParams(
            size=config.dimensions,
            distance=Distance.COSINE,
            on_disk=config.on_disk,
        )

        hnsw_config = HnswConfigDiff(m=0) if config.defer_indexing else None

        try:
            client.delete_collection(collection_name)
        except:
            pass

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            hnsw_config=hnsw_config,
            shard_number=config.shard_number,
        )

        print(f"[{config.name}] Created collection: {collection_name}")

        # Read and process
        parquet_file = pq.ParquetFile(parquet_path)
        metrics.total_rows = parquet_file.metadata.num_rows

        total_embedding_time = 0
        total_upsert_time = 0
        batch_count = 0
        vector_count = 0

        for batch in parquet_file.iter_batches(batch_size=config.batch_size, columns=[text_column]):
            texts = [str(t) for t in batch[text_column].to_pylist() if t]
            if not texts:
                continue

            batch_count += 1

            # Embed on GPU
            embed_start = time.time()
            vectors = [list(e) for e in embedder.embed(texts)]
            embed_time = (time.time() - embed_start) * 1000
            total_embedding_time += embed_time

            # Create points
            points = [
                PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vec,
                    payload={"text": text[:1000], "batch": batch_count},
                )
                for text, vec in zip(texts, vectors)
            ]

            # Upsert
            upsert_start = time.time()
            client.upsert(collection_name=collection_name, points=points, wait=True)
            upsert_time = (time.time() - upsert_start) * 1000
            total_upsert_time += upsert_time

            vector_count += len(points)

            if batch_count % 10 == 0:
                print(f"  [{config.name}] Batch {batch_count}: {vector_count:,} vectors")

        # Re-enable indexing
        if config.defer_indexing and vector_count > 0:
            print(f"  [{config.name}] Re-enabling HNSW...")
            client.update_collection(
                collection_name=collection_name,
                hnsw_config=HnswConfigDiff(m=16),
            )
            while True:
                info = client.get_collection(collection_name)
                if info.status.value == "green":
                    break
                time.sleep(1)

        total_time = (time.time() - total_start) * 1000

        metrics.total_vectors = vector_count
        metrics.total_batches = batch_count
        metrics.embedding_time_ms = total_embedding_time
        metrics.upsert_time_ms = total_upsert_time
        metrics.total_time_ms = total_time
        metrics.vectors_per_second = vector_count / (total_time / 1000) if total_time > 0 else 0
        metrics.estimated_size_mb = (config.dimensions * 4 * vector_count) / (1024 * 1024)
        metrics.status = "completed"
        metrics.completed_at = datetime.utcnow().isoformat()

        print(f"\n[{config.name}] COMPLETED: {metrics.total_vectors:,} vectors @ {metrics.vectors_per_second:.1f}/s")

    except Exception as e:
        metrics.status = "failed"
        metrics.errors.append(str(e))
        metrics.completed_at = datetime.utcnow().isoformat()
        print(f"[{config.name}] FAILED: {e}")

    # Save results
    result_path = f"/results/{experiment_id}.json"
    with open(result_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)

    return asdict(metrics)


# =============================================================================
# Experiment Suite
# =============================================================================

@app.function(
    image=base_image,
    volumes={"/data": data_volume, "/results": results_volume},
    timeout=3600,
)
def run_experiment_suite(
    parquet_files: List[str],
    configs: List[str] = None,
) -> List[Dict]:
    """
    Run multiple configs on different parquet files in parallel.

    Args:
        parquet_files: List of parquet file paths (one per config)
        configs: Config names to run (defaults to all)
    """
    if configs is None:
        configs = list(CONFIGS.keys())

    # Match configs to parquet files
    jobs = []
    for i, config_name in enumerate(configs):
        parquet_idx = i % len(parquet_files)
        parquet_path = parquet_files[parquet_idx]

        config = CONFIGS[config_name]
        if config.embedding_provider == "fastembed":
            jobs.append(ingest_parquet_gpu.spawn(config_name, parquet_path))
        else:
            jobs.append(ingest_parquet_cpu.spawn(config_name, parquet_path))

    # Collect results
    results = []
    for job in jobs:
        try:
            result = job.get()
            results.append(result)
        except Exception as e:
            results.append({"error": str(e)})

    return results


@app.function(
    image=base_image,
    volumes={"/results": results_volume},
)
def show_results() -> str:
    """Show all experiment results"""
    import os
    import json

    results = []
    for filename in os.listdir("/results"):
        if filename.endswith(".json"):
            with open(f"/results/{filename}") as f:
                results.append(json.load(f))

    if not results:
        return "No results found."

    # Sort by started_at
    results.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    output = ["=" * 80, "EXPERIMENT RESULTS", "=" * 80, ""]

    headers = ["Config", "Vectors", "Vec/s", "Embed ms/v", "P50 ms", "Size MB", "Status"]
    output.append("  ".join(f"{h:<15}" for h in headers))
    output.append("-" * 110)

    for r in results:
        row = [
            r.get("config_name", "?")[:13],
            f"{r.get('total_vectors', 0):,}",
            f"{r.get('vectors_per_second', 0):.1f}",
            f"{r.get('embedding_time_ms', 0) / max(r.get('total_vectors', 1), 1):.2f}",
            str(r.get("search_latency_p50_ms", "N/A")),
            f"{r.get('estimated_size_mb', 0):.2f}",
            r.get("status", "?"),
        ]
        output.append("  ".join(f"{v:<15}" for v in row))

    return "\n".join(output)


# =============================================================================
# Quick Experiment from HuggingFace
# =============================================================================

def extract_rich_metadata(title: str, text: str, wiki_id: str = None, url: str = None) -> Dict[str, Any]:
    """
    Extract rich metadata from Wikipedia article for filtering.

    Returns metadata fields optimized for Qdrant payload filtering:
    - Numeric fields for range queries (word_count, quality_score, etc.)
    - Boolean fields for match queries (has_infobox, is_stub, etc.)
    - Keyword fields for exact match (category, first_letter, etc.)
    - Arrays for "any" matching (topics, entities, eras, etc.)

    Example Qdrant filter queries enabled by this metadata:
    - quality_score >= 70 (high quality articles only)
    - topic_domain = "science" (domain filtering)
    - mentions_year BETWEEN 1900 AND 2000 (temporal filtering)
    - geographic_mentions ANY ["United States", "Europe"] (location filtering)
    - reading_level <= 8 (accessibility filtering)
    - is_biographical = true (people articles)
    - has_coordinates = true (geo-enabled articles)
    """
    import re
    import hashlib
    from datetime import datetime

    # Basic text stats
    word_count = len(text.split())
    char_count = len(text)
    paragraph_count = len([p for p in text.split("\n\n") if p.strip()])
    sentence_count = len(re.findall(r'[.!?]+', text))
    avg_sentence_length = word_count / max(sentence_count, 1)

    # First paragraph (for preview/summary)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    first_paragraph = paragraphs[0][:500] if paragraphs else ""

    # Section detection
    sections = re.findall(r'^#+\s*(.+)$|^==+\s*(.+?)\s*==+$', text, re.MULTILINE)
    section_count = len(sections)
    section_titles = [s[0] or s[1] for s in sections[:10]]  # First 10 sections

    # Content indicators
    has_references = bool(re.search(r'references|bibliography|sources|citations', text, re.IGNORECASE))
    has_infobox = bool(re.search(r'\{\{infobox|\{\{taxobox|\{\{chembox', text, re.IGNORECASE))
    has_images = bool(re.search(r'\[\[file:|\[\[image:|\.jpg|\.png|\.svg', text, re.IGNORECASE))
    has_tables = bool(re.search(r'\{\||\|\}|<table', text, re.IGNORECASE))
    has_links = bool(re.search(r'\[\[.+?\]\]', text))
    link_count = len(re.findall(r'\[\[.+?\]\]', text))

    # Quality indicators
    is_stub = word_count < 300 or bool(re.search(r'\{\{stub\}\}|\{\{.*-stub\}\}', text, re.IGNORECASE))
    is_disambiguation = bool(re.search(r'\{\{disambiguation\}\}|may refer to:', text, re.IGNORECASE))
    is_list = bool(re.search(r'^list of |^index of ', title, re.IGNORECASE))
    is_redirect = text.strip().lower().startswith('#redirect')

    # =========================================================================
    # CREATIVE METADATA ADDITIONS
    # =========================================================================

    # ----- TOPIC/DOMAIN DETECTION -----
    topic_signals = {
        "science": r"\b(physics|chemistry|biology|science|scientific|experiment|theory|hypothesis|molecule|atom|cell|organism|evolution|quantum)\b",
        "technology": r"\b(computer|software|internet|technology|digital|algorithm|programming|data|network|processor|AI|machine learning)\b",
        "history": r"\b(century|ancient|medieval|war|empire|kingdom|dynasty|historical|civilization|archaeology|revolution)\b",
        "geography": r"\b(country|city|river|mountain|ocean|continent|island|territory|region|latitude|longitude|climate)\b",
        "arts": r"\b(art|music|painting|sculpture|artist|composer|museum|gallery|film|movie|director|novel|poetry)\b",
        "sports": r"\b(football|basketball|soccer|olympics|championship|athlete|team|league|tournament|medal|score)\b",
        "politics": r"\b(government|president|minister|election|parliament|congress|democracy|political|party|vote|law)\b",
        "medicine": r"\b(disease|treatment|medicine|medical|hospital|doctor|patient|symptom|diagnosis|therapy|drug|health)\b",
        "mathematics": r"\b(equation|theorem|formula|mathematical|algebra|geometry|calculus|number|proof|function)\b",
        "philosophy": r"\b(philosophy|philosopher|ethics|metaphysics|logic|epistemology|existential|morality|consciousness)\b",
    }
    detected_topics = []
    topic_scores = {}
    for topic, pattern in topic_signals.items():
        matches = len(re.findall(pattern, text, re.IGNORECASE))
        if matches >= 3:
            detected_topics.append(topic)
            topic_scores[topic] = min(matches, 50)  # Cap at 50

    primary_topic = max(topic_scores, key=topic_scores.get) if topic_scores else "general"

    # ----- ENTITY DETECTION -----
    # People (names with titles)
    is_biographical = bool(re.search(
        r'\b(born|died|was a|is a|he was|she was|his|her|president|king|queen|dr\.|prof\.)\b',
        text[:2000], re.IGNORECASE
    ))

    # Dates and years mentioned
    years_mentioned = [int(y) for y in re.findall(r'\b(1[0-9]{3}|20[0-2][0-9])\b', text)]
    unique_years = sorted(set(years_mentioned))
    earliest_year = min(unique_years) if unique_years else None
    latest_year = max(unique_years) if unique_years else None
    year_span = (latest_year - earliest_year) if earliest_year and latest_year else 0

    # Historical era detection
    era_patterns = {
        "ancient": r"\b(ancient|BC|BCE|classical|roman empire|greek|egyptian|mesopotamia)\b",
        "medieval": r"\b(medieval|middle ages|feudal|crusade|knight|castle|dark ages)\b",
        "renaissance": r"\b(renaissance|reformation|15th century|16th century)\b",
        "industrial": r"\b(industrial revolution|19th century|victorian|steam|factory)\b",
        "modern": r"\b(20th century|world war|cold war|nuclear|space age)\b",
        "contemporary": r"\b(21st century|internet|digital age|social media|smartphone|2010s|2020s)\b",
    }
    detected_eras = [era for era, pattern in era_patterns.items() if re.search(pattern, text, re.IGNORECASE)]

    # ----- GEOGRAPHIC DETECTION -----
    continent_patterns = {
        "north_america": r"\b(united states|america|canada|mexico|usa|u\.s\.)\b",
        "south_america": r"\b(brazil|argentina|chile|peru|colombia|south america)\b",
        "europe": r"\b(europe|france|germany|italy|spain|uk|united kingdom|britain|russia)\b",
        "asia": r"\b(china|japan|india|korea|asia|vietnam|indonesia|thailand)\b",
        "africa": r"\b(africa|egypt|nigeria|south africa|kenya|morocco)\b",
        "oceania": r"\b(australia|new zealand|oceania|pacific islands)\b",
    }
    geographic_regions = [region for region, pattern in continent_patterns.items()
                          if re.search(pattern, text, re.IGNORECASE)]

    # Coordinates detection
    has_coordinates = bool(re.search(r'\d+°\s*\d*′?\s*[NS]\s*\d+°\s*\d*′?\s*[EW]', text))

    # ----- READING LEVEL (Flesch-Kincaid approximation) -----
    syllable_count = sum(1 for word in text.split()
                         for match in re.findall(r'[aeiouy]+', word.lower()))
    avg_syllables_per_word = syllable_count / max(word_count, 1)
    # Simplified Flesch-Kincaid Grade Level
    reading_level = round(0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59, 1)
    reading_level = max(1, min(reading_level, 18))  # Clamp to 1-18

    # Complexity tier
    if reading_level <= 6:
        complexity = "easy"
    elif reading_level <= 10:
        complexity = "moderate"
    elif reading_level <= 14:
        complexity = "advanced"
    else:
        complexity = "expert"

    # ----- NUMERIC DATA DETECTION -----
    has_statistics = bool(re.search(r'\d+%|\d+\.\d+|million|billion|trillion|average|median|percentage', text, re.IGNORECASE))
    has_measurements = bool(re.search(r'\d+\s*(km|m|cm|mm|ft|miles|kg|lb|°C|°F|hz|mhz)', text, re.IGNORECASE))
    numbers_count = len(re.findall(r'\b\d+\b', text))

    # ----- CITATION/REFERENCE DENSITY -----
    citation_patterns = len(re.findall(r'\[\d+\]|\{\{cite|\{\{citation|\<ref', text, re.IGNORECASE))
    citation_density = round(citation_patterns / max(paragraph_count, 1), 2)

    # ----- CONTENT FRESHNESS -----
    current_year = datetime.now().year
    recent_years_count = sum(1 for y in years_mentioned if y >= current_year - 10)
    is_contemporary = recent_years_count >= 3

    # ----- SPECIAL CONTENT TYPES -----
    has_formula = bool(re.search(r'<math>|\$\$|\\frac|\\sum|\\int|=\s*[a-z]\^', text, re.IGNORECASE))
    has_code = bool(re.search(r'<code>|<pre>|```|def |function |class |import |#include', text))
    has_timeline = bool(re.search(r'timeline|chronology|\d{4}\s*[-–]\s*\d{4}', text, re.IGNORECASE))
    has_controversy = bool(re.search(r'controversy|disputed|debate|criticism|criticized', text, re.IGNORECASE))

    # Compute quality score (0-100)
    quality_score = min(100, (
        min(word_count / 50, 30) +  # Up to 30 points for length (1500+ words)
        (15 if has_references else 0) +
        (10 if has_infobox else 0) +
        (10 if has_images else 0) +
        (5 if has_tables else 0) +
        min(section_count * 2, 15) +  # Up to 15 points for sections
        min(link_count / 10, 15) +  # Up to 15 points for internal links
        (0 if is_stub else 5)  # 5 points for not being a stub
    ))

    # Category extraction (simplified - real Wikipedia has [[Category:...]])
    categories = re.findall(r'\[\[category:([^\]|]+)', text, re.IGNORECASE)[:5]

    # Title metadata
    first_letter = title[0].upper() if title else ""
    title_word_count = len(title.split())
    has_parenthetical = "(" in title  # Like "Mercury (planet)"

    # Language detection (basic)
    non_ascii_ratio = sum(1 for c in text if ord(c) > 127) / max(len(text), 1)

    return {
        # === IDs ===
        "wiki_id": wiki_id or hashlib.md5(title.encode()).hexdigest()[:12],
        "url": url or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "ingested_at": datetime.utcnow().isoformat(),

        # === Title metadata ===
        "title": title,
        "title_lower": title.lower(),
        "first_letter": first_letter,
        "title_word_count": title_word_count,
        "has_parenthetical": has_parenthetical,

        # === Text metadata ===
        "text_preview": text[:1000],
        "first_paragraph": first_paragraph,
        "word_count": word_count,
        "char_count": char_count,
        "paragraph_count": paragraph_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 1),
        "section_count": section_count,
        "section_titles": section_titles,

        # === Content indicators ===
        "has_references": has_references,
        "has_infobox": has_infobox,
        "has_images": has_images,
        "has_tables": has_tables,
        "has_links": has_links,
        "link_count": link_count,

        # === Article type ===
        "is_stub": is_stub,
        "is_disambiguation": is_disambiguation,
        "is_list": is_list,
        "is_redirect": is_redirect,
        "is_biographical": is_biographical,

        # === Quality ===
        "quality_score": round(quality_score, 1),

        # === Categories & Topics ===
        "categories": categories,
        "detected_topics": detected_topics,
        "primary_topic": primary_topic,

        # === Temporal metadata ===
        "years_mentioned": unique_years[:20],  # First 20 unique years
        "earliest_year_mentioned": earliest_year,
        "latest_year_mentioned": latest_year,
        "year_span": year_span,
        "detected_eras": detected_eras,
        "is_contemporary": is_contemporary,

        # === Geographic metadata ===
        "geographic_regions": geographic_regions,
        "has_coordinates": has_coordinates,

        # === Reading metrics ===
        "reading_level": reading_level,
        "complexity": complexity,
        "avg_syllables_per_word": round(avg_syllables_per_word, 2),

        # === Numeric data ===
        "has_statistics": has_statistics,
        "has_measurements": has_measurements,
        "numbers_count": min(numbers_count, 1000),  # Cap at 1000

        # === Citation quality ===
        "citation_count": citation_patterns,
        "citation_density": citation_density,

        # === Special content ===
        "has_formula": has_formula,
        "has_code": has_code,
        "has_timeline": has_timeline,
        "has_controversy": has_controversy,

        # === Language ===
        "non_ascii_ratio": round(non_ascii_ratio, 3),
    }


@app.function(
    image=base_image,
    volumes={"/results": results_volume},
    timeout=3600 * 2,
    secrets=[
        modal.Secret.from_name("qdrant"),
        modal.Secret.from_name("openai"),
    ],
    cpu=4,
    memory=8192,
)
def run_wiki_experiment(
    config_name: str = "openai_256_mrl",
    num_samples: int = 5000,
    dataset_name: str = "wikimedia/wikipedia",
    dataset_config: str = "20231101.simple",
) -> Dict:
    """
    Run experiment by downloading Wikipedia directly from HuggingFace.

    Each point gets 50+ metadata fields for rich filtering:
    - Topic detection: primary_topic, detected_topics
    - Temporal: years_mentioned, detected_eras, is_contemporary
    - Geographic: geographic_regions, has_coordinates
    - Quality: quality_score, reading_level, complexity
    - Content type: is_biographical, is_list, has_formula, has_controversy

    Example Qdrant filter queries:
        # High-quality science articles
        {"must": [
            {"key": "quality_score", "range": {"gte": 70}},
            {"key": "primary_topic", "match": {"value": "science"}}
        ]}

        # Biographical articles from 20th century
        {"must": [
            {"key": "is_biographical", "match": {"value": true}},
            {"key": "earliest_year_mentioned", "range": {"gte": 1900}},
            {"key": "latest_year_mentioned", "range": {"lte": 2000}}
        ]}

        # Easy-to-read contemporary articles with references
        {"must": [
            {"key": "complexity", "match": {"value": "easy"}},
            {"key": "is_contemporary", "match": {"value": true}},
            {"key": "has_references", "match": {"value": true}}
        ]}

        # Articles mentioning Europe with geographic coordinates
        {"must": [
            {"key": "geographic_regions", "match": {"any": ["europe"]}},
            {"key": "has_coordinates", "match": {"value": true}}
        ]}

    Args:
        config_name: Config to test (openai_256_mrl, openai_512_mrl, etc.)
        num_samples: Number of Wikipedia articles to embed
        dataset_name: HuggingFace dataset name
        dataset_config: Dataset config (20220301.simple for Simple English Wikipedia)
    """
    import time
    import uuid
    import openai
    from datasets import load_dataset
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        ScalarQuantization, ScalarType, HnswConfigDiff,
    )

    config = CONFIGS[config_name]
    experiment_id = uuid.uuid4().hex[:12]
    collection_name = f"wiki_exp_{config_name}_{experiment_id}"

    metrics = IngestMetrics(
        experiment_id=experiment_id,
        config_name=config.name,
        config=asdict(config),
        parquet_file=f"hf://{dataset_name}/{dataset_config}",
        collection_name=collection_name,
        started_at=datetime.utcnow().isoformat(),
    )

    print(f"[{config.name}] Starting experiment {experiment_id}")
    print(f"  Dataset: {dataset_name}/{dataset_config}")
    print(f"  Samples: {num_samples}")

    # Get secrets
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=300)
    openai_client = openai.OpenAI(api_key=openai_key)

    total_start = time.time()

    try:
        # Load dataset
        print(f"  Loading dataset from HuggingFace...")
        ds = load_dataset(dataset_name, dataset_config, split=f"train[:{num_samples}]")
        metrics.total_rows = len(ds)
        print(f"  Loaded {len(ds)} articles")

        # Create collection
        vectors_config = VectorParams(
            size=config.dimensions,
            distance=Distance.COSINE,
            on_disk=config.on_disk,
        )

        quantization = None
        if config.use_quantization and config.quantization_type == "int8":
            quantization = ScalarQuantization(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )

        hnsw_config = HnswConfigDiff(m=0) if config.defer_indexing else None

        try:
            client.delete_collection(collection_name)
        except:
            pass

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            quantization_config=quantization,
            hnsw_config=hnsw_config,
            shard_number=config.shard_number,
        )
        print(f"  Created collection: {collection_name}")

        # Create payload indexes for efficient filtering
        from qdrant_client.models import PayloadSchemaType
        indexed_fields = [
            # Numeric range filters
            ("quality_score", PayloadSchemaType.FLOAT),
            ("word_count", PayloadSchemaType.INTEGER),
            ("reading_level", PayloadSchemaType.FLOAT),
            ("earliest_year_mentioned", PayloadSchemaType.INTEGER),
            ("latest_year_mentioned", PayloadSchemaType.INTEGER),
            ("link_count", PayloadSchemaType.INTEGER),
            ("citation_count", PayloadSchemaType.INTEGER),
            # Keyword filters
            ("primary_topic", PayloadSchemaType.KEYWORD),
            ("complexity", PayloadSchemaType.KEYWORD),
            ("first_letter", PayloadSchemaType.KEYWORD),
            # Boolean filters
            ("is_stub", PayloadSchemaType.BOOL),
            ("is_biographical", PayloadSchemaType.BOOL),
            ("has_references", PayloadSchemaType.BOOL),
            ("has_infobox", PayloadSchemaType.BOOL),
            ("has_coordinates", PayloadSchemaType.BOOL),
            ("is_contemporary", PayloadSchemaType.BOOL),
            ("has_formula", PayloadSchemaType.BOOL),
            ("has_controversy", PayloadSchemaType.BOOL),
        ]
        for field_name, field_type in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                    wait=False,  # Don't wait for each index
                )
            except Exception:
                pass  # Index might already exist
        print(f"  Created {len(indexed_fields)} payload indexes")

        # Process in batches
        total_embedding_time = 0
        total_upsert_time = 0
        batch_count = 0
        vector_count = 0

        for i in range(0, len(ds), config.batch_size):
            batch = ds[i:i + config.batch_size]
            texts = [str(t)[:4000] for t in batch["text"] if t]  # ~1000 tokens per article max
            if not texts:
                continue

            batch_count += 1

            # Embed with OpenAI
            embed_start = time.time()
            embed_kwargs = {"model": config.embedding_model, "input": texts}
            if config.use_mrl:
                embed_kwargs["dimensions"] = config.dimensions

            response = openai_client.embeddings.create(**embed_kwargs)
            vectors = [d.embedding for d in response.data]
            embed_time = (time.time() - embed_start) * 1000
            total_embedding_time += embed_time

            # Create points with rich metadata
            points = []
            for j, vec in enumerate(vectors):
                title = batch["title"][j] if j < len(batch["title"]) else ""
                text = texts[j]
                wiki_id = batch["id"][j] if "id" in batch and j < len(batch["id"]) else None
                url = batch["url"][j] if "url" in batch and j < len(batch["url"]) else None

                # Extract rich metadata for filtering
                payload = extract_rich_metadata(title, text, wiki_id, url)
                payload["batch"] = batch_count

                points.append(PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vec,
                    payload=payload,
                ))

            # Upsert
            upsert_start = time.time()
            client.upsert(collection_name=collection_name, points=points, wait=True)
            upsert_time = (time.time() - upsert_start) * 1000
            total_upsert_time += upsert_time

            vector_count += len(points)

            if batch_count % 5 == 0 or batch_count == 1:
                print(f"  Batch {batch_count}: {vector_count:,} vectors - "
                      f"Embed: {embed_time:.0f}ms, Upsert: {upsert_time:.0f}ms")

        # Re-enable indexing
        if config.defer_indexing and vector_count > 0:
            print(f"  Re-enabling HNSW indexing...")
            index_start = time.time()
            client.update_collection(
                collection_name=collection_name,
                hnsw_config=HnswConfigDiff(m=16),
            )
            while True:
                info = client.get_collection(collection_name)
                if info.status.value == "green":
                    break
                time.sleep(1)
            print(f"  Indexing done in {(time.time() - index_start):.1f}s")

        total_time = (time.time() - total_start) * 1000

        # Calculate metrics
        metrics.total_vectors = vector_count
        metrics.total_batches = batch_count
        metrics.embedding_time_ms = total_embedding_time
        metrics.upsert_time_ms = total_upsert_time
        metrics.total_time_ms = total_time
        metrics.vectors_per_second = vector_count / (total_time / 1000) if total_time > 0 else 0

        bytes_per_float = 1 if config.use_quantization else 4
        metrics.estimated_size_mb = (config.dimensions * bytes_per_float * vector_count) / (1024 * 1024)

        # Search latency test
        print(f"  Running search latency test...")
        test_texts = [ds[j]["text"][:500] for j in range(min(10, len(ds)))]
        test_response = openai_client.embeddings.create(
            model=config.embedding_model,
            input=test_texts,
            **({"dimensions": config.dimensions} if config.use_mrl else {}),
        )
        test_vecs = [d.embedding for d in test_response.data]

        latencies = []
        for vec in test_vecs:
            start = time.time()
            client.query_points(collection_name=collection_name, query=vec, limit=10)
            latencies.append((time.time() - start) * 1000)

        latencies.sort()
        metrics.search_latency_p50_ms = latencies[len(latencies) // 2]
        metrics.search_latency_p95_ms = latencies[int(len(latencies) * 0.95)]

        metrics.status = "completed"
        metrics.completed_at = datetime.utcnow().isoformat()

        print(f"\n[{config.name}] COMPLETED:")
        print(f"  Vectors: {metrics.total_vectors:,}")
        print(f"  Total time: {metrics.total_time_ms / 1000:.1f}s")
        print(f"  Throughput: {metrics.vectors_per_second:.1f} vectors/sec")
        print(f"  Embed time/vec: {total_embedding_time / vector_count:.2f}ms")
        print(f"  Search P50: {metrics.search_latency_p50_ms:.1f}ms")
        print(f"  Est. size: {metrics.estimated_size_mb:.2f}MB")

    except Exception as e:
        metrics.status = "failed"
        metrics.errors.append(str(e))
        metrics.completed_at = datetime.utcnow().isoformat()
        print(f"[{config.name}] FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Save results
    result_path = f"/results/{experiment_id}.json"
    with open(result_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)

    return asdict(metrics)


# =============================================================================
# Experiment with ColBERT Reranking
# =============================================================================

@app.function(
    image=gpu_image,
    gpu="T4",
    volumes={"/results": results_volume},
    timeout=3600 * 2,
    secrets=[
        modal.Secret.from_name("qdrant"),
        modal.Secret.from_name("openai"),
    ],
)
def run_wiki_experiment_with_reranking(
    config_name: str = "openai_256_mrl",
    num_samples: int = 5000,
) -> Dict:
    """
    Run experiment with OpenAI dense retrieval + ColBERT reranking.

    This is the recommended pattern:
    1. First-stage: OpenAI dense vectors for fast retrieval
    2. Reranking: ColBERT multi-vectors for precision

    Args:
        config_name: Dense config to test
        num_samples: Number of Wikipedia articles
    """
    import time
    import uuid
    import numpy as np
    import openai
    from datasets import load_dataset
    from fastembed import LateInteractionTextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        ScalarQuantization, ScalarType, HnswConfigDiff,
        MultiVectorConfig, MultiVectorComparator,
    )

    config = CONFIGS[config_name]
    experiment_id = uuid.uuid4().hex[:12]
    collection_name = f"wiki_rerank_{config_name}_{experiment_id}"

    metrics = IngestMetrics(
        experiment_id=experiment_id,
        config_name=f"{config.name} + ColBERT Rerank",
        config={**asdict(config), "colbert_rerank": True},
        parquet_file="hf://wikimedia/wikipedia/20231101.simple",
        collection_name=collection_name,
        started_at=datetime.utcnow().isoformat(),
    )

    print(f"[{config.name} + ColBERT] Starting experiment {experiment_id}")

    # Get secrets
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=300)
    openai_client = openai.OpenAI(api_key=openai_key)

    # Initialize ColBERT
    print("  Loading ColBERT model...")
    colbert = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")

    total_start = time.time()

    try:
        # Load dataset
        print(f"  Loading Wikipedia from HuggingFace...")
        ds = load_dataset("wikimedia/wikipedia", "20231101.simple", split=f"train[:{num_samples}]")
        metrics.total_rows = len(ds)
        print(f"  Loaded {len(ds)} articles")

        # Create collection with named vectors: dense + colbert
        vectors_config = {
            "dense": VectorParams(
                size=config.dimensions,
                distance=Distance.COSINE,
                on_disk=config.on_disk,
            ),
            "colbert": VectorParams(
                size=128,  # ColBERT dimension
                distance=Distance.COSINE,
                on_disk=config.on_disk,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM,
                ),
            ),
        }

        quantization = None
        if config.use_quantization and config.quantization_type == "int8":
            quantization = ScalarQuantization(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )

        # Disable HNSW for colbert (brute force MaxSim)
        hnsw_config = HnswConfigDiff(m=0)

        try:
            client.delete_collection(collection_name)
        except:
            pass

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            quantization_config=quantization,
            hnsw_config=hnsw_config,
            shard_number=config.shard_number,
        )
        print(f"  Created collection: {collection_name}")
        print(f"  Vectors: dense ({config.dimensions}d) + colbert (128d multi-vector)")

        # Create payload indexes for efficient filtering
        from qdrant_client.models import PayloadSchemaType
        indexed_fields = [
            ("quality_score", PayloadSchemaType.FLOAT),
            ("word_count", PayloadSchemaType.INTEGER),
            ("reading_level", PayloadSchemaType.FLOAT),
            ("earliest_year_mentioned", PayloadSchemaType.INTEGER),
            ("latest_year_mentioned", PayloadSchemaType.INTEGER),
            ("primary_topic", PayloadSchemaType.KEYWORD),
            ("complexity", PayloadSchemaType.KEYWORD),
            ("is_stub", PayloadSchemaType.BOOL),
            ("is_biographical", PayloadSchemaType.BOOL),
            ("has_references", PayloadSchemaType.BOOL),
            ("is_contemporary", PayloadSchemaType.BOOL),
        ]
        for field_name, field_type in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                    wait=False,
                )
            except Exception:
                pass
        print(f"  Created {len(indexed_fields)} payload indexes")

        # Process in batches
        total_dense_time = 0
        total_colbert_time = 0
        total_upsert_time = 0
        batch_count = 0
        vector_count = 0

        for i in range(0, len(ds), config.batch_size):
            batch = ds[i:i + config.batch_size]
            texts = [str(t)[:4000] for t in batch["text"] if t]  # ~1000 tokens per article max
            if not texts:
                continue

            batch_count += 1

            # Dense embeddings (OpenAI)
            dense_start = time.time()
            embed_kwargs = {"model": config.embedding_model, "input": texts}
            if config.use_mrl:
                embed_kwargs["dimensions"] = config.dimensions
            response = openai_client.embeddings.create(**embed_kwargs)
            dense_vectors = [d.embedding for d in response.data]
            dense_time = (time.time() - dense_start) * 1000
            total_dense_time += dense_time

            # ColBERT multi-vectors
            colbert_start = time.time()
            colbert_vectors = list(colbert.embed(texts))  # List of [num_tokens, 128]
            colbert_time = (time.time() - colbert_start) * 1000
            total_colbert_time += colbert_time

            # Create points with both vectors and rich metadata
            points = []
            for j, (dense_vec, colbert_vec) in enumerate(zip(dense_vectors, colbert_vectors)):
                title = batch["title"][j] if j < len(batch["title"]) else ""
                text = texts[j]
                wiki_id = batch["id"][j] if "id" in batch and j < len(batch["id"]) else None
                url = batch["url"][j] if "url" in batch and j < len(batch["url"]) else None

                # Extract rich metadata for filtering
                payload = extract_rich_metadata(title, text, wiki_id, url)
                payload["batch"] = batch_count

                points.append(PointStruct(
                    id=uuid.uuid4().hex,
                    vector={
                        "dense": dense_vec,
                        "colbert": colbert_vec.tolist(),  # Multi-vector
                    },
                    payload=payload,
                ))

            # Upsert
            upsert_start = time.time()
            client.upsert(collection_name=collection_name, points=points, wait=True)
            upsert_time = (time.time() - upsert_start) * 1000
            total_upsert_time += upsert_time

            vector_count += len(points)

            if batch_count % 5 == 0 or batch_count == 1:
                print(f"  Batch {batch_count}: {vector_count:,} - "
                      f"Dense: {dense_time:.0f}ms, ColBERT: {colbert_time:.0f}ms")

        # Re-enable HNSW for dense vectors only
        print(f"  Re-enabling HNSW for dense vectors...")
        client.update_collection(
            collection_name=collection_name,
            hnsw_config=HnswConfigDiff(m=16),
        )
        while True:
            info = client.get_collection(collection_name)
            if info.status.value == "green":
                break
            time.sleep(1)

        total_time = (time.time() - total_start) * 1000

        # Metrics
        metrics.total_vectors = vector_count
        metrics.total_batches = batch_count
        metrics.embedding_time_ms = total_dense_time + total_colbert_time
        metrics.upsert_time_ms = total_upsert_time
        metrics.total_time_ms = total_time
        metrics.vectors_per_second = vector_count / (total_time / 1000) if total_time > 0 else 0

        # Size estimate (dense + colbert avg ~50 tokens)
        dense_size = config.dimensions * 4 * vector_count
        colbert_size = 128 * 4 * 50 * vector_count  # ~50 tokens avg
        metrics.estimated_size_mb = (dense_size + colbert_size) / (1024 * 1024)

        # Search latency test: Dense-only vs Dense+Rerank
        print(f"  Running search latency comparison...")
        test_texts = [ds[j]["text"][:500] for j in range(min(10, len(ds)))]

        # Dense query vectors
        test_response = openai_client.embeddings.create(
            model=config.embedding_model,
            input=test_texts,
            **({"dimensions": config.dimensions} if config.use_mrl else {}),
        )
        test_dense = [d.embedding for d in test_response.data]

        # ColBERT query vectors
        test_colbert = list(colbert.query_embed(test_texts))

        dense_latencies = []
        rerank_latencies = []

        for dense_vec, colbert_vec in zip(test_dense, test_colbert):
            # Dense-only search
            start = time.time()
            client.query_points(
                collection_name=collection_name,
                query=dense_vec,
                using="dense",
                limit=10,
            )
            dense_latencies.append((time.time() - start) * 1000)

            # Dense retrieval + ColBERT reranking (prefetch pattern)
            start = time.time()
            client.query_points(
                collection_name=collection_name,
                prefetch={
                    "query": dense_vec,
                    "using": "dense",
                    "limit": 50,  # Retrieve 50 candidates
                },
                query=colbert_vec.tolist(),
                using="colbert",
                limit=10,  # Rerank to top 10
            )
            rerank_latencies.append((time.time() - start) * 1000)

        dense_latencies.sort()
        rerank_latencies.sort()

        metrics.search_latency_p50_ms = dense_latencies[len(dense_latencies) // 2]
        metrics.search_latency_p95_ms = rerank_latencies[len(rerank_latencies) // 2]  # Use p95 field for rerank p50

        metrics.status = "completed"
        metrics.completed_at = datetime.utcnow().isoformat()

        print(f"\n[{config.name} + ColBERT] COMPLETED:")
        print(f"  Vectors: {metrics.total_vectors:,}")
        print(f"  Total time: {metrics.total_time_ms / 1000:.1f}s")
        print(f"  Throughput: {metrics.vectors_per_second:.1f} vectors/sec")
        print(f"  Dense embed: {total_dense_time / vector_count:.2f}ms/vec")
        print(f"  ColBERT embed: {total_colbert_time / vector_count:.2f}ms/vec")
        print(f"  Search P50 (dense only): {dense_latencies[len(dense_latencies) // 2]:.1f}ms")
        print(f"  Search P50 (dense+rerank): {rerank_latencies[len(rerank_latencies) // 2]:.1f}ms")
        print(f"  Est. size: {metrics.estimated_size_mb:.2f}MB")

    except Exception as e:
        metrics.status = "failed"
        metrics.errors.append(str(e))
        metrics.completed_at = datetime.utcnow().isoformat()
        print(f"[{config.name} + ColBERT] FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Save results
    result_path = f"/results/{experiment_id}.json"
    with open(result_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)

    return asdict(metrics)


# =============================================================================
# Multimodal Experiment (Text + Image + ColBERT)
# =============================================================================

# Image-capable GPU image with CLIP
multimodal_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "qdrant-client>=1.12.0",
        "fastembed>=0.4.0",
        "openai>=1.50.0",
        "datasets>=2.20.0",
        "Pillow>=10.0.0",
        "requests>=2.31.0",
        "torch>=2.2.0",
        "tqdm>=4.66.0",
    )
)


@app.function(
    image=multimodal_image,
    gpu="T4",
    volumes={"/results": results_volume},
    timeout=3600 * 3,
    secrets=[
        modal.Secret.from_name("qdrant"),
        modal.Secret.from_name("openai"),
    ],
)
def run_wiki_experiment_multimodal(
    num_samples: int = 1000,
) -> Dict:
    """
    Run multimodal experiment with:
    1. OpenAI dense text embeddings (256d MRL)
    2. CLIP image embeddings (512d) from Wikipedia images
    3. ColBERT late interaction for reranking (128d multi-vector)

    This creates a collection with 3 named vectors for maximum flexibility:
    - "text": Dense text retrieval
    - "image": Image similarity search
    - "colbert": Late interaction reranking

    Search patterns enabled:
    - Text-only search (fast)
    - Image-only search (visual similarity)
    - Text + ColBERT rerank (high precision)
    - Cross-modal: text query → image results
    """
    import time
    import uuid
    import requests
    from io import BytesIO
    import openai
    from PIL import Image
    from datasets import load_dataset
    from fastembed import LateInteractionTextEmbedding, ImageEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        HnswConfigDiff, MultiVectorConfig, MultiVectorComparator,
        PayloadSchemaType,
    )

    experiment_id = uuid.uuid4().hex[:12]
    collection_name = f"wiki_multimodal_{experiment_id}"

    metrics = IngestMetrics(
        experiment_id=experiment_id,
        config_name="Multimodal (Text + CLIP + ColBERT)",
        config={"text_dim": 256, "image_dim": 512, "colbert_dim": 128},
        parquet_file="hf://wikimedia/wikipedia/20231101.simple",
        collection_name=collection_name,
        started_at=datetime.utcnow().isoformat(),
    )

    print(f"[Multimodal] Starting experiment {experiment_id}")

    # Get secrets
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=300)
    openai_client = openai.OpenAI(api_key=openai_key)

    # Initialize embedding models
    print("  Loading CLIP and ColBERT models...")
    clip_model = ImageEmbedding("Qdrant/clip-ViT-B-32-vision")
    colbert_model = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")

    total_start = time.time()

    try:
        # Load dataset
        print(f"  Loading Wikipedia from HuggingFace...")
        ds = load_dataset("wikimedia/wikipedia", "20231101.simple", split=f"train[:{num_samples}]")
        metrics.total_rows = len(ds)
        print(f"  Loaded {len(ds)} articles")

        # Create collection with 3 named vectors
        vectors_config = {
            "text": VectorParams(
                size=256,
                distance=Distance.COSINE,
                on_disk=True,
            ),
            "image": VectorParams(
                size=512,
                distance=Distance.COSINE,
                on_disk=True,
            ),
            "colbert": VectorParams(
                size=128,
                distance=Distance.COSINE,
                on_disk=True,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM,
                ),
            ),
        }

        hnsw_config = HnswConfigDiff(m=0)  # Disable during bulk insert

        try:
            client.delete_collection(collection_name)
        except:
            pass

        client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            hnsw_config=hnsw_config,
            shard_number=2,
        )
        print(f"  Created collection: {collection_name}")
        print(f"  Vectors: text (256d) + image (512d) + colbert (128d multi)")

        # Create payload indexes
        indexed_fields = [
            ("quality_score", PayloadSchemaType.FLOAT),
            ("primary_topic", PayloadSchemaType.KEYWORD),
            ("has_image", PayloadSchemaType.BOOL),
            ("is_biographical", PayloadSchemaType.BOOL),
        ]
        for field_name, field_type in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                    wait=False,
                )
            except:
                pass

        # Process in batches
        batch_size = 10  # Small batches due to ColBERT multi-vector size
        total_text_time = 0
        total_image_time = 0
        total_colbert_time = 0
        total_upsert_time = 0
        batch_count = 0
        vector_count = 0
        images_embedded = 0

        for i in range(0, len(ds), batch_size):
            batch = ds[i:i + batch_size]
            texts = [str(t)[:2000] for t in batch["text"] if t]  # Shorter for ColBERT
            if not texts:
                continue

            batch_count += 1

            # 1. Text embeddings (OpenAI 256d MRL)
            text_start = time.time()
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                dimensions=256,
            )
            text_vectors = [d.embedding for d in response.data]
            text_time = (time.time() - text_start) * 1000
            total_text_time += text_time

            # 2. ColBERT multi-vectors
            colbert_start = time.time()
            colbert_vectors = list(colbert_model.embed(texts))
            colbert_time = (time.time() - colbert_start) * 1000
            total_colbert_time += colbert_time

            # 3. Try to get images from Wikipedia via MediaWiki API (more reliable)
            image_vectors = []
            image_start = time.time()
            for j, title in enumerate(batch["title"]):
                try:
                    # Use MediaWiki API which is more reliable from cloud
                    encoded_title = title.replace(' ', '_')
                    api_url = "https://en.wikipedia.org/w/api.php"
                    params = {
                        "action": "query",
                        "titles": encoded_title,
                        "prop": "pageimages",
                        "format": "json",
                        "pithumbsize": 300,
                    }
                    resp = requests.get(api_url, params=params, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        pages = data.get("query", {}).get("pages", {})
                        for page_id, page_data in pages.items():
                            if "thumbnail" in page_data:
                                img_url = page_data["thumbnail"]["source"]
                                img_resp = requests.get(img_url, timeout=5)
                                if img_resp.status_code == 200:
                                    img = Image.open(BytesIO(img_resp.content)).convert("RGB")
                                    img_vec = list(clip_model.embed([img]))[0]
                                    image_vectors.append(img_vec.tolist())
                                    images_embedded += 1
                                    break
                        else:
                            image_vectors.append(None)
                    else:
                        image_vectors.append(None)
                except Exception as e:
                    image_vectors.append(None)

            image_time = (time.time() - image_start) * 1000
            total_image_time += image_time

            # Create points with all vectors
            points = []
            for j, (text_vec, colbert_vec) in enumerate(zip(text_vectors, colbert_vectors)):
                title = batch["title"][j] if j < len(batch["title"]) else ""
                text = texts[j]

                # Build vector dict
                vectors = {
                    "text": text_vec,
                    "colbert": colbert_vec.tolist(),
                }

                # Add image vector if available
                has_image = False
                if j < len(image_vectors) and image_vectors[j] is not None:
                    vectors["image"] = image_vectors[j]
                    has_image = True

                # Extract metadata
                payload = extract_rich_metadata(title, text)
                payload["batch"] = batch_count
                payload["has_image"] = has_image

                points.append(PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vectors,
                    payload=payload,
                ))

            # Upsert
            upsert_start = time.time()
            client.upsert(collection_name=collection_name, points=points, wait=True)
            upsert_time = (time.time() - upsert_start) * 1000
            total_upsert_time += upsert_time

            vector_count += len(points)

            if batch_count % 5 == 0 or batch_count == 1:
                print(f"  Batch {batch_count}: {vector_count} pts, {images_embedded} imgs - "
                      f"Text: {text_time:.0f}ms, CLIP: {image_time:.0f}ms, ColBERT: {colbert_time:.0f}ms")

        # Re-enable HNSW indexing
        print(f"  Re-enabling HNSW indexing...")
        client.update_collection(
            collection_name=collection_name,
            hnsw_config=HnswConfigDiff(m=16),
        )
        while True:
            info = client.get_collection(collection_name)
            if info.status.value == "green":
                break
            time.sleep(1)

        total_time = (time.time() - total_start) * 1000

        # Metrics
        metrics.total_vectors = vector_count
        metrics.total_batches = batch_count
        metrics.embedding_time_ms = total_text_time + total_image_time + total_colbert_time
        metrics.upsert_time_ms = total_upsert_time
        metrics.total_time_ms = total_time
        metrics.vectors_per_second = vector_count / (total_time / 1000) if total_time > 0 else 0

        # Size estimate
        text_size = 256 * 4 * vector_count
        image_size = 512 * 4 * images_embedded
        colbert_size = 128 * 4 * 50 * vector_count  # ~50 tokens avg
        metrics.estimated_size_mb = (text_size + image_size + colbert_size) / (1024 * 1024)

        metrics.status = "completed"
        metrics.completed_at = datetime.utcnow().isoformat()

        print(f"\n[Multimodal] COMPLETED:")
        print(f"  Points: {metrics.total_vectors:,}")
        print(f"  Images embedded: {images_embedded}")
        print(f"  Total time: {metrics.total_time_ms / 1000:.1f}s")
        print(f"  Text embed: {total_text_time / vector_count:.2f}ms/pt")
        print(f"  CLIP embed: {total_image_time / max(images_embedded, 1):.2f}ms/img")
        print(f"  ColBERT embed: {total_colbert_time / vector_count:.2f}ms/pt")
        print(f"  Est. size: {metrics.estimated_size_mb:.2f}MB")

    except Exception as e:
        metrics.status = "failed"
        metrics.errors.append(str(e))
        metrics.completed_at = datetime.utcnow().isoformat()
        print(f"[Multimodal] FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Save results
    result_path = f"/results/{experiment_id}.json"
    with open(result_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)

    return asdict(metrics)


# =============================================================================
# Local Entry Point
# =============================================================================

@app.local_entrypoint()
def main():
    """List available configs"""
    print("\nAvailable Configurations:")
    print("=" * 60)
    for name, config in CONFIGS.items():
        print(f"\n{name}:")
        print(f"  {config.name}")
        print(f"  Provider: {config.embedding_provider}")
        print(f"  Dimensions: {config.dimensions}, MRL: {config.use_mrl}")

    print("\n\nUsage:")
    print("  modal run modal_wiki_ingest.py::ingest_parquet_cpu --config-name openai_256_mrl --parquet-path /data/wiki.parquet")
    print("  modal run modal_wiki_ingest.py::show_results")
