# Quiz Mode - Interactive Learning & Agent Transparency

## 🎯 Purpose

Quiz mode lets users **test themselves** against the AI on real California housing law questions, while seeing **verbose CrewAI agent output** in real-time.

## 📊 What Users See

### 1. Scoreboard (Top)
```
┌───────────────────────────────────┐
│  Your Score    AI Score   Total   │
│     5/10         9/10       10     │
└───────────────────────────────────┘
```

### 2. Question
```
┌───────────────────────────────────────────────┐
│ Question 11                                   │
│                                               │
│ Can a landlord evict a tenant without notice? │
│                                               │
│ [Yes]  [No]  [Submit Answer]                  │
└───────────────────────────────────────────────┘
```

### 3. After Submission - Answer Comparison
```
┌─────────────┬─────────────┬─────────────┐
│ Your Answer │  AI Answer  │   Correct   │
│     Yes ✓   │    Yes ✓    │     Yes     │
└─────────────┴─────────────┴─────────────┘
```

### 4. **Verbose Agent Output** (Terminal-style)
```
┌─────────────────────────────────────────────────┐
│ 🤖 Agent Process (Verbose Output)              │
├─────────────────────────────────────────────────┤
│  [2025-11-12 05:30:15] Agent starting...       │
│                                                 │
│  > Entering new AgentExecutor chain...          │
│  > Using tool: hybrid_search                   │
│  > Tool Input: "eviction notice requirements"  │
│                                                 │
│  Searching with:                               │
│    • Dense vector (semantic similarity)        │
│    • Sparse vector (BM42 keywords)             │
│    • RRF fusion                                │
│                                                 │
│  Retrieved 5 statutes:                         │
│  [1] CA Civil Code § 1946.2 (score: 0.923)    │
│  [2] CA Civ Pro Code § 1161b (score: 0.891)   │
│  ...                                           │
│                                                 │
│  > Thought: Based on these statutes, I can     │
│    see that California law requires notice...  │
│                                                 │
│  > Thought: § 1946.2 specifically states...    │
│                                                 │
│  > Final Answer: Yes                           │
│  > Finished chain.                             │
└─────────────────────────────────────────────────┘
```

### 5. Retrieval Metrics
```
┌──────────────────────────────────┐
│ AI Retrieval Performance         │
│                                  │
│ Recall: 100%                     │
│ Found 1/1 golden statutes        │
│                                  │
│ Precision: 20%                   │
│ 1/5 results were golden          │
└──────────────────────────────────┘
```

### 6. Statute Comparison
```
┌────────────────────────────────────┐
│ Golden Statutes (1)                │
│ ✓ CA Civil Code § 1946.2           │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│ AI Retrieved (Top 5)               │
│ ✓ CA Civil Code § 1946.2   92.3%   │  ← Golden match!
│ ○ CA Civ Pro Code § 1161b  89.1%   │
│ ○ CA Civil Code § 1947.10  87.5%   │
│ ○ CA Civ Code § 1942.4     85.2%   │
│ ○ CA Civ Pro Code § 1161.4 83.9%   │
└────────────────────────────────────┘
```

## 🎓 Educational Value

### What Users Learn:

1. **How AI Thinks**
   - See actual agent reasoning
   - Watch tool use in real-time
   - Understand hybrid search process

2. **How Good Is AI?**
   - Compare their answer to AI
   - See retrieval metrics (recall/precision)
   - Understand confidence scores

3. **What Makes Good Retrieval?**
   - See which statutes AI finds
   - Compare to golden statutes
   - Learn from mismatches

4. **Build Trust**
   - Complete transparency
   - See every step
   - Verify against ground truth

## 🔍 Agent Output Examples

### Verbose CrewAI Output Shown:
```
> Entering new AgentExecutor chain...
> 
> Thought: I need to find California housing statutes about eviction notice requirements
> 
> Action: hybrid_search
> Action Input: {"query": "landlord eviction notice requirement California", "top_k": 5}
>
> Observation: 
> [1] CA Civil Code § 1946.2
> Score: 0.923
> Text: Notwithstanding any other law, after a tenant has continuously...
>
> [2] CA Civ Pro Code § 1161b
> Score: 0.891  
> Text: A tenant or subtenant in possession of a rental housing unit...
>
> Thought: Based on § 1946.2, landlords must provide written notice...
>
> Thought: § 1161b specifies the notice requirements and procedures...
>
> Final Answer: Yes
>
> Finished chain.
```

### What This Shows:

- ✅ **Tool calls** - Which searches it runs
- ✅ **Search queries** - How it reformulates the question
- ✅ **Retrieved statutes** - What it finds
- ✅ **Reasoning** - Why it reaches conclusions
- ✅ **Citations** - Which statutes it relies on

## 💡 Why This is Valuable (Not Tacky)

### For Law Students:
- Learn how to research effectively
- See expert-level reasoning
- Compare their intuition to AI

### For Paralegals:
- Verify AI findings
- Learn statute relationships
- Build confidence in the tool

### For Lawyers:
- Audit AI reasoning
- Catch edge cases
- Understand limitations

### For Product Demo:
- **Shows transparency** - Nothing hidden
- **Builds trust** - See the whole process
- **Educational** - Learn by doing
- **Competitive** - Gamification keeps engagement

## 🎮 Game Mechanics

### Scoring:
- You vs. AI on same questions
- Track accuracy over time
- See where you beat the AI
- See where AI outperforms

### Insights:
```
After 10 questions:

You:  7/10 (70%)
AI:   9/10 (90%)

AI's retrieval:
  • Avg Recall: 85%
  • Avg Precision: 32%
  
Your strong areas: Eviction law
AI's strong areas: Deposit regulations

Takeaway: AI found golden statutes 
in 8.5/10 cases, even when wrong!
```

## 🚀 Flow

```
1. Question appears
   ↓
2. User answers (Yes/No)
   ↓
3. User clicks "Submit"
   ↓
4. Show user's answer (✓ or ✗)
   ↓
5. Stream AI agent output (verbose)
   - "Entering chain..."
   - "Using tool: hybrid_search..."
   - "Retrieved statutes..."
   - "Thought: ..."
   - "Final answer: ..."
   ↓
6. Show comparison:
   - User vs AI vs Golden
   - Retrieval metrics
   - Golden statutes vs Retrieved
   ↓
7. Next question button
```

## ✨ Key Features

### Non-Tacky Value Props:
- ✅ **Educational** - Learn from the agent
- ✅ **Transparent** - See everything
- ✅ **Competitive** - Test yourself
- ✅ **Professional** - Terminal-style output

### No Shouting About Money:
- ❌ No "$400 saved!" banners
- ❌ No "10x faster!" claims  
- ❌ No ROI calculators

### Implicit Value Through Quality:
- ✅ Fast results (you see the speed)
- ✅ High accuracy (score shows it)
- ✅ Comprehensive (retrieval metrics)
- ✅ Reliable (matches golden truth)

**The value is obvious from using it - no need to shout about it.** 🎯

