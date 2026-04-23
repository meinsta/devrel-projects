"""ESCI Dataset Loading for Sparse Encoder Training"""

import logging
from typing import Dict, List, Optional, Tuple

from datasets import Dataset, DatasetDict, load_dataset

from src.config import ESCI_SCORES, POSITIVE_LABELS, RELEVANT_LABELS
from src.data.text_builder import build_product_text

logger = logging.getLogger(__name__)


class ESCILoader:
    """
    Load Amazon ESCI (Shopping Queries Dataset) from HuggingFace.

    Dataset: https://huggingface.co/datasets/tasksource/esci
    Paper: https://github.com/amazon-science/esci-data

    Labels:
        E (Exact): The product is a direct match for the query
        S (Substitute): The product could serve as a substitute
        C (Complement): The product complements the query
        I (Irrelevant): The product is not relevant
    """

    DATASET_NAME = "tasksource/esci"
    LOCALE = "us"  # English US locale

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize ESCI loader.

        Args:
            cache_dir: Directory to cache downloaded dataset
        """
        self.cache_dir = cache_dir
        self._dataset: Optional[DatasetDict] = None

    def load_raw(self) -> DatasetDict:
        """Load raw ESCI dataset from HuggingFace."""
        if self._dataset is None:
            logger.info(f"Loading ESCI dataset from {self.DATASET_NAME}")
            self._dataset = load_dataset(
                self.DATASET_NAME,
                cache_dir=self.cache_dir,
            )
            logger.info(f"Loaded {len(self._dataset)} splits")
        return self._dataset

    def load_for_training(
        self,
        split: str = "train",
        max_samples: Optional[int] = None,
        include_substitutes: bool = True,
    ) -> Dataset:
        """
        Load dataset formatted for SparseEncoder training.

        Returns Dataset with columns:
        - anchor: query text
        - positive: product text (E or S labels)

        Uses SparseMultipleNegativesRankingLoss which only needs (anchor, positive) pairs.
        Negatives are sampled in-batch during training.

        Args:
            split: Dataset split ("train", "validation", "test")
            max_samples: Maximum number of samples (for testing)
            include_substitutes: Include S labels as positives (recommended)

        Returns:
            Dataset with anchor-positive pairs
        """
        raw = self.load_raw()
        data = raw[split]

        # Filter to locale
        data = data.filter(lambda x: x.get("product_locale", "us") == self.LOCALE)

        # Get positive labels
        positive_set = {"E", "Exact"}
        if include_substitutes:
            positive_set.update({"S", "Substitute"})

        # Filter to positive labels only
        data = data.filter(lambda x: x.get("esci_label", "") in positive_set)

        if max_samples and len(data) > max_samples:
            data = data.select(range(max_samples))

        logger.info(f"Loaded {len(data)} training pairs from {split}")

        # Transform to training format
        def transform_to_pairs(examples):
            anchors = []
            positives = []

            for i in range(len(examples["query"])):
                query = examples["query"][i]
                title = examples.get("product_title", [""])[i] or ""
                brand = examples.get("product_brand", [""])[i] or ""
                desc = examples.get("product_description", [""])[i] or ""
                bullets = examples.get("product_bullet_point", [""])[i] or ""

                # Build product text
                product_text = build_product_text(
                    title=title,
                    brand=brand,
                    description=desc,
                    bullets=bullets.split("\n") if bullets else [],
                )

                anchors.append(query)
                positives.append(product_text)

            return {"anchor": anchors, "positive": positives}

        # Map in batches for efficiency
        data = data.map(
            transform_to_pairs,
            batched=True,
            remove_columns=data.column_names,
            desc="Transforming to training pairs",
        )

        return data

    def load_for_evaluation(
        self,
        split: str = "test",
        max_queries: Optional[int] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load dataset formatted for retrieval evaluation.

        Returns:
            queries: List of {"query_id": str, "query": str, "relevance": {product_id: label}}
            products: List of {"product_id": str, "text": str, "payload": dict}
        """
        raw = self.load_raw()
        data = raw[split]

        # Filter to locale
        data = data.filter(lambda x: x.get("product_locale", "us") == self.LOCALE)

        # Group by query
        query_map: Dict[str, Dict] = {}
        product_map: Dict[str, Dict] = {}

        for item in data:
            query = item.get("query", "")
            query_id = item.get("query_id", query)
            product_id = item.get("product_id", "")
            label = item.get("esci_label", "I")

            # Build query entry
            if query_id not in query_map:
                query_map[query_id] = {
                    "query_id": query_id,
                    "query": query,
                    "relevance": {},
                }
            query_map[query_id]["relevance"][product_id] = label

            # Build product entry
            if product_id not in product_map:
                title = item.get("product_title", "") or ""
                brand = item.get("product_brand", "") or ""
                desc = item.get("product_description", "") or ""
                bullets = item.get("product_bullet_point", "") or ""

                product_text = build_product_text(
                    title=title,
                    brand=brand,
                    description=desc,
                    bullets=bullets.split("\n") if bullets else [],
                )

                product_map[product_id] = {
                    "product_id": product_id,
                    "text": product_text,
                    "payload": {
                        "title": title,
                        "brand": brand,
                    },
                }

        queries = list(query_map.values())
        products = list(product_map.values())

        if max_queries and len(queries) > max_queries:
            queries = queries[:max_queries]

        logger.info(f"Loaded {len(queries)} queries and {len(products)} products for evaluation")

        return queries, products

    def load_products_for_indexing(
        self,
        split: str = "train",
        max_products: Optional[int] = None,
    ) -> List[Dict]:
        """
        Load unique products for indexing into Qdrant.

        Returns:
            List of {"product_id": str, "text": str, "label": str, "payload": dict}
        """
        raw = self.load_raw()
        data = raw[split]

        # Filter to locale
        data = data.filter(lambda x: x.get("product_locale", "us") == self.LOCALE)

        product_map: Dict[str, Dict] = {}

        for item in data:
            product_id = item.get("product_id", "")
            if product_id in product_map:
                continue

            title = item.get("product_title", "") or ""
            brand = item.get("product_brand", "") or ""
            desc = item.get("product_description", "") or ""
            bullets = item.get("product_bullet_point", "") or ""
            label = item.get("esci_label", "I")

            product_text = build_product_text(
                title=title,
                brand=brand,
                description=desc,
                bullets=bullets.split("\n") if bullets else [],
            )

            product_map[product_id] = {
                "product_id": product_id,
                "text": product_text,
                "label": label,
                "payload": {
                    "title": title,
                    "brand": brand,
                    "label": label,
                },
            }

        products = list(product_map.values())

        if max_products and len(products) > max_products:
            products = products[:max_products]

        logger.info(f"Loaded {len(products)} unique products for indexing")

        return products

    def load_queries_for_mining(
        self,
        split: str = "train",
        max_queries: Optional[int] = None,
    ) -> List[Dict]:
        """
        Load queries for hard negative mining.

        Returns:
            List of {"query": str, "query_id": str, "positive_ids": set}
        """
        raw = self.load_raw()
        data = raw[split]

        # Filter to locale
        data = data.filter(lambda x: x.get("product_locale", "us") == self.LOCALE)

        query_map: Dict[str, Dict] = {}

        for item in data:
            query = item.get("query", "")
            query_id = item.get("query_id", query)
            product_id = item.get("product_id", "")
            label = item.get("esci_label", "I")

            if query_id not in query_map:
                query_map[query_id] = {
                    "query": query,
                    "query_id": query_id,
                    "positive_ids": set(),
                }

            # Track positive product IDs
            if label in POSITIVE_LABELS:
                query_map[query_id]["positive_ids"].add(product_id)

        queries = list(query_map.values())

        if max_queries and len(queries) > max_queries:
            queries = queries[:max_queries]

        logger.info(f"Loaded {len(queries)} queries for mining")

        return queries
