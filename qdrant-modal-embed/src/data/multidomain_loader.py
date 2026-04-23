"""Multi-Domain Dataset Loader for Generalized E-Commerce Training

Combines training data from multiple e-commerce datasets:
- Amazon ESCI (Shopping Queries Dataset)
- Wayfair WANDS
- Home Depot Product Search

This creates a more diverse training set for better generalization.
"""

import logging
from typing import Optional

from datasets import Dataset, concatenate_datasets, load_dataset
from tqdm import tqdm

logger = logging.getLogger(__name__)


class MultiDomainLoader:
    """Load and combine multiple e-commerce datasets for training.

    Produces anchor-positive pairs in the same format as ESCILoader:
    - anchor: query text
    - positive: product text
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize multi-domain loader.

        Args:
            cache_dir: Directory for caching datasets
        """
        self.cache_dir = cache_dir

    def _load_esci_pairs(
        self,
        max_samples: Optional[int] = None,
        include_substitutes: bool = True,
    ) -> Dataset:
        """Load training pairs from Amazon ESCI."""
        logger.info("Loading ESCI (Amazon) training data...")

        dataset = load_dataset(
            "tasksource/esci",
            cache_dir=self.cache_dir,
        )
        data = dataset["train"]

        # Filter to US locale
        data = data.filter(lambda x: x.get("product_locale", "us") == "us")

        # Get positive labels
        positive_set = {"E", "Exact"}
        if include_substitutes:
            positive_set.update({"S", "Substitute"})

        # Filter to positive labels only
        data = data.filter(lambda x: x.get("esci_label", "") in positive_set)

        if max_samples and len(data) > max_samples:
            data = data.shuffle(seed=42).select(range(max_samples))

        logger.info(f"ESCI: {len(data)} positive pairs")

        # Transform to anchor-positive format
        def transform(examples):
            anchors = []
            positives = []

            for i in range(len(examples["query"])):
                query = examples["query"][i]
                title = examples.get("product_title", [""])[i] or ""
                brand = examples.get("product_brand", [""])[i] or ""
                desc = examples.get("product_description", [""])[i] or ""

                # Build product text
                parts = []
                if brand:
                    parts.append(f"[{brand}]")
                parts.append(title)
                if desc:
                    # Truncate description
                    parts.append(desc[:500])

                product_text = " ".join(parts)

                anchors.append(query)
                positives.append(product_text)

            return {"anchor": anchors, "positive": positives, "source": ["esci"] * len(anchors)}

        return data.map(
            transform,
            batched=True,
            remove_columns=data.column_names,
            desc="Transforming ESCI pairs",
        )

    def _load_wands_pairs(
        self,
        max_samples: Optional[int] = None,
    ) -> Dataset:
        """Load training pairs from Wayfair WANDS."""
        logger.info("Loading WANDS (Wayfair) training data...")

        # WANDS has train/dev/test splits
        dataset = load_dataset(
            "napsternxg/wands",
            split="train",
            cache_dir=self.cache_dir,
        )

        # Filter to relevant labels (Exact=2, Partial=1)
        # Only use Exact matches for training (cleaner signal)
        data = dataset.filter(lambda x: x.get("label", 0) == 2)  # Exact only

        if max_samples and len(data) > max_samples:
            data = data.shuffle(seed=42).select(range(max_samples))

        logger.info(f"WANDS: {len(data)} positive pairs")

        # Transform to anchor-positive format
        def transform(examples):
            anchors = []
            positives = []

            # Get lists with safe defaults
            queries = examples.get("query", [])
            product_names = examples.get("product_name", [])
            product_classes = examples.get("product_class", [])
            categories = examples.get("category_hierarchy", [])
            descriptions = examples.get("product_description", [])

            for i in range(len(queries)):
                query = queries[i] if i < len(queries) else ""
                query = query or ""

                product_name = product_names[i] if i < len(product_names) else ""
                product_name = product_name or ""

                product_class = product_classes[i] if i < len(product_classes) else ""
                product_class = product_class or ""

                category = categories[i] if i < len(categories) else ""
                category = category or ""

                desc = descriptions[i] if i < len(descriptions) else ""
                desc = desc or ""

                # Build product text
                parts = []
                if product_class:
                    parts.append(f"[{product_class}]")
                parts.append(product_name)
                if category:
                    parts.append(f"Category: {category}")
                if desc:
                    parts.append(desc[:500])

                product_text = " ".join(parts)

                anchors.append(query)
                positives.append(product_text)

            return {"anchor": anchors, "positive": positives, "source": ["wands"] * len(anchors)}

        return data.map(
            transform,
            batched=True,
            remove_columns=data.column_names,
            desc="Transforming WANDS pairs",
        )

    def _load_homedepot_pairs(
        self,
        max_samples: Optional[int] = None,
        min_relevance: float = 2.5,  # Only highly relevant
    ) -> Dataset:
        """Load training pairs from Home Depot."""
        logger.info("Loading Home Depot training data...")

        dataset = load_dataset(
            "bstds/home_depot",
            split="train",
            cache_dir=self.cache_dir,
        )

        # Filter to highly relevant (>= 2.5 on 1-3 scale)
        data = dataset.filter(lambda x: x.get("relevance", 1.0) >= min_relevance)

        if max_samples and len(data) > max_samples:
            data = data.shuffle(seed=42).select(range(max_samples))

        logger.info(f"Home Depot: {len(data)} positive pairs")

        # Transform to anchor-positive format
        def transform(examples):
            anchors = []
            positives = []

            # Get lists with safe defaults
            queries = examples.get("query", [])
            names = examples.get("name", [])
            descriptions = examples.get("description", [])

            for i in range(len(queries)):
                query = queries[i] if i < len(queries) else ""
                query = query or ""

                name = names[i] if i < len(names) else ""
                name = name or ""

                desc = descriptions[i] if i < len(descriptions) else ""
                desc = desc or ""

                # Build product text
                parts = [name]
                if desc:
                    parts.append(desc[:500])

                product_text = " ".join(parts)

                anchors.append(query)
                positives.append(product_text)

            return {
                "anchor": anchors,
                "positive": positives,
                "source": ["homedepot"] * len(anchors),
            }

        return data.map(
            transform,
            batched=True,
            remove_columns=data.column_names,
            desc="Transforming Home Depot pairs",
        )

    def load_for_training(
        self,
        max_samples_per_dataset: Optional[int] = None,
        include_esci: bool = True,
        include_wands: bool = True,
        include_homedepot: bool = True,
        shuffle: bool = True,
    ) -> Dataset:
        """
        Load combined training data from multiple domains.

        Args:
            max_samples_per_dataset: Max samples per dataset (for balancing)
            include_esci: Include Amazon ESCI data
            include_wands: Include Wayfair WANDS data
            include_homedepot: Include Home Depot data
            shuffle: Shuffle the combined dataset

        Returns:
            Dataset with columns: anchor, positive, source
        """
        datasets = []

        if include_esci:
            esci_data = self._load_esci_pairs(max_samples=max_samples_per_dataset)
            datasets.append(esci_data)

        if include_wands:
            wands_data = self._load_wands_pairs(max_samples=max_samples_per_dataset)
            datasets.append(wands_data)

        if include_homedepot:
            homedepot_data = self._load_homedepot_pairs(max_samples=max_samples_per_dataset)
            datasets.append(homedepot_data)

        if not datasets:
            raise ValueError("At least one dataset must be included")

        # Combine all datasets
        combined = concatenate_datasets(datasets)

        logger.info(f"Combined dataset: {len(combined)} total training pairs")

        # Log distribution
        sources = combined["source"]
        from collections import Counter

        dist = Counter(sources)
        for source, count in dist.items():
            logger.info(f"  {source}: {count} pairs ({100 * count / len(combined):.1f}%)")

        if shuffle:
            combined = combined.shuffle(seed=42)

        # Remove source column for training (not needed by loss function)
        combined = combined.remove_columns(["source"])

        return combined


def load_multidomain_for_training(
    max_samples_per_dataset: Optional[int] = None,
    cache_dir: Optional[str] = None,
) -> Dataset:
    """
    Convenience function to load multi-domain training data.

    Args:
        max_samples_per_dataset: Max samples per dataset
        cache_dir: Cache directory

    Returns:
        Combined Dataset with anchor-positive pairs
    """
    loader = MultiDomainLoader(cache_dir=cache_dir)
    return loader.load_for_training(
        max_samples_per_dataset=max_samples_per_dataset,
    )
