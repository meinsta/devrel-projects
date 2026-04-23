"""
Graph builder service
Interface 2: build knowledge graphs using Qdrant with QCI embeddings
"""

import json
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScrollRequest,
    VectorParams,
)

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.llm_client import LLMClient
from .text_processor import TextProcessor


COLLECTION_NAME = "mirofish_graph"
QCI_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class GraphInfo:
    """Graph information summary"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    Graph builder service.
    Uses Qdrant with QCI (Qdrant Cloud Inference) for vector embeddings
    and stores entities, edges, and chunks as points in a single collection.
    """

    def __init__(self, qdrant_url: Optional[str] = None, qdrant_api_key: Optional[str] = None):
        self.qdrant_url = qdrant_url or Config.QDRANT_URL
        self.qdrant_api_key = qdrant_api_key or Config.QDRANT_API_KEY

        if not self.qdrant_url:
            raise ValueError("QDRANT_URL not configured")
        if not self.qdrant_api_key:
            raise ValueError("QDRANT_API_KEY not configured")

        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
        )
        self.task_manager = TaskManager()
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the shared collection if it does not exist, with payload indexes."""
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={"text-dense": VectorParams(size=384, distance=Distance.COSINE)},
            )
            # Create payload indexes for filtering
            for field in ["graph_id", "point_type", "entity_type", "name"]:
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=field,
                    field_schema="keyword",
                )

    # ------------------------------------------------------------------
    # Public async build entry point
    # ------------------------------------------------------------------

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        """
        Build a graph asynchronously in a background thread.

        Returns:
            task_id that can be polled for progress.
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
        )
        thread.daemon = True
        thread.start()

        return task_id

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
    ):
        """Background thread that orchestrates graph construction."""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph build...",
            )

            # 1. Create graph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}",
            )

            # 2. Store ontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology stored",
            )

            # 3. Split text into chunks
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks",
            )

            # 4. Upsert chunks in batches
            self.add_text_batches(
                graph_id,
                chunks,
                batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.5),  # 20-70%
                    message=msg,
                ),
            )

            # 5. Extract entities and relationships from chunks using LLM
            self.task_manager.update_task(
                task_id,
                progress=70,
                message="Extracting entities and relationships with LLM...",
            )

            self.extract_entities_from_chunks(
                graph_id,
                chunks,
                ontology,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=70 + int(prog * 0.2),  # 70-90%
                    message=msg,
                ),
            )

            self.task_manager.update_task(
                task_id,
                progress=92,
                message="Retrieving graph info...",
            )

            # 6. Gather graph info
            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    # ------------------------------------------------------------------
    # Core graph operations
    # ------------------------------------------------------------------

    def create_graph(self, name: str) -> str:
        """
        Create a new logical graph inside the shared collection.
        Returns a unique graph_id.
        """
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"

        # Store a metadata point that marks this graph's existence
        meta_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{graph_id}_meta"))
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=meta_point_id,
                    vector={"text-dense": {"text": f"Graph metadata: {name}", "model": QCI_MODEL}},
                    payload={
                        "graph_id": graph_id,
                        "point_type": "meta",
                        "graph_name": name,
                        "description": "MiroFish Social Simulation Graph",
                    },
                )
            ],
        )

        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """
        Store the ontology definition as a special point in the collection.
        This replaces Zep's dynamic class creation with a simple JSON payload.
        """
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{graph_id}_ontology"))
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector={"text-dense": {"text": "Ontology schema definition", "model": QCI_MODEL}},
                    payload={
                        "graph_id": graph_id,
                        "point_type": "ontology",
                        "entity_types": ontology.get("entity_types", []),
                        "edge_types": ontology.get("edge_types", []),
                        "ontology_raw": json.dumps(ontology),
                    },
                )
            ],
        )

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        """
        Upsert text chunks into Qdrant with QCI embeddings.
        Returns the list of point IDs created.
        """
        point_ids: List[str] = []
        total_chunks = len(chunks)

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    f"Uploading batch {batch_num}/{total_batches} ({len(batch_chunks)} chunks)...",
                    progress,
                )

            points = []
            for chunk in batch_chunks:
                pid = str(uuid.uuid4())
                point_ids.append(pid)
                points.append(
                    PointStruct(
                        id=pid,
                        vector={"text-dense": {"text": chunk, "model": QCI_MODEL}},
                        payload={
                            "graph_id": graph_id,
                            "point_type": "chunk",
                            "content": chunk,
                        },
                    )
                )

            try:
                self.client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                )
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Batch {batch_num} failed: {str(e)}", 0)
                raise

        return point_ids

    # ------------------------------------------------------------------
    # LLM-powered entity and relationship extraction
    # ------------------------------------------------------------------

    def extract_entities_from_chunks(
        self,
        graph_id: str,
        chunks: List[str],
        ontology: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
    ):
        """
        Use LLM to extract entities and relationships from text chunks,
        guided by the ontology schema. Store results in Qdrant.
        This replaces what Zep did automatically during episode processing.
        """
        llm = LLMClient()

        entity_types = [e["name"] for e in ontology.get("entity_types", [])]
        edge_types = [e["name"] for e in ontology.get("edge_types", [])]

        # Build ontology context for the LLM
        entity_desc = "\n".join(
            f"- {e['name']}: {e.get('description', '')}"
            for e in ontology.get("entity_types", [])
        )
        edge_desc = "\n".join(
            f"- {e['name']}: {e.get('description', '')} (source: {', '.join(st['source'] for st in e.get('source_targets', []))}, target: {', '.join(st['target'] for st in e.get('source_targets', []))})"
            for e in ontology.get("edge_types", [])
        )

        system_prompt = f"""Extract entities and relationships from the text using ONLY these types.

Entity types:
{entity_desc}

Relationship types:
{edge_desc}

Return valid JSON:
{{
  "entities": [
    {{"name": "...", "type": "EntityTypeName", "summary": "one sentence description"}}
  ],
  "edges": [
    {{"source": "entity name", "target": "entity name", "type": "EdgeTypeName", "fact": "one sentence describing the relationship"}}
  ]
}}

Be thorough. Extract every entity and relationship mentioned. Use exact entity type names from the list above."""

        all_entities: Dict[str, Dict[str, Any]] = {}  # name -> entity data (dedup)
        all_edges: List[Dict[str, Any]] = []

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"Extracting from chunk {i + 1}/{len(chunks)}...",
                    (i + 1) / len(chunks),
                )

            try:
                result = llm.chat_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk},
                    ],
                    temperature=0.2,
                    max_tokens=4096,
                )

                # Collect entities (dedup by name)
                for ent in result.get("entities", []):
                    name = ent.get("name", "").strip()
                    etype = ent.get("type", "Entity")
                    if name and etype in entity_types:
                        if name not in all_entities:
                            all_entities[name] = {
                                "name": name,
                                "type": etype,
                                "summary": ent.get("summary", ""),
                            }

                # Collect edges
                for edge in result.get("edges", []):
                    src = edge.get("source", "").strip()
                    tgt = edge.get("target", "").strip()
                    etype = edge.get("type", "")
                    if src and tgt and etype in edge_types:
                        all_edges.append({
                            "source": src,
                            "target": tgt,
                            "type": etype,
                            "fact": edge.get("fact", f"{src} {etype} {tgt}"),
                        })

            except Exception as e:
                # Non-fatal: skip chunk if LLM fails
                pass

        # Upsert entities into Qdrant
        if all_entities:
            entity_points = []
            for name, ent in all_entities.items():
                eid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{graph_id}_entity_{name}"))
                text_for_embed = f"{name}: {ent['summary']}" if ent["summary"] else name
                entity_points.append(
                    PointStruct(
                        id=eid,
                        vector={"text-dense": {"text": text_for_embed, "model": QCI_MODEL}},
                        payload={
                            "graph_id": graph_id,
                            "point_type": "entity",
                            "name": name,
                            "entity_type": ent["type"],
                            "labels": ["Entity", ent["type"]],
                            "summary": ent.get("summary", ""),
                            "attributes": {},
                        },
                    )
                )
            self.client.upsert(collection_name=COLLECTION_NAME, points=entity_points)

        # Upsert edges into Qdrant
        if all_edges:
            edge_points = []
            for edge in all_edges:
                eid = str(uuid.uuid4())
                fact_text = edge["fact"]
                edge_points.append(
                    PointStruct(
                        id=eid,
                        vector={"text-dense": {"text": fact_text, "model": QCI_MODEL}},
                        payload={
                            "graph_id": graph_id,
                            "point_type": "edge",
                            "name": edge["type"],
                            "fact": edge["fact"],
                            "source_name": edge["source"],
                            "target_name": edge["target"],
                            "attributes": {},
                        },
                    )
                )
            self.client.upsert(collection_name=COLLECTION_NAME, points=edge_points)

    # ------------------------------------------------------------------
    # Graph info and data retrieval
    # ------------------------------------------------------------------

    def _scroll_by_graph(
        self,
        graph_id: str,
        point_type: Optional[str] = None,
    ) -> list:
        """Scroll all points for a given graph_id, optionally filtered by point_type."""
        conditions = [
            FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
        ]
        if point_type:
            conditions.append(
                FieldCondition(key="point_type", match=MatchValue(value=point_type)),
            )

        all_points = []
        offset = None

        while True:
            results, next_offset = self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(must=conditions),
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_points.extend(results)
            if next_offset is None:
                break
            offset = next_offset

        return all_points

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """Gather summary statistics for a graph."""
        entities = self._scroll_by_graph(graph_id, point_type="entity")
        edges = self._scroll_by_graph(graph_id, point_type="edge")

        entity_types: set = set()
        for point in entities:
            payload = point.payload or {}
            etype = payload.get("entity_type")
            if etype:
                entity_types.add(etype)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(entities),
            edge_count=len(edges),
            entity_types=list(entity_types),
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        Return full graph data including entities, edges, and chunks.
        """
        all_points = self._scroll_by_graph(graph_id)

        nodes_data = []
        edges_data = []
        chunks_data = []

        # Build a node map for resolving edge source/target names
        node_map: Dict[str, str] = {}
        for point in all_points:
            payload = point.payload or {}
            if payload.get("point_type") == "entity":
                node_map[str(point.id)] = payload.get("name", "")

        for point in all_points:
            payload = point.payload or {}
            ptype = payload.get("point_type")

            if ptype == "entity":
                nodes_data.append({
                    "uuid": str(point.id),
                    "name": payload.get("name", ""),
                    "labels": payload.get("labels", []),
                    "entity_type": payload.get("entity_type", ""),
                    "summary": payload.get("summary", ""),
                    "attributes": payload.get("attributes", {}),
                    "created_at": payload.get("created_at"),
                })

            elif ptype == "edge":
                source_id = payload.get("source_node_uuid", "")
                target_id = payload.get("target_node_uuid", "")
                edges_data.append({
                    "uuid": str(point.id),
                    "name": payload.get("name", ""),
                    "fact": payload.get("fact", ""),
                    "fact_type": payload.get("fact_type", ""),
                    "source_node_uuid": source_id,
                    "target_node_uuid": target_id,
                    "source_node_name": node_map.get(source_id, ""),
                    "target_node_name": node_map.get(target_id, ""),
                    "attributes": payload.get("attributes", {}),
                    "created_at": payload.get("created_at"),
                })

            elif ptype == "chunk":
                chunks_data.append({
                    "uuid": str(point.id),
                    "content": payload.get("content", ""),
                })

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "chunks": chunks_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
            "chunk_count": len(chunks_data),
        }

    def get_ontology(self, graph_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the stored ontology for a graph."""
        points = self._scroll_by_graph(graph_id, point_type="ontology")
        if not points:
            return None
        payload = points[0].payload or {}
        raw = payload.get("ontology_raw")
        if raw:
            return json.loads(raw)
        return {
            "entity_types": payload.get("entity_types", []),
            "edge_types": payload.get("edge_types", []),
        }

    def delete_graph(self, graph_id: str):
        """Delete all points belonging to a graph."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
                ]
            ),
        )

    def query_graph(
        self,
        graph_id: str,
        query_text: str,
        point_type: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """
        Semantic search within a graph using QCI.
        Returns matching points ranked by relevance.
        """
        conditions = [
            FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
        ]
        if point_type:
            conditions.append(
                FieldCondition(key="point_type", match=MatchValue(value=point_type)),
            )

        results = self.client.query(
            collection_name=COLLECTION_NAME,
            query={"text": query_text, "model": QCI_MODEL}, using="text-dense",
            query_filter=Filter(must=conditions),
            limit=limit,
            with_payload=True,
        )

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]
