# Evaluation

This directory is for performance evaluation scripts and results.

## Overview

Evaluation helps quantify the difference between vanilla and agentic RAG approaches.

## Metrics

Key metrics for comparing systems:

### Answer Accuracy
- **Definition**: Percentage of questions answered correctly (Yes/No)
- **Why it matters**: The ultimate measure of system quality

### Retrieval Quality
- **Hit@k**: Percentage of questions where at least one relevant statute is in top-k results
- **MRR**: Mean Reciprocal Rank - position of first relevant result
- **Why it matters**: Better retrieval → Better answers

### Efficiency
- **Queries per question**: How many searches the system performs
- **Time per question**: Total latency
- **Cost per question**: LLM API costs

### Trade-offs
- Agentic RAG: Higher accuracy, slower, more expensive
- Vanilla RAG: Lower accuracy, faster, cheaper

## Running Evaluations

### Quick Comparison

Using existing scripts from root:

```bash
# Evaluate Vanilla RAG on Wyoming (10 questions)
python vanilla_rag.py wyoming 10

# Evaluate Agentic RAG on Wyoming (10 questions)  
python crewai_enhanced.py wyoming 10

# Compare results
python compare_rag_systems.py
```

### Full Evaluation

For comprehensive results:

```bash
# All Wyoming questions (99 questions)
python vanilla_rag.py wyoming
python crewai_enhanced.py wyoming

# All Idaho questions
python vanilla_rag.py idaho
python crewai_enhanced.py idaho

# All Iowa questions
python vanilla_rag.py iowa
python crewai_enhanced.py iowa
```

**Note**: Full evaluation can take hours and cost several dollars in API fees.

## Evaluation Scripts (To Create)

Recommended evaluation scripts to add:

### `evaluate_vanilla.py`
```python
# Systematic evaluation of vanilla RAG
# - Load test questions
# - Run vanilla RAG on each
# - Calculate metrics
# - Save results
```

### `evaluate_agentic.py`
```python
# Systematic evaluation of agentic RAG
# - Load test questions
# - Run agentic RAG on each
# - Track number of searches
# - Calculate metrics
# - Save results
```

### `compare_results.py`
```python
# Compare two evaluation runs
# - Load results from both systems
# - Calculate delta metrics
# - Generate comparison report
# - Identify where each system succeeds/fails
```

## Results Format

Evaluation results are saved as JSON:

```json
{
  "state": "wyoming",
  "system": "vanilla_rag",
  "timestamp": "2024-03-15T10:30:00",
  "num_questions": 99,
  "answer_accuracy": 70.0,
  "avg_time_per_question": 3.2,
  "results": [
    {
      "question_idx": "q_1",
      "question": "...",
      "golden_answer": "Yes",
      "predicted_answer": "Yes",
      "correct": true,
      "time": 3.1
    },
    ...
  ]
}
```

## Expected Results

Based on our Wyoming evaluation:

| Metric | Vanilla RAG | Agentic RAG | Improvement |
|--------|-------------|-------------|-------------|
| **Answer Accuracy** | 70% | 80% | +10 points |
| **Avg Time/Question** | 3 sec | 25 sec | 8x slower |
| **Searches/Question** | 1 | 2-4 | 2-4x more |
| **Cost/Question** | $0.01 | $0.08 | 8x more |

## Existing Results

Pre-run evaluation results are in `../evaluation_results/`:

```bash
ls ../evaluation_results/
# vanilla_rag_wyoming_*.json
# crewai_enhanced_wyoming_*.json
# ...
```

You can load and analyze these without re-running evaluations.

## Error Analysis

For failed questions, investigate:

1. **What went wrong?**
   - Retrieval failure (didn't find relevant statutes)
   - Generation failure (found statutes but wrong answer)
   - Ambiguous question

2. **Why did vanilla fail?**
   - Single search missed key terms
   - Question-statute semantic mismatch

3. **Why did agentic succeed/fail?**
   - Multiple searches found missing info
   - Agent reasoning identified gaps
   - Or: Agent searched wrong angles

## Creating Visualizations

Example analysis:

```python
import json
import matplotlib.pyplot as plt

# Load results
with open('evaluation_results/vanilla_wyoming.json') as f:
    vanilla = json.load(f)

with open('evaluation_results/agentic_wyoming.json') as f:
    agentic = json.load(f)

# Compare accuracy
plt.bar(['Vanilla', 'Agentic'], 
        [vanilla['answer_accuracy'], agentic['answer_accuracy']])
plt.ylabel('Accuracy (%)')
plt.title('Answer Accuracy Comparison')
plt.show()

# Time comparison
plt.bar(['Vanilla', 'Agentic'],
        [vanilla['avg_time_per_question'], agentic['avg_time_per_question']])
plt.ylabel('Time (seconds)')
plt.title('Latency Comparison')
plt.show()
```

## Best Practices

1. **Use consistent test sets**: Same questions for both systems
2. **Run multiple times**: Average results across runs for stability
3. **Track all metrics**: Don't optimize for just accuracy
4. **Analyze failures**: Understand where each approach breaks down
5. **Consider costs**: Factor in API usage for production planning

## Statistical Significance

With ~100 questions:
- 10% accuracy difference is meaningful
- 5% might be noise
- Use confidence intervals for formal comparisons

## Production Considerations

Before deploying based on evaluation:

- **Latency**: Can you wait 25 seconds? If not, optimize agentic approach
- **Cost**: Can you afford 8x API costs? If not, use hybrid approach
- **Accuracy needs**: Is 70% good enough? If yes, vanilla might suffice
- **Question complexity**: Simple questions → vanilla, complex → agentic

## Future Enhancements

Evaluation features to add:

- [ ] Automated A/B testing framework
- [ ] Per-category performance (fees, evictions, deposits, etc.)
- [ ] Confidence scoring (how sure is the system?)
- [ ] Retrieval quality metrics (beyond just accuracy)
- [ ] User preference testing (which answers are more helpful?)
- [ ] Cost-performance frontier analysis

## Questions?

For evaluation methodology questions, see:
- [HousingQA paper](https://huggingface.co/datasets/reglab/housing_qa)
- Standard IR evaluation metrics (Recall, Precision, MRR)
- RAG evaluation best practices

