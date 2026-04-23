"""MS MARCO Passage Retrieval Dataset Loader

MS MARCO for testing generalization to general information retrieval.
Uses the mteb/msmarco dataset which has a modern format.

Dataset: https://huggingface.co/datasets/mteb/msmarco
"""

import logging
from typing import Dict, List, Optional, Tuple

from datasets import load_dataset
from tqdm import tqdm

logger = logging.getLogger(__name__)


class MSMARCOLoader:
    """Load and process MS MARCO dataset for evaluation.

    Uses mteb/msmarco which contains:
    - corpus: _id, title, text
    - queries: _id, text
    - default split: query-id, corpus-id, score (qrels)
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize MS MARCO loader.

        Args:
            cache_dir: Directory for caching dataset
        """
        self.cache_dir = cache_dir
        self._corpus = None
        self._queries = None

    def load_for_evaluation(
        self,
        max_queries: Optional[int] = None,
        max_corpus: Optional[int] = None,
        split: str = "dev",
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load queries and passages for evaluation.

        Uses the mteb/msmarco dataset which has a cleaner format.

        Args:
            max_queries: Maximum queries to return
            max_corpus: Maximum corpus passages to index
            split: Which split to use ("dev" or "test")

        Returns:
            Tuple of (queries, passages) where:
            - queries: List of {"query_id", "query", "relevance": {pid: grade}}
            - passages: List of {"product_id", "text", "payload": dict}
        """
        # Load corpus
        logger.info("Loading MS MARCO corpus...")
        corpus_dataset = load_dataset(
            "mteb/msmarco",
            "corpus",
            cache_dir=self.cache_dir,
        )
        corpus_data = corpus_dataset["corpus"]
        logger.info(f"Loaded corpus with {len(corpus_data)} passages")

        # Load queries
        logger.info("Loading MS MARCO queries...")
        queries_dataset = load_dataset(
            "mteb/msmarco",
            "queries",
            cache_dir=self.cache_dir,
        )
        queries_data = queries_dataset["queries"]
        logger.info(f"Loaded {len(queries_data)} queries")

        # Load the qrels (default split has query-id, corpus-id, score)
        logger.info("Loading MS MARCO qrels...")
        qrels_dataset = load_dataset(
            "mteb/msmarco",
            "default",
            cache_dir=self.cache_dir,
        )

        # Get the appropriate split
        if split in qrels_dataset:
            qrels_data = qrels_dataset[split]
        else:
            available_splits = list(qrels_dataset.keys())
            logger.warning(f"Split '{split}' not found, using '{available_splits[0]}'")
            qrels_data = qrels_dataset[available_splits[0]]

        logger.info(f"Loaded {len(qrels_data)} qrel entries")

        # Build qrels lookup: {query_id: {doc_id: relevance}}
        qrels_lookup = {}
        relevant_doc_ids = set()

        for item in tqdm(qrels_data, desc="Processing qrels"):
            query_id = str(item["query-id"])
            doc_id = str(item["corpus-id"])
            score = int(item["score"])

            if query_id not in qrels_lookup:
                qrels_lookup[query_id] = {}
            qrels_lookup[query_id][doc_id] = score

            if score > 0:
                relevant_doc_ids.add(doc_id)

        logger.info(f"Found {len(qrels_lookup)} unique queries with relevance judgments")
        logger.info(f"Found {len(relevant_doc_ids)} relevant documents")

        # Build query ID to text mapping
        query_text_lookup = {}
        for item in tqdm(queries_data, desc="Building query lookup"):
            query_id = str(item["_id"])
            query_text_lookup[query_id] = item["text"]

        # Build queries list
        queries = []
        for query_id, doc_scores in list(qrels_lookup.items()):
            if max_queries and len(queries) >= max_queries:
                break
            if query_id in query_text_lookup:
                queries.append(
                    {
                        "query_id": query_id,
                        "query": query_text_lookup[query_id],
                        "relevance": doc_scores,
                    }
                )

        # Update relevant doc IDs based on selected queries
        if max_queries:
            relevant_doc_ids = set()
            for q in queries:
                for doc_id, score in q["relevance"].items():
                    if score > 0:
                        relevant_doc_ids.add(doc_id)

        logger.info(f"Selected {len(queries)} queries")

        # Build corpus ID to data mapping
        corpus_lookup = {}
        for item in tqdm(corpus_data, desc="Indexing corpus"):
            doc_id = str(item["_id"])
            corpus_lookup[doc_id] = item

        # Build passage list - prioritize relevant documents
        passages = []
        seen_ids = set()

        # First, add all relevant documents we can find
        logger.info("Adding relevant documents to corpus...")
        for doc_id in tqdm(relevant_doc_ids, desc="Adding relevant docs"):
            if doc_id in corpus_lookup and doc_id not in seen_ids:
                item = corpus_lookup[doc_id]
                title = item.get("title", "") or ""
                text = item.get("text", "") or ""

                if title:
                    full_text = f"{title} | {text}"
                else:
                    full_text = text

                passages.append(
                    {
                        "product_id": doc_id,
                        "text": full_text[:2000],
                        "payload": {
                            "title": title[:200] if title else "",
                        },
                    }
                )
                seen_ids.add(doc_id)

        logger.info(f"Added {len(passages)} relevant documents")

        # Add additional documents up to max_corpus
        if max_corpus and len(passages) < max_corpus:
            remaining = max_corpus - len(passages)
            logger.info(f"Adding {remaining} additional documents...")
            count = 0
            for item in corpus_data:
                if count >= remaining:
                    break
                doc_id = str(item["_id"])
                if doc_id not in seen_ids:
                    title = item.get("title", "") or ""
                    text = item.get("text", "") or ""

                    if title:
                        full_text = f"{title} | {text}"
                    else:
                        full_text = text

                    passages.append(
                        {
                            "product_id": doc_id,
                            "text": full_text[:2000],
                            "payload": {
                                "title": title[:200] if title else "",
                            },
                        }
                    )
                    seen_ids.add(doc_id)
                    count += 1

        logger.info(f"Loaded {len(queries)} queries, {len(passages)} passages from MS MARCO")
        return queries, passages


def load_msmarco_for_evaluation(
    max_queries: int = 1000,
    max_corpus: int = 100000,
    cache_dir: Optional[str] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Convenience function to load MS MARCO for evaluation.

    Args:
        max_queries: Maximum queries
        max_corpus: Maximum corpus size
        cache_dir: Cache directory

    Returns:
        Tuple of (queries, passages)
    """
    loader = MSMARCOLoader(cache_dir=cache_dir)
    return loader.load_for_evaluation(
        max_queries=max_queries,
        max_corpus=max_corpus,
    )
