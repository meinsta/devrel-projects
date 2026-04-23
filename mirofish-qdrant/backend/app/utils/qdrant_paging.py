"""Qdrant scroll-based pagination utility.

Replaces the Zep cursor-based paging. Qdrant uses offset-based scrolling
with optional point ID cursors.
"""

from __future__ import annotations

import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from .logger import get_logger

logger = get_logger('mirofish.qdrant_paging')

_DEFAULT_PAGE_SIZE = 100
_MAX_ITEMS = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0


def _scroll_with_retry(
    client: QdrantClient,
    collection_name: str,
    scroll_filter: Filter | None = None,
    limit: int = _DEFAULT_PAGE_SIZE,
    offset: str | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
) -> tuple[list[Any], str | None]:
    """Single scroll page with retry on transient errors."""
    last_exception: Exception | None = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            points, next_offset = client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            return points, next_offset
        except (ConnectionError, TimeoutError, OSError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Qdrant {page_description} attempt {attempt + 1} failed: "
                    f"{str(e)[:100]}, retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(
                    f"Qdrant {page_description} failed after {max_retries} attempts: {str(e)}"
                )

    assert last_exception is not None
    raise last_exception


def scroll_all(
    client: QdrantClient,
    collection_name: str,
    scroll_filter: Filter | None = None,
    max_items: int = _MAX_ITEMS,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """Scroll through all matching points in a collection."""
    all_points: list[Any] = []
    offset: str | None = None
    page_num = 0

    while True:
        page_num += 1
        points, next_offset = _scroll_with_retry(
            client=client,
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=page_size,
            offset=offset,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"scroll page {page_num}",
        )

        if not points:
            break

        all_points.extend(points)
        if len(all_points) >= max_items:
            all_points = all_points[:max_items]
            logger.warning(f"Reached limit ({max_items}), stopping pagination")
            break

        if next_offset is None:
            break
        offset = next_offset

    return all_points


def make_graph_filter(graph_id: str, point_type: str | None = None) -> Filter:
    """Build a Qdrant filter for graph_id and optional point_type."""
    conditions = [
        FieldCondition(key="graph_id", match=MatchValue(value=graph_id)),
    ]
    if point_type:
        conditions.append(
            FieldCondition(key="point_type", match=MatchValue(value=point_type)),
        )
    return Filter(must=conditions)
