export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Agentic Vector Search API</h1>
      <p>A multi-query planning, fusion, reranking, critique, and corrective retrieval system.</p>
      
      <h2>Endpoints</h2>
      <ul>
        <li><code>POST /api/answer</code> - Query with agent loop (streaming)</li>
        <li><code>POST /api/search</code> - Direct search without answer generation</li>
        <li><code>POST /api/ingest</code> - Ingest documents</li>
        <li><code>GET /api/trace/[traceId]</code> - View agent run trace</li>
        <li><code>POST /api/feedback</code> - Submit feedback</li>
        <li><code>POST /api/memory</code> - Create or search memories</li>
        <li><code>GET /api/memory?userId=...</code> - List user memories</li>
      </ul>

      <h2>Example: Ask a Question</h2>
      <pre style={{ background: "#f4f4f4", padding: "1rem", overflow: "auto" }}>
{`curl -X POST http://localhost:3489/api/answer \\
  -H "Content-Type: application/json" \\
  -d '{"query": "How does the corrective retrieval loop work?", "stream": false}'`}
      </pre>

      <h2>Example: Ingest a Document</h2>
      <pre style={{ background: "#f4f4f4", padding: "1rem", overflow: "auto" }}>
{`curl -X POST http://localhost:3489/api/ingest \\
  -H "Content-Type: application/json" \\
  -d '{
    "documents": [{
      "content": "# My Document\\n\\nThis is the content...",
      "metadata": {
        "source": "docs",
        "title": "My Document"
      }
    }]
  }'`}
      </pre>

      <h2>Example: Search</h2>
      <pre style={{ background: "#f4f4f4", padding: "1rem", overflow: "auto" }}>
{`curl -X POST http://localhost:3489/api/search \\
  -H "Content-Type: application/json" \\
  -d '{"query": "corrective retrieval", "mode": "hybrid", "topK": 10}'`}
      </pre>
    </main>
  );
}
