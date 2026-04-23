"""
Evaluation service for RAG experiments.
Adapted from mission_control.py logic.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
import logging

logger = logging.getLogger(__name__)

# Configuration matching mission_control.py
EMBEDDING_MODELS = {
    "bge-small": {
        "model_name": "BAAI/bge-small-en-v1.5",
        "vector_size": 384,
        "description": "Fast & efficient"
    },
    "bge-base": {
        "model_name": "BAAI/bge-base-en-v1.5",
        "vector_size": 768,
        "description": "High quality"
    },
    "minilm-l6": {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "description": "Ultra fast"
    }
}

RESULTS_FILE = Path("mission_results.json")


class EvaluationService:
    """Service for running RAG evaluation experiments."""
    
    def __init__(self, qdrant_url: str = "http://localhost:6333", collection_name: str = "california_housing_test"):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.client = None
        self.embedding_models = {}
        
    def _get_client(self):
        """Lazy initialize Qdrant client."""
        if self.client is None:
            self.client = QdrantClient(url=self.qdrant_url)
        return self.client
    
    def _get_embedding_model(self, model_key: str):
        """Get or initialize embedding model."""
        if model_key not in self.embedding_models:
            model_info = EMBEDDING_MODELS[model_key]
            self.embedding_models[model_key] = TextEmbedding(
                model_name=model_info["model_name"]
            )
        return self.embedding_models[model_key]
    
    async def run_experiment(
        self,
        embedding_model: str,
        retrieval_mode: str,
        top_k: int,
        noise_level: int = 0,
        test_queries: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Run a single evaluation experiment.
        
        Args:
            embedding_model: Key from EMBEDDING_MODELS
            retrieval_mode: "dense", "sparse", or "hybrid"
            top_k: Number of results to retrieve
            noise_level: Noise percentage (0-100)
            test_queries: List of test queries with golden answers
            
        Returns:
            Dict with experiment results
        """
        logger.info(f"Starting experiment: {embedding_model}, {retrieval_mode}, k={top_k}")
        
        start_time = time.time()
        
        # If no test queries provided, use sample queries
        if test_queries is None:
            test_queries = self._get_sample_queries()
        
        results = []
        total_recall = 0.0
        total_precision = 0.0
        
        client = self._get_client()
        embedding_model_obj = self._get_embedding_model(embedding_model)
        
        for query_data in test_queries:
            query = query_data["question"]
            golden_ids = query_data.get("golden_statute_ids", [])
            
            # Run search based on retrieval mode
            if retrieval_mode.lower() == "dense" or retrieval_mode.lower() == "dense (semantic)":
                search_results = await self._dense_search(
                    client, embedding_model_obj, query, top_k
                )
            elif retrieval_mode.lower() == "sparse" or retrieval_mode.lower() == "sparse (lexical)":
                search_results = await self._sparse_search(
                    client, query, top_k
                )
            else:  # hybrid
                search_results = await self._hybrid_search(
                    client, embedding_model_obj, query, top_k
                )
            
            # Calculate metrics
            retrieved_ids = [hit.id for hit in search_results]
            recall, precision = self._calculate_metrics(retrieved_ids, golden_ids, top_k)
            
            total_recall += recall
            total_precision += precision
            
            results.append({
                "query": query,
                "recall": recall,
                "precision": precision,
                "retrieved_count": len(retrieved_ids)
            })
        
        elapsed_time = (time.time() - start_time) * 1000  # ms
        
        experiment_result = {
            "id": f"exp_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "embedding_model": embedding_model,
                "retrieval_mode": retrieval_mode,
                "top_k": top_k,
                "noise_level": noise_level
            },
            "metrics": {
                "avg_recall": total_recall / len(test_queries) if test_queries else 0,
                "avg_precision": total_precision / len(test_queries) if test_queries else 0,
                "total_queries": len(test_queries),
                "latency_ms": elapsed_time / len(test_queries) if test_queries else 0
            },
            "status": "completed",
            "query_results": results[:5]  # Sample of results
        }
        
        # Save to results file
        self._save_result(experiment_result)
        
        logger.info(f"Experiment completed: Recall={experiment_result['metrics']['avg_recall']:.2%}")
        
        return experiment_result
    
    async def _dense_search(self, client, embedding_model, query: str, top_k: int):
        """Dense vector search."""
        query_vector = list(embedding_model.embed([query]))[0]
        
        return client.search(
            collection_name=self.collection_name,
            query_vector=("fast-bge-small-en", query_vector.tolist()),
            limit=top_k
        )
    
    async def _sparse_search(self, client, query: str, top_k: int):
        """Sparse BM25 search."""
        from qdrant_client.models import SparseVector
        
        # Simple word-based sparse vector (in production, use proper BM25)
        words = query.lower().split()
        indices = [hash(word) % 10000 for word in words]
        values = [1.0] * len(words)
        
        return client.search(
            collection_name=self.collection_name,
            query_vector=("text-sparse", SparseVector(indices=indices, values=values)),
            limit=top_k
        )
    
    async def _hybrid_search(self, client, embedding_model, query: str, top_k: int):
        """Hybrid search with RRF fusion."""
        # Get both dense and sparse results
        dense_results = await self._dense_search(client, embedding_model, query, top_k)
        sparse_results = await self._sparse_search(client, query, top_k)
        
        # Simple RRF fusion (in production, use proper RRF)
        scores = {}
        k = 60  # RRF constant
        
        for rank, hit in enumerate(dense_results):
            scores[hit.id] = scores.get(hit.id, 0) + 1 / (k + rank + 1)
        
        for rank, hit in enumerate(sparse_results):
            scores[hit.id] = scores.get(hit.id, 0) + 1 / (k + rank + 1)
        
        # Sort by RRF score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Get full point data for top results
        points = client.retrieve(
            collection_name=self.collection_name,
            ids=[id for id, _ in sorted_ids]
        )
        
        return points
    
    def _calculate_metrics(self, retrieved_ids: List, golden_ids: List[int], k: int) -> tuple:
        """Calculate recall and precision."""
        if not golden_ids:
            return 0.0, 0.0
        
        retrieved_set = set(retrieved_ids[:k])
        golden_set = set(golden_ids)
        
        hits = len(retrieved_set & golden_set)
        
        recall = hits / len(golden_set) if golden_set else 0.0
        precision = hits / k if k > 0 else 0.0
        
        return recall, precision
    
    def _get_sample_queries(self) -> List[Dict]:
        """Get sample test queries."""
        return [
            {
                "question": "Can a landlord evict a tenant without notice?",
                "golden_statute_ids": [1946, 1161]
            },
            {
                "question": "What is the maximum security deposit allowed?",
                "golden_statute_ids": [1950.5]
            },
            {
                "question": "How many days notice for rent increase?",
                "golden_statute_ids": [827]
            }
        ]
    
    def _save_result(self, result: Dict):
        """Save experiment result to file."""
        results = []
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
        
        results.append(result)
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
    
    def get_all_results(self) -> List[Dict]:
        """Get all experiment results."""
        if not RESULTS_FILE.exists():
            return []
        
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top experiments sorted by recall."""
        results = self.get_all_results()
        sorted_results = sorted(
            results,
            key=lambda x: x.get("metrics", {}).get("avg_recall", 0),
            reverse=True
        )
        return sorted_results[:limit]





