# Qdrant Cloud Reference

This document covers Qdrant Cloud, the fully managed vector database service.

## Overview

Qdrant Cloud provides:
- Fully managed Qdrant clusters
- Automatic scaling and backups
- Built-in monitoring and observability
- Multi-region deployment options
- Enterprise security features

**Console**: https://cloud.qdrant.io/

## Deployment Tiers

### Free Tier
- **Storage**: 1GB
- **Nodes**: Single node
- **Use case**: Development, prototyping, small projects
- **Limits**: No SLA, shared resources

### Standard Tier
- **Storage**: Configurable (pay per GB)
- **Nodes**: 1-3 nodes
- **Use case**: Production workloads
- **Features**: Automatic backups, monitoring, 99.9% SLA

### Enterprise Tier
- **Storage**: Unlimited
- **Nodes**: Custom configuration
- **Use case**: Large-scale production
- **Features**: 
  - Dedicated infrastructure
  - Custom SLAs
  - Private regions
  - SSO/SAML
  - Priority support

## Cluster Configuration

### Creating a Cluster

1. Log in to https://cloud.qdrant.io/
2. Click "Create Cluster"
3. Configure:
   - **Name**: Unique identifier
   - **Region**: Choose closest to your users
   - **Size**: RAM and storage allocation
   - **Nodes**: Number of replicas (1-3 for Standard)

### Cluster Sizing Guidelines

| Use Case | Vectors | Dimensions | Recommended RAM |
|----------|---------|------------|-----------------|
| Small | < 100K | 384 | 1 GB |
| Medium | 100K - 1M | 768 | 4 GB |
| Large | 1M - 10M | 1536 | 16 GB |
| XL | > 10M | 1536 | 32+ GB |

**Formula**: `RAM ≈ (num_vectors × dimensions × 4 bytes × 1.5 overhead) / 1GB`

### Regional Availability

Qdrant Cloud is available in:
- **AWS**: us-east-1, us-west-2, eu-west-1, eu-central-1, ap-northeast-1
- **GCP**: us-central1, europe-west1, asia-east1
- **Azure**: eastus, westeurope

## Authentication

### API Keys

API keys authenticate requests to your Qdrant Cloud cluster.

**Creating API Keys**:
1. Go to cluster dashboard
2. Navigate to "API Keys" section
3. Click "Create API Key"
4. Choose permission level:
   - **Read-only**: Search and retrieve only
   - **Read-write**: Full access

**Best Practices**:
- Never commit API keys to version control
- Use environment variables
- Rotate keys periodically
- Use read-only keys for client-side applications

### Connection Example

```python
import os
from qdrant_client import QdrantClient

client = QdrantClient(
    url=os.environ["QDRANT_URL"],  # https://xxx.cloud.qdrant.io
    api_key=os.environ["QDRANT_API_KEY"],
)
```

```typescript
const client = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});
```

### Environment Variables

```bash
# .env file (never commit this!)
QDRANT_URL=https://your-cluster-id.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here
```

## Hybrid Cloud

Hybrid Cloud allows you to run Qdrant on your own infrastructure while Qdrant manages operations.

### Use Cases
- Data residency requirements
- Compliance (GDPR, HIPAA)
- Low-latency requirements (edge deployment)
- Cost optimization for large deployments

### Architecture
- Qdrant control plane in Qdrant Cloud
- Data plane in your Kubernetes cluster
- Encrypted communication between planes

### Setup Requirements
- Kubernetes cluster (EKS, GKE, AKS, or self-managed)
- Helm 3.x
- kubectl configured

### Installation

```bash
# Add Qdrant Helm repo
helm repo add qdrant https://qdrant.github.io/qdrant-helm

# Install with Hybrid Cloud config
helm install qdrant qdrant/qdrant \
  --set hybridCloud.enabled=true \
  --set hybridCloud.token=<your-token>
```

## Backups and Recovery

### Automatic Backups
- Enabled by default on Standard/Enterprise tiers
- Daily snapshots retained for 7 days
- Point-in-time recovery available

### Manual Snapshots

```python
# Create snapshot
client.create_snapshot(collection_name="my_collection")

# List snapshots
snapshots = client.list_snapshots(collection_name="my_collection")

# Restore from snapshot
client.recover_snapshot(
    collection_name="my_collection",
    location="http://snapshot-url/snapshot.snapshot"
)
```

### Cross-Region Backup

For disaster recovery, replicate snapshots to another region:

1. Create snapshot in primary cluster
2. Download snapshot file
3. Upload to secondary cluster
4. Restore in secondary cluster

## Monitoring

### Built-in Metrics

Qdrant Cloud provides:
- Request latency (p50, p95, p99)
- Throughput (requests/second)
- Storage utilization
- Memory usage
- CPU usage

### Accessing Metrics

1. Go to cluster dashboard
2. Click "Monitoring" tab
3. View real-time and historical metrics

### Alerting

Configure alerts for:
- High latency (> threshold)
- Storage nearing capacity (> 80%)
- Error rate spikes
- Cluster health issues

## Security

### Network Security

**IP Allowlisting**:
- Restrict access to specific IP ranges
- Configure in cluster settings

**Private Endpoints**:
- Available on Enterprise tier
- Direct VPC peering
- No public internet exposure

### Data Encryption

- **In transit**: TLS 1.3 required
- **At rest**: AES-256 encryption
- **Key management**: Customer-managed keys (Enterprise)

### Compliance

- SOC 2 Type II certified
- GDPR compliant
- HIPAA available (Enterprise)

## Cost Optimization

### Right-sizing

1. Start small, scale up as needed
2. Monitor actual usage vs. allocation
3. Use quantization to reduce memory requirements

### Quantization Impact

| Quantization | Memory Reduction | Recall Impact |
|--------------|------------------|---------------|
| None | 0% | 100% |
| Scalar | 75% | 99%+ |
| Binary | 97% | 95%+ |
| Product | 90% | 97%+ |

### Reserved Capacity

Enterprise tier offers reserved capacity discounts for committed usage.

## Migration

### From Self-Hosted to Cloud

1. Create snapshot of self-hosted collection
2. Upload snapshot to cloud storage (S3, GCS)
3. Create collection in Qdrant Cloud
4. Restore from snapshot URL

```python
# On self-hosted
client.create_snapshot(collection_name="my_collection")

# On Cloud
cloud_client.recover_snapshot(
    collection_name="my_collection",
    location="https://storage.example.com/snapshot.snapshot"
)
```

### From Cloud to Self-Hosted

Same process in reverse - create snapshot in Cloud, restore to self-hosted.

## Troubleshooting

### Common Issues

**Connection Refused**:
- Check API key is correct
- Verify cluster is running
- Check IP allowlist if configured

**Slow Queries**:
- Enable payload indexes on filtered fields
- Consider quantization for large collections
- Check if HNSW index is built (status in collection info)

**Out of Memory**:
- Reduce collection size
- Enable quantization
- Upgrade cluster tier

### Support Channels

- **Documentation**: https://qdrant.tech/documentation/
- **Discord**: https://discord.gg/qdrant
- **Email**: support@qdrant.tech (Enterprise)
- **GitHub Issues**: https://github.com/qdrant/qdrant/issues
