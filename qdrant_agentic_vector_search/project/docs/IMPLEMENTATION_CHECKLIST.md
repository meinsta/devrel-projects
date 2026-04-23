# Implementation Checklist - Practitioner-Grade UI

## ✅ DONE (Top-Priority Fixes)

### 1. Fixed Metrics
- [x] "Avg Confidence 31.5%" → "Avg Retrieval Score: 31"
- [x] Added tooltip: "Ranking signal, not legal strength"
- [x] Neutral color (slate, not green)

### 2. Quote Pills Created
- [x] Component built: `QuotePill.tsx`
- [x] Shows: `§ 1940.2 (L12-19) — "No landlord..." [Copy] [Open]`
- [x] Copy citation button
- [ ] **Open button → statute drawer** (drawer not built yet)

### 3. Color Semantics Fixed
- [x] Green "92.5% match" → Neutral "Score: 0.93"
- [x] Monospace font for scores
- [x] Only green for success states (✓ completed)

### 4. Workflow Step Cards
- [x] Component built: `WorkflowSteps.tsx`
- [x] Interactive checkboxes (Todo/Done)
- [x] Due date chips
- [x] Required doc chips
- [x] Quote pills for citations
- [x] Local alert banners
- [x] Export Packet button (sticky)

### 5. Visual Polish
- [x] Left border on cards: `border-l-4 border-l-slate-200 hover:border-l-indigo-500`
- [x] Tooltips on metrics
- [x] Removed redundant jurisdiction badge

---

## 🚧 MISSING (High Priority - Do Next)

### 4. AI Analysis → Findings List ⚠️ CRITICAL
**Current:** Wall of text paragraph

**Need:**
```
**Findings**
• Governing sections: § 1946.2, § 1940.2
• Exceptions found: none
• Deadlines: 3 days (notice), 10-14 days (hearing)
• Local overlay: SF just-cause required

[Show full reasoning ▼]
```

**Impact:** Makes answers scannable, citable

---

### Interaction & Layout

- [ ] **Sticky right drawer** for statute preview
  - Slide-out panel
  - Full statute text
  - Highlighted quoted span
  - Line numbers
  - Copy citation button

- [ ] **"Preview lines" chevron** on search result cards
  - Expands quoted span inline
  - No page jump
  - Shows exact text AI used

- [ ] **Agent Verbose Output**
  - Default: collapsed
  - Button: "Copy plan to clipboard"
  - Toggle to expand/collapse

- [ ] **Quiz Mode button** muted styling
  - Currently: purple button (loud)
  - Should be: text link
  - Hover tooltip: "Test yourself on 50 CA housing law questions"

- [ ] **Filters bar** above results
  - Topic, Code section, Year
  - Show count badges when active
  - Filter retrieved statutes

---

### Copy & Micro-UX

- [ ] **Top breadcrumb**
  - `California → Housing → Eviction (Non-payment)`
  - Contextualizes the query

- [ ] **CTA button labels**
  - Search page: "Ask a Question" | "Generate Workflow"
  - Workflow page: "Recompute Dates" | "Export Packet"

- [ ] **Tooltips for legal terms**
  - "Business vs calendar days"
  - "Local overlay = city rules that supersede state defaults"
  - "RRF = Reciprocal Rank Fusion"

- [ ] **Better empty states**
  - No results → "Try synonyms: 'damage deposit' → 'security deposit'"
  - Show query reformulation suggestions

---

### Trust & Legal Hygiene

- [ ] **Model params footer**
  - "Last updated: 2021 | Model: GPT-4o-mini | Temp: 0.2 | k: 20"
  - Small, bottom of page

- [ ] **Ambiguity banner**
  - When agent abstains or is uncertain
  - "⚠️ Insufficient statutory basis; cite § ____ for partial rule"
  - "Escalate to attorney for fact-specific analysis"

---

### Data & Structure

- [ ] **Section path** under each citation
  - `Civ. Code → Obligations → §1946.2`
  - Shows hierarchy/context

- [ ] **Auto "Followed Ref" chip**
  - When excerpt contains "except as provided in §"
  - Add chip: "📎 Followed § 1942.5"
  - Links to that statute

- [ ] **Packet Summary** (workflow mode)
  - Bottom of workflow
  - "📎 Packet: 3 docs, 2 signatures, 1 proof of service"
  - Shows what export will include

---

### Accessibility & Performance

- [ ] **44px minimum tap targets**
  - All buttons and chips
  - Touch-friendly

- [ ] **Color contrast AA+**
  - Check all text/background combinations
  - Tool: contrast checker

- [ ] **Skeleton loaders**
  - While search runs
  - While workflow generates
  - Matches final layout

- [ ] **Fast first paint**
  - Defer verbose panel JSON
  - Lazy load agent output

---

### Nice-to-Haves

- [ ] **Scenario header** (editable)
  - "Tenant missed rent on Nov 1 (SF). Month-to-month." [✏️]
  - Edit → recomputes all dates

- [ ] **Decision Log download**
  - JSON export of:
    - Plan steps
    - Statutes cited (with line spans)
    - Computed dates
    - Tool calls

- [ ] **Deep links for quotes**
  - URL: `...#§1946.2:L12-L19`
  - Share specific citations
  - Bookmarkable

---

## 📊 Priority Order

### Must-Do (Makes it practitioner-grade):
1. **AI Analysis → Findings list** ← CRITICAL
2. **Statute preview drawer** ← HIGH VALUE
3. **Agent verbose default collapsed** ← UX
4. **Section path under citations** ← CLARITY
5. **Ambiguity banner** ← TRUST

### Should-Do (Polish):
6. Preview lines chevron
7. Filters bar
8. Breadcrumb
9. Better tooltips
10. Model params footer

### Nice-to-Have (Later):
11. Packet summary
12. Skeleton loaders
13. Scenario header
14. Decision log export
15. Deep links

---

## 🎯 Current Status

**Implemented:** ~40% of improvements
**Core practitioner features:** 80% done
**Polish & nice-to-haves:** 20% done

**Next 3 must-dos:**
1. Findings list (replace AI Analysis paragraph)
2. Statute drawer (makes quotes clickable)
3. Collapse verbose output by default

These 3 will take it from "good demo" to "built by a lawyer." 🎯

