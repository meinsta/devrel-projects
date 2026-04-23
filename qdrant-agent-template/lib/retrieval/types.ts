/**
 * Retrieval layer types
 */

export type RetrievalMode = "dense" | "sparse" | "hybrid";
export type FusionMethod = "rrf" | "dbsf";

export interface ChunkPayload {
  doc_id: string;
  chunk_id: string;
  text: string;
  source: string;
  title: string;
  url?: string;
  created_at: string;
  updated_at?: string;
  access_scope: string;
  tags: string[];
  path?: string;
  lang?: string;
  section?: string;
  token_count: number;
  hash: string;
  entities?: Array<{ type: string; value: string }>;
}

export interface RetrievedChunk {
  id: string;
  score: number;
  payload: ChunkPayload;
  queryIndex?: number; // Which sub-query retrieved this
}

export interface SearchParams {
  query: string;
  mode: RetrievalMode;
  topK: number;
  filters?: SearchFilters;
  fusionMethod?: FusionMethod;
  rrfK?: number;
}

export interface SearchFilters {
  source?: string[];
  tags?: string[];
  accessScope?: string;
  docId?: string;
  timeRange?: {
    start?: string;
    end?: string;
  };
}

export interface MultiQuerySearchParams {
  queries: Array<{
    text: string;
    weight: number;
    filters?: SearchFilters;
  }>;
  mode: RetrievalMode;
  topKPerQuery: number;
  globalCap: number;
  fusionMethod?: FusionMethod;
  rrfK?: number;
  maxPerDoc?: number;
}

export interface RerankResult {
  index: number;
  score: number;
  document?: string;
}

export interface RerankParams {
  query: string;
  documents: string[];
  topN?: number;
}
