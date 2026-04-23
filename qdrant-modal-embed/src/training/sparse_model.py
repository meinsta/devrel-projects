"""Sparse Encoder Model Setup using Sentence Transformers v5"""

import logging
from pathlib import Path
from typing import Literal, Optional, Union

from sentence_transformers import SparseEncoder
from sentence_transformers.models import Router
from sentence_transformers.sparse_encoder.models import (
    MLMTransformer,
    SpladePooling,
    SparseStaticEmbedding,
)

logger = logging.getLogger(__name__)


def create_sparse_encoder(
    base_model: str = "distilbert/distilbert-base-uncased",
    architecture: Literal["splade", "inference_free_splade"] = "inference_free_splade",
    pooling_strategy: Literal["max", "sum"] = "max",
    device: Optional[str] = None,
) -> SparseEncoder:
    """
    Create a SparseEncoder for fine-tuning on e-commerce search.

    Args:
        base_model: HuggingFace model name or local path.
            Pretrained SPLADE options:
            - "naver/splade-cocondenser-ensembledistil" (best quality)
            - "naver/splade-v3" (latest)
            - "prithivida/Splade_PP_en_v1" (good balance)

            Base models for training from scratch:
            - "distilbert/distilbert-base-uncased" (fast, good)
            - "bert-base-uncased" (standard)
            - "answerdotai/ModernBERT-base" (2025 state-of-art)

        architecture: Model architecture type.
            - "splade": Standard SPLADE with MLM head + max pooling.
              Both queries and documents use the full transformer.
              Best quality but slower inference.

            - "inference_free_splade": Asymmetric architecture.
              Queries use SparseStaticEmbedding (instant, vocabulary-based).
              Documents use full SPLADE (MLM + pooling).
              Best for production with many queries.

        pooling_strategy: How to aggregate token-level sparse weights.
            - "max": Take max activation per vocabulary term (default for SPLADE)
            - "sum": Sum activations (more aggressive expansion)

        device: Device to run on ("cuda", "cpu", or None for auto)

    Returns:
        SparseEncoder ready for training or inference
    """
    # Check if loading pretrained SPLADE
    if "splade" in base_model.lower() and architecture == "splade":
        logger.info(f"Loading pretrained SPLADE model: {base_model}")
        return SparseEncoder(base_model, device=device)

    logger.info(f"Creating {architecture} model from {base_model}")

    if architecture == "splade":
        # Standard SPLADE: MLM transformer + SPLADE pooling
        mlm = MLMTransformer(base_model)
        pooling = SpladePooling(pooling_strategy=pooling_strategy)
        model = SparseEncoder(modules=[mlm, pooling], device=device)

    elif architecture == "inference_free_splade":
        # Inference-free SPLADE: Fast queries, full SPLADE for documents
        # This is the recommended architecture for production use cases
        mlm = MLMTransformer(base_model)
        router = Router.for_query_document(
            query_modules=[
                SparseStaticEmbedding(
                    tokenizer=mlm.tokenizer,
                    frozen=False,  # Train the static embeddings
                )
            ],
            document_modules=[
                mlm,
                SpladePooling(pooling_strategy=pooling_strategy),
            ],
        )
        model = SparseEncoder(
            modules=[router],
            similarity_fn_name="dot",  # Sparse vectors use dot product
            device=device,
        )

    else:
        raise ValueError(f"Unknown architecture: {architecture}")

    logger.info(f"Created SparseEncoder with {architecture} architecture")
    return model


def load_sparse_encoder(
    model_path: Union[str, Path],
    device: Optional[str] = None,
) -> SparseEncoder:
    """
    Load a trained SparseEncoder from disk.

    Args:
        model_path: Path to saved model directory
        device: Device to load model on

    Returns:
        Loaded SparseEncoder
    """
    logger.info(f"Loading SparseEncoder from {model_path}")
    return SparseEncoder(str(model_path), device=device)


def save_sparse_encoder(
    model: SparseEncoder,
    output_path: Union[str, Path],
) -> Path:
    """
    Save a SparseEncoder to disk.

    Args:
        model: SparseEncoder to save
        output_path: Directory to save to

    Returns:
        Path where model was saved
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_path))
    logger.info(f"Saved SparseEncoder to {output_path}")
    return output_path


def get_vocab_size(model: SparseEncoder) -> int:
    """
    Get the vocabulary size of the sparse encoder.

    SPLADE outputs sparse vectors with dimension = vocab size.
    Typically ~30,522 for BERT-based models.

    Args:
        model: SparseEncoder

    Returns:
        Vocabulary size (sparse vector dimension)
    """
    # Try to get tokenizer from model modules
    for module in model.modules():
        if hasattr(module, "tokenizer"):
            return module.tokenizer.vocab_size
        if hasattr(module, "auto_model") and hasattr(module.auto_model, "config"):
            return module.auto_model.config.vocab_size

    # Default BERT vocab size
    return 30522
