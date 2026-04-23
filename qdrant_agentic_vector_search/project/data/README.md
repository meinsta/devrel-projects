# Data Directory

This directory contains cached data and information about the HousingQA dataset used in this demo.

## HousingQA Dataset

This demo uses the [**HousingQA dataset**](https://huggingface.co/datasets/reglab/housing_qa) from Stanford RegLab.

### Overview

- **Purpose**: Evaluate retrieval systems for legal housing law research
- **Statutes**: ~2,400 housing law statute chunks from multiple US states
- **Questions**: 108 real legal questions with ground truth answers
- **States included**: Iowa, Idaho, Wyoming, California, and others

### Dataset Structure

#### Statutes Corpus

Each statute contains:
- `idx`: Unique identifier
- `citation`: Legal citation (e.g., "Iowa Code § 562A.27")
- `state`: State name
- `text`: Full text of the statute section
- `path`: Hierarchical path in the legal code

#### Questions

Each question contains:
- `idx`: Unique identifier
- `state`: Which state's law it applies to
- `question`: The legal question
- `answer`: Ground truth answer (Yes/No format)
- `statutes`: List of relevant statute IDs
- `question_group`: Category of question

### Example Statute

```json
{
  "idx": "iowa_123",
  "citation": "Iowa Code § 562A.27",
  "state": "Iowa",
  "text": "A landlord shall not retaliate by increasing rent or decreasing services...",
  "path": "Iowa Code/Title XV/Chapter 562A/Section 562A.27"
}
```

### Example Question

```json
{
  "idx": "q_45",
  "state": "Iowa",
  "question": "Can landlords charge late fees on rent?",
  "answer": "Yes",
  "statutes": ["iowa_145", "iowa_289"],
  "question_group": "fees_and_charges"
}
```

## Loading the Dataset

The dataset is loaded automatically by the setup scripts:

```python
from datasets import load_dataset

# Load statutes
statutes = load_dataset(
    "reglab/housing_qa",
    "statutes",
    split="corpus",
    trust_remote_code=True
)

# Load questions
questions = load_dataset(
    "reglab/housing_qa",
    "questions",
    split="test",
    trust_remote_code=True
)
```

## Data Processing

### Chunking

Statutes are pre-chunked in the dataset at natural legal boundaries (sections, subsections). No additional chunking is needed for this demo.

### Embeddings

We use **BGE-small-en-v1.5** (384 dimensions) to embed statute text:
- Fast inference
- Good semantic understanding
- Proven performance on legal text

### Storage in Qdrant

Each statute becomes a point in Qdrant with:
- **Vector**: 384-dim BGE embedding
- **Payload**: Citation, text, state, statute_idx, path

## Collections

After running `setup/01_ingest_data.py`, you'll have:

| Collection | State | Approximate Size |
|------------|-------|------------------|
| `iowa_housing_statutes` | Iowa | ~1,000 statutes |
| `idaho_housing_statutes` | Idaho | ~800 statutes |
| `wyoming_housing_statutes` | Wyoming | ~600 statutes |

## Caching

The `chunks_cache_*.json` files (if present) are cached processed statutes to speed up re-ingestion. They're automatically generated and can be safely deleted.

## Using Your Own Data

To adapt this demo to your own documents:

1. **Format your data** similarly to HousingQA:
   ```python
   {
       "idx": "unique_id",
       "text": "Your document text",
       "metadata": {...}
   }
   ```

2. **Update** `setup/01_ingest_data.py`:
   - Replace dataset loading code
   - Adjust payload fields as needed

3. **Chunk if needed** (if your docs are longer than 512 tokens):
   ```python
   from src.chunker import chunk_documents
   chunks = chunk_documents(your_docs)
   ```

4. **Embed and upload** following the same pattern

## Dataset Citation

If you use the HousingQA dataset in your research, please cite:

```bibtex
@article{housing_qa_2024,
  title={HousingQA: A Legal Question Answering Dataset for Housing Law},
  author={RegLab Team},
  journal={Stanford RegLab},
  year={2024}
}
```

## Dataset License

The HousingQA dataset is released under the Apache 2.0 license. See the [HuggingFace dataset page](https://huggingface.co/datasets/reglab/housing_qa) for details.

## Additional Resources

- [HuggingFace Dataset Card](https://huggingface.co/datasets/reglab/housing_qa)
- [Stanford RegLab](https://reglab.stanford.edu/)
- [Legal AI Research](https://reglab.stanford.edu/research/)

