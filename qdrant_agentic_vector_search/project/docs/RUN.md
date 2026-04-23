# California Legal Research - Setup & Run

## 🚀 Quick Start

### Backend (FastAPI)

```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Ensure fastembed is installed for hybrid search
pip install fastembed

# Run server from backend directory
cd backend
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --port 8000
```

Backend will be available at: `http://localhost:8000`

### Frontend (Next.js)

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## 📋 Prerequisites

1. **Environment Variables** (`.env` in project root):
   ```
   QDRANT_CLOUD_URL=your_qdrant_url
   QDRANT_API_KEY=your_api_key
   OPENAI_API_KEY=your_openai_key  # Optional
   ```

2. **Data Ingestion** must be complete:
   ```bash
   # Check progress
   python check_ingestion_progress.py
   ```

## 🎯 Features

### Agentic Flow
- **Real-time streaming** of agent thought process
- **Hybrid search** with RRF fusion
- **Progress indicators** for each step
- **Transparent process** for legal professionals

### Search Capabilities
- Dense vector search (semantic)
- Sparse vector search (BM25/keywords)
- Reciprocal Rank Fusion
- 155,974+ California housing statutes

### User Interface
- Professional legal research interface
- Live agent process visualization
- Statute cards with citations
- Confidence scores
- Full text display

## 🏗️ Architecture

```
┌─────────────┐
│   Next.js   │  ← User Interface
│  (Port 3000)│
└──────┬──────┘
       │
       │ HTTP/SSE
       │
┌──────▼──────────────────────────┐
│   FastAPI Backend (Port 8000)   │
│  ┌────────────────────────────┐ │
│  │ CaliforniaService          │ │
│  │ • Streaming agentic flow   │ │
│  │ • Hybrid Search (RRF)      │ │
│  │ • Dense + Sparse vectors   │ │
│  └────────────────────────────┘ │
│  Existing Services:             │
│  • SearchService (Simple RAG)   │
│  • CrewService (Agentic RAG)    │
│  • QdrantService                │
└──────┬──────────────────────────┘
       │
       │ Hybrid Search
       │
┌──────▼──────┐
│   Qdrant    │  ← Vector Database
│   (Cloud)   │  • california_housing_statutes_full
│             │  • california_housing_questions
└─────────────┘
```

## 🔍 API Endpoints

### POST /api/research
Streaming endpoint for agentic legal research.

**Request:**
```json
{
  "query": "Can a landlord evict without notice?"
}
```

**Response:** Server-Sent Events (SSE) stream
```
data: {"type": "step", "action": "analyze", ...}
data: {"type": "step", "action": "search", ...}
data: {"type": "result", "statutes": [...], ...}
```

### GET /api/health
Health check endpoint.

### GET /api/stats
Collection statistics.

## 🎨 Customization

### Modify Search Parameters
Edit `backend_api/main.py`:
```python
# Change number of results
limit=10  # Increase for more statutes

# Adjust prefetch limits
limit=20  # More candidates for RRF
```

### Styling
Edit `frontend/app/globals.css` for custom styles.

### Agent Steps
Modify `research_flow()` in `backend_api/main.py` to add/remove steps.

## 📊 Monitoring

```bash
# Check backend logs
tail -f backend_api.log

# Check ingestion progress
python check_ingestion_progress.py --watch

# View full ingestion log
tail -f california_full_ingestion.log
```

## 🐛 Troubleshooting

**CORS Errors:** Ensure frontend URL is in `allow_origins` in `backend_api/main.py`

**Connection Refused:** Check that backend is running on port 8000

**No Results:** Verify ingestion completed:
```bash
python check_ingestion_progress.py
```

**Slow Search:** Large collection - first query may be slower

## 📝 Development

```bash
# Frontend hot reload
cd frontend && npm run dev

# Backend hot reload
cd backend_api && uvicorn main:app --reload

# Type checking (frontend)
cd frontend && npm run lint
```

## 🚢 Production

```bash
# Build frontend
cd frontend && npm run build && npm start

# Run backend with gunicorn
cd backend_api
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

