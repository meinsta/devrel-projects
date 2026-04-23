"""
Entity reader service backed by Qdrant.
Reads nodes and edges from a Qdrant collection, filters by predefined entity types.
"""

import os
import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from ..utils.logger import get_logger

logger = get_logger('mirofish.entity_reader')

COLLECTION_NAME = "mirofish_graph"

T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """Get entity type (excluding default Entity/Node labels)"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class EntityReader:
    """
    Entity reader backed by Qdrant.

    Reads entities and edges from the mirofish_graph collection.
    Points are distinguished by the `point_type` payload field:
      - "entity" for nodes
      - "edge" for edges
    All points within a graph share the same `graph_id` payload field.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        self.url = url or os.environ.get("QDRANT_URL")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")
        if not self.url:
            raise ValueError("QDRANT_URL is not configured")

        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
        )

    def _call_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0,
    ) -> T:
        """
        Call a function with exponential-backoff retry.

        Args:
            func: Zero-arg callable to execute.
            operation_name: Human-readable name for logging.
            max_retries: Maximum number of attempts.
            initial_delay: Seconds to wait before the first retry.

        Returns:
            The return value of func().
        """
        last_exception = None
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Qdrant {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(
                        f"Qdrant {operation_name} failed after {max_retries} attempts: {str(e)}"
                    )

        raise last_exception

    def _scroll_all(
        self,
        scroll_filter: Filter,
        operation_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Scroll through all matching points in the collection, handling pagination.

        Returns a list of payload dicts (each point's payload).
        """
        all_payloads: List[Dict[str, Any]] = []
        offset = None
        batch_size = 200

        while True:
            points, next_offset = self._call_with_retry(
                func=lambda _offset=offset: self.client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=scroll_filter,
                    limit=batch_size,
                    offset=_offset,
                    with_payload=True,
                ),
                operation_name=operation_name,
            )

            for point in points:
                payload = point.payload or {}
                payload["_point_id"] = point.id
                all_payloads.append(payload)

            if next_offset is None:
                break
            offset = next_offset

        return all_payloads

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Get all entity nodes for a graph.

        Args:
            graph_id: The graph identifier.

        Returns:
            List of node dicts with uuid, name, labels, summary, attributes.
        """
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        scroll_filter = Filter(must=[
            FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
            FieldCondition(key="point_type", match=MatchValue(value="entity")),
        ])

        raw_nodes = self._scroll_all(scroll_filter, f"get_all_nodes({graph_id})")

        nodes_data = []
        for payload in raw_nodes:
            nodes_data.append({
                "uuid": payload.get("uuid", ""),
                "name": payload.get("name", ""),
                "labels": payload.get("labels", []),
                "summary": payload.get("summary", ""),
                "attributes": payload.get("attributes", {}),
            })

        logger.info(f"Fetched {len(nodes_data)} nodes")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        Get all edges for a graph.

        Args:
            graph_id: The graph identifier.

        Returns:
            List of edge dicts.
        """
        logger.info(f"Fetching all edges for graph {graph_id}...")

        scroll_filter = Filter(must=[
            FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
            FieldCondition(key="point_type", match=MatchValue(value="edge")),
        ])

        raw_edges = self._scroll_all(scroll_filter, f"get_all_edges({graph_id})")

        edges_data = []
        for payload in raw_edges:
            edges_data.append({
                "uuid": payload.get("uuid", ""),
                "name": payload.get("name", ""),
                "fact": payload.get("fact", ""),
                "source_node_uuid": payload.get("source_node_uuid", ""),
                "target_node_uuid": payload.get("target_node_uuid", ""),
                "attributes": payload.get("attributes", {}),
            })

        logger.info(f"Fetched {len(edges_data)} edges")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all edges connected to a specific node (as source or target).

        This scrolls edges in the collection where source_node_uuid or
        target_node_uuid matches the given node_uuid.

        Args:
            node_uuid: The node UUID.

        Returns:
            List of edge dicts.
        """
        try:
            # Edges where this node is the source
            source_filter = Filter(must=[
                FieldCondition(key="point_type", match=MatchValue(value="edge")),
                FieldCondition(key="source_node_uuid", match=MatchValue(value=node_uuid)),
            ])
            source_edges = self._scroll_all(source_filter, f"get_node_edges(source={node_uuid[:8]}...)")

            # Edges where this node is the target
            target_filter = Filter(must=[
                FieldCondition(key="point_type", match=MatchValue(value="edge")),
                FieldCondition(key="target_node_uuid", match=MatchValue(value=node_uuid)),
            ])
            target_edges = self._scroll_all(target_filter, f"get_node_edges(target={node_uuid[:8]}...)")

            edges_data = []
            seen_ids = set()
            for payload in source_edges + target_edges:
                edge_uuid = payload.get("uuid", "")
                if edge_uuid in seen_ids:
                    continue
                seen_ids.add(edge_uuid)
                edges_data.append({
                    "uuid": edge_uuid,
                    "name": payload.get("name", ""),
                    "fact": payload.get("fact", ""),
                    "source_node_uuid": payload.get("source_node_uuid", ""),
                    "target_node_uuid": payload.get("target_node_uuid", ""),
                    "attributes": payload.get("attributes", {}),
                })

            return edges_data
        except Exception as e:
            logger.warning(f"Failed to get edges for node {node_uuid}: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        """
        Filter nodes to those matching predefined entity types.

        Filtering logic:
        - If a node's labels contain only "Entity" or "Node", it is skipped.
        - If a node has labels beyond "Entity"/"Node", it is kept.
        - If defined_entity_types is provided, only nodes with matching labels are kept.

        Args:
            graph_id: The graph identifier.
            defined_entity_types: Optional list of allowed entity type labels.
            enrich_with_edges: Whether to attach related edge/node info.

        Returns:
            FilteredEntities with matching entities.
        """
        logger.info(f"Filtering entities for graph {graph_id}...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []

        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])

            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids: Set[str] = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(
            f"Filtering complete: {total_count} total nodes, {len(filtered_entities)} matched, "
            f"entity types: {entity_types_found}"
        )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str,
    ) -> Optional[EntityNode]:
        """
        Get a single entity with its full context (edges and related nodes).

        Args:
            graph_id: The graph identifier.
            entity_uuid: The entity's UUID.

        Returns:
            EntityNode with related edges/nodes, or None on failure.
        """
        try:
            # Retrieve the entity node by scrolling with uuid filter
            scroll_filter = Filter(must=[
                FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
                FieldCondition(key="point_type", match=MatchValue(value="entity")),
                FieldCondition(key="uuid", match=MatchValue(value=entity_uuid)),
            ])

            results = self._scroll_all(scroll_filter, f"get_entity({entity_uuid[:8]}...)")

            if not results:
                return None

            node_payload = results[0]

            # Get edges for this node
            edges = self.get_node_edges(entity_uuid)

            # Get all nodes for the graph to resolve related node info
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids: Set[str] = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=node_payload.get("uuid", ""),
                name=node_payload.get("name", ""),
                labels=node_payload.get("labels", []),
                summary=node_payload.get("summary", ""),
                attributes=node_payload.get("attributes", {}),
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"Failed to get entity {entity_uuid}: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        """
        Get all entities of a specific type.

        Args:
            graph_id: The graph identifier.
            entity_type: The entity type label (e.g. "Student", "PublicFigure").
            enrich_with_edges: Whether to attach related edge info.

        Returns:
            List of matching EntityNode objects.
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return result.entities


# Backwards compat
ZepEntityReader = EntityReader
