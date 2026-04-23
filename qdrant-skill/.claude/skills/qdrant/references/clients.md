# Qdrant Client Libraries Reference

This document covers the official Qdrant client libraries for each supported language.

## Python Client

**Package**: `qdrant-client`

```bash
pip install qdrant-client
```

### Connection

```python
from qdrant_client import QdrantClient

# Local instance
client = QdrantClient("localhost", port=6333)

# Qdrant Cloud
client = QdrantClient(
    url="https://your-cluster.cloud.qdrant.io",
    api_key=os.environ["QDRANT_API_KEY"],
)

# In-memory (for testing)
client = QdrantClient(":memory:")
```

### Key Classes

```python
from qdrant_client import QdrantClient, models

# Vector configuration
models.VectorParams(size=384, distance=models.Distance.COSINE)

# Points
models.PointStruct(id=1, vector=[0.1, 0.2, ...], payload={"key": "value"})

# Filters
models.Filter(
    must=[models.FieldCondition(key="city", match=models.MatchValue(value="Berlin"))]
)

# Search request
models.SearchRequest(vector=[0.1, 0.2, ...], limit=10, filter=filter)
```

### Async Support

```python
from qdrant_client import AsyncQdrantClient

async_client = AsyncQdrantClient("localhost", port=6333)
results = await async_client.search(collection_name="test", query_vector=[0.1, 0.2, ...])
```

### gRPC Mode

```python
# Use gRPC for better performance
client = QdrantClient("localhost", port=6334, prefer_grpc=True)
```

---

## JavaScript/TypeScript Client

**Package**: `@qdrant/js-client-rest`

```bash
npm install @qdrant/js-client-rest
# or
pnpm add @qdrant/js-client-rest
```

### Connection

```typescript
import { QdrantClient } from '@qdrant/js-client-rest';

// Local instance
const client = new QdrantClient({ url: 'http://localhost:6333' });

// Qdrant Cloud
const client = new QdrantClient({
  url: 'https://your-cluster.cloud.qdrant.io',
  apiKey: process.env.QDRANT_API_KEY,
});
```

### Key Operations

```typescript
// Create collection
await client.createCollection('my_collection', {
  vectors: { size: 384, distance: 'Cosine' },
});

// Upsert points
await client.upsert('my_collection', {
  wait: true,
  points: [
    { id: 1, vector: [0.1, 0.2, ...], payload: { city: 'Berlin' } },
  ],
});

// Search
const results = await client.search('my_collection', {
  vector: [0.1, 0.2, ...],
  limit: 10,
  filter: {
    must: [{ key: 'city', match: { value: 'Berlin' } }],
  },
});
```

---

## Rust Client

**Crate**: `qdrant-client`

```toml
[dependencies]
qdrant-client = "1"
tokio = { version = "1", features = ["full"] }
```

### Connection

```rust
use qdrant_client::Qdrant;

// Local instance
let client = Qdrant::from_url("http://localhost:6334").build()?;

// Qdrant Cloud
let client = Qdrant::from_url("https://your-cluster.cloud.qdrant.io:6334")
    .api_key(std::env::var("QDRANT_API_KEY"))
    .build()?;
```

### Key Operations

```rust
use qdrant_client::qdrant::{
    CreateCollectionBuilder, Distance, PointStruct, SearchPointsBuilder,
    VectorParamsBuilder,
};

// Create collection
client
    .create_collection(
        CreateCollectionBuilder::new("my_collection")
            .vectors_config(VectorParamsBuilder::new(384, Distance::Cosine)),
    )
    .await?;

// Upsert points
client
    .upsert_points("my_collection")
    .wait(true)
    .points(vec![
        PointStruct::new(1, vec![0.1, 0.2, ...], json!({"city": "Berlin"}).try_into()?),
    ])
    .await?;

// Search
let results = client
    .search_points(SearchPointsBuilder::new("my_collection", vec![0.1, 0.2, ...], 10))
    .await?;
```

---

## Go Client

**Module**: `github.com/qdrant/go-client`

```bash
go get github.com/qdrant/go-client
```

### Connection

```go
import (
    "github.com/qdrant/go-client/qdrant"
)

// Local instance
client, err := qdrant.NewClient(&qdrant.Config{
    Host: "localhost",
    Port: 6334,
})

// Qdrant Cloud
client, err := qdrant.NewClient(&qdrant.Config{
    Host:   "your-cluster.cloud.qdrant.io",
    Port:   6334,
    APIKey: os.Getenv("QDRANT_API_KEY"),
    UseTLS: true,
})
```

### Key Operations

```go
// Create collection
client.CreateCollection(ctx, &qdrant.CreateCollection{
    CollectionName: "my_collection",
    VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
        Size:     384,
        Distance: qdrant.Distance_Cosine,
    }),
})

// Upsert points
client.Upsert(ctx, &qdrant.UpsertPoints{
    CollectionName: "my_collection",
    Wait:           qdrant.PtrOf(true),
    Points: []*qdrant.PointStruct{
        {
            Id:      qdrant.NewIDNum(1),
            Vectors: qdrant.NewVectors(0.1, 0.2, ...),
            Payload: qdrant.NewValueMap(map[string]any{"city": "Berlin"}),
        },
    },
})

// Search
results, err := client.Search(ctx, &qdrant.SearchPoints{
    CollectionName: "my_collection",
    Vector:         []float32{0.1, 0.2, ...},
    Limit:          10,
})
```

---

## Java Client

**Maven**:
```xml
<dependency>
    <groupId>io.qdrant</groupId>
    <artifactId>client</artifactId>
    <version>1.x.x</version>
</dependency>
```

### Connection

```java
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;

// Local instance
QdrantClient client = new QdrantClient(
    QdrantGrpcClient.newBuilder("localhost", 6334, false).build()
);

// Qdrant Cloud
QdrantClient client = new QdrantClient(
    QdrantGrpcClient.newBuilder("your-cluster.cloud.qdrant.io", 6334, true)
        .withApiKey(System.getenv("QDRANT_API_KEY"))
        .build()
);
```

### Key Operations

```java
import io.qdrant.client.grpc.Collections.*;
import io.qdrant.client.grpc.Points.*;

// Create collection
client.createCollectionAsync("my_collection",
    VectorParams.newBuilder()
        .setSize(384)
        .setDistance(Distance.Cosine)
        .build()
).get();

// Upsert points
client.upsertAsync("my_collection",
    List.of(
        PointStruct.newBuilder()
            .setId(PointId.newBuilder().setNum(1))
            .setVectors(Vectors.newBuilder().setVector(
                Vector.newBuilder().addAllData(List.of(0.1f, 0.2f, ...))
            ))
            .putAllPayload(Map.of("city", Value.newBuilder().setStringValue("Berlin").build()))
            .build()
    )
).get();

// Search
List<ScoredPoint> results = client.searchAsync(SearchPoints.newBuilder()
    .setCollectionName("my_collection")
    .addAllVector(List.of(0.1f, 0.2f, ...))
    .setLimit(10)
    .build()
).get();
```

---

## .NET/C# Client

**NuGet**: `Qdrant.Client`

```bash
dotnet add package Qdrant.Client
```

### Connection

```csharp
using Qdrant.Client;

// Local instance
var client = new QdrantClient("localhost", 6334);

// Qdrant Cloud
var client = new QdrantClient(
    "your-cluster.cloud.qdrant.io",
    6334,
    true,  // useTls
    Environment.GetEnvironmentVariable("QDRANT_API_KEY")
);
```

### Key Operations

```csharp
using Qdrant.Client.Grpc;

// Create collection
await client.CreateCollectionAsync("my_collection",
    new VectorParams { Size = 384, Distance = Distance.Cosine }
);

// Upsert points
await client.UpsertAsync("my_collection", new List<PointStruct>
{
    new()
    {
        Id = 1,
        Vectors = new float[] { 0.1f, 0.2f, ... },
        Payload = { ["city"] = "Berlin" }
    }
});

// Search
var results = await client.SearchAsync("my_collection",
    new float[] { 0.1f, 0.2f, ... },
    limit: 10
);
```

---

## Client Comparison

| Feature | Python | JS/TS | Rust | Go | Java | .NET |
|---------|--------|-------|------|-----|------|------|
| Protocol | REST/gRPC | REST | gRPC | gRPC | gRPC | gRPC |
| Async | Yes | Yes | Yes | Yes | Yes | Yes |
| In-memory mode | Yes | No | No | No | No | No |
| Type hints | Yes | Yes | Yes | Yes | Yes | Yes |

## Common Patterns

### Connection with Retry

```python
# Python with tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_client():
    return QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
```

### Connection Pooling

For high-throughput applications, create a single client instance and reuse it across your application. All official clients handle connection pooling internally.

### Timeout Configuration

```python
# Python
client = QdrantClient("localhost", timeout=30)

# JavaScript
const client = new QdrantClient({ url: '...', timeout: 30000 });
```
