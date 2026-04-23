# How CrewAI + Qdrant Deliver on Practitioner Jobs

## Technology → Jobs Mapping

### 🔍 Qdrant Hybrid Search → Locate Controlling Law

**Job:** Surface governing Civil Code/Code of Civ. Proc. sections instantly

**How Qdrant Delivers:**
```python
# Hybrid Search with RRF
results = client.query_points(
    collection_name="california_housing_statutes",
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=20),    # ← Semantic understanding
        Prefetch(query=sparse_vector, using="sparse", limit=20),  # ← Exact terms/keywords
    ],
    query=FusionQuery(fusion=Fusion.RRF),  # ← Best of both worlds
    limit=10
)
```

**Why This Matters:**
- **Dense vectors** catch "eviction" even when statute says "termination of tenancy"
- **Sparse vectors** ensure exact terms like "§ 1946.2" are prioritized
- **RRF fusion** balances semantic understanding with keyword precision
- **Result:** Find the right section on first query, not 10th search

---

### 🤖 CrewAI Agents → Operationalize Statutes

**Jobs:** 
- Resolve definitions & exceptions
- Generate procedural workflows
- Compute deadlines
- Flag local variations

**How CrewAI Delivers:**

#### Agent Architecture
```python
# Specialized agents with custom tools
legal_agent = Agent(
    role="California Housing Law Expert",
    tools=[
        HybridSearchTool(),      # Find statutes
        FollowRefTool(),         # "except as provided in §..."
        DefinitionTool(),        # Look up "dwelling unit"
        DateMathTool(),          # Compute deadlines
        LocalRuleTool(),         # Check SF/LA overlays
    ]
)

# Task decomposition
task = Task(
    description="Generate 5-day notice workflow for nonpayment",
    expected_output="Step-by-step checklist with dates and cites"
)
```

#### Custom Tools for Legal Jobs

**1. FollowRefTool** → Resolve exceptions
```python
# When statute says "except as provided in § 1942.5"
@tool
def follow_ref(statute_citation: str):
    """Retrieve the referenced exception statute."""
    results = hybrid_search(f"California {statute_citation}")
    return full_text_with_line_numbers
```

**2. DefinitionTool** → Resolve definitions
```python
# When term needs defining
@tool
def get_definition(term: str, context_statute: str):
    """Find statutory definition of legal term."""
    search_query = f'definition of "{term}" California housing'
    return verified_definition_with_cite
```

**3. DateMathTool** → Compute deadlines
```python
# When timeline required
@tool
def compute_deadline(trigger_date: str, days: int, day_type: str):
    """Calculate exact deadline with CA court holidays."""
    # Calendar vs business days
    # Skip weekends/holidays
    # Return: "Due by: Dec 15, 2025 (5 PM)"
```

**4. LocalRuleTool** → Flag local variations
```python
# When location matters
@tool
def check_local_rules(city: str, issue: str):
    """Flag stricter local ordinances (LA/SF/Oakland)."""
    return {
        "has_local_rules": True,
        "stricter_than_state": True,
        "summary": "LA requires just cause + relocation assistance"
    }
```

---

## Complete Flow Example

### User Job: "Generate procedural workflow for nonpayment eviction"

```
User Query: "How do I evict for nonpayment in California?"
    ↓
┌─────────────────────────────────────────────┐
│ CrewAI Agent (California Housing Expert)    │
├─────────────────────────────────────────────┤
│ Thought: Need to find nonpayment statutes   │
│ Action: hybrid_search("nonpayment eviction")│
│ ↓                                           │
│ Qdrant Hybrid Search (RRF)                  │
│   Dense: "nonpayment" → termination rules   │
│   Sparse: exact "§ 1161" matches            │
│   RRF: Fuse to top 5                        │
│ ↓                                           │
│ Observation: Found § 1161(2), § 1946.2      │
│                                             │
│ Thought: § 1161(2) mentions 3-day notice    │
│ Action: follow_ref("§ 1161")                │
│ Observation: Full notice requirements       │
│                                             │
│ Thought: Need exact timeline                │
│ Action: compute_deadline(                   │
│    trigger="today",                         │
│    days=3,                                  │
│    type="calendar"                          │
│ )                                           │
│ Observation: Due by Nov 15, 2025            │
│                                             │
│ Thought: Check for local rules              │
│ Action: check_local_rules("Los Angeles")    │
│ Observation: LA requires just cause         │
│                                             │
│ Final Answer:                               │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Nonpayment Eviction Workflow (CA)          │
│                                             │
│ 1. ✅ Serve 3-Day Notice (§ 1161(2))       │
│    Due: Nov 15, 2025                        │
│    Required: Amount owed, payment address   │
│    Cite: Cal. Civ. Proc. Code § 1161(2)    │
│                                             │
│ 2. ✅ Wait 3 Calendar Days                  │
│    No payment → proceed to filing           │
│                                             │
│ 3. ✅ File Unlawful Detainer                │
│    Form: UD-100                             │
│    Cite: Cal. Civ. Proc. Code § 1166        │
│                                             │
│ ⚠️  LOCAL ALERT (LA):                       │
│    Just cause required per LAMC § 151.09    │
│                                             │
│ 📎 Packet Ready: Notice + Cover + Checklist │
└─────────────────────────────────────────────┘
```

---

## Why This Stack?

### Qdrant Hybrid Search
✅ **Solves:** "Find the controlling section on first query"
- Dense + Sparse = catches both concepts and exact terms
- 155k statutes searched in <300ms
- RRF fusion = best of both approaches

### CrewAI Agents
✅ **Solves:** "Operationalize statutes into actionable steps"
- Tools can follow cross-references
- Tools can compute dates
- Tools can check local rules
- Agent reasoning shows its work

### The Combination
**Qdrant** = Find the law (retrieval)
**CrewAI** = Apply the law (reasoning + tools)

## Feature Roadmap (Mapped to Jobs)

### ✅ Phase 1 (Current - Demo)
- [x] Hybrid search with RRF
- [x] Basic RAG with citations
- [x] Transparent agent process
- [x] Quiz mode (test vs AI)

**Delivers Jobs:** Locate law, Verify claims, Transparent process

### 🚧 Phase 2 (Next - MVP)
- [ ] FollowRefTool (parse "except as provided...")
- [ ] DefinitionTool (look up statutory definitions)
- [ ] DateMathTool (CA court calendar aware)
- [ ] Workflow templates (Notice → Filing → Service)

**Delivers Jobs:** Resolve exceptions, Compute deadlines, Generate workflows

### 🔮 Phase 3 (Future - Full Product)
- [ ] LocalRuleTool (LA/SF/Oakland overlays)
- [ ] PacketExporter (PDF with auto-filled forms)
- [ ] Abstain policy ("insufficient basis")
- [ ] Decision log export

**Delivers Jobs:** Flag local variations, Assemble packets, Know when to escalate

---

## Architecture

```
┌──────────────────────────────────────┐
│         User (Practitioner)          │
│   Attorney | Paralegal | Prop Mgr   │
└─────────────────┬────────────────────┘
                  │
        "How do I evict for nonpayment?"
                  │
┌─────────────────▼────────────────────┐
│        Next.js Frontend              │
│  Shows agent process transparently   │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│         FastAPI Backend              │
│  ┌────────────────────────────────┐  │
│  │     CrewAI Agent               │  │
│  │  ┌──────────────────────────┐  │  │
│  │  │ Custom Tools:            │  │  │
│  │  │ • HybridSearchTool       │  │  │ ← Uses Qdrant
│  │  │ • FollowRefTool          │  │  │ ← Uses Qdrant
│  │  │ • DefinitionTool         │  │  │ ← Uses Qdrant
│  │  │ • DateMathTool           │  │  │
│  │  │ • LocalRuleTool          │  │  │
│  │  └──────────────────────────┘  │  │
│  └────────────────────────────────┘  │
└─────────────────┬────────────────────┘
                  │
┌─────────────────▼────────────────────┐
│          Qdrant Cloud                │
│  ┌────────────────────────────────┐  │
│  │ california_housing_statutes    │  │
│  │ • 155,974 statutes             │  │
│  │ • Dense vectors (BGE-small)    │  │
│  │ • Sparse vectors (BM42)        │  │
│  │ • Metadata: citation, path     │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ california_housing_questions   │  │
│  │ • 181 golden questions         │  │
│  │ • Golden statute IDs           │  │
│  │ • For evaluation/quiz          │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## Value Proposition (JTBD-Aligned)

### For the Practitioner:
**"CrewAI agents + Qdrant hybrid search deliver what Westlaw can't: operationalized workflows with verified cites, not just search results."**

### What Makes This Different:

| Traditional Tools | Our Approach |
|------------------|--------------|
| **Westlaw/Lexis** | **Qdrant Hybrid Search** |
| Search returns citations | Search + context |
| You figure out next steps | Agent generates workflow |
| Manual cross-ref following | FollowRefTool auto-retrieves |
| Guess at definitions | DefinitionTool finds them |
| Calendar math on paper | DateMathTool with holidays |
| | |
| **Manual Checklists** | **CrewAI Agents** |
| Static templates | Dynamic, fact-responsive |
| No verification | Every step cited |
| One-size-fits-all | Adapts to scenario |

---

## The "Receipts" (Transparency)

### Every Result Shows:
1. **What Qdrant found** - Dense + sparse search results
2. **How CrewAI reasoned** - Tool calls, thoughts, decisions
3. **Which statutes cited** - § number + verbatim quote
4. **Why this answer** - Decision log
5. **Confidence level** - Retrieval scores

### Example Output:
```
┌─────────────────────────────────────────────┐
│ 🧠 Agent Process                            │
├─────────────────────────────────────────────┤
│ > Tool: hybrid_search                       │
│   Query: "nonpayment eviction notice"       │
│   Qdrant RRF: Dense (semantic) + Sparse    │
│   Results: 5 statutes (92% confidence)      │
│                                             │
│ > Retrieved: § 1161(2), § 1946.2, § 1166    │
│                                             │
│ > Tool: follow_ref                          │
│   Following: "except as provided in § 1942" │
│   Found: Habitability exception             │
│                                             │
│ > Tool: compute_deadline                    │
│   Trigger: Nov 12, 2025                     │
│   + 3 calendar days                         │
│   = Due: Nov 15, 2025 (weekday)             │
│                                             │
│ > Decision: Proceed with 3-day notice       │
│   Cite: Cal. Civ. Proc. Code § 1161(2)      │
│   Quote: "...by default in payment of..."   │
└─────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1 (Current - Demo Working)
```python
# Qdrant: Basic hybrid search
✅ Dense + Sparse vectors ingested
✅ RRF fusion working
✅ 155k+ California statutes indexed
✅ Golden questions for evaluation

# CrewAI: Simplified agent
✅ Streaming verbose output
✅ HybridSearchTool integrated
⏳ Quiz mode showing agent process
```

### Phase 2 (Next - Practitioner MVP)
```python
# CrewAI: Add legal tools
@tool
def follow_ref(statute_ref: str):
    """Follow 'except as provided in §' cross-references."""
    return qdrant_hybrid_search(statute_ref)

@tool
def get_definition(term: str):
    """Find statutory definition."""
    return qdrant_hybrid_search(f'definition "{term}" California')

@tool  
def compute_deadline(start_date, days, day_type):
    """Calculate exact deadline with CA holidays."""
    # Court calendar logic
    return deadline_with_cite

# Workflow templates
eviction_workflow = Agent(
    role="Eviction Procedure Expert",
    tools=[HybridSearchTool, FollowRefTool, DateMathTool],
    goal="Generate compliant eviction checklist"
)
```

### Phase 3 (Future - Full Product)
```python
# CrewAI: Multi-agent collaboration
team = Crew(
    agents=[
        research_agent,      # Find statutes
        procedure_agent,     # Generate steps
        compliance_agent,    # Check local rules
        document_agent,      # Prepare packets
    ]
)

# Advanced tools
@tool
def check_local_ordinance(city: str, issue: str):
    """Check LA/SF/Oakland rent control, just cause."""
    return local_rules_with_preemption_analysis

@tool
def export_packet(workflow: dict):
    """Generate PDF with auto-filled forms."""
    return {notice_pdf, cover_sheet, evidence_list}
```

---

## Why CrewAI + Qdrant (Not Just LangChain or Others)

### CrewAI Strengths:
- ✅ **Role-based agents** - Natural for legal specializations
- ✅ **Task delegation** - Multi-step workflows
- ✅ **Verbose output** - See the thinking (critical for legal)
- ✅ **Custom tools** - Build legal-specific capabilities

### Qdrant Strengths:
- ✅ **Hybrid search** - Semantic + keyword in one query
- ✅ **RRF built-in** - Proven fusion algorithm
- ✅ **Sparse vectors** - True keyword matching (like BM25)
- ✅ **Performance** - 155k vectors, <300ms search

### The Combination:
- **Qdrant handles retrieval** (what it's best at)
- **CrewAI handles reasoning** (what it's best at)
- **Result:** Operationalized law, not just search results

---

## Positioning Statement

**"Qdrant hybrid search finds the right statute. CrewAI agents operationalize it into defensible steps. You get from question to compliant workflow—in seconds, with receipts."**

### For Technical Audience:
- Built on Qdrant's RRF hybrid search
- Powered by CrewAI's multi-agent framework
- Custom legal tools (FollowRef, DateMath, LocalRule)
- Transparent, auditable, cite-verified

### For Legal Audience:
- Fast statute location
- Step-by-step procedures
- Verified citations
- Local rule awareness
- Knows when to abstain

---

## Demo Flow

### 1. Search Demo (Qdrant Showcase)
- Show hybrid search speed
- Dense + sparse results
- RRF fusion in action

### 2. Quiz Mode (Agent Showcase)
- Watch CrewAI think
- See tool calls
- Compare to human
- Evaluate retrieval quality

### 3. Workflow Demo (Full Stack)
- Input: "3-day notice for nonpayment"
- Output: 5-step procedure with dates + cites
- Shows: Both Qdrant retrieval + CrewAI reasoning

This is **practitioner-grade**, not consumer fluff. 🎯

