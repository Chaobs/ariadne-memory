/**
 * Search — Semantic and RAG search interface with autocomplete
 */

import { useState, useRef, useEffect } from 'react';
import { searchApi, systemApi } from '../api/ariadne';
import { t } from '../i18n';

const LS_RESULTS_KEY = 'ariadne_search_results';

export default function Search() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<any[]>(() => {
    try { const s = sessionStorage.getItem(LS_RESULTS_KEY); return s ? JSON.parse(s) : []; }
    catch { return []; }
  });
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'semantic' | 'rag'>('semantic');
  const [systems, setSystems] = useState<{ name: string }[]>([]);
  const [memory, setMemory] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState(-1);
  const [ragHealth, setRagHealth] = useState<any>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Persist results to sessionStorage
  useEffect(() => {
    if (results.length > 0) {
      try { sessionStorage.setItem(LS_RESULTS_KEY, JSON.stringify(results)); } catch {}
    }
  }, [results]);

  systemApi.info().then(info => setSystems(info.systems)).catch(console.error);

  // Check RAG health when switching to RAG mode
  useEffect(() => {
    if (mode === 'rag' && !ragHealth) {
      searchApi.health(memory || undefined).then(setRagHealth).catch(() => setRagHealth({ healthy: false }));
    }
  }, [mode, memory]);

  async function handleRebuildIndex() {
    setRebuilding(true);
    try {
      const res = await searchApi.rebuildIndex(memory || undefined);
      setRagHealth({ healthy: true, components: { bm25: { healthy: true, doc_count: res.indexed_docs } } });
    } catch (e) {
      console.error(e);
    } finally {
      setRebuilding(false);
    }
  }

  async function handleCheckHealth() {
    try {
      const res = await searchApi.health(memory || undefined);
      setRagHealth(res);
    } catch (e) {
      console.error(e);
    }
  }

  // Fetch suggestions with debounce
  useEffect(() => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
      try {
        const res = await searchApi.suggest(query, memory || undefined);
        setSuggestions(res.suggestions);
      } catch {
        setSuggestions([]);
      }
    }, 300);
    return () => {
      if (suggestTimer.current) clearTimeout(suggestTimer.current);
    };
  }, [query, memory]);

  function handleSuggestionClick(suggestion: string) {
    setQuery(suggestion);
    setSuggestions([]);
    setShowSuggestions(false);
    // Trigger search immediately
    const form = document.createElement('form');
    const input = document.createElement('input');
    input.value = suggestion;
    form.appendChild(input);
    handleSearch({ preventDefault: () => {} } as React.FormEvent);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedSuggestion(prev => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedSuggestion(prev => Math.max(prev - 1, -1));
    } else if (e.key === 'Enter') {
      if (selectedSuggestion >= 0) {
        e.preventDefault();
        handleSuggestionClick(suggestions[selectedSuggestion]);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSuggestions([]);
    setShowSuggestions(false);
    setSelectedSuggestion(-1);
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
        <h1>🔍 {t('search.title')}</h1>
        <div className="mode-toggle">
          <button
            className={mode === 'semantic' ? 'active' : ''}
            onClick={() => setMode('semantic')}
          >
            {t('search.semantic')}
          </button>
          <button
            className={mode === 'rag' ? 'active' : ''}
            onClick={() => setMode('rag')}
          >
            {t('search.rag')}
          </button>
          {mode === 'rag' && (
            <div className="rag-tools">
              <button
                className="btn-small"
                onClick={() => alert(t('search.rag_help') + '\n\n' + t('search.rag_help_body'))}
                title={t('search.rag_help')}
              >
                ❓ {t('search.rag_help')}
              </button>
              <button
                className="btn-small"
                onClick={handleRebuildIndex}
                disabled={rebuilding}
                title={t('search.rebuild_bm25')}
              >
                {rebuilding ? '⏳' : '🔄'} {t('search.rebuild_bm25')}
              </button>
              <button className="btn-small" onClick={handleCheckHealth} title={t('search.health')}>
                🔍 {t('search.health')}
              </button>
              {ragHealth && (
                <div className="rag-health-info">
                  {ragHealth.components?.bm25 && (
                    <span>📚 BM25: {ragHealth.components.bm25.doc_count ?? ragHealth.components.bm25.error ?? '?'} {t('search.docs')}</span>
                  )}
                  {ragHealth.components?.reranker && (
                    <span>🔄 Reranker: {ragHealth.components.reranker.method ?? ragHealth.components.reranker.error ?? '?'}</span>
                  )}
                  {ragHealth.components?.vector_store && (
                    <span>🗄️ Store: {ragHealth.components.vector_store.error ?? 'OK'}</span>
                  )}
                  {!ragHealth.healthy && <span className="health-warning">⚠️ RAG may return no results</span>}
                </div>
              )}
            </div>
          )}
        </div>
      </header>

      <form className="search-form" onSubmit={handleSearch}>
        <div className="search-input-wrapper" style={{ position: 'relative' }}>
          <input
            ref={inputRef}
            type="text"
            className="search-input"
            placeholder={mode === 'rag' ? t('search.rag_placeholder') : t('search.placeholder')}
            value={query}
            onChange={e => { setQuery(e.target.value); setShowSuggestions(true); setSelectedSuggestion(-1); }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            onKeyDown={handleKeyDown}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions.map((s, i) => (
                <div
                  key={i}
                  className={`suggestion-item ${i === selectedSuggestion ? 'selected' : ''}`}
                  onMouseDown={() => handleSuggestionClick(s)}
                >
                  🔍 {s}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="search-controls">
          <label>
            Results:
            <input
              type="number"
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              min={1}
              max={50}
            />
          </label>
          <label>
            Memory:
            <select value={memory} onChange={e => setMemory(e.target.value)}>
              <option value="">{t('common.default')}</option>
              {systems.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? t('search.loading') : '🔍'}
          </button>
        </div>
      </form>

      {results.length > 0 && (
        <div className="results-list">
          <h2>{t('search.results')} ({results.length})</h2>
          {results.map((r, i) => (
            <div key={i} className="result-card">
              <div className="result-meta">
                <span className="source-type">{r.source_type}</span>
                <span className="source-path">{r.source_path}</span>
                <span className="score">{t('search.score')}: {r.score?.toFixed(4)}</span>
              </div>
              <p className="result-content">{r.content}</p>
              {r.metadata && Object.keys(r.metadata).length > 0 && (
                <details className="result-metadata">
                  <summary>{t('search.metadata')}</summary>
                  <pre>{JSON.stringify(r.metadata, null, 2)}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && results.length === 0 && query.trim() === '' && (
        <div className="empty-state">
          <p>Enter a query to search your memory systems.</p>
          <p>Try semantic search for natural language queries, or RAG for hybrid retrieval.</p>
        </div>
      )}
    </div>
  );
}
