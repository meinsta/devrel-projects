# Fine-Tuning SPLADE for E-Commerce Search

[![Modal](https://img.shields.io/badge/Modal-GPU%20Training-blue)](https://modal.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Sparse%20Vectors-red)](https://qdrant.tech)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Models-yellow)](https://huggingface.co/thierrydamiba)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

Train domain-specific SPLADE models that beat BM25 by **28%** on e-commerce search, using Modal for GPU training and Qdrant for sparse vector storage.

## Results

### Amazon ESCI (In-Domain)

| Model | nDCG@10 | vs BM25 |
|-------|---------|---------|
| BM25 (baseline) | 0.305 | — |
| SPLADE (off-the-shelf) | 0.326 | +7% |
| **SPLADE (fine-tuned)** | **0.389** | **+28%** |

### Cross-Domain Generalization

| Dataset | BM25 | SPLADE (fine-tuned) | Improvement |
|---------|------|---------------------|-------------|
| WANDS (Wayfair) | 0.329 | 0.355 | +8% |
| Home Depot | 0.349 | 0.384 | +10% |

*Multi-domain training improves generalization further: WANDS 0.366 (+11%), Home Depot 0.410 (+17%)*

## Pre-trained Models

Use our fine-tuned models directly from HuggingFace:

| Model | Description | Link |
|-------|-------------|------|
| **splade-ecommerce-esci** | Best in-domain performance (+28% vs BM25) | [🤗 HuggingFace](https://huggingface.co/thierrydamiba/splade-ecommerce-esci) |
| **splade-ecommerce-multidomain** | Better cross-domain generalization (+11-17% vs BM25) | [🤗 HuggingFace](https://huggingface.co/thierrydamiba/splade-ecommerce-multidomain) |

```python
from sentence_transformers import SparseEncoder

# Load pre-trained model
model = SparseEncoder("thierrydamiba/splade-ecommerce-esci")

# Encode queries and products
embeddings = model.encode(["wireless headphones", "bluetooth speaker"])
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Modal](https://modal.com) account (free tier works)
- [Qdrant Cloud](https://cloud.qdrant.io) account (optional, for hosted deployment)

### Installation

```bash
git clone https://github.com/qdrant/qdrant-modal-embed
cd qdrant-modal-embed

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### Train a Model

```bash
# Train SPLADE on Amazon ESCI dataset (100K samples, ~6 min on A100)
uv run modal run modal_app.py --mode train --config-path configs/splade_standard.yaml

# Train on multiple e-commerce datasets for better generalization
uv run modal run modal_app.py --mode train-multi --config-path configs/splade_multidomain.yaml
```

### Evaluate

```bash
# Evaluate on ESCI test set
uv run modal run modal_app.py --mode eval --model-path splade_standard/final

# Cross-domain evaluation
uv run modal run modal_app.py --mode wands --model-path splade_standard/final
uv run modal run modal_app.py --mode homedepot --model-path splade_standard/final
```

### Search with Qdrant

```python
from qdrant_client import QdrantClient, models
from sentence_transformers import SparseEncoder

# Load fine-tuned model from HuggingFace
model = SparseEncoder("thierrydamiba/splade-ecommerce-esci")

# Connect to Qdrant
client = QdrantClient(url="<your-qdrant-url>", api_key="<your-api-key>")

# Search
def search_products(query: str, limit=10):
    embedding = model.encode(query)
    
    results = client.query_points(
        collection_name="ecommerce_splade",
        query=models.SparseVector(
            indices=embedding["indices"].tolist(),
            values=embedding["values"].tolist(),
        ),
        using="text",
        limit=limit,
    )
    
    return [{"id": r.id, "score": r.score, "title": r.payload["title"]} 
            for r in results.points]

# Example
results = search_products("wireless noise canceling headphones")
for r in results:
    print(f"{r['score']:.3f} - {r['title']}")
```

## Project Structure

```
qdrant-modal-embed/
├── modal_app.py          # Main Modal application (training + evaluation)
├── configs/
│   ├── splade_standard.yaml      # Single-domain training config
│   └── splade_multidomain.yaml   # Multi-domain training config
├── src/
│   ├── data/             # Dataset loaders (ESCI, WANDS, Home Depot, MS MARCO)
│   ├── eval/             # Evaluation metrics and baselines
│   ├── training/         # SPLADE model creation
│   └── qdrant/           # Qdrant indexing utilities
└── pyproject.toml
```

## Datasets

This project uses the following datasets:

| Dataset | Domain | Size | Source |
|---------|--------|------|--------|
| [Amazon ESCI](https://github.com/amazon-science/esci-data) | General e-commerce | 1.2M pairs | KDD Cup 2022 |
| [WANDS](https://github.com/wayfair/WANDS) | Home goods (Wayfair) | 480K pairs | Wayfair |
| [Home Depot](https://www.kaggle.com/c/home-depot-product-search-relevance) | Home improvement | 240K pairs | Kaggle |
| [MS MARCO](https://microsoft.github.io/msmarco/) | Web search | 8.8M passages | Microsoft |

## Key Findings

1. **Domain-specific fine-tuning matters**: +28% over BM25, +19% over off-the-shelf SPLADE
2. **Specialization vs generalization trade-off**: Single-domain training hurts cross-domain performance
3. **Multi-domain training balances both**: Modest in-domain loss (-5%) for better generalization (+8-17%)
4. **Inference-free SPLADE doesn't work for e-commerce**: Context matters for ambiguous queries

## Configuration

### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `batch_size` | 32 | Training batch size |
| `learning_rate` | 2e-5 | Learning rate |
| `num_epochs` | 1 | Number of training epochs |
| `max_samples` | 100000 | Max training samples (null for full dataset) |
| `query_regularizer_weight` | 5e-5 | Query sparsity regularization |
| `document_regularizer_weight` | 3e-5 | Document sparsity regularization |

### Qdrant Configuration

For production deployments, configure sparse vectors with on-disk storage:

```python
client.create_collection(
    collection_name="ecommerce_splade",
    vectors_config={},
    sparse_vectors_config={
        "text": models.SparseVectorParams(
            index=models.SparseIndexParams(on_disk=True)
        )
    },
)
```

## Hybrid Search

Combine sparse and dense vectors for best results:

```python
# Hybrid search with RRF fusion
results = client.query_points(
    collection_name="products",
    prefetch=[
        models.Prefetch(query=sparse_vector, using="sparse", limit=100),
        models.Prefetch(query=dense_vector, using="dense", limit=100),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=10,
)
```

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Sentence Transformers](https://sbert.net/) for the SparseEncoder implementation
- [Modal](https://modal.com) for serverless GPU infrastructure
- [Qdrant](https://qdrant.tech) for native sparse vector support
- Amazon, Wayfair, and Microsoft for the open datasets
