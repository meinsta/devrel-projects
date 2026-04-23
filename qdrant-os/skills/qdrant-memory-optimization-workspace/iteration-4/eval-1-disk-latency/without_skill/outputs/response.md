# Fixing High Latency After Switching to Disk-Based Storage

Yes, there is a middle ground between full RAM and full disk.

## Why latency jumped

When you move everything to disk, each HNSW graph traversal step requires a disk read. HNSW typically performs hundreds of random reads per query. On disk, each read takes microseconds to milliseconds depending on your storage hardware. Multiplied across hundreds of hops, this adds up to seconds.

## The middle ground: memory-mapped files (mmap)

Instead of full disk or full RAM, use mmap-based storage. With mmap:

- Data lives in files on disk
- The operating system's page cache automatically keeps frequently accessed data in RAM
- Cold data stays on disk and is only loaded on demand
- You do not need to manage the caching yourself

This typically gives you latency in the 50-500ms range instead of 3-4 seconds, depending on how much of your data is "hot" and what kind of disk you are using (NVMe is strongly recommended).

## Even better: mmap + quantization

For the best results, combine mmap with scalar quantization:

1. **Quantize your vectors** using scalar (int8) quantization. This compresses each vector to 1/4 the size.
2. **Keep quantized vectors in RAM** by setting `always_ram: true`. These small compressed vectors are used for the initial search.
3. **Store full vectors on disk via mmap.** Full-precision vectors are only loaded for rescoring the top candidates.

This approach gives you:
- Fast initial search (quantized vectors in RAM)
- Good accuracy (rescoring against full vectors)
- Low memory footprint (only the compressed vectors need RAM)

Expected latency should be well under 500ms for most workloads, which should be acceptable for a chatbot.

## Configuration

Update your collection to use mmap storage and add scalar quantization:

```json
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

Also ensure your storage is set to mmap rather than full disk mode.

## If you need lower latency

If 50-500ms is still too slow:
- Use NVMe SSDs for the fastest disk I/O
- Consider keeping more data in RAM by using a larger instance
- Look into binary quantization if your embedding model supports it (OpenAI, Cohere), which compresses even further and can reduce latency
