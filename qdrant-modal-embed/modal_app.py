"""
Modal App for Sparse Encoder Training on E-Commerce Search

Following the Modal blog pattern: https://modal.com/blog/fine-tuning-embeddings

Run training:
    modal run modal_app.py::train_sparse_encoder --config configs/baseline.yaml

Run ANCE loop:
    modal run modal_app.py::train_ance_loop --config configs/baseline.yaml

Run sweep:
    modal run modal_app.py::run_sweep
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

import modal

# =============================================================================
# Modal App Configuration
# =============================================================================

app = modal.App("esci-sparse-encoder")

# Volumes for persistent storage
checkpoint_volume = modal.Volume.from_name("esci-sparse-checkpoints", create_if_missing=True)
dataset_volume = modal.Volume.from_name("esci-datasets", create_if_missing=True)

# GPU configuration (2025 Modal API)
gpu_config = "A100-40GB"
gpu_config_sweep = "A10G"

# Docker image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Core ML - Sentence Transformers v5 for SparseEncoder
        "sentence-transformers>=5.0.0",
        "torch>=2.2.0",
        "transformers>=4.45.0",
        # Data
        "datasets>=2.20.0",
        # Qdrant
        "qdrant-client>=1.12.0",
        # Config
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.0",
        "tqdm>=4.66.0",
        # Eval
        "numpy>=1.26.0",
        "scipy>=1.12.0",
        "scikit-learn>=1.4.0",
        # FastEmbed for baseline sparse models (GPU-accelerated)
        "fastembed-gpu>=0.4.0",
        # Training
        "accelerate>=0.30.0",
    )
    .add_local_dir(
        Path(__file__).parent / "src",
        remote_path="/root/src",
    )
)


# =============================================================================
# Training Functions
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 12,  # 12 hours max
    secrets=[modal.Secret.from_name("qdrant")],
)
def train_sparse_encoder(
    config: Dict,
    resume_from_checkpoint: Optional[str] = None,
) -> str:
    """
    Train SPLADE sparse encoder on Modal with checkpointing.

    This follows the Modal blog pattern for fine-tuning embeddings,
    adapted for sparse models.

    Args:
        config: Training configuration dict with:
            - run_name: Identifier for this run
            - base_model: HuggingFace model name
            - architecture: "splade" or "inference_free_splade"
            - batch_size, learning_rate, num_epochs
            - query_regularizer_weight, document_regularizer_weight
        resume_from_checkpoint: Path to checkpoint to resume from

    Returns:
        Path to final saved model
    """
    import sys

    sys.path.insert(0, "/root")

    from datasets import load_dataset
    from sentence_transformers import (
        SparseEncoder,
        SparseEncoderTrainer,
        SparseEncoderTrainingArguments,
    )
    from sentence_transformers.sparse_encoder.losses import (
        SpladeLoss,
        SparseMultipleNegativesRankingLoss,
    )
    from sentence_transformers.training_args import BatchSamplers

    from src.training.sparse_model import create_sparse_encoder

    from src.data.esci_loader import ESCILoader

    print(f"Starting training run: {config.get('run_name', 'default')}")
    print(f"Config: {config}")

    # Load or create model
    if resume_from_checkpoint:
        print(f"Resuming from checkpoint: {resume_from_checkpoint}")
        model = SparseEncoder(resume_from_checkpoint)
    else:
        model = create_sparse_encoder(
            base_model=config.get("base_model", "distilbert/distilbert-base-uncased"),
            architecture=config.get("architecture", "inference_free_splade"),
        )

    # Load dataset using ESCILoader
    print("Loading ESCI dataset...")
    loader = ESCILoader(cache_dir="/datasets/cache")
    train_dataset = loader.load_for_training(
        split="train",
        max_samples=config.get("max_samples"),
        include_substitutes=True,
    )

    print(f"Training dataset size: {len(train_dataset)}")

    # Create loss
    loss = SpladeLoss(
        model=model,
        loss=SparseMultipleNegativesRankingLoss(model=model),
        query_regularizer_weight=float(config.get("query_regularizer_weight", 5e-5)),
        document_regularizer_weight=float(config.get("document_regularizer_weight", 3e-5)),
    )

    # Training arguments
    output_dir = f"/checkpoints/{config.get('run_name', 'default')}"

    # Router mapping for inference-free SPLADE (separate query/doc encoders)
    router_mapping = {"anchor": "query", "positive": "document"}

    args = SparseEncoderTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config.get("num_epochs", 3),
        per_device_train_batch_size=config.get("batch_size", 32),
        learning_rate=float(config.get("learning_rate", 2e-5)),
        warmup_ratio=0.1,
        fp16=True,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        # Router mapping for query/document routing
        router_mapping=router_mapping,
        # Checkpointing
        save_strategy="steps",
        save_steps=config.get("save_steps", 1000),
        save_total_limit=3,
        # Logging
        logging_steps=config.get("logging_steps", 100),
        report_to=[],  # Disable tensorboard for Modal runs
    )

    # Trainer
    trainer = SparseEncoderTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        loss=loss,
    )

    # Train
    print("Starting training...")
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    # Save final model
    final_path = f"{output_dir}/final"
    model.save_pretrained(final_path)
    print(f"Saved final model to {final_path}")

    # Commit volume
    checkpoint_volume.commit()

    return final_path


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 12,  # 12 hours for multi-domain training
)
def train_multidomain(
    config: Dict,
    resume_from_checkpoint: Optional[str] = None,
) -> str:
    """
    Train SPLADE sparse encoder on multiple e-commerce domains.

    Combines training data from:
    - Amazon ESCI
    - Wayfair WANDS
    - Home Depot

    This produces a more generalized model that should perform
    well across different e-commerce domains.

    Args:
        config: Training configuration dict
        resume_from_checkpoint: Path to checkpoint to resume from

    Returns:
        Path to final saved model
    """
    import sys

    sys.path.insert(0, "/root")

    from sentence_transformers import (
        SparseEncoder,
        SparseEncoderTrainer,
        SparseEncoderTrainingArguments,
    )
    from sentence_transformers.sparse_encoder.losses import (
        SpladeLoss,
        SparseMultipleNegativesRankingLoss,
    )
    from sentence_transformers.training_args import BatchSamplers

    from src.training.sparse_model import create_sparse_encoder
    from src.data.multidomain_loader import MultiDomainLoader

    print(f"Starting MULTI-DOMAIN training run: {config.get('run_name', 'multidomain')}")
    print(f"Config: {config}")

    # Load or create model
    if resume_from_checkpoint:
        print(f"Resuming from checkpoint: {resume_from_checkpoint}")
        model = SparseEncoder(resume_from_checkpoint)
    else:
        model = create_sparse_encoder(
            base_model=config.get("base_model", "distilbert/distilbert-base-uncased"),
            architecture=config.get("architecture", "inference_free_splade"),
        )

    # Load combined dataset from all three domains
    print("Loading multi-domain dataset (ESCI + WANDS + Home Depot)...")
    loader = MultiDomainLoader(cache_dir="/datasets/cache")
    train_dataset = loader.load_for_training(
        max_samples_per_dataset=config.get("max_samples_per_dataset"),
        include_esci=config.get("include_esci", True),
        include_wands=config.get("include_wands", True),
        include_homedepot=config.get("include_homedepot", True),
    )

    print(f"Combined training dataset size: {len(train_dataset)}")

    # Create loss
    loss = SpladeLoss(
        model=model,
        loss=SparseMultipleNegativesRankingLoss(model=model),
        query_regularizer_weight=float(config.get("query_regularizer_weight", 5e-5)),
        document_regularizer_weight=float(config.get("document_regularizer_weight", 3e-5)),
    )

    # Training arguments
    output_dir = f"/checkpoints/{config.get('run_name', 'multidomain')}"

    # Router mapping for inference-free SPLADE (separate query/doc encoders)
    router_mapping = {"anchor": "query", "positive": "document"}

    args = SparseEncoderTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config.get("num_epochs", 3),
        per_device_train_batch_size=config.get("batch_size", 32),
        learning_rate=float(config.get("learning_rate", 2e-5)),
        warmup_ratio=0.1,
        fp16=True,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        router_mapping=router_mapping,
        # Checkpointing
        save_strategy="steps",
        save_steps=config.get("save_steps", 1000),
        save_total_limit=3,
        # Logging
        logging_steps=config.get("logging_steps", 100),
        report_to=[],
    )

    # Trainer
    trainer = SparseEncoderTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        loss=loss,
    )

    # Train
    print("Starting multi-domain training...")
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    # Save final model
    final_path = f"{output_dir}/final"
    model.save_pretrained(final_path)
    print(f"Saved final model to {final_path}")

    # Commit volume
    checkpoint_volume.commit()

    return final_path


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 24,  # 24 hours for full ANCE loop
    secrets=[modal.Secret.from_name("qdrant")],
)
def train_ance_loop(
    config: Dict,
    num_iterations: int = 3,
) -> str:
    """
    ANCE (Approximate Nearest Neighbor Contrastive Estimation) training loop.

    Each iteration:
    1. Index products with current model into Qdrant sparse collection
    2. Mine hard negatives (top-K retrieved but not relevant)
    3. Train for 1 epoch with mined negatives
    4. Save checkpoint

    This is the core "Qdrant in training" feature.

    Args:
        config: Training configuration
        num_iterations: Number of ANCE iterations

    Returns:
        Path to final model
    """
    import sys

    sys.path.insert(0, "/root")

    from datasets import Dataset, load_dataset
    from qdrant_client import QdrantClient
    from sentence_transformers import (
        SparseEncoder,
        SparseEncoderTrainer,
        SparseEncoderTrainingArguments,
    )
    from sentence_transformers.sparse_encoder.losses import (
        SpladeLoss,
        SparseMultipleNegativesRankingLoss,
    )
    from sentence_transformers.training_args import BatchSamplers

    from src.qdrant.client import create_sparse_collection, delete_collection
    from src.qdrant.index import index_sparse_vectors
    from src.qdrant.mining import SparseQdrantMiner
    from src.training.sparse_model import create_sparse_encoder

    print(f"Starting ANCE training loop with {num_iterations} iterations")

    # Initialize Qdrant client
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )

    # Load ESCI dataset
    print("Loading ESCI dataset...")
    dataset = load_dataset(
        "tasksource/esci",
        split="train",
        cache_dir="/datasets/cache",
    )
    dataset = dataset.filter(lambda x: x.get("product_locale", "us") == "us")

    # Build products list for indexing
    product_map = {}
    query_map = {}

    for item in dataset:
        pid = item.get("product_id", "")
        query = item.get("query", "")
        query_id = item.get("query_id", query)
        label = item.get("esci_label", "I")

        # Product
        if pid not in product_map:
            title = item.get("product_title", "") or ""
            brand = item.get("product_brand", "") or ""
            desc = item.get("product_description", "") or ""
            product_text = f"[{brand}] {title}" if brand else title
            if desc:
                product_text += f" | {desc[:200]}"

            product_map[pid] = {
                "product_id": pid,
                "text": product_text,
                "label": label,
            }

        # Query
        if query_id not in query_map:
            query_map[query_id] = {
                "query": query,
                "query_id": query_id,
                "positive_ids": set(),
                "positive_texts": [],
            }
        if label in {"E", "S"}:
            query_map[query_id]["positive_ids"].add(pid)
            query_map[query_id]["positive_texts"].append(product_map[pid]["text"])

    products = list(product_map.values())
    queries = [q for q in query_map.values() if q["positive_ids"]]

    print(f"Loaded {len(products)} products and {len(queries)} queries")

    # Limit for testing
    max_products = config.get("max_products", 50000)
    max_queries = config.get("max_queries", 10000)
    if len(products) > max_products:
        products = products[:max_products]
    if len(queries) > max_queries:
        queries = queries[:max_queries]

    # Initialize model
    current_model_path = config.get("base_model", "distilbert/distilbert-base-uncased")
    run_name = config.get("run_name", "ance")

    for iteration in range(num_iterations):
        print(f"\n{'=' * 60}")
        print(f"ANCE Iteration {iteration + 1}/{num_iterations}")
        print(f"{'=' * 60}")

        # Load model
        if iteration == 0 and "splade" not in current_model_path.lower():
            model = create_sparse_encoder(
                base_model=current_model_path,
                architecture=config.get("architecture", "inference_free_splade"),
            )
        else:
            model = SparseEncoder(current_model_path)

        # Create collection for this iteration
        collection_name = f"esci_ance_{run_name}_iter{iteration}"
        print(f"Creating collection: {collection_name}")
        create_sparse_collection(client, collection_name, recreate=True)

        # Index products
        print("Indexing products...")
        index_sparse_vectors(client, collection_name, model, products)

        # Mine hard negatives
        print("Mining hard negatives...")
        miner = SparseQdrantMiner(client, model, collection_name)

        # Add positive_text to queries for training
        queries_with_positives = []
        for q in queries:
            if q["positive_texts"]:
                queries_with_positives.append(
                    {
                        "query": q["query"],
                        "positive_ids": q["positive_ids"],
                        "positive_text": q["positive_texts"][0],  # Use first positive
                    }
                )

        hard_neg_examples = miner.mine_for_training(
            queries=queries_with_positives,
            top_k=config.get("mining_top_k", 20),
            num_negatives=3,
        )

        print(f"Created {len(hard_neg_examples)} training examples with hard negatives")

        # Create training dataset
        train_data = {
            "anchor": [ex["anchor"] for ex in hard_neg_examples],
            "positive": [ex["positive"] for ex in hard_neg_examples],
        }
        train_dataset = Dataset.from_dict(train_data)

        # Create loss and trainer
        loss = SpladeLoss(
            model=model,
            loss=SparseMultipleNegativesRankingLoss(model=model),
            query_regularizer_weight=float(config.get("query_regularizer_weight", 5e-5)),
            document_regularizer_weight=float(config.get("document_regularizer_weight", 3e-5)),
        )

        output_dir = f"/checkpoints/{run_name}/iter{iteration}"
        router_mapping = {"anchor": "query", "positive": "document"}
        args = SparseEncoderTrainingArguments(
            output_dir=output_dir,
            num_train_epochs=config.get("epochs_per_iteration", 1),
            per_device_train_batch_size=config.get("batch_size", 32),
            learning_rate=float(config.get("learning_rate", 2e-5)),
            warmup_ratio=0.1,
            fp16=True,
            batch_sampler=BatchSamplers.NO_DUPLICATES,
            router_mapping=router_mapping,
            save_strategy="epoch",
            logging_steps=50,
            report_to=[],
        )

        trainer = SparseEncoderTrainer(
            model=model,
            args=args,
            train_dataset=train_dataset,
            loss=loss,
        )

        # Train
        print(f"Training iteration {iteration + 1}...")
        trainer.train()

        # Save checkpoint
        model.save_pretrained(output_dir)
        current_model_path = output_dir
        checkpoint_volume.commit()

        # Cleanup collection
        print(f"Cleaning up collection: {collection_name}")
        delete_collection(client, collection_name)

    # Save final model
    final_path = f"/checkpoints/{run_name}/final"
    model.save_pretrained(final_path)
    checkpoint_volume.commit()

    print(f"\nANCE training complete. Final model: {final_path}")
    return final_path


@app.function(
    image=image,
    gpu=gpu_config_sweep,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 6,
    secrets=[modal.Secret.from_name("qdrant")],
)
def train_sweep_trial(
    trial_config: Dict,
    trial_id: int,
) -> Dict:
    """
    Single trial for hyperparameter sweep.

    Args:
        trial_config: Configuration for this trial
        trial_id: Trial identifier

    Returns:
        Dict with trial results and metrics
    """
    import sys

    sys.path.insert(0, "/root")

    # Train with limited samples for sweep
    trial_config["max_samples"] = trial_config.get("max_samples", 5000)
    trial_config["num_epochs"] = trial_config.get("num_epochs", 1)
    trial_config["run_name"] = f"sweep_trial_{trial_id}"

    # Run training
    final_path = train_sparse_encoder.local(trial_config)

    # Evaluate the trained model on a small validation set
    from sentence_transformers import SparseEncoder
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm

    from src.data.esci_loader import ESCILoader
    from src.eval.retrieval_metrics import evaluate_retrieval
    from src.qdrant.index import sparse_embedding_to_qdrant

    print(f"Evaluating trial {trial_id}...")

    # Load trained model
    model = SparseEncoder(final_path)

    # Load small evaluation set
    loader = ESCILoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(
        split="test",
        max_queries=200,  # Small set for fast sweep evaluation
    )
    products = products[:2000]  # Limit products for speed

    # Create temporary collection for this trial
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    collection_name = f"sweep_eval_trial_{trial_id}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={},
        sparse_vectors_config={"text": models.SparseVectorParams()},
    )

    # Index products
    batch_size = 32
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        texts = [p["text"] for p in batch]
        embeddings = model.encode(texts, prompt_name="document")

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector={"text": sparse_vector},
                    payload={"product_id": doc["product_id"]},
                )
            )
        client.upsert(collection_name=collection_name, points=points)

    # Run evaluation
    retrieved_results = []
    for q in queries:
        emb = model.encode([q["query"]], prompt_name="document")[0]
        sparse_vector = sparse_embedding_to_qdrant(emb)

        results = client.query_points(
            collection_name=collection_name,
            query=sparse_vector,
            using="text",
            limit=100,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append({
            "query_id": q["query_id"],
            "retrieved_ids": retrieved_ids,
        })

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=[10, 50, 100],
    )

    # Cleanup temporary collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    print(f"Trial {trial_id} metrics: nDCG@10={metrics.get('ndcg@10', 0):.4f}")

    return {
        "trial_id": trial_id,
        "config": trial_config,
        "model_path": final_path,
        "metrics": metrics,
    }


# =============================================================================
# Baseline Evaluation
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config_sweep,  # Use GPU for FastEmbed acceleration
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 24,  # 24 hours for full dataset runs
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_baselines(
    max_products: int = 10000,  # Reduced for faster evaluation
    max_queries: int = 1000,  # Reduced for faster evaluation
    collection_name: str = "esci_baselines",
) -> Dict:
    """
    Evaluate BM25 and SPLADE baselines using FastEmbed for local embedding.

    Uses FastEmbed-GPU for sparse encoding (BM25, SPLADE) and Qdrant for storage/search.
    GPU accelerates SPLADE inference via CUDA.

    Args:
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with baseline metrics for BM25 and SPLADE
    """
    import sys

    sys.path.insert(0, "/root")

    from src.data.esci_loader import ESCILoader
    from src.eval.baselines import run_baseline_evaluation

    print(f"Loading ESCI dataset...")
    loader = ESCILoader(cache_dir="/datasets/cache")

    # Load products
    products = loader.load_products_for_indexing(split="train", max_products=max_products)
    print(f"Loaded {len(products)} products")

    # Load queries
    queries, _ = loader.load_for_evaluation(split="test", max_queries=max_queries)
    print(f"Loaded {len(queries)} queries")

    # Run evaluation
    print("Running baseline evaluation with Qdrant Cloud inference...")
    results = run_baseline_evaluation(
        products=products,
        queries=queries,
        collection_name=collection_name,
        recreate=True,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("BASELINE RESULTS")
    print("=" * 60)
    for model_name, metrics in results.items():
        print(f"\n{model_name.upper()}:")
        print(f"  nDCG@10:    {metrics.get('ndcg@10', 0):.4f}")
        print(f"  MRR@10:     {metrics.get('mrr@10', 0):.4f}")
        print(f"  Recall@100: {metrics.get('recall@100', 0):.4f}")

    return results


@app.function(
    image=image,
    gpu=gpu_config_sweep,  # Use GPU for FastEmbed acceleration
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_dense(
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "esci_dense",
) -> Dict:
    """
    Evaluate dense embedding baseline (all-MiniLM-L6-v2).

    Args:
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with dense baseline metrics
    """
    import sys

    sys.path.insert(0, "/root")

    from src.data.esci_loader import ESCILoader
    from src.eval.baselines import run_dense_evaluation

    print(f"Loading ESCI dataset...")
    loader = ESCILoader(cache_dir="/datasets/cache")

    # Load products
    products = loader.load_products_for_indexing(split="train", max_products=max_products)
    print(f"Loaded {len(products)} products")

    # Load queries
    queries, _ = loader.load_for_evaluation(split="test", max_queries=max_queries)
    print(f"Loaded {len(queries)} queries")

    # Run dense evaluation
    print("Running dense baseline evaluation...")
    metrics = run_dense_evaluation(
        products=products,
        queries=queries,
        collection_name=collection_name,
        recreate=True,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("DENSE BASELINE RESULTS")
    print("=" * 60)
    print(f"  nDCG@10:    {metrics.get('ndcg@10', 0):.4f}")
    print(f"  MRR@10:     {metrics.get('mrr@10', 0):.4f}")
    print(f"  Recall@100: {metrics.get('recall@100', 0):.4f}")

    return metrics


# =============================================================================
# Generalization Testing (WANDS Dataset)
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_wands(
    model_path: str = "splade_standard/final",
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "wands_eval",
) -> Dict:
    """
    Evaluate fine-tuned SPLADE model on WANDS dataset for generalization testing.

    Tests if ESCI-trained model generalizes to Wayfair home goods domain.

    Args:
        model_path: Path to model in checkpoint volume
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with evaluation metrics
    """
    import os
    import sys

    sys.path.insert(0, "/root")

    from sentence_transformers import SparseEncoder
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm

    from src.data.wands_loader import WANDSLoader
    from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics
    from src.qdrant.index import sparse_embedding_to_qdrant

    # Load fine-tuned model
    full_model_path = f"/checkpoints/{model_path}"
    print(f"Loading fine-tuned model from {full_model_path}...")
    model = SparseEncoder(full_model_path)

    # Load WANDS dataset
    print("Loading WANDS dataset...")
    loader = WANDSLoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(split="test", max_queries=max_queries)
    if max_products and len(products) > max_products:
        products = products[:max_products]
    print(f"Loaded {len(products)} products, {len(queries)} queries from WANDS")

    # Connect to Qdrant
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    # Create collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={},
        sparse_vectors_config={"text": models.SparseVectorParams()},
    )
    print(f"Created collection: {collection_name}")

    # Index products
    print("Encoding and indexing products...")
    batch_size = 32
    for i in tqdm(range(0, len(products), batch_size), desc="Indexing"):
        batch = products[i : i + batch_size]
        texts = [p["text"] for p in batch]

        embeddings = model.encode(texts, prompt_name="document")

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector={"text": sparse_vector},
                    payload={"product_id": doc["product_id"], "text": doc["text"]},
                )
            )

        client.upsert(collection_name=collection_name, points=points)

    print(f"Indexed {len(products)} products")

    # Evaluate
    print("Running evaluation...")
    retrieved_results = []
    k_values = [10, 50, 100]
    max_k = max(k_values)

    for q in tqdm(queries, desc="Evaluating"):
        emb = model.encode([q["query"]], prompt_name="document")[0]
        sparse_vector = sparse_embedding_to_qdrant(emb)

        results = client.query_points(
            collection_name=collection_name,
            query=sparse_vector,
            using="text",
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append(
            {
                "query_id": q["query_id"],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )

    print_metrics(metrics, "WANDS Generalization Results (Fine-tuned SPLADE)")
    return metrics


@app.function(
    image=image,
    gpu=gpu_config_sweep,
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_wands_baselines(
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "wands_baselines",
) -> Dict:
    """
    Evaluate BM25 and SPLADE baselines on WANDS dataset.

    Args:
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with baseline metrics for BM25 and SPLADE
    """
    import sys

    sys.path.insert(0, "/root")

    from src.data.wands_loader import WANDSLoader
    from src.eval.baselines import run_baseline_evaluation

    print(f"Loading WANDS dataset...")
    loader = WANDSLoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(split="test", max_queries=max_queries)
    if max_products and len(products) > max_products:
        products = products[:max_products]

    print(f"Loaded {len(products)} products, {len(queries)} queries")

    # Run baseline evaluation
    print("Running WANDS baseline evaluation...")
    results = run_baseline_evaluation(
        products=products,
        queries=queries,
        collection_name=collection_name,
        recreate=True,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("WANDS BASELINE RESULTS")
    print("=" * 60)
    for model_name, metrics in results.items():
        print(f"\n{model_name.upper()}:")
        print(f"  nDCG@10:    {metrics.get('ndcg@10', 0):.4f}")
        print(f"  MRR@10:     {metrics.get('mrr@10', 0):.4f}")
        print(f"  Recall@100: {metrics.get('recall@100', 0):.4f}")

    return results


# =============================================================================
# Home Depot Generalization Evaluation
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_homedepot(
    model_path: str = "splade_standard/final",
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "homedepot_eval",
) -> Dict:
    """
    Evaluate fine-tuned SPLADE model on Home Depot dataset for generalization testing.

    Tests cross-domain transfer: Amazon (training) -> Home Depot (home improvement).

    Args:
        model_path: Path to model in checkpoint volume
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with evaluation metrics
    """
    import os
    import sys

    sys.path.insert(0, "/root")

    from sentence_transformers import SparseEncoder
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm

    from src.data.homedepot_loader import HomeDepotLoader
    from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics
    from src.qdrant.index import sparse_embedding_to_qdrant

    # Load fine-tuned model
    full_model_path = f"/checkpoints/{model_path}"
    print(f"Loading fine-tuned model from {full_model_path}...")
    model = SparseEncoder(full_model_path)

    # Load Home Depot data
    print("Loading Home Depot dataset...")
    loader = HomeDepotLoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(max_queries=max_queries)
    if max_products and len(products) > max_products:
        products = products[:max_products]
    print(f"Loaded {len(products)} products, {len(queries)} queries from Home Depot")

    # Connect to Qdrant
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    # Create collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={},
        sparse_vectors_config={"text": models.SparseVectorParams()},
    )
    print(f"Created collection: {collection_name}")

    # Index products
    print("Encoding and indexing products...")
    batch_size = 32
    for i in tqdm(range(0, len(products), batch_size), desc="Indexing"):
        batch = products[i : i + batch_size]
        texts = [p["text"] for p in batch]

        embeddings = model.encode(texts, prompt_name="document")

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector={"text": sparse_vector},
                    payload={"product_id": doc["product_id"], "text": doc["text"]},
                )
            )

        client.upsert(collection_name=collection_name, points=points)

    print(f"Indexed {len(products)} products")

    # Evaluate
    print("Running evaluation...")
    retrieved_results = []
    k_values = [10, 50, 100]
    max_k = max(k_values)

    for q in tqdm(queries, desc="Evaluating"):
        emb = model.encode([q["query"]], prompt_name="document")[0]
        sparse_vector = sparse_embedding_to_qdrant(emb)

        results = client.query_points(
            collection_name=collection_name,
            query=sparse_vector,
            using="text",
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append(
            {
                "query_id": q["query_id"],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )

    print_metrics(metrics, "Home Depot Generalization Results (Fine-tuned SPLADE)")
    return metrics


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_homedepot_baselines(
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "homedepot_baselines",
) -> Dict[str, Dict]:
    """
    Evaluate BM25 and SPLADE baselines on Home Depot dataset.

    Args:
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict mapping model_name -> metrics
    """
    import sys

    sys.path.insert(0, "/root")

    from src.data.homedepot_loader import HomeDepotLoader
    from src.eval.baselines import run_baseline_evaluation
    from src.eval.retrieval_metrics import print_metrics

    # Load Home Depot data
    print("Loading Home Depot dataset...")
    loader = HomeDepotLoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(max_queries=max_queries)
    if max_products and len(products) > max_products:
        products = products[:max_products]
    print(f"Loaded {len(products)} products, {len(queries)} queries")

    # Run baseline evaluation
    print("Running Home Depot baseline evaluation...")
    results = run_baseline_evaluation(
        products=products,
        queries=queries,
        collection_name=collection_name,
        recreate=True,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("HOME DEPOT BASELINE RESULTS")
    print("=" * 60)

    for model_name, metrics in results.items():
        print(f"\n{model_name.upper()}:")
        print(f"  nDCG@10:    {metrics.get('ndcg@10', 0):.4f}")
        print(f"  MRR@10:     {metrics.get('mrr@10', 0):.4f}")
        print(f"  Recall@100: {metrics.get('recall@100', 0):.4f}")

    return results


# =============================================================================
# MS MARCO Generalization Evaluation
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 4,  # 4 hours for large corpus
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_msmarco(
    model_path: str = "splade_standard/final",
    max_corpus: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "msmarco_eval",
) -> Dict:
    """
    Evaluate fine-tuned SPLADE model on MS MARCO dataset for generalization testing.

    Tests cross-domain transfer: Amazon e-commerce (training) -> Web search (MS MARCO).

    Args:
        model_path: Path to model in checkpoint volume
        max_corpus: Max passages to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with evaluation metrics
    """
    import os
    import sys

    sys.path.insert(0, "/root")

    from sentence_transformers import SparseEncoder
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm

    from src.data.msmarco_loader import MSMARCOLoader
    from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics
    from src.qdrant.index import sparse_embedding_to_qdrant

    # Load fine-tuned model
    full_model_path = f"/checkpoints/{model_path}"
    print(f"Loading fine-tuned model from {full_model_path}...")
    model = SparseEncoder(full_model_path)

    # Load MS MARCO data
    print("Loading MS MARCO dataset...")
    loader = MSMARCOLoader(cache_dir="/datasets/cache")
    queries, passages = loader.load_for_evaluation(
        max_queries=max_queries,
        max_corpus=max_corpus,
    )
    print(f"Loaded {len(passages)} passages, {len(queries)} queries from MS MARCO")

    # Connect to Qdrant
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    # Create collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={},
        sparse_vectors_config={"text": models.SparseVectorParams()},
    )
    print(f"Created collection: {collection_name}")

    # Index passages
    print("Encoding and indexing passages...")
    batch_size = 32
    for i in tqdm(range(0, len(passages), batch_size), desc="Indexing"):
        batch = passages[i : i + batch_size]
        texts = [p["text"] for p in batch]

        embeddings = model.encode(texts, prompt_name="document")

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector={"text": sparse_vector},
                    payload={"product_id": doc["product_id"], "text": doc["text"][:500]},
                )
            )

        client.upsert(collection_name=collection_name, points=points)

    print(f"Indexed {len(passages)} passages")

    # Evaluate
    print("Running evaluation...")
    retrieved_results = []
    k_values = [10, 50, 100]
    max_k = max(k_values)

    for q in tqdm(queries, desc="Evaluating"):
        emb = model.encode([q["query"]], prompt_name="document")[0]
        sparse_vector = sparse_embedding_to_qdrant(emb)

        results = client.query_points(
            collection_name=collection_name,
            query=sparse_vector,
            using="text",
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append(
            {
                "query_id": q["query_id"],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )

    print_metrics(metrics, "MS MARCO Generalization Results (Fine-tuned SPLADE)")
    return metrics


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 4,  # 4 hours for large corpus
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_msmarco_baselines(
    max_corpus: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "msmarco_baselines",
) -> Dict[str, Dict]:
    """
    Evaluate BM25 and SPLADE baselines on MS MARCO dataset.

    Args:
        max_corpus: Max passages to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict mapping model_name -> metrics
    """
    import sys

    sys.path.insert(0, "/root")

    from src.data.msmarco_loader import MSMARCOLoader
    from src.eval.baselines import run_baseline_evaluation

    # Load MS MARCO data
    print("Loading MS MARCO dataset...")
    loader = MSMARCOLoader(cache_dir="/datasets/cache")
    queries, passages = loader.load_for_evaluation(
        max_queries=max_queries,
        max_corpus=max_corpus,
    )
    print(f"Loaded {len(passages)} passages, {len(queries)} queries")

    # Run baseline evaluation
    print("Running MS MARCO baseline evaluation...")
    results = run_baseline_evaluation(
        products=passages,  # Using 'products' param name for compatibility
        queries=queries,
        collection_name=collection_name,
        recreate=True,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("MS MARCO BASELINE RESULTS")
    print("=" * 60)

    for model_name, metrics in results.items():
        print(f"\n{model_name.upper()}:")
        print(f"  nDCG@10:    {metrics.get('ndcg@10', 0):.4f}")
        print(f"  MRR@10:     {metrics.get('mrr@10', 0):.4f}")
        print(f"  Recall@100: {metrics.get('recall@100', 0):.4f}")

    return results


# =============================================================================
# RexBERT Evaluation (E-Commerce Specialized Dense Encoder)
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={"/datasets": dataset_volume},
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_rexbert(
    dataset: str = "esci",
    model_name: str = "thebajajra/RexBERT-base",
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "rexbert_eval",
) -> Dict:
    """
    Evaluate RexBERT e-commerce specialized dense encoder.

    RexBERT is trained on 2.3T+ e-commerce tokens and optimized for product search.
    Uses [CLS] token pooling for embeddings.

    Available models:
    - thebajajra/RexBERT-micro (17M params)
    - thebajajra/RexBERT-mini (68M params)
    - thebajajra/RexBERT-base (150M params)
    - thebajajra/RexBERT-large (400M params)

    Args:
        dataset: "esci", "wands", or "homedepot"
        model_name: HuggingFace model name for RexBERT variant
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with evaluation metrics
    """
    import os
    import sys

    sys.path.insert(0, "/root")

    import torch
    from transformers import AutoTokenizer, AutoModel
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm
    import numpy as np

    from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics

    # Load model and tokenizer
    print(f"Loading RexBERT model: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    # Move to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    print(f"Model loaded on {device}")

    # Load dataset
    print(f"Loading {dataset} dataset...")
    if dataset == "esci":
        from src.data.esci_loader import ESCILoader

        loader = ESCILoader(cache_dir="/datasets/cache")
        queries, products = loader.load_for_evaluation(split="test", max_queries=max_queries)
    elif dataset == "wands":
        from src.data.wands_loader import WANDSLoader

        loader = WANDSLoader(cache_dir="/datasets/cache")
        queries, products = loader.load_for_evaluation(split="test", max_queries=max_queries)
    elif dataset == "homedepot":
        from src.data.homedepot_loader import HomeDepotLoader

        loader = HomeDepotLoader(cache_dir="/datasets/cache")
        queries, products = loader.load_for_evaluation(max_queries=max_queries)
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    if max_products and len(products) > max_products:
        products = products[:max_products]
    print(f"Loaded {len(products)} products, {len(queries)} queries")

    # Helper function to get embeddings
    def get_embeddings(texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Get [CLS] token embeddings for texts."""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            inputs = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(device)

            with torch.no_grad():
                outputs = model(**inputs)
                # Use [CLS] token embedding (first token)
                embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                all_embeddings.append(embeddings)

        return np.vstack(all_embeddings)

    # Get embedding dimension
    sample_emb = get_embeddings(["test"])
    embedding_dim = sample_emb.shape[1]
    print(f"Embedding dimension: {embedding_dim}")

    # Connect to Qdrant
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    # Create collection
    full_collection_name = f"{collection_name}_{dataset}"
    try:
        client.delete_collection(full_collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=full_collection_name,
        vectors_config=models.VectorParams(
            size=embedding_dim,
            distance=models.Distance.COSINE,
        ),
    )
    print(f"Created collection: {full_collection_name}")

    # Index products
    print("Encoding and indexing products...")
    batch_size = 32
    for i in tqdm(range(0, len(products), batch_size), desc="Indexing"):
        batch = products[i : i + batch_size]
        texts = [p["text"] for p in batch]

        embeddings = get_embeddings(texts, batch_size=batch_size)

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector=emb.tolist(),
                    payload={"product_id": doc["product_id"], "text": doc["text"]},
                )
            )

        client.upsert(collection_name=full_collection_name, points=points)

    print(f"Indexed {len(products)} products")

    # Evaluate
    print("Running evaluation...")
    retrieved_results = []
    k_values = [10, 50, 100]
    max_k = max(k_values)

    # Batch query encoding for efficiency
    query_texts = [q["query"] for q in queries]
    query_embeddings = get_embeddings(query_texts, batch_size=32)

    for i, q in enumerate(tqdm(queries, desc="Evaluating")):
        query_vector = query_embeddings[i].tolist()

        results = client.query_points(
            collection_name=full_collection_name,
            query=query_vector,
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append(
            {
                "query_id": q["query_id"],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )

    model_short = model_name.split("/")[-1]
    print_metrics(metrics, f"RexBERT ({model_short}) on {dataset.upper()}")
    return metrics


# =============================================================================
# Fine-tuned Model Evaluation
# =============================================================================


@app.function(
    image=image,
    gpu=gpu_config,
    volumes={
        "/checkpoints": checkpoint_volume,
        "/datasets": dataset_volume,
    },
    timeout=3600 * 2,
    secrets=[modal.Secret.from_name("qdrant")],
)
def evaluate_finetuned(
    model_path: str = "baseline/final",
    max_products: int = 10000,
    max_queries: int = 1000,
    collection_name: str = "esci_finetuned",
) -> Dict:
    """
    Evaluate fine-tuned SPLADE model.

    Args:
        model_path: Path to model in checkpoint volume (e.g., "baseline/final")
        max_products: Max products to index
        max_queries: Max queries to evaluate
        collection_name: Qdrant collection name

    Returns:
        Dict with evaluation metrics
    """
    import os
    import sys

    sys.path.insert(0, "/root")

    from sentence_transformers import SparseEncoder
    from qdrant_client import QdrantClient, models
    from tqdm import tqdm

    from src.data.esci_loader import ESCILoader
    from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics
    from src.qdrant.index import sparse_embedding_to_qdrant

    # Load fine-tuned model
    full_model_path = f"/checkpoints/{model_path}"
    print(f"Loading fine-tuned model from {full_model_path}...")
    model = SparseEncoder(full_model_path)
    print(f"Model loaded successfully")

    # Load data - use test split for both queries AND products to match relevance labels
    print("Loading ESCI dataset...")
    loader = ESCILoader(cache_dir="/datasets/cache")
    queries, products = loader.load_for_evaluation(split="test", max_queries=max_queries)
    if max_products and len(products) > max_products:
        products = products[:max_products]
    print(f"Loaded {len(products)} products, {len(queries)} queries from test split")

    # Connect to Qdrant
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    # Create collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config={},
        sparse_vectors_config={"text": models.SparseVectorParams()},
    )
    print(f"Created collection: {collection_name}")

    # Index products
    print("Encoding and indexing products...")
    batch_size = 32
    for i in tqdm(range(0, len(products), batch_size), desc="Indexing"):
        batch = products[i : i + batch_size]
        texts = [p["text"] for p in batch]

        # Encode with fine-tuned model (document mode)
        embeddings = model.encode(texts, prompt_name="document")

        points = []
        for j, (doc, emb) in enumerate(zip(batch, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)
            points.append(
                models.PointStruct(
                    id=i + j,
                    vector={"text": sparse_vector},
                    payload={"product_id": doc["product_id"], "text": doc["text"]},
                )
            )

        client.upsert(collection_name=collection_name, points=points)

    print(f"Indexed {len(products)} products")

    # Evaluate
    print("Running evaluation...")
    retrieved_results = []
    k_values = [10, 50, 100]
    max_k = max(k_values)

    for q in tqdm(queries, desc="Evaluating"):
        # Encode query using document encoder (bypass static query embedding)
        emb = model.encode([q["query"]], prompt_name="document")[0]
        sparse_vector = sparse_embedding_to_qdrant(emb)

        results = client.query_points(
            collection_name=collection_name,
            query=sparse_vector,
            using="text",
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]
        retrieved_results.append(
            {
                "query_id": q["query_id"],
                "retrieved_ids": retrieved_ids,
            }
        )

    metrics = evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )

    print_metrics(metrics, "Fine-tuned SPLADE Results")
    return metrics


# =============================================================================
# Entry Points
# =============================================================================


@app.local_entrypoint()
def main(
    config_path: str = "configs/baseline.yaml",
    mode: str = "train",
    model_path: str = "baseline/final",
):
    """
    Main entry point for Modal training.

    Args:
        config_path: Path to YAML config file
        mode: "train", "ance", "sweep", "baselines", "dense", or "eval"
        model_path: Path to fine-tuned model for eval mode
    """
    import yaml

    print(f"Mode: {mode}")

    if mode == "baselines":
        # Run baseline evaluation (no config needed)
        print("Running baseline evaluation with FastEmbed (BM25 + SPLADE)...")
        results = evaluate_baselines.remote()
        print(f"\nBaseline results: {results}")
        return

    if mode == "dense":
        # Run dense baseline evaluation
        print("Running dense baseline evaluation (all-MiniLM-L6-v2)...")
        results = evaluate_dense.remote()
        print(f"\nDense baseline results: {results}")
        return

    if mode == "wands":
        # Run WANDS generalization test with fine-tuned model
        print(f"Testing generalization on WANDS dataset with model: {model_path}")
        results = evaluate_wands.remote(model_path=model_path)
        print(f"\nWANDS generalization results: {results}")
        return

    if mode == "wands-baselines":
        # Run WANDS baselines
        print("Running WANDS baseline evaluation (BM25 + SPLADE)...")
        results = evaluate_wands_baselines.remote()
        print(f"\nWANDS baseline results: {results}")
        return

    if mode == "homedepot":
        # Run Home Depot generalization test with fine-tuned model
        print(f"Testing generalization on Home Depot dataset with model: {model_path}")
        results = evaluate_homedepot.remote(model_path=model_path)
        print(f"\nHome Depot generalization results: {results}")
        return

    if mode == "homedepot-baselines":
        # Run Home Depot baselines
        print("Running Home Depot baseline evaluation (BM25 + SPLADE)...")
        results = evaluate_homedepot_baselines.remote()
        print(f"\nHome Depot baseline results: {results}")
        return

    if mode == "msmarco":
        # Run MS MARCO generalization test with fine-tuned model
        print(f"Testing generalization on MS MARCO dataset with model: {model_path}")
        results = evaluate_msmarco.remote(model_path=model_path)
        print(f"\nMS MARCO generalization results: {results}")
        return

    if mode == "msmarco-baselines":
        # Run MS MARCO baselines
        print("Running MS MARCO baseline evaluation (BM25 + SPLADE)...")
        results = evaluate_msmarco_baselines.remote()
        print(f"\nMS MARCO baseline results: {results}")
        return

    if mode == "rexbert-esci":
        # Run RexBERT on ESCI
        print("Running RexBERT evaluation on ESCI dataset...")
        results = evaluate_rexbert.remote(dataset="esci")
        print(f"\nRexBERT ESCI results: {results}")
        return

    if mode == "rexbert-wands":
        # Run RexBERT on WANDS
        print("Running RexBERT evaluation on WANDS dataset...")
        results = evaluate_rexbert.remote(dataset="wands")
        print(f"\nRexBERT WANDS results: {results}")
        return

    if mode == "rexbert-homedepot":
        # Run RexBERT on Home Depot
        print("Running RexBERT evaluation on Home Depot dataset...")
        results = evaluate_rexbert.remote(dataset="homedepot")
        print(f"\nRexBERT Home Depot results: {results}")
        return

    # ==========================================================================
    # SCALED-UP EVALUATIONS (50K+ products, 5K+ queries)
    # ==========================================================================

    if mode == "baselines-large":
        # Run baseline evaluation at scale
        print("Running LARGE baseline evaluation (50K products, 5K queries)...")
        results = evaluate_baselines.remote(
            max_products=50000,
            max_queries=5000,
            collection_name="esci_baselines_large",
        )
        print(f"\nLarge baseline results: {results}")
        return

    if mode == "eval-large":
        # Evaluate fine-tuned model at scale
        print(f"Evaluating fine-tuned model at LARGE scale: {model_path}")
        results = evaluate_finetuned.remote(
            model_path=model_path,
            max_products=50000,
            max_queries=5000,
            collection_name="esci_finetuned_large",
        )
        print(f"\nLarge fine-tuned results: {results}")
        return

    if mode == "wands-large":
        # Run WANDS at full scale
        print(f"Testing WANDS at LARGE scale with model: {model_path}")
        results = evaluate_wands.remote(
            model_path=model_path,
            max_products=50000,
            max_queries=5000,
            collection_name="wands_eval_large",
        )
        print(f"\nLarge WANDS results: {results}")
        return

    if mode == "wands-baselines-large":
        # Run WANDS baselines at scale
        print("Running LARGE WANDS baseline evaluation...")
        results = evaluate_wands_baselines.remote(
            max_products=50000,
            max_queries=5000,
            collection_name="wands_baselines_large",
        )
        print(f"\nLarge WANDS baseline results: {results}")
        return

    if mode == "homedepot-large":
        # Run Home Depot at full scale (uses all available data)
        print(f"Testing Home Depot at LARGE scale with model: {model_path}")
        results = evaluate_homedepot.remote(
            model_path=model_path,
            max_products=50000,
            max_queries=5000,
            collection_name="homedepot_eval_large",
        )
        print(f"\nLarge Home Depot results: {results}")
        return

    if mode == "homedepot-baselines-large":
        # Run Home Depot baselines at scale
        print("Running LARGE Home Depot baseline evaluation...")
        results = evaluate_homedepot_baselines.remote(
            max_products=50000,
            max_queries=5000,
            collection_name="homedepot_baselines_large",
        )
        print(f"\nLarge Home Depot baseline results: {results}")
        return

    # ==========================================================================
    # XLARGE EVALUATIONS (100K+ products, 10K+ queries)
    # ==========================================================================

    if mode == "baselines-xlarge":
        # Run baseline evaluation at XL scale
        print("Running XLARGE baseline evaluation (100K products, 10K queries)...")
        results = evaluate_baselines.remote(
            max_products=100000,
            max_queries=10000,
            collection_name="esci_baselines_xlarge",
        )
        print(f"\nXLarge baseline results: {results}")
        return

    if mode == "eval-xlarge":
        # Evaluate fine-tuned model at XL scale
        print(f"Evaluating fine-tuned model at XLARGE scale: {model_path}")
        results = evaluate_finetuned.remote(
            model_path=model_path,
            max_products=100000,
            max_queries=10000,
            collection_name="esci_finetuned_xlarge",
        )
        print(f"\nXLarge fine-tuned results: {results}")
        return

    # ==========================================================================
    # XXL EVALUATIONS (200K products, 20K queries) - ~4-5 hours
    # ==========================================================================

    if mode == "baselines-xxl":
        # Run baseline evaluation at XXL scale using spawn (async)
        print("Running XXL baseline evaluation (200K products, 20K queries)...")
        print("Using spawn() - check Modal dashboard for results")
        fc = evaluate_baselines.spawn(
            max_products=200000,
            max_queries=20000,
            collection_name="esci_baselines_xxl",
        )
        print(f"\nFunction spawned! Function call ID: {fc.object_id}")
        print("Monitor at Modal dashboard - results will appear when complete")
        return

    if mode == "eval-xxl":
        # Evaluate fine-tuned model at XXL scale
        print(f"Evaluating fine-tuned model at XXL scale: {model_path}")
        results = evaluate_finetuned.remote(
            model_path=model_path,
            max_products=200000,
            max_queries=20000,
            collection_name="esci_finetuned_xxl",
        )
        print(f"\nXXL fine-tuned results: {results}")
        return

    # ==========================================================================
    # FULL DATASET EVALUATIONS (no limits) - WARNING: 15+ hours
    # ==========================================================================

    if mode == "baselines-full":
        # Run baseline evaluation on full dataset using spawn (fire-and-forget)
        print("Running FULL baseline evaluation (all products, all queries)...")
        print("WARNING: This will take 15+ hours!")
        print("Using spawn() for long-running job - monitor on Modal dashboard")
        fc = evaluate_baselines.spawn(
            max_products=None,
            max_queries=None,
            collection_name="esci_baselines_full",
        )
        print(f"\nFunction spawned! ID: {fc.object_id}")
        print("Results will be logged to Modal - check dashboard when complete")
        return

    if mode == "eval-full":
        # Evaluate fine-tuned model on full dataset
        print(f"Evaluating fine-tuned model on FULL dataset: {model_path}")
        print("WARNING: This will take 15+ hours!")
        results = evaluate_finetuned.remote(
            model_path=model_path,
            max_products=None,
            max_queries=None,
            collection_name="esci_finetuned_full",
        )
        print(f"\nFull fine-tuned results: {results}")
        return

    if mode == "eval":
        # Evaluate fine-tuned model
        print(f"Evaluating fine-tuned model: {model_path}")
        results = evaluate_finetuned.remote(model_path=model_path)
        print(f"\nFine-tuned model results: {results}")
        return

    # Load config for other modes
    with open(config_path) as f:
        config = yaml.safe_load(f)

    print(f"Loaded config from {config_path}")

    if mode == "train":
        result = train_sparse_encoder.remote(config)
        print(f"Training complete. Model saved to: {result}")

    elif mode == "train-multi":
        # Multi-domain training (ESCI + WANDS + Home Depot)
        print("Starting multi-domain training...")
        result = train_multidomain.remote(config)
        print(f"Multi-domain training complete. Model saved to: {result}")

    elif mode == "ance":
        result = train_ance_loop.remote(
            config,
            num_iterations=config.get("ance_iterations", 3),
        )
        print(f"ANCE training complete. Model saved to: {result}")

    elif mode == "sweep":
        run_sweep()

    else:
        print(f"Unknown mode: {mode}")
        print("Available modes:")
        print("  train           - Train SPLADE model on ESCI")
        print("  train-multi     - Train on ESCI + WANDS + Home Depot (generalized)")
        print("  ance            - Train with ANCE hard negative mining")
        print("  sweep           - Hyperparameter sweep")
        print("  baselines       - Evaluate BM25 + SPLADE on ESCI")
        print("  dense           - Evaluate dense embeddings on ESCI")
        print("  eval            - Evaluate fine-tuned model on ESCI")
        print("  wands           - Test fine-tuned model on WANDS (Wayfair)")
        print("  wands-baselines - Evaluate BM25 + SPLADE on WANDS")
        print("  homedepot       - Test fine-tuned model on Home Depot")
        print("  homedepot-baselines - Evaluate BM25 + SPLADE on Home Depot")
        print("  msmarco         - Test fine-tuned model on MS MARCO")
        print("  msmarco-baselines - Evaluate BM25 + SPLADE on MS MARCO")
        print("  rexbert-esci    - Evaluate RexBERT on ESCI")
        print("  rexbert-wands   - Evaluate RexBERT on WANDS")
        print("  rexbert-homedepot - Evaluate RexBERT on Home Depot")


def run_sweep():
    """Run hyperparameter sweep with parallel trials."""
    sweep_configs = [
        {
            "learning_rate": 1e-5,
            "query_regularizer_weight": 1e-5,
            "document_regularizer_weight": 1e-5,
        },
        {
            "learning_rate": 2e-5,
            "query_regularizer_weight": 5e-5,
            "document_regularizer_weight": 3e-5,
        },
        {
            "learning_rate": 5e-5,
            "query_regularizer_weight": 1e-4,
            "document_regularizer_weight": 5e-5,
        },
        {
            "learning_rate": 2e-5,
            "query_regularizer_weight": 1e-4,
            "document_regularizer_weight": 1e-4,
        },
    ]

    # Add base config to all
    base_config = {
        "base_model": "distilbert/distilbert-base-uncased",
        "architecture": "inference_free_splade",
        "batch_size": 32,
        "max_samples": 5000,
        "num_epochs": 1,
    }

    for i, config in enumerate(sweep_configs):
        config.update(base_config)

    # Run in parallel
    print(f"Running {len(sweep_configs)} sweep trials in parallel...")
    results = list(
        train_sweep_trial.starmap([(config, i) for i, config in enumerate(sweep_configs)])
    )

    # Print results sorted by nDCG@10
    print("\n" + "=" * 60)
    print("Sweep Results (sorted by nDCG@10)")
    print("=" * 60)

    # Sort by nDCG@10 descending
    sorted_results = sorted(
        results,
        key=lambda x: x.get("metrics", {}).get("ndcg@10", 0),
        reverse=True,
    )

    for result in sorted_results:
        metrics = result.get("metrics", {})
        config = result.get("config", {})
        print(f"\nTrial {result['trial_id']}:")
        print(f"  nDCG@10:  {metrics.get('ndcg@10', 0):.4f}")
        print(f"  MRR@10:   {metrics.get('mrr@10', 0):.4f}")
        print(f"  Recall@10: {metrics.get('recall@10', 0):.4f}")
        print(f"  Config: lr={config.get('learning_rate')}, "
              f"q_reg={config.get('query_regularizer_weight')}, "
              f"d_reg={config.get('document_regularizer_weight')}")

    # Print best trial
    if sorted_results:
        best = sorted_results[0]
        print("\n" + "=" * 60)
        print(f"BEST TRIAL: {best['trial_id']} with nDCG@10 = {best.get('metrics', {}).get('ndcg@10', 0):.4f}")
        print(f"Model path: {best.get('model_path')}")
        print("=" * 60)


if __name__ == "__main__":
    main()
