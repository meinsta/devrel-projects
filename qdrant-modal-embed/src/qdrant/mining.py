"""Hard Negative Mining with Qdrant Sparse Vector Search"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set

from qdrant_client import QdrantClient, models
from sentence_transformers import SparseEncoder
from tqdm import tqdm

from src.qdrant.index import sparse_embedding_to_qdrant

logger = logging.getLogger(__name__)


class SparseQdrantMiner:
    """
    Mine hard negatives using Qdrant sparse vector search.

    Hard negatives are documents that:
    1. Rank highly for a query (appear in top-K results)
    2. Are NOT relevant (Irrelevant label in ESCI)

    These "confusable" documents are critical for contrastive learning
    as they force the model to learn fine-grained distinctions.
    """

    def __init__(
        self,
        client: QdrantClient,
        model: SparseEncoder,
        collection_name: str,
        vector_name: str = "text",
    ):
        """
        Initialize the sparse miner.

        Args:
            client: Qdrant client
            model: SparseEncoder for query encoding
            collection_name: Collection to mine from
            vector_name: Name of sparse vector field
        """
        self.client = client
        self.model = model
        self.collection_name = collection_name
        self.vector_name = vector_name

    def mine_hard_negatives(
        self,
        queries: List[Dict],
        top_k: int = 20,
        filter_positives: bool = True,
        max_negatives_per_query: int = 5,
        num_workers: int = 8,
    ) -> Dict[str, List[str]]:
        """
        Mine hard negatives for a batch of queries.

        Args:
            queries: List of dicts with:
                - "query": str (query text)
                - "query_id": str (optional query identifier)
                - "positive_ids": Set[str] (product IDs to exclude)
            top_k: Number of top results to consider
            filter_positives: Remove known positives from results
            max_negatives_per_query: Max hard negatives to return per query
            num_workers: Parallel workers for search

        Returns:
            Dict mapping query_text -> list of hard negative product texts
        """
        logger.info(f"Mining hard negatives for {len(queries)} queries")

        query_texts = [q["query"] for q in queries]
        positive_ids_list = [q.get("positive_ids", set()) for q in queries]

        # Encode all queries
        logger.info("Encoding queries...")
        query_embeddings = self.model.encode(
            query_texts,
            convert_to_tensor=True,
            show_progress_bar=True,
        )

        hard_negatives: Dict[str, List[str]] = {}

        def search_single(args):
            """Search for a single query."""
            idx, query_text, emb, positive_ids = args

            try:
                sparse_vector = sparse_embedding_to_qdrant(emb)

                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=sparse_vector,
                    using=self.vector_name,
                    limit=top_k,
                    with_payload=True,
                )

                # Extract hard negatives
                hard_negs = []
                for point in results.points:
                    payload = point.payload or {}
                    product_id = payload.get("product_id", "")
                    product_text = payload.get("text", "")

                    # Skip if this is a known positive
                    if filter_positives and product_id in positive_ids:
                        continue

                    hard_negs.append(product_text)

                    if len(hard_negs) >= max_negatives_per_query:
                        break

                return query_text, hard_negs

            except Exception as e:
                logger.warning(f"Error mining for query '{query_text[:50]}...': {e}")
                return query_text, []

        # Prepare arguments
        args_list = [
            (i, qt, emb, pids)
            for i, (qt, emb, pids) in enumerate(
                zip(query_texts, query_embeddings, positive_ids_list)
            )
        ]

        # Parallel search
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(
                tqdm(
                    executor.map(search_single, args_list),
                    total=len(args_list),
                    desc="Mining hard negatives",
                )
            )

        # Collect results
        for query_text, negs in results:
            if negs:
                hard_negatives[query_text] = negs

        logger.info(f"Mined hard negatives for {len(hard_negatives)} queries")
        return hard_negatives

    def mine_for_training(
        self,
        queries: List[Dict],
        top_k: int = 20,
        sample_strategy: str = "top",
        num_negatives: int = 3,
    ) -> List[Dict]:
        """
        Mine hard negatives and format for training.

        Args:
            queries: List of query dicts with positive info
            top_k: Top-K for retrieval
            sample_strategy: How to sample negatives:
                - "top": Take top-ranked negatives (hardest)
                - "mixed": Mix of top (hard) and middle (semi-hard)
                - "random": Random sample from top-K
            num_negatives: Number of negatives per query

        Returns:
            List of training examples with hard negatives:
            [{"anchor": str, "positive": str, "negative": List[str]}]
        """
        # First, get the hard negatives
        hard_negatives = self.mine_hard_negatives(
            queries=queries,
            top_k=top_k,
            filter_positives=True,
            max_negatives_per_query=top_k,
        )

        training_examples = []

        for query in queries:
            query_text = query["query"]
            positive_text = query.get("positive_text", "")

            if not positive_text or query_text not in hard_negatives:
                continue

            negs = hard_negatives[query_text]

            if len(negs) < num_negatives:
                continue

            # Sample negatives based on strategy
            if sample_strategy == "top":
                selected_negs = negs[:num_negatives]
            elif sample_strategy == "mixed":
                # Half from top, half from middle
                n_top = num_negatives // 2
                n_mid = num_negatives - n_top
                selected_negs = negs[:n_top] + negs[len(negs) // 2 : len(negs) // 2 + n_mid]
            elif sample_strategy == "random":
                import random

                selected_negs = random.sample(negs, min(num_negatives, len(negs)))
            else:
                selected_negs = negs[:num_negatives]

            training_examples.append(
                {
                    "anchor": query_text,
                    "positive": positive_text,
                    "negative": selected_negs,
                }
            )

        logger.info(f"Created {len(training_examples)} training examples with hard negatives")
        return training_examples


def mine_hard_negatives_batch(
    client: QdrantClient,
    model: SparseEncoder,
    collection_name: str,
    queries: List[Dict],
    top_k: int = 20,
    vector_name: str = "text",
) -> Dict[str, List[str]]:
    """
    Convenience function for one-shot hard negative mining.

    Args:
        client: Qdrant client
        model: SparseEncoder
        collection_name: Collection name
        queries: List of query dicts
        top_k: Top-K for retrieval
        vector_name: Sparse vector field name

    Returns:
        Dict mapping query -> list of hard negative texts
    """
    miner = SparseQdrantMiner(
        client=client,
        model=model,
        collection_name=collection_name,
        vector_name=vector_name,
    )
    return miner.mine_hard_negatives(queries, top_k=top_k)
