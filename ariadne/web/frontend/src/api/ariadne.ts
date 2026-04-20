/**
 * Ariadne API Client
 * Connects to the FastAPI backend at http://localhost:8770
 */

const API_BASE = '/api';

// SSE (Server-Sent Events) for real-time ingestion progress
export async function* ingestWithProgress(
  files: File[],
  memory?: string,
  enrich?: boolean
): AsyncGenerator<IngestProgressEvent, IngestResultResponse, undefined> {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  if (memory) formData.append('memory', memory);
  if (enrich) formData.append('enrich', 'true');

  const response = await fetch(`${API_BASE}/ingest/files?enrich=${enrich ?? false}${memory ? `&memory=${memory}` : ''}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const result: IngestResultResponse = await response.json();
  yield { type: 'complete', result };
  return result;
}

export interface IngestProgressEvent {
  type: 'complete';
  result: IngestResultResponse;
}

// Type definitions
export interface MemoryInfo {
  name: string;
  description: string;
  path: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface SearchResult {
  content: string;
  source_type: string;
  source_path: string;
  chunk_index: number;
  total_chunks: number;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  memory: string;
}

export interface RAGResult {
  results: SearchResult[];
  citations: Array<{
    text: string;
    source: string;
    format_markdown: string;
  }>;
  metadata: Record<string, unknown>;
  memory: string;
}

export interface SystemInfo {
  version: string;
  current_system: string;
  total_systems: number;
  systems: MemoryInfo[];
  llm_provider: string;
  llm_model: string;
  llm_configured: boolean;
  locale: string;
}

export interface GraphStatus {
  entities: number;
  relations: number;
}

export interface IngestResult {
  docs_added: number;
  skipped: number;
  errors: Array<{ file: string; error: string }>;
  total_files: number;
}

export type IngestResultResponse = IngestResult;

// API helpers
async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json();
}

// Memory System API
export const memoryApi = {
  list: () => fetchJSON<MemoryInfo[]>(`${API_BASE}/memory/list`),

  create: (name: string, description = '') =>
    fetchJSON<MemoryInfo>(`${API_BASE}/memory/create`, {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  rename: (oldName: string, newName: string) =>
    fetchJSON(`${API_BASE}/memory/rename`, {
      method: 'POST',
      body: JSON.stringify({ old_name: oldName, new_name: newName }),
    }),

  delete: (name: string) =>
    fetchJSON(`${API_BASE}/memory/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  merge: (sourceNames: string[], newName: string, deleteSources = false) =>
    fetchJSON(`${API_BASE}/memory/merge`, {
      method: 'POST',
      body: JSON.stringify({ source_names: sourceNames, new_name: newName, delete_sources: deleteSources }),
    }),

  getInfo: (name: string) =>
    fetchJSON<MemoryInfo>(`${API_BASE}/memory/${encodeURIComponent(name)}/info`),

  clear: (name: string) =>
    fetchJSON(`${API_BASE}/memory/${encodeURIComponent(name)}/clear`, {
      method: 'POST',
    }),
};

// Search API
export const searchApi = {
  semantic: (query: string, topK = 5, memory?: string) =>
    fetchJSON<SearchResponse>(`${API_BASE}/search/semantic`, {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, memory }),
    }),

  rag: (query: string, topK = 5, fetchK = 20, alpha = 0.5, memory?: string) =>
    fetchJSON<RAGResult>(`${API_BASE}/search/rag`, {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, fetch_k: fetchK, alpha, memory }),
    }),
};

// Graph API
export const graphApi = {
  status: () => fetchJSON<GraphStatus>(`${API_BASE}/graph/status`),

  getData: (maxNodes = 50) =>
    fetchJSON<{ nodes: GraphNode[]; edges: GraphEdge[]; stats: { entities: number; relations: number } }>(
      `${API_BASE}/graph/data?max_nodes=${maxNodes}`
    ),

  enrich: (memory?: string, limit = 100) =>
    fetchJSON(`${API_BASE}/graph/enrich`, {
      method: 'POST',
      body: JSON.stringify({ memory, limit, force: false }),
    }),
};

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

// Ingest API
export const ingestApi = {
  files: async (files: File[], memory?: string, enrich = false): Promise<IngestResult> => {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    if (memory) form.append('memory', memory);
    form.append('enrich', String(enrich));

    const res = await fetch(`${API_BASE}/ingest/files?memory=${memory || ''}&enrich=${enrich}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },

  directory: (directory: string, memory?: string, recursive = true, enrich = false) =>
    fetchJSON<IngestResult>(`${API_BASE}/ingest/directory`, {
      method: 'POST',
      body: JSON.stringify({ directory, memory, recursive, enrich }),
    }),
};

// Config API
export const configApi = {
  get: () => fetchJSON(`${API_BASE}/config/`),
  set: (key: string, value: string) =>
    fetchJSON(`${API_BASE}/config/set`, {
      method: 'POST',
      body: JSON.stringify({ key, value }),
    }),
  testLLM: () => fetchJSON<{ success: boolean; message: string }>(`${API_BASE}/config/llm/test`, { method: 'POST' }),
  configureLLM: (provider: string, model: string, apiKey: string, baseUrl?: string) =>
    fetchJSON(`${API_BASE}/config/llm`, {
      method: 'POST',
      body: JSON.stringify({ provider, model, api_key: apiKey, base_url: baseUrl }),
    }),
  setLanguage: (locale: string) =>
    fetchJSON(`${API_BASE}/config/language`, {
      method: 'POST',
      body: JSON.stringify({ locale }),
    }),
  providers: () => fetchJSON(`${API_BASE}/config/providers`),
};

// System API
export const systemApi = {
  info: () => fetchJSON<SystemInfo>(`${API_BASE}/system/info`),
  health: () => fetchJSON<{ status: string; version: string }>(`${API_BASE}/health`),
  summarize: (query: string, memory?: string, outputLang?: string) =>
    fetchJSON(`${API_BASE}/system/summarize`, {
      method: 'POST',
      body: JSON.stringify({ query, memory, output_lang: outputLang }),
    }),
};