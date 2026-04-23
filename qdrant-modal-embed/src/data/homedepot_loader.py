"""Home Depot Product Search Relevance Dataset Loader

Home Depot dataset for testing generalization to home improvement domain.
Uses crowdsourced relevance scores (1-3 scale).

Dataset: https://huggingface.co/datasets/bstds/home_depot
Original: Kaggle Home Depot Product Search Relevance competition
"""

import logging
from typing import Dict, List, Optional, Tuple

from datasets import load_dataset
from tqdm import tqdm

logger = logging.getLogger(__name__)


class HomeDepotLoader:
    """Load and process Home Depot dataset for evaluation.

    The dataset contains:
    - id: unique identifier
    - entity_id: product identifier
    - name: product name
    - query: customer search term
    - relevance: 1-3 float score (1=not relevant, 2=mildly relevant, 3=highly relevant)
    - description: product description
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize Home Depot loader.

        Args:
            cache_dir: Directory for caching dataset
        """
        self.cache_dir = cache_dir
        self._dataset = None

    def _load_dataset(self):
        """Load Home Depot dataset from Hugging Face."""
        if self._dataset is None:
            logger.info("Loading Home Depot dataset from Hugging Face...")
            self._dataset = load_dataset(
                "bstds/home_depot",
                split="train",
                cache_dir=self.cache_dir,
            )
            logger.info(f"Loaded {len(self._dataset)} rows from Home Depot")
        return self._dataset

    def load_for_evaluation(
        self,
        max_queries: Optional[int] = None,
        min_relevance_for_relevant: float = 2.0,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load queries and products for evaluation.

        Home Depot uses continuous relevance scores:
        - 3.0: Highly relevant (exact match)
        - 2.0-2.99: Mildly relevant (substitute)
        - 1.0-1.99: Not relevant

        We convert to integer grades for nDCG:
        - score >= 2.5 -> grade 2 (exact)
        - score >= 2.0 -> grade 1 (partial)
        - score < 2.0 -> grade 0 (irrelevant)

        Args:
            max_queries: Maximum queries to return
            min_relevance_for_relevant: Minimum score to consider relevant (default 2.0)

        Returns:
            Tuple of (queries, products) where:
            - queries: List of {"query_id", "query", "relevance": {pid: grade}}
            - products: List of {"product_id", "text", "payload": dict}
        """
        dataset = self._load_dataset()

        # Build product map (unique products by entity_id)
        product_map = {}
        # Build query map (aggregate relevance labels per query)
        query_map = {}

        for item in tqdm(dataset, desc="Processing Home Depot data"):
            product_id = str(item.get("entity_id", ""))
            query_text = item.get("query", "") or ""
            relevance_score = item.get("relevance", 1.0)
            product_name = item.get("name", "") or ""
            description = item.get("description", "") or ""

            # Create query_id from query text (hash)
            query_id = str(hash(query_text) % 10**8)

            # Build product entry if not exists
            if product_id not in product_map:
                # Build product text
                text_parts = [product_name]
                if description:
                    # Truncate long descriptions
                    text_parts.append(description[:500])

                text = " | ".join(text_parts)

                product_map[product_id] = {
                    "product_id": product_id,
                    "text": text,
                    "payload": {
                        "product_name": product_name,
                    },
                }

            # Build query entry
            if query_id not in query_map:
                query_map[query_id] = {
                    "query_id": query_id,
                    "query": query_text,
                    "relevance": {},
                }

            # Convert continuous score to integer grade
            # 3.0 -> 2, 2.5 -> 2, 2.0 -> 1, 1.5 -> 0, 1.0 -> 0
            if relevance_score >= 2.5:
                grade = 2  # Highly relevant
            elif relevance_score >= min_relevance_for_relevant:
                grade = 1  # Mildly relevant
            else:
                grade = 0  # Not relevant

            # Store the highest grade if multiple judgments exist
            current_grade = query_map[query_id]["relevance"].get(product_id, -1)
            if grade > current_grade:
                query_map[query_id]["relevance"][product_id] = grade

        # Filter queries with at least one relevant product
        queries = [q for q in query_map.values() if any(
            v > 0 for v in q["relevance"].values()
        )]

        if max_queries and len(queries) > max_queries:
            queries = queries[:max_queries]

        # Get only products that appear in relevance judgments
        relevant_pids = set()
        for q in queries:
            relevant_pids.update(q["relevance"].keys())

        products = [p for pid, p in product_map.items() if pid in relevant_pids]

        logger.info(f"Loaded {len(queries)} queries, {len(products)} products from Home Depot")
        return queries, products


def load_homedepot_for_evaluation(
    max_queries: int = 1000,
    cache_dir: Optional[str] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Convenience function to load Home Depot for evaluation.

    Args:
        max_queries: Maximum queries
        cache_dir: Cache directory

    Returns:
        Tuple of (queries, products)
    """
    loader = HomeDepotLoader(cache_dir=cache_dir)
    return loader.load_for_evaluation(max_queries=max_queries)
