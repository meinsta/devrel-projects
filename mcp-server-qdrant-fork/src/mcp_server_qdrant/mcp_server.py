import json
import logging
from typing import Annotated, Any, Optional

from fastmcp import Context, FastMCP
from pydantic import Field
from qdrant_client import models

from mcp_server_qdrant.common.filters import make_indexes
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.qdrant import (
    ArbitraryFilter,
    BatchEntry,
    Entry,
    Metadata,
    MultiVectorConnector,
    MultiVectorEntry,
    QdrantConnector,
)
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    MultiVectorSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)


# FastMCP is an alternative interface for declaring the capabilities
# of the server. Its API is based on FastAPI.
class QdrantMCPServer(FastMCP):
    """
    A MCP server for Qdrant.
    """

    def __init__(
        self,
        tool_settings: ToolSettings,
        qdrant_settings: QdrantSettings,
        embedding_provider_settings: Optional[EmbeddingProviderSettings] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        multi_vector_settings: Optional[MultiVectorSettings] = None,
        name: str = "mcp-server-qdrant",
        instructions: str | None = None,
        **settings: Any,
    ):
        self.tool_settings = tool_settings
        self.qdrant_settings = qdrant_settings
        self.multi_vector_settings = multi_vector_settings

        if embedding_provider_settings and embedding_provider:
            raise ValueError(
                "Cannot provide both embedding_provider_settings and embedding_provider"
            )

        if not embedding_provider_settings and not embedding_provider:
            raise ValueError(
                "Must provide either embedding_provider_settings or embedding_provider"
            )

        self.embedding_provider_settings: Optional[EmbeddingProviderSettings] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None

        if embedding_provider_settings:
            self.embedding_provider_settings = embedding_provider_settings
            self.embedding_provider = create_embedding_provider(
                embedding_provider_settings
            )
        else:
            self.embedding_provider_settings = None
            self.embedding_provider = embedding_provider

        assert self.embedding_provider is not None, "Embedding provider is required"

        self.qdrant_connector = QdrantConnector(
            qdrant_settings.location,
            qdrant_settings.api_key,
            qdrant_settings.collection_name,
            self.embedding_provider,
            qdrant_settings.local_path,
            make_indexes(qdrant_settings.filterable_fields_dict()),
        )

        # Multi-vector connector (optional, for named vectors support)
        self.multi_vector_connector: Optional[MultiVectorConnector] = None
        if multi_vector_settings and multi_vector_settings.enabled:
            vector_configs = multi_vector_settings.get_vector_config_dict()
            if vector_configs:
                self.multi_vector_connector = MultiVectorConnector(
                    qdrant_settings.location,
                    qdrant_settings.api_key,
                    qdrant_settings.collection_name,
                    vector_configs,
                    qdrant_settings.local_path,
                    make_indexes(qdrant_settings.filterable_fields_dict()),
                )

        super().__init__(name=name, instructions=instructions, **settings)

        self.setup_tools()

    def format_entry(self, entry: Entry) -> str:
        """
        Feel free to override this method in your subclass to customize the format of the entry.
        """
        entry_metadata = json.dumps(entry.metadata) if entry.metadata else ""
        return f"<entry><content>{entry.content}</content><metadata>{entry_metadata}</metadata></entry>"

    def setup_tools(self):
        """
        Register the tools in the server.
        """

        async def store(
            ctx: Context,
            information: Annotated[str, Field(description="Text to store")],
            collection_name: Annotated[
                str, Field(description="The collection to store the information in")
            ],
            # The `metadata` parameter is defined as non-optional, but it can be None.
            # If we set it to be optional, some of the MCP clients, like Cursor, cannot
            # handle the optional parameter correctly.
            metadata: Annotated[
                Metadata | None,
                Field(
                    description="Extra metadata stored along with memorised information. Any json is accepted."
                ),
            ] = None,
        ) -> str:
            """
            Store some information in Qdrant.
            :param ctx: The context for the request.
            :param information: The information to store.
            :param metadata: JSON metadata to store with the information, optional.
            :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                    the default collection is used.
            :return: A message indicating that the information was stored.
            """
            await ctx.debug(f"Storing information {information} in Qdrant")

            entry = Entry(content=information, metadata=metadata)

            await self.qdrant_connector.store(entry, collection_name=collection_name)
            if collection_name:
                return f"Remembered: {information} in collection {collection_name}"
            return f"Remembered: {information}"

        async def find(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str] | None:
            """
            Find memories in Qdrant.
            :param ctx: The context for the request.
            :param query: The query to use for the search.
            :param collection_name: The name of the collection to search in, optional. If not provided,
                                    the default collection is used.
            :param query_filter: The filter to apply to the query.
            :return: A list of entries found or None.
            """

            # Log query_filter
            await ctx.debug(f"Query filter: {query_filter}")

            query_filter = models.Filter(**query_filter) if query_filter else None

            await ctx.debug(f"Finding results for query {query}")

            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=query_filter,
            )
            if not entries:
                return None
            content = [
                f"Results for the query '{query}'",
            ]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        find_foo = find
        store_foo = store

        filterable_conditions = (
            self.qdrant_settings.filterable_fields_dict_with_conditions()
        )

        if len(filterable_conditions) > 0:
            find_foo = wrap_filters(find_foo, filterable_conditions)
        elif not self.qdrant_settings.allow_arbitrary_filter:
            find_foo = make_partial_function(find_foo, {"query_filter": None})

        if self.qdrant_settings.collection_name:
            find_foo = make_partial_function(
                find_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            store_foo = make_partial_function(
                store_foo, {"collection_name": self.qdrant_settings.collection_name}
            )

        self.tool(
            find_foo,
            name="qdrant-find",
            description=self.tool_settings.tool_find_description,
        )

        if not self.qdrant_settings.read_only:
            # Those methods can modify the database
            self.tool(
                store_foo,
                name="qdrant-store",
                description=self.tool_settings.tool_store_description,
            )

        # Register additional tools for batch operations and collection management
        self._setup_batch_tools()
        self._setup_collection_tools()

        # Register multi-vector tools if enabled
        if self.multi_vector_connector:
            self._setup_multi_vector_tools()

    def _setup_batch_tools(self):
        """
        Register batch operation tools.
        """

        async def store_batch(
            ctx: Context,
            documents: Annotated[
                list[str], Field(description="List of text documents to store")
            ],
            ids: Annotated[
                list[str], Field(description="List of unique IDs for each document")
            ],
            collection_name: Annotated[
                str, Field(description="The collection to store documents in")
            ],
            metadatas: Annotated[
                list[Metadata] | None,
                Field(description="Optional list of metadata dicts for each document"),
            ] = None,
        ) -> str:
            """
            Store multiple documents in Qdrant in a single batch operation.
            More efficient than storing one by one.
            :param ctx: The context for the request.
            :param documents: List of text documents to store.
            :param ids: List of unique IDs for each document (must match documents length).
            :param collection_name: The collection to store in.
            :param metadatas: Optional list of metadata dicts (must match documents length if provided).
            :return: A message indicating how many documents were stored.
            """
            if len(documents) != len(ids):
                raise ValueError(
                    f"documents and ids must have same length: {len(documents)} vs {len(ids)}"
                )

            if metadatas and len(metadatas) != len(documents):
                raise ValueError(
                    f"metadatas must match documents length: {len(metadatas)} vs {len(documents)}"
                )

            await ctx.debug(f"Batch storing {len(documents)} documents in {collection_name}")

            entries = []
            for i, (doc, doc_id) in enumerate(zip(documents, ids)):
                meta = metadatas[i] if metadatas else None
                entries.append(BatchEntry(id=doc_id, content=doc, metadata=meta))

            count = await self.qdrant_connector.store_batch(
                entries, collection_name=collection_name
            )

            return f"Stored {count} documents in collection {collection_name}"

        store_batch_foo = store_batch

        if self.qdrant_settings.collection_name:
            store_batch_foo = make_partial_function(
                store_batch_foo,
                {"collection_name": self.qdrant_settings.collection_name},
            )

        if not self.qdrant_settings.read_only:
            self.tool(
                store_batch_foo,
                name="qdrant-store-batch",
                description="Store multiple documents in Qdrant efficiently in a single batch operation.",
            )

    def _setup_collection_tools(self):
        """
        Register collection management and scroll tools.
        """

        async def get_collection_info(
            ctx: Context,
            collection_name: Annotated[
                str, Field(description="The collection to get info for")
            ],
        ) -> str:
            """
            Get information about a Qdrant collection.
            :param ctx: The context for the request.
            :param collection_name: The collection to get info for.
            :return: JSON string with collection info.
            """
            await ctx.debug(f"Getting collection info for {collection_name}")

            info = await self.qdrant_connector.get_collection_info(
                collection_name=collection_name
            )

            return json.dumps(info.model_dump())

        async def scroll(
            ctx: Context,
            collection_name: Annotated[
                str, Field(description="The collection to scroll through")
            ],
            limit: Annotated[
                int, Field(description="Maximum number of points to return")
            ] = 100,
            offset: Annotated[
                str | int | None,
                Field(description="Offset for pagination (from previous scroll result)"),
            ] = None,
            query_filter: ArbitraryFilter | None = None,
            with_payload: Annotated[
                list[str] | None,
                Field(description="List of payload fields to include, or None for all"),
            ] = None,
        ) -> str:
            """
            Scroll through points in a collection with pagination.
            Use this to iterate through all points or find existing document IDs.
            :param ctx: The context for the request.
            :param collection_name: The collection to scroll.
            :param limit: Max points to return (default 100).
            :param offset: Offset from previous scroll for pagination.
            :param query_filter: Optional filter to apply.
            :param with_payload: List of payload fields to include.
            :return: JSON with points and next_offset for pagination.
            """
            await ctx.debug(f"Scrolling collection {collection_name}, limit={limit}")

            filter_obj = models.Filter(**query_filter) if query_filter else None

            result = await self.qdrant_connector.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                query_filter=filter_obj,
                with_payload=with_payload if with_payload else True,
            )

            return json.dumps(result.model_dump())

        get_collection_info_foo = get_collection_info
        scroll_foo = scroll

        if self.qdrant_settings.collection_name:
            get_collection_info_foo = make_partial_function(
                get_collection_info_foo,
                {"collection_name": self.qdrant_settings.collection_name},
            )
            scroll_foo = make_partial_function(
                scroll_foo,
                {"collection_name": self.qdrant_settings.collection_name},
            )

        self.tool(
            get_collection_info_foo,
            name="qdrant-get-collection-info",
            description="Get information about a Qdrant collection (exists, points count, status).",
        )

        self.tool(
            scroll_foo,
            name="qdrant-scroll",
            description="Scroll through points in a collection with pagination. Useful for iterating all documents or checking existing IDs.",
        )

    def _setup_multi_vector_tools(self):
        """
        Register multi-vector (named vectors) tools.
        Only available when QDRANT_MULTI_VECTOR=true is configured.
        """
        assert self.multi_vector_connector is not None

        async def store_multi(
            ctx: Context,
            information: Annotated[str, Field(description="Text to store")],
            document_id: Annotated[str, Field(description="Unique ID for this document")],
            collection_name: Annotated[
                str, Field(description="The collection to store the information in")
            ],
            metadata: Annotated[
                Metadata | None,
                Field(description="Extra metadata stored along with the information"),
            ] = None,
        ) -> str:
            """
            Store a document with multiple vector embeddings (named vectors).
            Each document is embedded with ALL configured embedding models.
            This enables hybrid search across different embedding types.
            :param ctx: The context for the request.
            :param information: The text content to store.
            :param document_id: Unique identifier for this document.
            :param collection_name: The collection to store in.
            :param metadata: Optional metadata dict.
            :return: Confirmation message.
            """
            await ctx.debug(f"Multi-vector storing '{information[:50]}...' as {document_id}")

            entry = MultiVectorEntry(id=document_id, content=information, metadata=metadata)
            await self.multi_vector_connector.store_multi(entry, collection_name=collection_name)

            vector_names = self.multi_vector_connector.get_vector_names()
            return f"Stored document {document_id} with vectors: {', '.join(vector_names)}"

        async def store_multi_batch(
            ctx: Context,
            documents: Annotated[
                list[str], Field(description="List of text documents to store")
            ],
            ids: Annotated[
                list[str], Field(description="List of unique IDs for each document")
            ],
            collection_name: Annotated[
                str, Field(description="The collection to store documents in")
            ],
            metadatas: Annotated[
                list[Metadata] | None,
                Field(description="Optional list of metadata dicts for each document"),
            ] = None,
        ) -> str:
            """
            Store multiple documents with multiple vector embeddings (named vectors) in batch.
            More efficient than storing one by one.
            :param ctx: The context for the request.
            :param documents: List of text documents to store.
            :param ids: List of unique IDs (must match documents length).
            :param collection_name: The collection to store in.
            :param metadatas: Optional list of metadata dicts (must match documents length).
            :return: Confirmation message.
            """
            if len(documents) != len(ids):
                raise ValueError(
                    f"documents and ids must have same length: {len(documents)} vs {len(ids)}"
                )

            if metadatas and len(metadatas) != len(documents):
                raise ValueError(
                    f"metadatas must match documents length: {len(metadatas)} vs {len(documents)}"
                )

            await ctx.debug(f"Multi-vector batch storing {len(documents)} documents")

            entries = []
            for i, (doc, doc_id) in enumerate(zip(documents, ids)):
                meta = metadatas[i] if metadatas else None
                entries.append(MultiVectorEntry(id=doc_id, content=doc, metadata=meta))

            count = await self.multi_vector_connector.store_multi_batch(
                entries, collection_name=collection_name
            )

            vector_names = self.multi_vector_connector.get_vector_names()
            return f"Stored {count} documents with vectors: {', '.join(vector_names)}"

        async def find_single(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            vector_name: Annotated[
                str, Field(description="Which vector to search (e.g., 'code' or 'text')")
            ],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str] | None:
            """
            Search using a specific named vector embedding.
            Use this to search with a particular embedding model (e.g., code-optimized or general text).
            :param ctx: The context for the request.
            :param query: The search query.
            :param vector_name: Which named vector to use (e.g., 'code', 'text').
            :param collection_name: The collection to search.
            :param query_filter: Optional filter.
            :return: List of results or None.
            """
            filter_obj = models.Filter(**query_filter) if query_filter else None

            await ctx.debug(f"Searching '{query}' using vector '{vector_name}'")

            results = await self.multi_vector_connector.search_single(
                query,
                vector_name,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=filter_obj,
            )

            if not results:
                return None

            content = [f"Results for '{query}' using vector '{vector_name}':"]
            for r in results:
                entry = Entry(content=r.content, metadata=r.metadata)
                content.append(f"[score={r.score:.4f}] {self.format_entry(entry)}")
            return content

        async def find_hybrid(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            vector_names: Annotated[
                list[str] | None,
                Field(description="Which vectors to combine (default: all)"),
            ] = None,
            fusion_method: Annotated[
                str,
                Field(description="Fusion method: 'rrf' (Reciprocal Rank Fusion) or 'dbsf' (Distribution-Based Score Fusion)"),
            ] = "rrf",
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str] | None:
            """
            Hybrid search across multiple named vectors with fusion.
            Combines results from different embedding models using RRF or DBSF.
            This is the killer feature - search with multiple embedding types simultaneously.
            :param ctx: The context for the request.
            :param query: The search query.
            :param collection_name: The collection to search.
            :param vector_names: Which vectors to combine (default: all configured vectors).
            :param fusion_method: 'rrf' (Reciprocal Rank Fusion) or 'dbsf' (Distribution-Based Score Fusion).
            :param query_filter: Optional filter.
            :return: List of fused results or None.
            """
            filter_obj = models.Filter(**query_filter) if query_filter else None

            used_vectors = vector_names or self.multi_vector_connector.get_vector_names()
            await ctx.debug(f"Hybrid search '{query}' across vectors: {used_vectors}")

            results = await self.multi_vector_connector.search_hybrid(
                query,
                vector_names=vector_names,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=filter_obj,
                fusion_method=fusion_method,
            )

            if not results:
                return None

            content = [
                f"Hybrid search results for '{query}' using {fusion_method.upper()} fusion across: {', '.join(used_vectors)}"
            ]
            for r in results:
                entry = Entry(content=r.content, metadata=r.metadata)
                content.append(f"[score={r.score:.4f}] {self.format_entry(entry)}")
            return content

        async def get_vector_config(
            ctx: Context,
        ) -> str:
            """
            Get the configured named vectors and their embedding models.
            :param ctx: The context for the request.
            :return: JSON string with vector configurations.
            """
            await ctx.debug("Getting vector configuration")

            config = {
                "enabled": True,
                "vectors": self.multi_vector_connector.get_vector_names(),
                "models": self.multi_vector_settings.get_vector_config_dict() if self.multi_vector_settings else {},
            }
            return json.dumps(config)

        # Apply collection_name partial if configured
        store_multi_foo = store_multi
        store_multi_batch_foo = store_multi_batch
        find_single_foo = find_single
        find_hybrid_foo = find_hybrid

        if self.qdrant_settings.collection_name:
            store_multi_foo = make_partial_function(
                store_multi_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            store_multi_batch_foo = make_partial_function(
                store_multi_batch_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            find_single_foo = make_partial_function(
                find_single_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            find_hybrid_foo = make_partial_function(
                find_hybrid_foo, {"collection_name": self.qdrant_settings.collection_name}
            )

        # Register multi-vector tools
        if not self.qdrant_settings.read_only:
            self.tool(
                store_multi_foo,
                name="qdrant-store-multi",
                description="Store a document with multiple vector embeddings (named vectors). Each document gets embedded with ALL configured models.",
            )
            self.tool(
                store_multi_batch_foo,
                name="qdrant-store-multi-batch",
                description="Batch store documents with multiple vector embeddings. More efficient than one-by-one.",
            )

        self.tool(
            find_single_foo,
            name="qdrant-find-single",
            description="Search using a specific named vector (e.g., 'code' for code-optimized search, 'text' for general).",
        )
        self.tool(
            find_hybrid_foo,
            name="qdrant-find-hybrid",
            description="Hybrid search across multiple vectors with RRF/DBSF fusion. Combines code + text embeddings for best results.",
        )
        self.tool(
            get_vector_config,
            name="qdrant-get-vector-config",
            description="Get the configured named vectors and their embedding models.",
        )
