# Performance Objection Playbook

## Diagnosing performance complaints

### Get specific numbers first
"Slow" is not actionable. Ask:
1. What latency are you seeing? (p50, p95, p99)
2. What is your target latency?
3. When does it happen? (always? during writes? at peak load?)
4. How many vectors? What dimensions?
5. What is your current configuration? (HNSW params, quantization, storage)

### Common patterns and fixes

#### Pattern 1: Latency spikes during ingestion
**Symptoms:** Normal query latency but spikes to seconds during bulk uploads
**Root cause:** HNSW index rebuilding during writes
**Fix:** Enable deferred indexing for bulk operations
- Set indexing threshold higher during upload
- Run optimization after upload completes
- CareerFlow pattern: 20-30s spikes during 4M daily jobs, resolved
  with deferred indexing

#### Pattern 2: Consistent high latency (100ms-1s)
**Symptoms:** Every query is slow, not just during writes
**Root cause:** Usually HNSW ef parameter too high or no quantization
**Fix:**
- Reduce ef (search accuracy parameter) from 512 to 128
  Expected: 600ms drops to < 100ms
- Enable scalar quantization with rescoring
  Expected: further 2-3x improvement
- DocketAI pattern: 600ms-1min, resolved with HNSW tuning

#### Pattern 3: Latency > 2 seconds
**Symptoms:** Every query takes 2-5 seconds
**Root cause:** Full disk storage without quantization or mmap
**Fix:** Switch to mmap + scalar quantization
- Do NOT suggest going to full RAM (too expensive)
- mmap + scalar gives < 500ms at 70-80% cost savings
- This is the PointClickCare pattern

#### Pattern 4: Timeouts during writes
**Symptoms:** Write operations timeout or fail
**Root cause:** Instance undersized for write throughput, or
collection not configured for concurrent reads + writes
**Fix:**
- Check instance CPU and memory utilization
- Enable write-ahead log
- Consider separate write and read replicas
- Worldline pattern: 200 upserts/5min on 2M points causing timeouts

#### Pattern 5: Works in dev, fails in production
**Symptoms:** Performance is fine with small data, degrades at scale
**Root cause:** Linear scan instead of HNSW (small collections),
or HNSW parameters not tuned for production data size
**Fix:**
- Verify HNSW index is built (check collection info)
- Tune m and ef_construct for the data size
- Enable quantization before scaling up
- J&J pattern: 85% utilization at 100 users, needed 1000

### Response template for sales calls

"I hear that performance is not meeting your expectations. Let me
understand the specific issue so we can fix it.

[Ask diagnostic questions above]

Based on what you have described, this looks like [pattern X]. We
have seen this before with other customers at similar scale.

The fix is [specific recommendation]. I expect this will bring your
latency from [current] to [target].

I recommend we set up a 30-minute technical session with our SA
team to implement these changes together. If the optimization
requires more extensive work, we can discuss our managed service
option which includes ongoing performance tuning."
