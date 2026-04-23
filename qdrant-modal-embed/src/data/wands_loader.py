"""Wayfair WANDS Dataset Loader

WANDS (Wayfair ANnotated Dataset for e-commerce Search) for testing
generalization of fine-tuned models to different e-commerce domains.

Dataset: https://huggingface.co/datasets/napsternxg/wands
Original source: https://github.com/wayfair/WANDS
"""

import logging
from typing import Dict, List, Optional, Tuple

from datasets import load_dataset
from tqdm import tqdm

logger = logging.getLogger(__name__)


class WANDSLoader:
    """Load and process WANDS dataset for evaluation.

    The dataset is pre-merged with columns:
    - query_id, query, query_class
    - product_id, product_name, product_class, category_hierarchy, product_description
    - label: "Irrelevant" (0), "Partial" (1), "Exact" (2)
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize WANDS loader.

        Args:
            cache_dir: Directory for caching dataset
        """
        self.cache_dir = cache_dir
        self._dataset = None

    def _load_dataset(self, split: str = "test"):
        """Load WANDS dataset from Hugging Face."""
        if self._dataset is None:
            logger.info(f"Loading WANDS dataset (split={split}) from Hugging Face...")
            # WANDS is available at napsternxg/wands (community upload of wayfair/WANDS)
            self._dataset = load_dataset(
                "napsternxg/wands",
                split=split,
                cache_dir=self.cache_dir,
            )
            logger.info(f"Loaded {len(self._dataset)} rows from WANDS {split} split")
        return self._dataset

    def load_for_evaluation(
        self,
        split: str = "test",
        max_queries: Optional[int] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load queries and products for evaluation.

        WANDS uses label grades:
        - Exact (2): Product is exactly what the user is searching for
        - Partial (1): Product is somewhat relevant
        - Irrelevant (0): Product is not relevant

        Args:
            split: Dataset split ("train", "dev", or "test")
            max_queries: Maximum queries to return

        Returns:
            Tuple of (queries, products) where:
            - queries: List of {"query_id", "query", "relevance": {pid: label}}
            - products: List of {"product_id", "text", "payload": dict}
        """
        dataset = self._load_dataset(split=split)

        # Build product map (unique products)
        product_map = {}
        # Build query map (aggregate relevance labels per query)
        query_map = {}

        for item in tqdm(dataset, desc="Processing WANDS data"):
            product_id = str(item.get("product_id", ""))
            query_id = str(item.get("query_id", ""))
            query_text = item.get("query", "") or ""
            label = item.get("label", 0)  # 0=Irrelevant, 1=Partial, 2=Exact

            # Build product entry if not exists
            if product_id not in product_map:
                product_name = item.get("product_name", "") or ""
                product_class = item.get("product_class", "") or ""
                category_hierarchy = item.get("category_hierarchy", "") or ""
                product_description = item.get("product_description", "") or ""

                # Build product text
                text_parts = []
                if product_class:
                    text_parts.append(f"[{product_class}]")
                text_parts.append(product_name)
                if category_hierarchy:
                    text_parts.append(f"Category: {category_hierarchy}")
                if product_description:
                    # Truncate long descriptions
                    text_parts.append(product_description[:300])

                text = " | ".join(text_parts)

                product_map[product_id] = {
                    "product_id": product_id,
                    "text": text,
                    "payload": {
                        "product_name": product_name,
                        "product_class": product_class,
                        "category": category_hierarchy,
                    },
                }

            # Build query entry
            if query_id not in query_map:
                query_map[query_id] = {
                    "query_id": query_id,
                    "query": query_text,
                    "relevance": {},
                }

            # Add relevance label (use numeric grade)
            # Exact=2, Partial=1, Irrelevant=0 -> convert to nDCG-friendly grades
            query_map[query_id]["relevance"][product_id] = label

        # Filter queries with at least one relevant product (Exact or Partial)
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

        logger.info(f"Loaded {len(queries)} queries, {len(products)} products from WANDS")
        return queries, products


def load_wands_for_evaluation(
    split: str = "test",
    max_queries: int = 1000,
    cache_dir: Optional[str] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Convenience function to load WANDS for evaluation.

    Args:
        split: Dataset split
        max_queries: Maximum queries
        cache_dir: Cache directory

    Returns:
        Tuple of (queries, products)
    """
    loader = WANDSLoader(cache_dir=cache_dir)
    return loader.load_for_evaluation(split=split, max_queries=max_queries)
