# Qdrant Documentation Map

This is a comprehensive map of all Qdrant documentation pages, organized by topic for easy navigation.

> **Note:** Use these URLs with the `fetch_doc` tool to get full page content.
> Source: https://qdrant.tech/llms.txt
> Last verified: 2026-02-19 against Qdrant v1.16.3

## Document Structure

* **##** marks documentation groups
* **###** marks individual documentation pages
* Each page links to the full documentation URL
* Brief descriptions help you pick the right page

## Overview

### [What is Qdrant?](https://qdrant.tech/documentation/overview/)
Vector database for AI: stores embeddings, fast similarity search, multiple distance metrics, production-ready.

### [Understanding Vector Search](https://qdrant.tech/documentation/overview/vector-search/)
Dense embeddings vs sparse vectors, HNSW indexing, how semantic search works.

### [Qdrant Fundamentals FAQ](https://qdrant.tech/documentation/faq/qdrant-fundamentals/)
Max dimensions (65,535), multiple vectors per point, multitenancy recommendations, version upgrades.

### [Database Optimization FAQ](https://qdrant.tech/documentation/faq/database-optimization/)
Quantization config, on-disk vectors, payload indexing, memory limits, performance tuning.

## Getting Started

### [Local Quickstart](https://qdrant.tech/documentation/quickstart/)
Docker setup, create collections, add vectors, run searches. All client libraries.

### [Cloud Quickstart](https://qdrant.tech/documentation/quickstart-cloud/)
Sign up, create cluster, get API key, connect with SDKs.

### [Data Ingestion for Beginners](https://qdrant.tech/documentation/data-ingestion-beginners/)
S3 to Qdrant pipeline: extract text/images, generate embeddings, store in Qdrant.

## Core Concepts

### [Concepts Overview](https://qdrant.tech/documentation/concepts/)
Glossary: Collections, Payloads, Points, Search, Explore, Filtering, Hybrid Queries, Inference, Indexing, Snapshots.

### [Collections](https://qdrant.tech/documentation/concepts/collections/)
Create/configure collections. Distance metrics (dot, cosine, euclidean). Named vectors, sparse vectors, multitenancy, on-disk storage, indexing options.

### [Points](https://qdrant.tech/documentation/concepts/points/)
Core data structure: vectors + payloads. Dense, sparse, named vectors. Batch upload, update, delete. Write-ahead-log consistency.

### [Vectors](https://qdrant.tech/documentation/concepts/vectors/)
Dense, sparse, multivectors, named vectors. Data types: Float32, Float16, Uint8. Memory optimization.

### [Payload](https://qdrant.tech/documentation/concepts/payload/)
JSON metadata alongside vectors. Types: int, float, keyword, geo, datetime. Set, overwrite, clear, delete, index operations.

### [Search](https://qdrant.tech/documentation/concepts/search/)
Query API: k-NN, filtered search, recommendations, hybrid queries. Cosine similarity, batch search, exact vs approximate.

### [Explore](https://qdrant.tech/documentation/concepts/explore/)
Recommendation API, Discovery API. Average vector, best score, sum scores strategies. Multi-vector, batch, inter-collection lookup.

### [Hybrid Queries](https://qdrant.tech/documentation/concepts/hybrid-queries/)
Query API for multi-stage search. Prefetch, fusion (rrf with configurable k, dbsf), re-scoring, MMR diversity, score boosting.

### [Filtering](https://qdrant.tech/documentation/concepts/filtering/)
AND/OR/NOT clauses. Match, MatchAny, MatchExcept, TextAny, nested filters. Payload and point ID conditions. ASCII folding.

### [Inference](https://qdrant.tech/documentation/concepts/inference/)
Server-side embedding generation. Generate, store, and index embeddings in a single API call. Cloud-hosted and external provider models.

### [Optimizer](https://qdrant.tech/documentation/concepts/optimizer/)
Vacuum (delete cleanup), Merge (consolidate segments), Indexing (dynamic index/memmap). All configurable.

### [Storage](https://qdrant.tech/documentation/concepts/storage/)
Segments: appendable vs non-appendable. In-memory vs memmap. Gridstore backend. Payload storage options. Configurable thresholds.

### [Indexing](https://qdrant.tech/documentation/concepts/indexing/)
HNSW vector index + payload indexes. Parameterized, on-disk options. Tenant and principal indexes for multi-tenant. GPU-accelerated indexing.

### [Snapshots](https://qdrant.tech/documentation/concepts/snapshots/)
Tar archives of collection data. Per-node snapshots in distributed mode. Restore via URL, file upload, or startup param.

## Guides

### [Installation](https://qdrant.tech/documentation/guides/installation/)
64-bit CPU required. Qdrant Cloud, Kubernetes (Helm), Docker. Ports 6333/6334/6335. Storage requirements.

### [Configuration](https://qdrant.tech/documentation/guides/configuration/)
Config files, env vars (highest priority). Merge order. Not available on Qdrant Cloud.

### [Administration](https://qdrant.tech/documentation/guides/administration/)
Recovery mode, strict mode. Runtime behavior modification. Lock API removed in v1.16.

### [Security](https://qdrant.tech/documentation/guides/security/)
API key auth (full + read-only), JWT RBAC, TLS. Internal ports need network-level restriction.

### [Distributed Deployment](https://qdrant.tech/documentation/guides/distributed_deployment/)
Multi-node clusters. Shard replication, rebalancing, resharding. 3+ nodes recommended for production.

### [Quantization](https://qdrant.tech/documentation/guides/quantization/)
Scalar, binary, 1.5-bit, 2-bit, asymmetric, product quantization. Memory reduction vs accuracy tradeoffs.

### [Optimize Performance](https://qdrant.tech/documentation/guides/optimize/)
Three strategies: quantization for speed, on-disk for low memory, RAM + quantization + rescore for both.

### [Capacity Planning](https://qdrant.tech/documentation/guides/capacity-planning/)
RAM/disk formulas based on vector count, dimensions, payload. 50% overhead for metadata/indexing.

### [Multitenancy](https://qdrant.tech/documentation/guides/multitenancy/)
Single collection with payload partitioning. Tiered multitenancy: tenant promotion from shared to dedicated shards. Tenant index for performance.

### [Text Search](https://qdrant.tech/documentation/guides/text-search/)
Full-text search with multilingual tokenization, stop words, stemming, phrase matching, ASCII folding. TextAny condition for multi-term matching.

### [Running with GPU](https://qdrant.tech/documentation/guides/running-with-gpu/)
NVIDIA/AMD/Intel GPU acceleration via Vulkan API. v1.13.0+. Docker images. Multi-GPU support. 16GB per-GPU limit.

### [Monitoring & Telemetry](https://qdrant.tech/documentation/guides/monitoring/)
Prometheus/OpenMetrics endpoints. /metrics, /sys_metrics, /telemetry. Health checks: /healthz, /livez, /readyz.

### [Common Errors](https://qdrant.tech/documentation/guides/common-errors/)
"Too many files open" fix. WAL errors. gRPC + multiprocessing issues. Solutions.

### [Usage Statistics](https://qdrant.tech/documentation/guides/usage-statistics/)
Anonymous telemetry. Disable with env var. No PII collected. Disabled by default on Cloud.

## Search Precision

### [Reranking in Semantic Search](https://qdrant.tech/documentation/search-precision/reranking-semantic-search/)
Cross-encoders, ColBERT multi-vector rerankers, LLM rerankers. Score-boosting reranker with formula expressions and decay functions.

### [Automate Filtering with LLMs](https://qdrant.tech/documentation/search-precision/automate-filtering-with-llms/)
LLM-generated structured filters for Qdrant. Instructor library. Schema-validated filter generation.

## API & SDKs

### [API & SDKs](https://qdrant.tech/documentation/interfaces/)
Python, JS/TS, Rust, Go, .NET, Java clients. REST (port 6333) and gRPC (port 6334) APIs.

### [Qdrant Web UI](https://qdrant.tech/documentation/web-ui/)
Dashboard at :6333/dashboard. REST API interaction, collection management, interactive tutorial.

## Tutorials: Basics

### [Semantic Search 101](https://qdrant.tech/documentation/tutorials-basics/search-beginners/)
Build a semantic search engine for books in 5 minutes. Python + Sentence Transformers.

## Tutorials: Search Engineering

### [Build a Neural Search Service](https://qdrant.tech/documentation/tutorials-search-engineering/neural-search/)
Encode company descriptions, store in Qdrant, serve via FastAPI.

### [Setup Hybrid Search with FastEmbed](https://qdrant.tech/documentation/tutorials-search-engineering/hybrid-search-fastembed/)
Dense + sparse embeddings, FastEmbed, Qdrant, FastAPI. Full tutorial.

### [Measure Search Quality](https://qdrant.tech/documentation/tutorials-search-engineering/retrieval-quality/)
Evaluate embeddings, compare ANN vs exact kNN, precision@k metrics.

### [Multivector Representations (ColBERT)](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/)
Token-level vectors for precise reranking. Disable HNSW for multivectors. ColBERT pipeline with FastEmbed.

### [Reranking in Hybrid Search](https://qdrant.tech/documentation/tutorials-search-engineering/reranking-hybrid-search/)
Dense + sparse + ColBERT embeddings. Multi-vector collection setup. Hybrid retrieval with reranking.

### [Search Through Your Codebase](https://qdrant.tech/documentation/tutorials-search-engineering/code-search/)
Semantic code search with Qdrant. Code chunking, NL conversion, embedding, ingestion pipeline.

### [Collaborative Filtering](https://qdrant.tech/documentation/tutorials-search-engineering/collaborative-filtering/)
Movie recommendations using sparse vectors of user ratings. No model training needed.

### [Scaling PDF Retrieval](https://qdrant.tech/documentation/tutorials-search-engineering/pdf-retrieval-at-scale/)
ColPali/ColQwen2 + mean pooling. Two-stage retrieval for large-scale PDF search.

### [Static Embeddings](https://qdrant.tech/documentation/tutorials-search-engineering/static-embeddings/)
400-500x faster than transformers. Minimal quality loss. Good for mobile/IoT.

## Tutorials: Operations & Scale

### [Create & Restore Snapshots](https://qdrant.tech/documentation/tutorials-operations/create-snapshot/)
Backup collections via HTTP endpoints. Download and restore. Python SDK requires Docker/Cloud.

### [Migration to Qdrant](https://qdrant.tech/documentation/tutorials-operations/migration/)
Migration tool: live batch streaming from other DBs (Pinecone). Resume, reconfigure. Docker.

### [Large-Scale Search](https://qdrant.tech/documentation/tutorials-operations/large-scale-search/)
LAION-400M (400M vectors) on 8 CPUs/64GB RAM. FLOAT16, binary quantization, on-disk storage.

### [Migrate to a New Embedding Model](https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/)
Conditional updates for safe concurrent embedding migration. Version-controlled point updates.

## Tutorials: Develop & Implement

### [Bulk Upload Vectors](https://qdrant.tech/documentation/tutorials-develop/bulk-upload/)
Fastest upload: Rust client, parallel uploads, disable HNSW during ingestion (m:0), re-enable after.

### [Build With Async API](https://qdrant.tech/documentation/tutorials-develop/async-api/)
AsyncQdrantClient for FastAPI/async apps. async/await pattern. Multi-user concurrency.

## FastEmbed

### [FastEmbed Overview](https://qdrant.tech/documentation/fastembed/)
Lightweight Python embedding library. 42+ models: dense, sparse, multivector, image, rerankers. Minimal dependencies, CPU-optimized.

### [FastEmbed Quickstart](https://qdrant.tech/documentation/fastembed/fastembed-quickstart/)
Install, load BAAI/bge-small-en-v1.5, embed documents, get 384-dim vectors.

### [FastEmbed Semantic Search](https://qdrant.tech/documentation/fastembed/fastembed-semantic-search/)
FastEmbed + Qdrant integration. In-memory vector search. Upload documents, query.

### [Working with SPLADE](https://qdrant.tech/documentation/fastembed/fastembed-splade/)
Sparse text vectors. Token expansion, importance ranking. Setup and interpretation.

### [Working with miniCOIL](https://qdrant.tech/documentation/fastembed/fastembed-minicoil/)
Sparse neural retriever. BM25 + contextual keyword scoring. Better than pure BM25.

### [Working with ColBERT](https://qdrant.tech/documentation/fastembed/fastembed-colbert/)
Multivector per-token embeddings. Strong reranking. Generate and upload to Qdrant.

### [Reranking with FastEmbed](https://qdrant.tech/documentation/fastembed/fastembed-rerankers/)
Cross-encoder rerankers. Jina Reranker v2. Retrieve then rerank pipeline.

### [Multi-Vector Postprocessing](https://qdrant.tech/documentation/fastembed/fastembed-postprocessing/)
Mean pooling, row-wise pooling for ColBERT/ColPali vectors. Reduce multivector overhead.

## Qdrant Edge

### [Qdrant Edge Overview](https://qdrant.tech/documentation/edge/)
Lightweight embedded vector search for on-device AI. No server process. Robotics, mobile, IoT.

### [Edge Quickstart](https://qdrant.tech/documentation/edge/edge-quickstart/)
Get started with Qdrant Edge for on-device vector search.

### [On-Device Embeddings](https://qdrant.tech/documentation/edge/edge-fastembed-embeddings/)
Local embedding generation with FastEmbed on edge devices.

### [Data Synchronization Patterns](https://qdrant.tech/documentation/edge/edge-data-synchronization-patterns/)
Patterns for syncing data between edge and cloud.

### [Synchronize with a Server](https://qdrant.tech/documentation/edge/edge-synchronization-guide/)
Step-by-step guide for edge-to-server data sync.

## Qdrant Cloud

### [Managed Cloud](https://qdrant.tech/documentation/cloud/)
SaaS: managed clusters, HA, scaling, monitoring, backups, disaster recovery. AWS/Azure/GCP.

### [Getting Started](https://qdrant.tech/documentation/cloud-getting-started/)
Create account, plan resources, deploy clusters. Terraform/API automation.

### [Account Setup](https://qdrant.tech/documentation/cloud-account-setup/)
Registration, user management, SSO for Premium. Multiple accounts.

### [Create a Cluster](https://qdrant.tech/documentation/cloud/create-cluster/)
Free (single-node, testing) and Standard (multi-node, HA, DR) tiers. 3+ nodes for production.

### [Configure Clusters](https://qdrant.tech/documentation/cloud/configure-cluster/)
Default collection settings, performance options, IP restrictions, restart modes, shard rebalancing.

### [Scale Clusters](https://qdrant.tech/documentation/cloud/cluster-scaling/)
Vertical (CPU/RAM/disk) and horizontal (add nodes). Resharding without downtime.

### [Update Clusters](https://qdrant.tech/documentation/cloud/cluster-upgrades/)
Version updates via console. Zero downtime with replication factor 2+.

### [Backup Clusters](https://qdrant.tech/documentation/cloud/backups/)
Automatic + manual backups. Snapshot API. Restore to previous state.

### [Monitor Clusters](https://qdrant.tech/documentation/cloud/cluster-monitoring/)
Metrics, logs, alerts. Prometheus-compatible endpoints. Grafana integration.

### [Cluster Access](https://qdrant.tech/documentation/cloud/cluster-access/)
Cluster UI, REST (6333), gRPC (6334). Load balanced. Node-specific endpoints.

### [Authentication](https://qdrant.tech/documentation/cloud/authentication/)
Database API keys with granular access. REST, gRPC, SDK auth. Rotate keys.

### [Inference](https://qdrant.tech/documentation/cloud/inference/)
Built-in embedding generation. Text and images. Cloud-hosted models (MiniLM, mxbai, SPLADE, BM25, CLIP) + external providers (OpenAI, Cohere, Jina, OpenRouter). 5M free tokens/month per text model.

### [Cloud API](https://qdrant.tech/documentation/cloud-api/)
gRPC + REST API for automation. Manage accounts, clusters. Terraform provider.

### [Billing & Payments](https://qdrant.tech/documentation/cloud-pricing-payments/)
Monthly billing: CPU, memory, disk. Credit card or marketplace (AWS/GCP/Azure).

### [Premium Tier](https://qdrant.tech/documentation/cloud-premium/)
24/7 support, 99.9% SLA, SSO, VPC Private Links, storage encryption.

### [Cloud RBAC](https://qdrant.tech/documentation/cloud-rbac/)
Role-based access control for Cloud console. Billing, clusters, hybrid cloud permissions.

### [Role Management](https://qdrant.tech/documentation/cloud-rbac/role-management/)
Built-in and custom roles. Create, edit, duplicate roles.

### [User Management](https://qdrant.tech/documentation/cloud-rbac/user-management/)
Invite users, assign roles. Revoke invites. Update active users.

### [Permission Reference](https://qdrant.tech/documentation/cloud-rbac/permission-reference/)
All Cloud permissions: IAM, clusters, API keys, backups, hybrid cloud, billing, account.

### [Infrastructure Tools](https://qdrant.tech/documentation/cloud-tools/)
Pulumi and Terraform for IaC.

### [Pulumi](https://qdrant.tech/documentation/cloud-tools/pulumi/)
Manage Qdrant Cloud via Pulumi SDK. Clusters, API keys.

### [Terraform](https://qdrant.tech/documentation/cloud-tools/terraform/)
Qdrant Terraform Provider. Automate cluster provisioning.

### [Support](https://qdrant.tech/documentation/support/)
Discord community. Jira portal for paying customers. Severity levels.

## Hybrid Cloud

### [Hybrid Cloud Overview](https://qdrant.tech/documentation/hybrid-cloud/)
Run on your Kubernetes. Data stays in your infrastructure. Operator + Cloud Agent.

### [Setup Hybrid Cloud](https://qdrant.tech/documentation/hybrid-cloud/hybrid-cloud-setup/)
Kubernetes requirements: CSI storage, cluster-admin, kubectl, helm. Installation steps.

### [Create Hybrid Cloud Cluster](https://qdrant.tech/documentation/hybrid-cloud/hybrid-cloud-cluster-creation/)
Select Hybrid Cloud Environment. Node selectors, tolerations, service types, auth.

### [Configure, Scale & Update](https://qdrant.tech/documentation/hybrid-cloud/configure-scale-upgrade/)
Vertical/horizontal scaling, shard rebalancing, resharding, version updates.

### [Networking, Logging & Monitoring](https://qdrant.tech/documentation/hybrid-cloud/networking-logging-monitoring/)
Network policies, kubectl logging, Prometheus/OTel endpoints, Grafana dashboards.

### [Operator Configuration](https://qdrant.tech/documentation/hybrid-cloud/operator-configuration/)
Advanced YAML config: resources, scheduling, storage, network, metrics, security.

### [Platform Deployment Options](https://qdrant.tech/documentation/hybrid-cloud/platform-deployment-options/)
Akamai, AWS, Civo, DigitalOcean, Gcore, GCP. Instance types, storage drivers.

## Private Cloud

### [Private Cloud Overview](https://qdrant.tech/documentation/private-cloud/)
Deploy on any Kubernetes. Zero-downtime upgrades, scaling, multi-AZ, backups, enterprise support.

### [Setup Private Cloud](https://qdrant.tech/documentation/private-cloud/private-cloud-setup/)
Kubernetes requirements. Helm installation. Namespace-scoped operator.

### [Private Cloud Configuration](https://qdrant.tech/documentation/private-cloud/configuration/)
Helm chart customization: replicas, images, security, networking, metrics, resources.

### [Cluster Management](https://qdrant.tech/documentation/private-cloud/qdrant-cluster-management/)
QdrantCluster resource. Unique IDs, labels, resources. TLS, API keys. Scaling, upgrading.

### [Backups](https://qdrant.tech/documentation/private-cloud/backups/)
QdrantClusterSnapshot for one-time, QdrantClusterScheduledSnapshot for recurring. Restore resource.

### [Logging & Monitoring](https://qdrant.tech/documentation/private-cloud/logging-monitoring/)
kubectl logs. External log systems. Prometheus/OTel metrics. Grafana dashboards.

### [API Reference](https://qdrant.tech/documentation/private-cloud/api-reference/)
qdrant.io/v1 schemas: clusters, regions, entities, GPU settings.

### [Changelog](https://qdrant.tech/documentation/private-cloud/changelog/)
Kubernetes component updates: metrics, shard balancing, GPU, OTel, P2P TLS.

## Agentic RAG

### [Simple Agentic RAG (CrewAI)](https://qdrant.tech/documentation/agentic-rag-crewai-zoom/)
Qdrant + CrewAI + Anthropic Claude. Meeting transcript analysis. Streamlit UI.

### [Agentic RAG With LangGraph](https://qdrant.tech/documentation/agentic-rag-langgraph/)
Multi-source retrieval: two Qdrant DBs + Brave Search. LangGraph orchestration.

### [Agentic RAG Discord Bot (CAMEL-AI)](https://qdrant.tech/documentation/agentic-rag-camelai-discord/)
Discord chatbot with multi-step reasoning. CAMEL-AI + Qdrant + OpenAI.

### [5 Minute RAG with DeepSeek](https://qdrant.tech/documentation/rag-deepseek/)
Quick RAG pipeline: Qdrant embeddings + DeepSeek LLM.

## Examples & Tutorials

### [Build Prototypes](https://qdrant.tech/documentation/examples/)
Index of end-to-end examples: chatbots, search, recommendations, extraction.

### [Multitenancy with LlamaIndex](https://qdrant.tech/documentation/examples/llama-index-multitenancy/)
Single collection, payload partitioning, tenant metadata, payload indexing.

### [GraphRAG with Neo4j](https://qdrant.tech/documentation/examples/graphrag-qdrant-neo4j/)
Knowledge graphs + vector search. Neo4j + Qdrant architecture.

### [Medical Chatbot (DSPy)](https://qdrant.tech/documentation/examples/qdrant-dspy-medicalbot/)
Chain-of-thought reasoning. Dense + ColBERT retrieval. Medical guardrails.

### [AI Customer Support](https://qdrant.tech/documentation/examples/rag-customer-support-cohere-airbyte-aws/)
Cohere + Qdrant + Airbyte on AWS. Private, multilingual support system.

### [Hybrid Search with LlamaIndex + Jina](https://qdrant.tech/documentation/examples/hybrid-search-llamaindex-jinaai/)
RAG chatbot for PDF manuals. Jina Embeddings, Qdrant, Mixtral LLM.

### [Cohere RAG Connector](https://qdrant.tech/documentation/examples/cohere-rag-connector/)
Custom HTTP connector for Cohere RAG. Qdrant backend. Inline citations.

### [Private RAG Engine (DSPy + Ollama)](https://qdrant.tech/documentation/examples/rag-chatbot-vultr-dspy-ollama/)
On-premise information extraction. Qdrant Hybrid Cloud. No external API calls.

### [Movie Recommendations](https://qdrant.tech/documentation/examples/recommendation-system-ovhcloud/)
Collaborative filtering with sparse vectors. MovieLens dataset. OVHcloud Kubernetes.

### [Blog-Reading Chatbot (GPT-4o)](https://qdrant.tech/documentation/examples/rag-chatbot-scaleway/)
RAG chatbot over blog content. Qdrant + LangChain + GPT-4o. Scaleway deployment.

### [Employee Onboarding RAG](https://qdrant.tech/documentation/examples/natural-language-search-oracle-cloud-infrastructure-cohere-langchain/)
Cohere + Qdrant + LangChain on Oracle Cloud. Company documentation search.

### [Contract Management (STACKIT)](https://qdrant.tech/documentation/examples/rag-contract-management-stackit-aleph-alpha/)
Region-specific, GDPR-compliant. Aleph Alpha + Qdrant Hybrid Cloud.

### [Private Chatbot (Red Hat OpenShift)](https://qdrant.tech/documentation/examples/rag-chatbot-red-hat-openshift-haystack/)
Mistral-7B + Qdrant + Haystack on OpenShift. Closed infrastructure.

### [Multilingual & Multimodal RAG (LlamaIndex)](https://qdrant.tech/documentation/multimodal-search/)
Text + image search with vdr-2b-multi-v1. Cross-lingual queries.

### [Cloud Inference Hybrid Search](https://qdrant.tech/documentation/tutorials-and-examples/cloud-inference-hybrid-search/)
Dense + BM25 sparse + RRF fusion. Qdrant Cloud inference API.

### [Monitoring with Prometheus & Grafana](https://qdrant.tech/documentation/tutorials-and-examples/hybrid-cloud-prometheus/)
Kubernetes monitoring setup. ServiceMonitors, Grafana dashboards.

## Data Pipelines

### [Send Data to Qdrant](https://qdrant.tech/documentation/send-data/)
Kafka, Databricks/Spark, Airflow/Astronomer. Migration guide link.

### [Qdrant on Databricks](https://qdrant.tech/documentation/send-data/databricks/)
FastEmbed vectorization + Spark connector. Dense + sparse embeddings.

### [Airflow + Astronomer](https://qdrant.tech/documentation/send-data/qdrant-airflow-astronomer/)
Parallel embedding DAG. Semantic retrieval for book recommendations.

### [Kafka Streaming](https://qdrant.tech/documentation/send-data/data-streaming-kafka-qdrant/)
Real-time pipeline: Kafka + MongoDB + Azure Blob + Qdrant. Sink connector.

### [Automating with n8n](https://qdrant.tech/documentation/qdrant-n8n/)
Low-code workflows: recommendations, big data analysis, anomaly detection.

## Embeddings Providers

### [Embeddings Overview](https://qdrant.tech/documentation/embeddings/)
All supported providers: OpenAI, Bedrock, Cohere, HuggingFace, and more.

### [OpenAI](https://qdrant.tech/documentation/embeddings/openai/)
Ada-003 integration. Binary quantization compatible.

### [Cohere](https://qdrant.tech/documentation/embeddings/cohere/)
Embed v3 with input types. Dense + sparse support.

### [Jina Embeddings](https://qdrant.tech/documentation/embeddings/jina-embeddings/)
jina-embeddings-v4: multilingual, code, text-matching. Matryoshka + Late Chunking.

### [Gemini](https://qdrant.tech/documentation/embeddings/gemini/)
Google Gemini models. Binary quantization support.

### [Mistral](https://qdrant.tech/documentation/embeddings/mistral/)
Mistral embedding API. Binary quantization compatible.

### [AWS Bedrock](https://qdrant.tech/documentation/embeddings/bedrock/)
Titan Embeddings. 1536-dim vectors.

### [Ollama](https://qdrant.tech/documentation/embeddings/ollama/)
Local embedding models for niche RAG.

### [Voyage AI](https://qdrant.tech/documentation/embeddings/voyage/)
voyage-large-2 model integration.

### [Nomic](https://qdrant.tech/documentation/embeddings/nomic/)
nomic-embed-text-v1. 8192 context. FastEmbed or API.

### [Nvidia](https://qdrant.tech/documentation/embeddings/nvidia/)
NV-Embed-QA model via Nvidia API.

### [Snowflake](https://qdrant.tech/documentation/embeddings/snowflake/)
snowflake-arctic-embed-s from HuggingFace.

### [Upstage](https://qdrant.tech/documentation/embeddings/upstage/)
Solar Embeddings. 4096-dim. Dual models for docs/queries.

### [MixedBread](https://qdrant.tech/documentation/embeddings/mixedbread/)
State-of-the-art embeddings for search and RAG.

### [Aleph Alpha](https://qdrant.tech/documentation/embeddings/aleph-alpha/)
Multimodal + multilingual. Shared latent space for text and images.

### [Prem AI](https://qdrant.tech/documentation/embeddings/premai/)
Unified platform for developing, deploying, monitoring GenAI.

### [Twelve Labs](https://qdrant.tech/documentation/embeddings/twelvelabs/)
Video, text, image, audio embeddings. Cross-modal search.

### [Mixpeek](https://qdrant.tech/documentation/embeddings/mixpeek/)
Video chunking and embedding for semantic search.

## Frameworks (37 integrations)

### [Frameworks Overview](https://qdrant.tech/documentation/frameworks/)
Index of all framework integrations.

### [LangChain](https://qdrant.tech/documentation/frameworks/langchain/)
Dense, sparse, hybrid retrieval. Flexible deployment. Minimal boilerplate.

### [LangChain4J](https://qdrant.tech/documentation/frameworks/langchain4j/)
Java port. langchain4j-qdrant module.

### [LangGraph](https://qdrant.tech/documentation/frameworks/langgraph/)
Stateful multi-actor workflows. Qdrant retrieval nodes.

### [LlamaIndex](https://qdrant.tech/documentation/frameworks/llama-index/)
Connect external data to LLMs. QdrantClient integration.

### [Haystack](https://qdrant.tech/documentation/frameworks/haystack/)
QdrantDocumentStore. Scalar quantization support.

### [DSPy](https://qdrant.tech/documentation/frameworks/dspy/)
Declarative LM programming. Qdrant as retriever.

### [CrewAI](https://qdrant.tech/documentation/frameworks/crewai/)
Multi-agent framework. Short-term + entity memory with Qdrant.

### [AutoGen](https://qdrant.tech/documentation/frameworks/autogen/)
Microsoft multi-agent conversations. Qdrant retrieval.

### [CAMEL](https://qdrant.tech/documentation/frameworks/camel/)
LLM-based agents. QdrantStorage class. Auto Retriever.

### [SmolAgents](https://qdrant.tech/documentation/frameworks/smolagents/)
HuggingFace code-based agents. Qdrant for semantic search.

### [Agno](https://qdrant.tech/documentation/frameworks/agno/)
Fast multi-agent framework with runtime and control plane.

### [Google ADK](https://qdrant.tech/documentation/frameworks/google-adk/)
Google's Python framework for building AI agents.

### [Semantic-Router](https://qdrant.tech/documentation/frameworks/semantic-router/)
Vector-based routing for LLM tool selection.

### [Mem0](https://qdrant.tech/documentation/frameworks/mem0/)
Self-improving memory layer for LLMs. Qdrant backend.

### [Spring AI](https://qdrant.tech/documentation/frameworks/spring-ai/)
Java/Spring Boot. Auto-create collections.

### [Dagster](https://qdrant.tech/documentation/frameworks/dagster/)
Data orchestration with Qdrant vector searches.

### [Feast](https://qdrant.tech/documentation/frameworks/feast/)
Feature store with Qdrant as online vector store.

### [FiftyOne](https://qdrant.tech/documentation/frameworks/fifty-one/)
Computer vision toolkit. Image + text similarity search.

### [Firebase Genkit](https://qdrant.tech/documentation/frameworks/genkit/)
JS/TS AI apps. Qdrant-Genkit plugin for semantic retrieval.

### [HoneyHive](https://qdrant.tech/documentation/frameworks/honeyhive/)
AI observability. Trace RAG pipelines with Qdrant.

### [Mastra](https://qdrant.tech/documentation/frameworks/mastra/)
TypeScript AI framework. Qdrant vector store.

### [Neo4j GraphRAG](https://qdrant.tech/documentation/frameworks/neo4j-graphrag/)
Graph + vector retrieval. Qdrant for vector queries.

### [Microsoft GraphRAG](https://qdrant.tech/documentation/frameworks/microsoft-graphrag/)
Knowledge graphs from unstructured data.

### [Microsoft NLWeb](https://qdrant.tech/documentation/frameworks/nlweb/)
Natural language website interfaces. Qdrant as vector backend.

### [Rig-rs](https://qdrant.tech/documentation/frameworks/rig-rs/)
Rust LLM library. Qdrant document storage and retrieval.

### [Swiftide](https://qdrant.tech/documentation/frameworks/swiftide/)
Rust library for streaming indexing/querying pipelines.

### [Sycamore](https://qdrant.tech/documentation/frameworks/sycamore/)
LLM-powered document processing. Qdrant connectors.

### [Testcontainers](https://qdrant.tech/documentation/frameworks/testcontainers/)
Docker-based integration testing. Qdrant module.

### [txtai](https://qdrant.tech/documentation/frameworks/txtai/)
Semantic search with neural embeddings. Qdrant backend.

### [Vanna.AI](https://qdrant.tech/documentation/frameworks/vanna-ai/)
Natural language to SQL. Qdrant as vector store.

### [VectaX (Mirror Security)](https://qdrant.tech/documentation/frameworks/mirror-security/)
Similarity-preserving encryption + RBAC for vectors.

### [VoltAgent](https://qdrant.tech/documentation/frameworks/voltagent/)
TypeScript AI agents. Qdrant vector search integration.

### [DeepEval](https://qdrant.tech/documentation/frameworks/deepeval/)
LLM output testing. RAG pipeline evaluation with Qdrant.

### [Dynamiq](https://qdrant.tech/documentation/frameworks/dynamiq/)
Gen AI framework. Qdrant retriever/writer nodes.

### [AWS Lakechain](https://qdrant.tech/documentation/frameworks/lakechain/)
CDK document processing pipelines. Qdrant storage connector.

### [Cheshire Cat](https://qdrant.tech/documentation/frameworks/cheshire-cat/)
Open-source agent framework. Qdrant as default vector memory.

### [Cognee](https://qdrant.tech/documentation/frameworks/cognee/)
AI memory framework. 30+ data source loading to graph/vector stores.

## Data Management

### [Data Management Overview](https://qdrant.tech/documentation/data-management/)
ETL/ELT integrations: Airbyte, Airflow, Spark, Kafka, and more.

### [Airbyte](https://qdrant.tech/documentation/data-management/airbyte/)
Open-source data replication. Qdrant as destination. Embedding configs.

### [Apache Airflow](https://qdrant.tech/documentation/data-management/airflow/)
Workflow orchestration. Qdrant provider: hooks and operators.

### [Apache Spark](https://qdrant.tech/documentation/data-management/spark/)
Qdrant-Spark connector. Batch writes. Databricks compatible.

### [Confluent Kafka](https://qdrant.tech/documentation/data-management/confluent/)
Kafka Sink Connector for streaming to Qdrant.

### [CocoIndex](https://qdrant.tech/documentation/data-management/cocoindex/)
Stateful ETL with incremental processing. Qdrant as vector DB.

### [DLT](https://qdrant.tech/documentation/data-management/dlt/)
Python data loading. Schema inference. Qdrant destination.

### [InfinyOn Fluvio](https://qdrant.tech/documentation/data-management/fluvio/)
Rust data streaming. Qdrant connector with delivery guarantees.

### [Redpanda Connect](https://qdrant.tech/documentation/data-management/redpanda/)
Declarative streaming. Qdrant output component.

### [Unstructured](https://qdrant.tech/documentation/data-management/unstructured/)
Text preprocessing. Qdrant ingestion destination.

## Platforms

### [Platforms Overview](https://qdrant.tech/documentation/platforms/)
Web scraping, workflow automation, RAG interfaces.

### [Apify](https://qdrant.tech/documentation/platforms/apify/)
Web scraping. Website Content Crawler to Qdrant.

### [BuildShip](https://qdrant.tech/documentation/platforms/buildship/)
Low-code backend builder. Qdrant semantic search nodes.

### [Keboola](https://qdrant.tech/documentation/platforms/keboola/)
Data operations. Qdrant component for RAG workflows.

### [Kotaemon](https://qdrant.tech/documentation/platforms/kotaemon/)
Open-source RAG UI. Qdrant as vectorstore.

### [Make.com](https://qdrant.tech/documentation/platforms/make/)
No-code automation. Qdrant integration modules.

### [N8N](https://qdrant.tech/documentation/platforms/n8n/)
Automation platform. Official Qdrant node.

### [Pipedream](https://qdrant.tech/documentation/platforms/pipedream/)
Workflow automation. Qdrant app for vector search.

### [Power Apps](https://qdrant.tech/documentation/platforms/powerapps/)
Microsoft low-code. Qdrant Connector.

### [PrivateGPT](https://qdrant.tech/documentation/platforms/privategpt/)
Offline LLM document queries. Qdrant as default vectorstore.

### [Salesforce MuleSoft](https://qdrant.tech/documentation/platforms/mulesoft/)
Integration platform. MAC Project Qdrant connector.

### [ToolJet](https://qdrant.tech/documentation/platforms/tooljet/)
Low-code business apps. Qdrant plugin for CRUD + search.

### [Vectorize.io](https://qdrant.tech/documentation/platforms/vectorize/)
Automated RAG pipelines. Qdrant vector storage.

## Observability

### [Observability Overview](https://qdrant.tech/documentation/observability/)
OpenLIT, OpenLLMetry, Datadog integrations.

### [OpenLIT](https://qdrant.tech/documentation/observability/openlit/)
OpenTelemetry-native. Auto-instrument qdrant_client. Two lines of code.

### [OpenLLMetry](https://qdrant.tech/documentation/observability/openllmetry/)
Traceloop SDK. Trace qdrant_client operations.

### [Datadog](https://qdrant.tech/documentation/observability/datadog/)
Cloud monitoring. Qdrant integration via Datadog Agent.

## Practice Datasets

### [Practice Datasets](https://qdrant.tech/documentation/datasets/)
Arxiv titles/abstracts, Wolt food descriptions. Pre-computed embeddings. Snapshot format.

## Client Libraries

### Python Client

#### [Python Client Overview](https://python-client.qdrant.tech/)
QdrantClient and AsyncQdrantClient API reference. Installation, quickstart, all client methods.

#### [QdrantClient API](https://python-client.qdrant.tech/qdrant_client.qdrant_client)
Full QdrantClient class: create_collection, upsert, search, query_points, scroll, delete, snapshot, and 50+ more methods.

#### [AsyncQdrantClient API](https://python-client.qdrant.tech/qdrant_client.async_qdrant_client)
Async version of QdrantClient. Same methods, async/await compatible for FastAPI and concurrent apps.

#### [QdrantClient Local](https://python-client.qdrant.tech/qdrant_client.local.qdrant_local)
Local in-memory Qdrant client for testing without a server. Same API as remote client.

#### [Python Models](https://python-client.qdrant.tech/qdrant_client.http.models.models)
Pydantic models: Distance, VectorParams, PointStruct, Filter, SearchRequest, and all request/response types.

### Rust Client

#### [Rust Client Crate](https://docs.rs/qdrant-client/latest/qdrant_client/)
qdrant-client crate overview. Qdrant struct, connection, TLS, API key auth.

#### [Qdrant Struct (Rust)](https://docs.rs/qdrant-client/latest/qdrant_client/qdrant/struct.Qdrant.html)
Main Qdrant client struct. Methods for collections, points, search, snapshots, cluster management.

#### [Rust Collection Operations](https://docs.rs/qdrant-client/latest/qdrant_client/qdrant/trait.CollectionOperations.html)
Create, update, delete collections. Set aliases. Collection info and config.

#### [Rust Point Operations](https://docs.rs/qdrant-client/latest/qdrant_client/qdrant/trait.PointOperations.html)
Upsert, delete, get, scroll, count points. Batch operations. Set payload.

#### [Rust Search Operations](https://docs.rs/qdrant-client/latest/qdrant_client/qdrant/trait.SearchOperations.html)
Search, query, recommend, discover points. Batch search. Hybrid queries.

### Go Client

#### [Go Client Package](https://pkg.go.dev/github.com/qdrant/go-client/qdrant)
Go qdrant package. Client struct, all collection/point/search methods, generated types from protobuf.

### Java Client

#### [Java Client Javadoc](https://qdrant.github.io/java-client/)
QdrantClient, QdrantGrpcClient. Factory classes for conditions, points, vectors.

#### [Java QdrantClient](https://qdrant.github.io/java-client/io/qdrant/client/QdrantClient.html)
Main Java client class. Collection, point, search, snapshot operations. ListenableFuture returns.

#### [Java ConditionFactory](https://qdrant.github.io/java-client/io/qdrant/client/ConditionFactory.html)
Helper methods to build filter conditions: matchKeyword, matchText, range, geo, nested, hasId.

### TypeScript/JavaScript Client

#### [TypeScript Client README](https://github.com/qdrant/qdrant-js)
JS/TS client for Qdrant. REST and gRPC transports. Collection, point, search operations.

### .NET Client

#### [.NET Client README](https://github.com/qdrant/qdrant-dotnet)
C# client for Qdrant via gRPC. QdrantClient class. Collection, point, search, snapshot operations.

## Benchmarks

### [How to Benchmark](https://qdrant.tech/benchmarks/benchmarks-intro/)
Methodology: reproducible, open-source, resource-efficient comparisons.

### [Single Node Benchmarks](https://qdrant.tech/benchmarks/single-node-speed-benchmark/)
Qdrant vs Elasticsearch, Milvus, Redis, Weaviate. RPS and latency comparisons.

### [Filtered Search Benchmark](https://qdrant.tech/benchmarks/filtered-search-intro/)
ANN + filter complexity. Pre/post-filtering problems. Qdrant's approach.

### [Benchmark FAQ](https://qdrant.tech/benchmarks/benchmark-faq/)
Open-source only. Consistent hardware. Community contributions welcome.

### [Vector Database Benchmarks](https://qdrant.tech/benchmarks/)
Overview page with all benchmark results.

## Key Articles

### [Hybrid Search Revamped](https://qdrant.tech/articles/hybrid-search/)
Query API for dense + sparse + multivector. RRF, layered reranking.

### [What is RAG?](https://qdrant.tech/articles/what-is-rag-in-ai/)
Retriever + generator architecture. Dense/sparse vectors. Hybrid search.

### [Agentic RAG](https://qdrant.tech/articles/agentic-rag/)
Agents with LLMs for multi-step retrieval. LangGraph workflows.

### [Data Privacy & RBAC](https://qdrant.tech/articles/data-privacy/)
API key + JWT auth, TLS, deployment flexibility, compliance.

### [Multitenancy & Custom Sharding](https://qdrant.tech/articles/multitenancy/)
Payload partitioning, custom sharding, data isolation, regional placement.

### [BM42: Hybrid Search Baseline](https://qdrant.tech/articles/bm42/)
BM25 limitations in RAG. Transformer + BM25 insights.

### [Sparse Vectors](https://qdrant.tech/articles/sparse-vectors/)
SPLADE, token weights, hybrid search with dense embeddings.

### [Modern Sparse Neural Retrieval](https://qdrant.tech/articles/modern-sparse-neural-retrieval/)
DeepCT, DeepImpact, TILDEv2, SPLADE++. Theory to practice.

### [miniCOIL](https://qdrant.tech/articles/minicoil/)
Lightweight sparse neural retriever. Semantic-aware sparse representations.

### [Late Interaction Models](https://qdrant.tech/articles/late-interaction-models/)
Qdrant 1.10 multi-vector support. Output token embeddings for retrieval.

### [Vector Quantization](https://qdrant.tech/articles/what-is-vector-quantization/)
Scalar, binary, product quantization. Memory reduction up to 32x.

### [Choosing an Embedding Model](https://qdrant.tech/articles/how-to-choose-an-embedding-model/)
Quality, languages, resources, tokenizer, model size, sequence length.

### [Vector Search in Production](https://qdrant.tech/articles/vector-search-production/)
Memory management, indexing tuning, quantization, offloading.

### [Optimizing Bulk Uploads](https://qdrant.tech/articles/indexing-optimization/)
Disable HNSW during ingestion (m=0). On-disk storage. Memory management.

### [Binary Quantization: 40x Faster](https://qdrant.tech/articles/binary-quantization/)
1024+ dimensions. Memory reduction. Speed/accuracy tradeoff.

### [Filtrable HNSW](https://qdrant.tech/articles/filtrable-hnsw/)
Apply filters during HNSW graph traversal. Categorical, numerical, geo constraints.

### [Gridstore: Custom Key-Value Store](https://qdrant.tech/articles/gridstore-key-value-storage/)
Why Qdrant replaced RocksDB. Three-layer architecture. WAL crash recovery.

### [What are Vector Embeddings?](https://qdrant.tech/articles/what-are-embeddings/)
Numerical representations of meaning. BERT, GPT context-aware embeddings.

### [Full-Text Filters and Indexes](https://qdrant.tech/articles/qdrant-introduces-full-text-filters-and-indexes/)
Full-text search alongside vector search. Tokenization options. Case-insensitive.

### [Semantic Cache](https://qdrant.tech/articles/semantic-cache-ai-data-retrieval/)
Cache semantically similar queries. Reduce cost and latency in RAG.

### [ColPali Optimization: 13x Faster](https://qdrant.tech/blog/colpali-qdrant-optimization/)
Row-wise pooling for multi-vector reduction. Two-stage retrieval.

### [RAG Evaluation Guide](https://qdrant.tech/blog/rag-evaluation-guide/)
Precision, recall, relevance. Ragas, Quotient AI, Arize Phoenix frameworks.

## Release Notes

### [Qdrant 1.16](https://qdrant.tech/blog/qdrant-1.16.x/)
Tiered multitenancy with tenant promotion, ACORN filtered search, inline storage for disk-efficient search, TextAny filter, conditional updates, ASCII folding, configurable RRF k, collection metadata, Web UI redesign.

### [Qdrant 1.15](https://qdrant.tech/blog/qdrant-1.15.x/)
1.5/2-bit quantization, asymmetric quantization, multilingual tokenization, stop words, stemming, phrase matching, MMR, HNSW healing.

### [Qdrant 1.14](https://qdrant.tech/blog/qdrant-1.14.x/)
Score-boosting reranker, incremental HNSW, parallel batch search, resource optimizations. 57% faster batch queries.

### [Qdrant 1.13](https://qdrant.tech/blog/qdrant-1.13.x/)
GPU indexing (vendor-agnostic via Vulkan), strict mode, HNSW compression, Gridstore storage engine, named vector filtering.

### [Qdrant 1.12](https://qdrant.tech/blog/qdrant-1.12.x/)
Distance Matrix API, facet counting, on-disk text/geo indexes, data exploration GUI.

### [Qdrant 1.11](https://qdrant.tech/blog/qdrant-1.11.x/)
Defragmented multitenant storage, on-disk payload indexing, GroupBy, random sampling, hybrid fusion.

### [Qdrant 1.10](https://qdrant.tech/blog/qdrant-1.10.x/)
Universal Query API, built-in IDF, ColBERT multivector support.

### [Qdrant 1.9](https://qdrant.tech/blog/qdrant-1.9.x/)
JWT RBAC, faster shard transfer, uint8 embeddings, sparse vector improvements.

### [Qdrant 1.8](https://qdrant.tech/articles/qdrant-1.8.x/)
16x faster sparse search, dynamic CPU allocation, text indexing improvements, datetime support.

### [Qdrant 1.7](https://qdrant.tech/articles/qdrant-1.7.x/)
Sparse vectors, Discovery API, user-defined sharding, snapshot-based shard transfer.
