/**
 * Graph — Knowledge graph visualization + enrichment + export
 */

import { useState, useEffect } from 'react';
import { graphApi } from '../api/ariadne';
import D3Graph from '../components/D3Graph';
import { t } from '../i18n';

const ENTITY_TYPES = [
  { code: 'ALL', label: 'All Types' },
  { code: 'PERSON', label: '👤 Person' },
  { code: 'ORGANIZATION', label: '🏢 Organization' },
  { code: 'LOCATION', label: '💡 Location' },
  { code: 'CONCEPT', label: '📍 Concept' },
  { code: 'TECHNOLOGY', label: '🔧 Technology' },
  { code: 'EVENT', label: '📅 Event' },
];

export default function Graph() {
  const [status, setStatus] = useState<{ entities: number; relations: number } | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<any>(null);
  const [filterType, setFilterType] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedNode, setHighlightedNode] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  useEffect(() => {
    graphApi.status().then(setStatus).catch(console.error);
  }, []);

  async function handleEnrich() {
    setEnriching(true);
    setEnrichResult(null);
    try {
      const result = await graphApi.enrich();
      setEnrichResult(result);
      const newStatus = await graphApi.status();
      setStatus(newStatus);
    } catch (e: any) {
      setEnrichResult({ error: e.message });
    } finally {
      setEnriching(false);
    }
  }

  function handleExport(format: string) {
    setShowExportMenu(false);
    graphApi.downloadExport(format, 200, 'Knowledge Graph Export');
  }

  function handleNodeHighlight(nodeId: string | null) {
    setHighlightedNode(nodeId);
  }

  return (
    <div className="page graph">
      <header className="page-header">
        <h1>🕸️ {t('graph.title')}</h1>
        <p className="subtitle">{t('graph.subtitle')}</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-icon">👤</span>
          <div className="stat-body">
            <span className="stat-value">{status?.entities ?? '—'}</span>
            <span className="stat-label">{t('graph.entities')}</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🔗</span>
          <div className="stat-body">
            <span className="stat-value">{status?.relations ?? '—'}</span>
            <span className="stat-label">{t('graph.relations')}</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📊</span>
          <div className="stat-body">
            <span className={`stat-value ${status?.entities ? 'ok' : ''}`}>
              {status?.entities ? t('stats.active') : t('stats.empty')}
            </span>
            <span className="stat-label">{t('graph.status')}</span>
          </div>
        </div>
      </div>

      <div className="form-card" style={{ marginBottom: '20px' }}>
        <h2>🔧 {t('graph.enrich')}</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: '16px', fontSize: '0.9rem' }}>
          {t('graph.enrich_hint')}
        </p>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            onClick={handleEnrich}
            disabled={enriching}
          >
            {enriching ? '⏳ ' + t('graph.enriching') : '🚀 ' + t('graph.enrich')}
          </button>

          {enrichResult && (
            <span className={enrichResult.error ? 'text-error' : 'text-success'}>
              {enrichResult.error ? (
                <>⚠️ {enrichResult.error}</>
              ) : (
                <>✅ {enrichResult.documents_processed} docs — {enrichResult.entities_added} entities</>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Graph controls: filter, search, export */}
      <div className="graph-controls-bar" style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Type filter */}
        <div className="form-group" style={{ margin: 0 }}>
          <label>{t('graph.filter_type')}:</label>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            style={{ minWidth: '140px' }}
          >
            {ENTITY_TYPES.map(et => (
              <option key={et.code} value={et.code}>{et.label}</option>
            ))}
          </select>
        </div>

        {/* Node search */}
        <div className="form-group" style={{ margin: 0, flex: 1, minWidth: '160px' }}>
          <input
            type="text"
            placeholder={t('graph.search_node')}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        {/* Export dropdown */}
        <div className="export-dropdown" style={{ position: 'relative' }}>
          <button
            className="btn-secondary"
            onClick={() => setShowExportMenu(!showExportMenu)}
          >
            📥 {t('graph.export')} ▾
          </button>
          {showExportMenu && (
            <div className="export-menu">
              <button onClick={() => handleExport('html')}>🌐 HTML</button>
              <button onClick={() => handleExport('markdown')}>📝 Markdown</button>
              <button onClick={() => handleExport('docx')}>📄 Word (.docx)</button>
              <button onClick={() => handleExport('svg')}>🖼️ SVG</button>
              <button onClick={() => handleExport('json')}>📋 JSON</button>
              <button onClick={() => handleExport('mermaid')}>📊 Mermaid</button>
              <hr style={{ margin: '4px 0', borderColor: 'var(--border)' }} />
              <button onClick={() => {
                setShowExportMenu(false);
                // Trigger PNG download from D3Graph component via custom event
                window.dispatchEvent(new CustomEvent('graph:export-png'));
              }}>📷 PNG</button>
            </div>
          )}
        </div>
      </div>

      <D3Graph
        filterType={filterType === 'ALL' ? undefined : filterType}
        searchQuery={searchQuery}
        onNodeHighlight={handleNodeHighlight}
        highlightedNodeId={highlightedNode}
      />
    </div>
  );
}
