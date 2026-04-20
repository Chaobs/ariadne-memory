/**
 * Search — Semantic and RAG search interface
 */

import { useState } from 'react';
import { searchApi, systemApi } from '../api/ariadne';

export default function Search() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'semantic' | 'rag'>('semantic');
  const [systems, setSystems] = useState<{ name: string }[]>([]);
  const [memory, setMemory] = useState('');

  // Load systems for dropdown
  systemApi.info().then(info => setSystems(info.systems)).catch(console.error);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      if (mode === 'rag') {
        const res = await searchApi.rag(query, topK, 20, 0.5, memory || undefined);
        setResults(res.results);
      } else {
        const res = await searchApi.semantic(query, topK, memory || undefined);
        setResults(res.results);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page search">
      <header className="page-header">
        <h1>🔍 Search</h1>
        <div className="mode-toggle">
          <button className={mode === 'semantic' ? 'active' : ''} onClick={() => setMode('semantic')}>
            Semantic
          </button>
          <button className={mode === 'rag' ? 'active' : ''} onClick={() => setMode('rag')}>
            RAG (Hybrid)
          </button>
        </div>
      </header>

      <form className="search-form" onSubmit={handleSearch}>
        <input
          type="text"
          className="search-input"
          placeholder={`Search with ${mode === 'rag' ? 'RAG (vector + BM25)' : 'semantic similarity'}...`}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <div className="search-controls">
          <label>
            Results:
            <input type="number" value={topK} onChange={e => setTopK(Number(e.target.value))} min={1} max={50} />
          </label>
          <label>
            Memory:
            <select value={memory} onChange={e => setMemory(e.target.value)}>
              <option value="">Default</option>
              {systems.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {results.length > 0 && (
        <div className="results-list">
          <h2>Results ({results.length})</h2>
          {results.map((r, i) => (
            <div key={i} className="result-card">
              <div className="result-meta">
                <span className="source-type">{r.source_type}</span>
                <span className="source-path">{r.source_path}</span>
                <span className="score">Score: {r.score?.toFixed(4)}</span>
              </div>
              <p className="result-content">{r.content}</p>
              {r.metadata && Object.keys(r.metadata).length > 0 && (
                <details className="result-metadata">
                  <summary>Metadata</summary>
                  <pre>{JSON.stringify(r.metadata, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}