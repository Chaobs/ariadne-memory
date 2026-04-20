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

  const response = await fetch(
    `${API_BASE}/ingest/files/stream?memory=${encodeURIComponent(memory || '')}&enrich=${enrich ?? false}`,
    { method: 'POST', body: formData }
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  if (!reader) throw new Error('No response body');

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('event:') || line.startsWith('data:')) {
        const eventMatch = line.match(/^event:\s*(\w+)/);
        const dataMatch = line.match(/^data:\s*(.+)/);
        if (dataMatch) {
          try {
            const data = JSON.parse(dataMatch[1]);
            if (eventMatch?.[1] === 'complete') {
              const result: IngestResultResponse = data;
              yield { type: 'complete', result };
              return result;
            } else if (eventMatch?.[1] === 'progress') {
              yield { type: 'progress', ...data };
            } else if (eventMatch?.[1] === 'success') {
              yield { type: 'success', ...data };
            } else if (eventMatch?.[1] === 'error') {
              yield { type: 'error', ...data };
            } else if (eventMatch?.[1] === 'skip') {
              yield { type: 'skip', ...data };
            }
          } catch {}
        }
      }
    }
  }

  throw new Error('Stream ended without complete event');
}

export interface IngestProgressEvent {
  type: 'complete' | 'progress' | 'success' | 'error' | 'skip';
  result?: IngestResultResponse;
  file?: string;
  progress?: number;
  phase?: string;
  docs?: number;
  error?: string;
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

  suggest: (q: string, memory?: string) =>
    fetchJSON<{ suggestions: string[] }>(
      `${API_BASE}/search/suggest?q=${encodeURIComponent(q)}${memory ? `&memory=${encodeURIComponent(memory)}` : ''}`
    ),

  /** Rebuild BM25 index after ingesting documents */
  rebuildIndex: (memory?: string) =>
    fetchJSON<{ success: boolean; indexed_docs: number; memory: string }>(
      `${API_BASE}/search/rag/rebuild-index`,
      {
        method: 'POST',
        body: memory !== undefined ? JSON.stringify({ memory }) : '{}',
        headers: { 'Content-Type': 'application/json' },
      }
    ),

  /** Check RAG pipeline health */
  health: (memory?: string) =>
    fetchJSON<{
      healthy: boolean;
      memory: string;
      components: Record<string, { healthy: boolean; doc_count?: number; method?: string; error?: string }>;
    }>(`${API_BASE}/search/rag/health${memory ? `?memory=${encodeURIComponent(memory)}` : ''}`),
};

// Graph API
export const graphApi = {
  status: () => fetchJSON<GraphStatus>(`${API_BASE}/graph/status`),

  getData: (maxNodes = 50, entityType?: string) =>
    fetchJSON<{ nodes: GraphNode[]; edges: GraphEdge[]; stats: { entities: number; relations: number; entity_types?: Record<string, number> } }>(
      `${API_BASE}/graph/data?max_nodes=${maxNodes}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ''}`
    ),

  enrich: (memory?: string, limit = 100) =>
    fetchJSON(`${API_BASE}/graph/enrich`, {
      method: 'POST',
      body: JSON.stringify({ memory, limit, force: false }),
    }),

  /** Download graph export as a file (HTML, Markdown, DOCX, SVG, JSON, Mermaid) */
  downloadExport: (format: string, maxNodes = 50, title = 'Knowledge Graph Export') => {
    const url = `${API_BASE}/graph/export/${format}?max_nodes=${maxNodes}&title=${encodeURIComponent(title)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `graph.${format === 'markdown' ? 'md' : format === 'mermaid' ? 'mm' : format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  },
};

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  description?: string;
  aliases?: string[];
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  type?: string;
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