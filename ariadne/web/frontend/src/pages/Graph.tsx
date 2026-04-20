/**
 * Graph — Knowledge graph visualization + enrichment
 */

import { useState, useEffect } from 'react';
import { graphApi } from '../api/ariadne';
import D3Graph from '../components/D3Graph';

export default function Graph() {
  const [status, setStatus] = useState<{ entities: number; relations: number } | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<any>(null);

  useEffect(() => {
    graphApi.status().then(setStatus).catch(console.error);
  }, []);

  async function handleEnrich() {
    setEnriching(true);
    setEnrichResult(null);
    try {
      const result = await graphApi.enrich();
      setEnrichResult(result);
      // Refresh status
      const newStatus = await graphApi.status();
      setStatus(newStatus);
    } catch (e: any) {
      setEnrichResult({ error: e.message });
    } finally {
      setEnriching(false);
    }
  }

  return (
    <div className="page graph">
      <header className="page-header">
        <h1>🕸️ Knowledge Graph</h1>
        <p className="subtitle">
          Interactive visualization of entities and relationships
        </p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-icon">👤</span>
          <div className="stat-body">
            <span className="stat-value">{status?.entities ?? '—'}</span>
            <span className="stat-label">Entities</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🔗</span>
          <div className="stat-body">
            <span className="stat-value">{status?.relations ?? '—'}</span>
            <span className="stat-label">Relations</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📊</span>
          <div className="stat-body">
            <span className={`stat-value ${status?.entities ? 'ok' : ''}`}>
              {status?.entities ? 'Active' : 'Empty'}
            </span>
            <span className="stat-label">Status</span>
          </div>
        </div>
      </div>

      <div className="form-card" style={{ marginBottom: '20px' }}>
        <h2>🔧 Graph Enrichment</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: '16px', fontSize: '0.9rem' }}>
          Extract entities and relations from documents using LLM. Requires LLM configuration.
        </p>
        <button
          className="btn-primary"
          onClick={handleEnrich}
          disabled={enriching}
        >
          {enriching ? '⏳ Enriching...' : '🚀 Enrich Graph'}
        </button>

        {enrichResult && (
          <div className={enrichResult.error ? 'test-result error' : 'test-result success'} style={{ marginTop: '12px' }}>
            {enrichResult.error ? (
              <>⚠️ {enrichResult.error}</>
            ) : (
              <>
                ✅ Processed {enrichResult.documents_processed} documents — {enrichResult.entities_added} entities, {enrichResult.relations_added} relations
              </>
            )}
          </div>
        )}
      </div>

      <D3Graph />
    </div>
  );
}
