"""Backwards compatibility shim. Use qdrant_paging instead."""
from .qdrant_paging import scroll_all, make_graph_filter

# Legacy function signatures for code that still imports from here
fetch_all_nodes = None  # removed: use scroll_all with point_type="entity"
fetch_all_edges = None  # removed: use scroll_all with point_type="edge"
