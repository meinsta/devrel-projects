"use client";

import { useState, useEffect, useCallback } from "react";

interface SearchResult {
  id: string;
  score: number;
  image_url: string;
  timestamp: string;
}

interface Status {
  is_indexing: boolean;
  frames_indexed: number;
  queue_size: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:7777";

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/status`);
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch {
      // API not ready yet
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), limit: 6 }),
      });

      if (!res.ok) throw new Error("Search failed");

      const data = await res.json();
      setResults(data);
    } catch {
      setError("Search failed. Make sure the API is running.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            Visual Search Demo
          </h1>
          <p className="text-purple-300 text-lg">
            Powered by{" "}
            <a
              href="https://qdrant.tech/edge/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-purple-400 hover:text-purple-200 underline"
            >
              Qdrant Edge
            </a>
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left Column - Video & Search */}
          <div className="space-y-6">
            {/* Video Player */}
            <div className="bg-slate-800/50 rounded-2xl p-6 backdrop-blur-sm border border-purple-500/20">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <span className="text-2xl">📹</span> Live Video Feed
              </h2>
              <div className="relative aspect-video bg-black rounded-xl overflow-hidden">
                <video
                  src={process.env.NEXT_PUBLIC_VIDEO_URL || "/video.mp4"}
                  autoPlay
                  muted
                  loop
                  playsInline
                  className="w-full h-full object-cover"
                />
                {status?.is_indexing && (
                  <div className="absolute top-3 right-3 bg-red-500 text-white text-xs px-2 py-1 rounded-full animate-pulse flex items-center gap-1">
                    <span className="w-2 h-2 bg-white rounded-full"></span>
                    Indexing
                  </div>
                )}
              </div>
              <p className="text-slate-400 text-sm mt-3">
                Video frames are being indexed in real-time using CLIP embeddings
              </p>
            </div>

            {/* Search Box */}
            <div className="bg-slate-800/50 rounded-2xl p-6 backdrop-blur-sm border border-purple-500/20">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <span className="text-2xl">🔍</span> Search What You Saw
              </h2>
              <form onSubmit={handleSearch} className="space-y-4">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Describe what you're looking for..."
                  className="w-full px-4 py-3 bg-slate-700/50 border border-purple-500/30 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <button
                  type="submit"
                  disabled={searching || !query.trim()}
                  className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors"
                >
                  {searching ? "Searching..." : "Search"}
                </button>
              </form>
              {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
            </div>
          </div>

          {/* Right Column - Results & Status */}
          <div className="space-y-6">
            {/* Edge Status */}
            <div className="bg-slate-800/50 rounded-2xl p-6 backdrop-blur-sm border border-purple-500/20">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <span className="text-2xl">⚡</span> Qdrant Edge Status
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-700/50 rounded-xl p-4">
                  <p className="text-slate-400 text-sm">Frames Indexed</p>
                  <p className="text-2xl font-bold text-purple-400">
                    {status?.frames_indexed ?? 0}
                  </p>
                </div>
                <div className="bg-slate-700/50 rounded-xl p-4">
                  <p className="text-slate-400 text-sm">Sync Queue</p>
                  <p className="text-2xl font-bold text-purple-400">
                    {status?.queue_size ?? 0}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <div
                  className={`w-3 h-3 rounded-full ${
                    status?.queue_size === 0 ? "bg-green-500" : "bg-yellow-500 animate-pulse"
                  }`}
                ></div>
                <span className="text-slate-300 text-sm">
                  {status?.queue_size === 0 ? "Synced with server" : "Syncing to server..."}
                </span>
              </div>
              <p className="text-slate-500 text-xs mt-3">
                Local edge shard enables instant search while syncing to cloud
              </p>
            </div>

            {/* Search Results */}
            <div className="bg-slate-800/50 rounded-2xl p-6 backdrop-blur-sm border border-purple-500/20">
              <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                <span className="text-2xl">🖼️</span> Search Results
              </h2>
              {results.length === 0 ? (
                <div className="text-center py-12 text-slate-400">
                  <p className="text-4xl mb-2">🔎</p>
                  <p>Search for something you saw in the video</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {results.map((result) => (
                    <div
                      key={result.id}
                      className="relative group rounded-xl overflow-hidden bg-slate-700/30"
                    >
                      <img
                        src={`${API_URL}${result.image_url}`}
                        alt="Search result"
                        className="w-full aspect-video object-cover"
                      />
                      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                        <p className="text-white text-xs">
                          Score: {(result.score * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-slate-500 text-sm">
          <p>
            Demo showcasing{" "}
            <a
              href="https://qdrant.tech/edge/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-purple-400 hover:underline"
            >
              Qdrant Edge
            </a>{" "}
            - Local vector search with cloud sync
          </p>
        </div>
      </div>
    </div>
  );
}
