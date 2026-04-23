# Setup Instructions

This directory contains scripts to set up your Qdrant collections with housing law data.

## Prerequisites

1. **Environment Setup**: Create a `.env` file in the project root with:
   ```
   QDRANT_CLOUD_URL=your_qdrant_cloud_url
   QDRANT_API_KEY=your_qdrant_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

2. **Install Dependencies**:
   ```bash
   uv pip install -e .
   ```

## Running Setup

### Step 1: Ingest Data

Load housing statutes from the HousingQA dataset into Qdrant:

```bash
python setup/01_ingest_data.py
```

This will:
- Load statutes for Iowa, Idaho, and Wyoming from HuggingFace
- Create embeddings using BGE-small-en-v1.5
- Upload to three Qdrant collections:
  - `iowa_housing_statutes`
  - `idaho_housing_statutes`
  - `wyoming_housing_statutes`

**Time**: ~5-10 minutes depending on your connection

### Step 2: Verify Collections

Verify everything loaded correctly:

```bash
python setup/02_verify_collections.py
```

This will:
- Check that all collections exist
- Display point counts
- Run test searches on each collection
- Confirm everything is operational

## What Gets Created

| Collection | State | Approximate Size |
|------------|-------|------------------|
| `iowa_housing_statutes` | Iowa | ~1,000 statutes |
| `idaho_housing_statutes` | Idaho | ~800 statutes |
| `wyoming_housing_statutes` | Wyoming | ~600 statutes |

## Troubleshooting

**Issue**: `QDRANT_CLOUD_URL not set`
- **Fix**: Make sure `.env` file exists in project root with your credentials

**Issue**: `Dataset download fails`
- **Fix**: Check internet connection. The HuggingFace dataset downloads automatically.

**Issue**: `Rate limit errors`
- **Fix**: The script includes delays. If you still see errors, the batching might need adjustment.

## Next Steps

After setup is complete, you can:

1. **Run Examples**: Try `examples/01_vanilla_rag.py` or `examples/02_agentic_rag.py`
2. **Run Demo**: Execute `examples/03_demo_comparison.py` for the full demo
3. **Evaluate**: Use scripts in `evaluation/` to compare performance

## Data Source

This demo uses the [HousingQA dataset](https://huggingface.co/datasets/reglab/housing_qa) from Stanford RegLab:
- 108 housing law questions
- ~2,400 statute chunks across multiple states
- Ground truth annotations for evaluation

