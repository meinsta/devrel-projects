# UI Mockup - California Legal Research

## 🎨 Visual Layout

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ⚖️  California Housing Law Research                                 ┃
┃      AI-powered search across 155,974+ housing statutes              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────┐
│  🔍  Ask a question about California housing law...        [Search] │
│                                                                      │
│  Try: • Can a landlord evict without notice?                        │
│       • Security deposit requirements                                │
│       • Rent control regulations                                     │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌─────────────────────────────────────────┐
│  🧠 Agent Process    │  │  📊 Research Results                     │
│                      │  │                                          │
│  ✅ Analyzing Query  │  │  ┌──────┬──────┬──────┐                 │
│  Understanding legal │  │  │ 10   │ 87%  │ 250ms│                 │
│  intent...          │  │  │Found │Conf. │Time  │                 │
│                      │  │  └──────┴──────┴──────┘                 │
│  ✅ Generating      │  │                                          │
│  Embeddings         │  │  💡 AI Analysis:                        │
│  Creating dense &   │  │  Based on CA Civil Code § 1946.2,       │
│  sparse vectors     │  │  landlords must provide written         │
│                      │  │  notice before eviction...              │
│  ✅ Hybrid Search   │  │                                          │
│  Dense + Sparse +   │  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  RRF Fusion         │  │                                          │
│                      │  │  📄 Relevant Statutes (10)              │
│  ✅ Retrieved       │  │                                          │
│  Statutes           │  │  ┌───────────────────────────────────┐  │
│  Found 10 relevant  │  │  │  #1  CA Civil Code § 1946.2       │  │
│  statutes (250ms)   │  │  │      92.5% match                  │  │
│                      │  │  │                                   │  │
│  ⏳ Generating      │  │  │  📍 CA Code > Civil > Chapter 2    │  │
│  Analysis...        │  │  │                                   │  │
│                      │  │  │  Notwithstanding any other law,  │  │
│                      │  │  │  after a tenant has continuously │  │
│                      │  │  │  and lawfully occupied a         │  │
│                      │  │  │  residential real property...    │  │
│                      │  │  │                                   │  │
│                      │  │  │  [Read Full Text →] [Copy]       │  │
│                      │  │  └───────────────────────────────────┘  │
│                      │  │                                          │
│                      │  │  ┌───────────────────────────────────┐  │
│                      │  │  │  #2  CA Civ Pro Code § 1161b      │  │
│                      │  │  │      89.3% match                  │  │
│                      │  │  │  ...                              │  │
│                      │  │  └───────────────────────────────────┘  │
└──────────────────────┘  └─────────────────────────────────────────┘
```

## 🎯 Key UI Elements

### Header
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚖️  California Housing Law Research     ┃
┃    AI-powered search • 155,974+ statutes ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```
- Professional legal branding
- Clear value proposition
- Trust indicators

### Search Bar (Prominent, Clean)
```
┌──────────────────────────────────────────────────┐
│ 🔍 | Ask a question...            [Search] │
└──────────────────────────────────────────────────┘
     Example chips below
```
- Large, inviting input
- Example questions as chips
- Clear call-to-action button

### Agent Flow Panel (Left Side - Sticky)
```
┌─────────────────────────┐
│ 🧠 Agent Process        │
├─────────────────────────┤
│                         │
│ ✅ Analyzing Query      │
│ 🟣 Understanding legal  │
│    intent...            │
│                         │
│ ✅ Generating Vectors   │
│ 🔵 Dense + Sparse       │
│                         │
│ ✅ Hybrid Search        │
│ 🟢 RRF Fusion           │
│    10 results • 250ms   │
│                         │
│ ⏳ Generating Analysis  │
│ 🟠 Synthesizing...      │
└─────────────────────────┘
```
Features:
- Color-coded steps
- Real-time updates
- Progress indicators
- Metadata (count, time)

### Statute Card (Main Content Area)
```
┌────────────────────────────────────────────────┐
│ #1  CA Civil Code § 1946.2    [92.5% match]    │
├────────────────────────────────────────────────┤
│ 🔗 CA Code › Civil › Chapter 2 › Section 1946.2 │
│                                                 │
│ Notwithstanding any other law, after a tenant  │
│ has continuously and lawfully occupied a       │
│ residential real property for 12 months, the   │
│ owner shall not terminate the tenancy without  │
│ just cause...                                  │
│                                                 │
│ [Read Full Text →]  [Copy Citation]            │
└────────────────────────────────────────────────┘
```
Features:
- Clear hierarchy
- Confidence scores
- Breadcrumb navigation
- Actionable buttons
- Hover effects

### Statistics Summary
```
┌──────────────────────────────────────┐
│ 📊 Research Results                  │
├──────────────────────────────────────┤
│ ┌────────┬──────────┬────────────┐  │
│ │   10   │   87%    │   250ms    │  │
│ │ Found  │ Avg Conf │ Search Time│  │
│ └────────┴──────────┴────────────┘  │
└──────────────────────────────────────┘
```

### AI Analysis Box (Optional)
```
┌────────────────────────────────────────┐
│ 💡 AI Legal Analysis                   │
├────────────────────────────────────────┤
│ Based on CA Civil Code § 1946.2 and    │
│ related statutes, California law       │
│ requires landlords to provide just     │
│ cause for eviction after 12 months     │
│ of tenancy. The notice must be in      │
│ writing and specify the cause...       │
└────────────────────────────────────────┘
```

## 🎨 Color Palette

### Primary Colors
```
🔵 Blue (#0ea5e9)    - Primary actions, links
🟢 Green (#10b981)   - Success, positive results
🟠 Orange (#f59e0b)  - Warnings, rankings
🟣 Purple (#8b5cf6)  - Analysis, thinking
⚫ Gray (#1e293b)    - Text, borders
```

### Usage
- **Blue**: Search buttons, primary actions
- **Green**: Checkmarks, successful steps
- **Orange**: Ranking indicators
- **Purple**: Analysis steps
- **Gray**: Text, subtle UI elements

## 📱 Responsive Breakpoints

### Desktop (1024px+)
```
┌──────────┬─────────────────────────┐
│  Agent   │    Results              │
│  Flow    │    (2/3 width)          │
│  (1/3)   │                         │
└──────────┴─────────────────────────┘
```

### Tablet (768px - 1023px)
```
┌──────────────────────────────────┐
│         Agent Flow                │
├──────────────────────────────────┤
│         Results                   │
│         (Full width)              │
└──────────────────────────────────┘
```

### Mobile (< 768px)
```
┌────────────────┐
│   Search Bar   │
├────────────────┤
│   Agent Flow   │
│   (Collapsed)  │
├────────────────┤
│    Results     │
│   (Stacked)    │
└────────────────┘
```

## ✨ Animations

### Agent Steps
- **Slide in from left** (0.3s)
- **Fade in** (0.2s)
- **Stagger** (0.1s delay between)

### Statute Cards
- **Fade in** (0.3s)
- **Slight scale** on hover (1.02x)
- **Shadow increase** on hover

### Loading States
- **Spinner** for active searches
- **Pulse** for thinking indicators
- **Progress bar** for long operations

## 🎭 States

### 1. Empty State
```
┌────────────────────────────────┐
│         📄                     │
│   Ask a Legal Question         │
│                                │
│   Search California housing    │
│   statutes using natural       │
│   language                     │
│                                │
│   [Example Cards Below]        │
└────────────────────────────────┘
```

### 2. Searching State
```
┌────────────────────────────────┐
│  🔄 Searching...               │
│  • Analyzing query             │
│  • Generating embeddings       │
│  • Searching database          │
└────────────────────────────────┘
```

### 3. Results State
```
┌────────────────────────────────┐
│  ✅ Found 10 statutes          │
│  📊 Stats | 💡 Analysis        │
│  📄 Statute cards...           │
└────────────────────────────────┘
```

### 4. Error State
```
┌────────────────────────────────┐
│  ⚠️ Search Error               │
│  Could not complete search.    │
│  Please try again.             │
│  [Retry]                       │
└────────────────────────────────┘
```

## 🎯 Call-to-Actions

### Primary (Blue)
- Search button
- "Read Full Text"
- "Try Example"

### Secondary (Gray)
- "Copy Citation"
- "View Path"
- "Save Search"

## 💼 Professional Features

1. **Confidence Scores** - Show reliability
2. **Citations** - Proper legal format
3. **Breadcrumbs** - Navigation path
4. **Timestamps** - Performance metrics
5. **Source Links** - Verification

## 🚀 User Journey

```
1. Land on page
   ↓
2. See example questions
   ↓
3. Enter query or click example
   ↓
4. Watch agent process (left panel)
   ↓
5. See results appear (right panel)
   ↓
6. Review AI analysis
   ↓
7. Read statute cards
   ↓
8. Copy citations / Read full text
```

This UI is designed for **lawyers, paralegals, and legal researchers** who need:
- ✅ Transparency in AI reasoning
- ✅ Professional appearance
- ✅ Fast, accurate results
- ✅ Proper legal citations
- ✅ Verifiable sources

