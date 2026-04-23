/**
 * Wiki — LLM Wiki interface (Karpathy-style persistent knowledge base)
 * Provides: Init, Ingest, Query, Lint, Pages CRUD, Preview
 */

import { useState, useEffect, useCallback } from 'react';
import { wikiApi, type WikiPage, type WikiIngestResult, type WikiQueryResult, type WikiLintResult } from '../api/ariadne';
import { t } from '../i18n';

// Page tabs
type Tab = 'overview' | 'ingest' | 'query' | 'lint' | 'pages' | 'log';

interface WikiOverview {
  projectPath: string;
  hasProject: boolean;
  pagesCount: number;
  overview: string;
}

const PAGE_TYPE_COLORS: Record<string, string> = {
  source: '#3b82f6',
  entity: '#8b5cf6',
  concept: '#10b981',
  comparison: '#f59e0b',
  query: '#06b6d4',
  synthesis: '#ec4899',
  index: '#6b7280',
  log: '#6b7280',
  overview: '#6b7280',
};

const OUTPUT_LANGS = [
  { code: '', name: 'Auto-detect' },
  { code: 'en', name: 'English' },
  { code: 'zh_CN', name: '简体中文' },
  { code: 'zh_TW', name: '繁體中文' },
  { code: 'ja', name: '日本語' },
  { code: 'fr', name: 'Français' },
  { code: 'es', name: 'Español' },
  { code: 'ru', name: 'Русский' },
];

export default function Wiki() {
  const [tab, setTab] = useState<Tab>('overview');
  const [projectPath, setProjectPath] = useState(() => localStorage.getItem('wiki_project_path') || '.');
  const [overview, setOverview] = useState<WikiOverview | null>(null);
  const [pages, setPages] = useState<WikiPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<{ path: string; content: string } | null>(null);
  const [logContent, setLogContent] = useState('');

  // Ingest state
  const [ingestSource, setIngestSource] = useState('');
  const [ingestLang, setIngestLang] = useState('');
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestResult, setIngestResult] = useState<WikiIngestResult | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Query state
  const [queryText, setQueryText] = useState('');
  const [queryLang, setQueryLang] = useState('');
  const [querySave, setQuerySave] = useState(false);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResult, setQueryResult] = useState<WikiQueryResult | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Lint state
  const [lintStructuralOnly, setLintStructuralOnly] = useState(false);
  const [lintLang, setLintLang] = useState('');
  const [lintLoading, setLintLoading] = useState(false);
  const [lintResult, setLintResult] = useState<WikiLintResult | null>(null);
  const [lintError, setLintError] = useState<string | null>(null);

  // Init state
  const [initName, setInitName] = useState('');
  const [initLoading, setInitLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  // Load overview
  const loadOverview = useCallback(async () => {
    try {
      const [pagesRes, overviewRes] = await Promise.all([
        wikiApi.pages(projectPath),
        wikiApi.overview(projectPath),
      ]);
      setOverview({
        projectPath,
        hasProject: pagesRes.total > 0 || overviewRes.content !== '(No overview yet)',
        pagesCount: pagesRes.total,
        overview: overviewRes.content,
      });
    } catch {
      setOverview({ projectPath, hasProject: false, pagesCount: 0, overview: '' });
    }
  }, [projectPath]);

  // Load pages list
  const loadPages = useCallback(async () => {
    try {
      const res = await wikiApi.pages(projectPath);
      setPages(res.pages);
    } catch {
      setPages([]);
    }
  }, [projectPath]);

  // Load log
  const loadLog = useCallback(async () => {
    try {
      const res = await wikiApi.log(projectPath);
      setLogContent(res.content);
    } catch {
      setLogContent('');
    }
  }, [projectPath]);

  useEffect(() => {
    localStorage.setItem('wiki_project_path', projectPath);
  }, [projectPath]);

  useEffect(() => {
    if (tab === 'overview') loadOverview();
    if (tab === 'pages') loadPages();
    if (tab === 'log') loadLog();
  }, [tab, projectPath, loadOverview, loadPages, loadLog]);

  // Handle page click
  async function handlePageClick(page: WikiPage) {
    try {
      const res = await wikiApi.page(page.path, projectPath);
      setSelectedPage({ path: page.path, content: res.content });
    } catch (e: any) {
      setSelectedPage({ path: page.path, content: `Error: ${e.message}` });
    }
  }

  // Ingest
  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!ingestSource.trim()) return;
    setIngestLoading(true);
    setIngestResult(null);
    setIngestError(null);
    try {
      const result = await wikiApi.ingest(ingestSource, projectPath, ingestLang, false);
      setIngestResult(result);
      if (result.ok) loadOverview();
    } catch (err: any) {
      setIngestError(err.message || String(err));
    } finally {
      setIngestLoading(false);
    }
  }

  // Query
  async function handleQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!queryText.trim()) return;
    setQueryLoading(true);
    setQueryResult(null);
    setQueryError(null);
    try {
      const result = await wikiApi.query(queryText, projectPath, queryLang, querySave);
      setQueryResult(result);
    } catch (err: any) {
      setQueryError(err.message || String(err));
    } finally {
      setQueryLoading(false);
    }
  }

  // Lint
  async function handleLint(e: React.FormEvent) {
    e.preventDefault();
    setLintLoading(true);
    setLintResult(null);
    setLintError(null);
    try {
      const result = await wikiApi.lint(projectPath, lintStructuralOnly, lintLang);
      setLintResult(result);
    } catch (err: any) {
      setLintError(err.message || String(err));
    } finally {
      setLintLoading(false);
    }
  }

  // Init project
  async function handleInit(e: React.FormEvent) {
    e.preventDefault();
    setInitLoading(true);
    setInitError(null);
    try {
      await wikiApi.init(projectPath, initName);
      await wikiApi.saveProject(projectPath);
      await loadOverview();
    } catch (err: any) {
      setInitError(err.message || String(err));
    } finally {
      setInitLoading(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'overview', label: 'wiki.overview', icon: '📋' },
    { id: 'ingest', label: 'wiki.ingest', icon: '📥' },
    { id: 'query', label: 'wiki.query', icon: '❓' },
    { id: 'lint', label: 'wiki.lint', icon: '🔍' },
    { id: 'pages', label: 'wiki.pages', icon: '📄' },
    { id: 'log', label: 'wiki.log', icon: '📜' },
  ];

  return (
    <div className="page wiki">
      <header className="page-header">
        <h1>📖 {t('wiki.title')}</h1>
        <p className="subtitle">{t('wiki.description')}</p>
      </header>

      {/* Project selector */}
      <div className="form-card" style={{ marginBottom: '16px' }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label>{t('wiki.project_dir')}</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={projectPath}
              onChange={e => setProjectPath(e.target.value)}
              placeholder="."
              style={{ flex: 1 }}
            />
            <button className="btn-secondary" onClick={loadOverview} title="Refresh">
              🔄
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          <button className="btn-primary" onClick={() => setTab('overview')}>
            📋 {t('wiki.init_project')}
          </button>
          <button className="btn-secondary" onClick={() => { wikiApi.saveProject(projectPath); }}>
            💾 {t('wiki.save_project')}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        {tabs.map(tb => (
          <button
            key={tb.id}
            className={`tab-btn ${tab === tb.id ? 'active' : ''}`}
            onClick={() => setTab(tb.id)}
          >
            {tb.icon} {t(tb.label)}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === 'overview' && overview && (
        <div className="tab-content">
          <div className="stat-cards">
            <div className="stat-card">
              <div className="stat-value">{overview.pagesCount}</div>
              <div className="stat-label">{t('wiki.pages')}</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{overview.hasProject ? '✓' : '—'}</div>
              <div className="stat-label">{t('wiki.project_status')}</div>
            </div>
          </div>

          {!overview.hasProject && (
            <div className="form-card">
              <h3>🆕 {t('wiki.init_new')}</h3>
              <form onSubmit={handleInit}>
                <div className="form-group">
                  <label>{t('wiki.project_name')} ({t('common.optional')})</label>
                  <input
                    type="text"
                    value={initName}
                    onChange={e => setInitName(e.target.value)}
                    placeholder="My Research Wiki"
                  />
                </div>
                {initError && <div className="alert alert-error">{initError}</div>}
                <button type="submit" className="btn-primary" disabled={initLoading}>
                  {initLoading ? '⏳...' : `✨ ${t('wiki.init_btn')}`}
                </button>
              </form>
            </div>
          )}

          {overview.overview && (
            <div className="form-card">
              <h3>📋 {t('wiki.overview')}</h3>
              <div className="markdown-preview">
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px' }}>{overview.overview}</pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ingest tab */}
      {tab === 'ingest' && (
        <div className="tab-content">
          <div className="form-card">
            <h3>📥 {t('wiki.ingest_file')}</h3>
            <p className="form-hint">{t('wiki.ingest_hint')}</p>
            <form onSubmit={handleIngest}>
              <div className="form-group">
                <label>{t('wiki.source_path')}</label>
                <input
                  type="text"
                  value={ingestSource}
                  onChange={e => setIngestSource(e.target.value)}
                  placeholder="C:\Documents\paper.pdf"
                  required
                />
              </div>
              <div className="form-group">
                <label>{t('summarize.output_lang')}</label>
                <select value={ingestLang} onChange={e => setIngestLang(e.target.value)}>
                  {OUTPUT_LANGS.map(l => (
                    <option key={l.code} value={l.code}>{l.name}</option>
                  ))}
                </select>
              </div>
              {ingestError && <div className="alert alert-error">{ingestError}</div>}
              <button type="submit" className="btn-primary" disabled={ingestLoading}>
                {ingestLoading ? '⏳ LLM processing...' : `📥 ${t('wiki.ingest_btn')}`}
              </button>
            </form>
          </div>

          {ingestResult && (
            <div className="result-panel">
              <h3>✅ {t('wiki.ingest_result')}</h3>
              <p><strong>{t('wiki.pages_created')}:</strong> {ingestResult.pages_count}</p>
              {ingestResult.cached && <span className="badge badge-info">⚡ Cached</span>}
              {ingestResult.pages_written.map((p, i) => (
                <div key={i} className="result-item">📄 {p}</div>
              ))}
              {ingestResult.warnings.length > 0 && (
                <div className="alert alert-warning">
                  {t('common.warning')}: {ingestResult.warnings.join(', ')}
                </div>
              )}
              {ingestResult.review_items.length > 0 && (
                <div>
                  <h4>⚠️ {t('wiki.review_items')} ({ingestResult.review_items.length})</h4>
                  {ingestResult.review_items.map((item, i) => (
                    <div key={i} className="review-item">
                      <strong>[{item.type}]</strong> {item.title}
                      <br /><small>{item.description}</small>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Query tab */}
      {tab === 'query' && (
        <div className="tab-content">
          <div className="form-card">
            <h3>❓ {t('wiki.ask_question')}</h3>
            <form onSubmit={handleQuery}>
              <div className="form-group">
                <label>{t('wiki.question')}</label>
                <textarea
                  value={queryText}
                  onChange={e => setQueryText(e.target.value)}
                  placeholder={t('wiki.query_placeholder')}
                  rows={3}
                  required
                />
              </div>
              <div className="form-group">
                <label>{t('summarize.output_lang')}</label>
                <select value={queryLang} onChange={e => setQueryLang(e.target.value)}>
                  {OUTPUT_LANGS.map(l => (
                    <option key={l.code} value={l.code}>{l.name}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>
                  <input
                    type="checkbox"
                    checked={querySave}
                    onChange={e => setQuerySave(e.target.checked)}
                    style={{ marginRight: '6px' }}
                  />
                  {t('wiki.save_to_wiki')}
                </label>
              </div>
              {queryError && <div className="alert alert-error">{queryError}</div>}
              <button type="submit" className="btn-primary" disabled={queryLoading}>
                {queryLoading ? '⏳ LLM thinking...' : `❓ ${t('wiki.query_btn')}`}
              </button>
            </form>
          </div>

          {queryResult && (
            <div className="result-panel">
              <h3>💬 {t('wiki.answer')}</h3>
              <div className="markdown-preview">
                <pre style={{ whiteSpace: 'pre-wrap' }}>{queryResult.answer}</pre>
              </div>
              {queryResult.cited_pages.length > 0 && (
                <p className="form-hint">
                  📚 {t('wiki.cited_pages')}: {queryResult.cited_pages.join(', ')}
                </p>
              )}
              {queryResult.saved_to && (
                <p className="form-hint">💾 {t('wiki.saved_to')}: {queryResult.saved_to}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Lint tab */}
      {tab === 'lint' && (
        <div className="tab-content">
          <div className="form-card">
            <h3>🔍 {t('wiki.lint_wiki')}</h3>
            <form onSubmit={handleLint}>
              <div className="form-group">
                <label>
                  <input
                    type="checkbox"
                    checked={lintStructuralOnly}
                    onChange={e => setLintStructuralOnly(e.target.checked)}
                    style={{ marginRight: '6px' }}
                  />
                  {t('wiki.structural_only')}
                </label>
                <p className="form-hint">{t('wiki.structural_only_hint')}</p>
              </div>
              {!lintStructuralOnly && (
                <div className="form-group">
                  <label>{t('summarize.output_lang')}</label>
                  <select value={lintLang} onChange={e => setLintLang(e.target.value)}>
                    {OUTPUT_LANGS.map(l => (
                      <option key={l.code} value={l.code}>{l.name}</option>
                    ))}
                  </select>
                </div>
              )}
              {lintError && <div className="alert alert-error">{lintError}</div>}
              <button type="submit" className="btn-primary" disabled={lintLoading}>
                {lintLoading ? '⏳ Analyzing...' : `🔍 ${t('wiki.lint_btn')}`}
              </button>
            </form>
          </div>

          {lintResult && (
            <div className="result-panel">
              <h3>🔍 {t('wiki.lint_result')}</h3>
              <p>
                {t('wiki.total_issues')}: <strong>{lintResult.total}</strong>
                {lintResult.warnings > 0 && (
                  <span className="badge badge-warning"> {lintResult.warnings} warnings</span>
                )}
              </p>
              {lintResult.issues.length === 0 && (
                <div className="alert alert-success">✅ {t('wiki.no_issues')}</div>
              )}
              {lintResult.issues.map((issue, i) => (
                <div key={i} className={`lint-issue lint-${issue.severity}`}>
                  <strong>[{issue.severity}] {issue.type}</strong>
                  <br />📄 {issue.page}
                  <br /><small>{issue.detail}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pages tab */}
      {tab === 'pages' && (
        <div className="tab-content" style={{ display: 'flex', gap: '16px' }}>
          <div style={{ flex: '0 0 320px' }}>
            <div className="form-card">
              <h3>📄 {t('wiki.pages_list')}</h3>
              {pages.length === 0 && <p className="form-hint">{t('wiki.no_pages')}</p>}
              {pages.map(page => (
                <div
                  key={page.path}
                  className="page-item"
                  onClick={() => handlePageClick(page)}
                  style={{ cursor: 'pointer', padding: '8px', borderBottom: '1px solid var(--border)', color: PAGE_TYPE_COLORS[page.type] || '#666' }}
                >
                  <span className="badge" style={{ background: PAGE_TYPE_COLORS[page.type] || '#666' }}>
                    {page.type}
                  </span>
                  {' '}{page.title || page.path}
                </div>
              ))}
            </div>
          </div>
          <div style={{ flex: 1 }}>
            {selectedPage ? (
              <div className="form-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3>📄 {selectedPage.path}</h3>
                  <button className="btn-secondary" onClick={() => setSelectedPage(null)}>✕</button>
                </div>
                <div className="markdown-preview">
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', maxHeight: '60vh', overflow: 'auto' }}>
                    {selectedPage.content}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="form-card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
                <p>{t('wiki.select_page')}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Log tab */}
      {tab === 'log' && (
        <div className="tab-content">
          <div className="form-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>📜 {t('wiki.operation_log')}</h3>
              <button className="btn-secondary" onClick={loadLog}>🔄</button>
            </div>
            <div className="markdown-preview">
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', maxHeight: '60vh', overflow: 'auto' }}>
                {logContent || '(No log yet)'}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
