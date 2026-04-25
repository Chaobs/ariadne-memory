/**
 * Wiki — LLM Wiki interface (Karpathy-style persistent knowledge base)
 *
 * Fixed:
 *  - Initialized Project / Save to Recent now correctly call backend
 *  - Initialize Wiki API 422 fixed (project_path sent as JSON body)
 *  - Ingest Source File: file picker dialog (server-side FS browser)
 *  - Project Directory: manual dir picker dialog
 *  - Help button added
 *  - Tab buttons unified with btn-secondary / btn-primary style
 *  - LLM 401 error: show config hint
 *  - docx/pdf read failure: fixed in backend (markitdown extraction)
 */

import { useState, useEffect, useCallback } from 'react';
import { wikiApi, type WikiPage, type WikiIngestResult, type WikiQueryResult, type WikiLintResult } from '../api/ariadne';
import { t } from '../i18n';

type Tab = 'overview' | 'ingest' | 'query' | 'lint' | 'pages' | 'log';

interface WikiOverview {
  projectPath: string;
  hasProject: boolean;
  pagesCount: number;
  overview: string;
}

interface FsEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

interface FsBrowseResult {
  ok: boolean;
  current: string;
  parent: string | null;
  entries: FsEntry[];
  drives: string[];
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

// ── File/Dir Picker Modal ──────────────────────────────────────────────────────

interface FsPickerProps {
  mode: 'dir' | 'file';
  title: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

function FsPicker({ mode, title, onSelect, onClose }: FsPickerProps) {
  const [current, setCurrent] = useState('');
  const [result, setResult] = useState<FsBrowseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [manualPath, setManualPath] = useState('');

  const browse = useCallback(async (path: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await wikiApi.fsBrowse(path, mode);
      setResult(res);
      setCurrent(res.current);
      setManualPath(res.current);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    browse('');
  }, [browse]);

  function handleSelect() {
    if (mode === 'dir') {
      onSelect(current);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{
        background: 'var(--bg-card, #1e1e2e)', border: '1px solid var(--border, #333)',
        borderRadius: '12px', width: '600px', maxHeight: '80vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
      }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border, #333)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>📁 {title}</strong>
          <button className="btn-secondary" onClick={onClose} style={{ padding: '4px 10px' }}>✕</button>
        </div>

        {/* Manual path bar */}
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #333)', display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={manualPath}
            onChange={e => setManualPath(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') browse(manualPath); }}
            style={{ flex: 1, fontSize: '13px' }}
            placeholder="输入路径后按 Enter..."
          />
          <button className="btn-secondary" onClick={() => browse(manualPath)} style={{ padding: '4px 10px' }}>→</button>
          {result?.parent && (
            <button className="btn-secondary" onClick={() => browse(result.parent!)} style={{ padding: '4px 10px' }}>⬆ 上级</button>
          )}
        </div>

        {/* Drives (Windows) */}
        {result?.drives && result.drives.length > 0 && (
          <div style={{ padding: '6px 16px', display: 'flex', gap: '6px', flexWrap: 'wrap', borderBottom: '1px solid var(--border, #333)' }}>
            {result.drives.map(d => (
              <button key={d} className="btn-secondary" onClick={() => browse(d)} style={{ padding: '2px 8px', fontSize: '12px' }}>{d}</button>
            ))}
          </div>
        )}

        {/* File list */}
        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {loading && <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary)' }}>加载中...</div>}
          {error && <div className="alert alert-error">{error}</div>}
          {!loading && result && result.entries.map(entry => (
            <div
              key={entry.path}
              onClick={() => {
                if (entry.is_dir) {
                  browse(entry.path);
                } else if (mode === 'file') {
                  onSelect(entry.path);
                  onClose();
                }
              }}
              style={{
                padding: '7px 12px',
                cursor: 'pointer',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '13px',
                color: entry.is_dir ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: 'transparent',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              {entry.is_dir ? '📁' : '📄'} {entry.name}
            </div>
          ))}
          {!loading && result && result.entries.length === 0 && (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>（空目录）</div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border, #333)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
            {mode === 'dir' ? `已选择: ${current}` : '点击文件选择'}
          </span>
          {mode === 'dir' && (
            <button className="btn-primary" onClick={handleSelect} style={{ padding: '6px 18px' }}>
              ✓ 选择此目录
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Help Modal ─────────────────────────────────────────────────────────────────

function HelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{
        background: 'var(--bg-card, #1e1e2e)', border: '1px solid var(--border, #333)',
        borderRadius: '12px', width: '580px', maxHeight: '80vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>📖 LLM Wiki 使用指南</strong>
          <button className="btn-secondary" onClick={onClose} style={{ padding: '4px 10px' }}>✕</button>
        </div>
        <div style={{ padding: '20px', overflow: 'auto', fontSize: '14px', lineHeight: 1.7 }}>
          <h4 style={{ margin: '0 0 8px', color: 'var(--accent)' }}>🚀 快速开始</h4>
          <ol style={{ paddingLeft: '20px', marginBottom: '16px' }}>
            <li><strong>设置 Project Directory</strong>：点击 📁 图标选择或手动输入 Wiki 项目目录路径（建议新建一个空文件夹）。</li>
            <li><strong>初始化项目</strong>：点击 <em>📋 Initialized Project</em> 按钮，跳转到 Overview 标签页，填写项目名称后点击 <em>✨ Initialize</em>。</li>
            <li><strong>保存到最近</strong>：点击 <em>💾 Save to Recent</em> 将当前路径保存，下次直接从历史选择。</li>
            <li><strong>摄入文档</strong>：切换到 <em>📥 Ingest</em> 标签，点击 📂 选择本地文件（支持 .pdf .docx .txt 等），点击摄入。</li>
            <li><strong>提问查询</strong>：切换到 <em>❓ Query</em> 标签，输入问题，AI 会从 Wiki 中检索并回答。</li>
          </ol>

          <h4 style={{ margin: '0 0 8px', color: 'var(--accent)' }}>⚙️ LLM 配置</h4>
          <p style={{ marginBottom: '12px' }}>
            Wiki 功能需要 LLM（大语言模型）支持。请在系统配置中设置 <strong>DeepSeek API Key</strong> 或其他提供商。
            如果出现 <em>401 Authorization Required</em>，说明 API Key 未配置或已失效。
          </p>
          <p style={{ marginBottom: '16px', padding: '8px 12px', background: 'rgba(255,200,0,0.08)', borderRadius: '6px', fontSize: '13px' }}>
            💡 前往 <strong>Settings → LLM Configuration</strong> 配置 DeepSeek / OpenAI / 其他提供商的 API Key。
          </p>

          <h4 style={{ margin: '0 0 8px', color: 'var(--accent)' }}>📂 支持的文件格式</h4>
          <p style={{ marginBottom: '12px', fontSize: '13px' }}>
            .txt .md .pdf .docx .xlsx .pptx .html .epub .csv .json .py .js 等 30+ 种格式
          </p>

          <h4 style={{ margin: '0 0 8px', color: 'var(--accent)' }}>🔧 Tab 说明</h4>
          <ul style={{ paddingLeft: '20px', fontSize: '13px' }}>
            <li><strong>Overview</strong>：项目状态总览，初始化新项目</li>
            <li><strong>Ingest</strong>：将文档摄入到 Wiki（LLM 自动生成结构化页面）</li>
            <li><strong>Query</strong>：自然语言提问，AI 检索 Wiki 回答</li>
            <li><strong>Lint</strong>：检查 Wiki 健康度（结构 + 语义一致性）</li>
            <li><strong>Pages</strong>：浏览所有 Wiki 页面，点击预览内容</li>
            <li><strong>Log</strong>：查看操作日志</li>
          </ul>

          <h4 style={{ margin: '12px 0 8px', color: 'var(--accent)' }}>💻 CLI 等价命令</h4>
          <pre style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '6px', padding: '10px', fontSize: '12px', overflow: 'auto' }}>{`# 初始化项目
ariadne wiki init ./my-wiki --name "My Wiki"

# 摄入文件
ariadne wiki ingest paper.pdf -p ./my-wiki -l Chinese

# 查询
ariadne wiki query "什么是RAG？" -p ./my-wiki

# Lint 检查
ariadne wiki lint -p ./my-wiki --structural`}</pre>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function Wiki() {
  const [tab, setTab] = useState<Tab>('overview');
  const [projectPath, setProjectPath] = useState(() => localStorage.getItem('wiki_project_path') || '.');
  const [overview, setOverview] = useState<WikiOverview | null>(null);
  const [pages, setPages] = useState<WikiPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<{ path: string; content: string } | null>(null);
  const [logContent, setLogContent] = useState('');

  // Recent projects
  const [recentProjects, setRecentProjects] = useState<string[]>([]);
  const [showRecent, setShowRecent] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  // Pickers
  const [showDirPicker, setShowDirPicker] = useState(false);
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

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
  const [initSuccess, setInitSuccess] = useState(false);

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

  const loadPages = useCallback(async () => {
    try {
      const res = await wikiApi.pages(projectPath);
      setPages(res.pages);
    } catch {
      setPages([]);
    }
  }, [projectPath]);

  const loadLog = useCallback(async () => {
    try {
      const res = await wikiApi.log(projectPath);
      setLogContent(res.content);
    } catch {
      setLogContent('');
    }
  }, [projectPath]);

  const loadRecent = useCallback(async () => {
    try {
      const res = await wikiApi.projects();
      setRecentProjects(res.projects || []);
    } catch {
      setRecentProjects([]);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('wiki_project_path', projectPath);
  }, [projectPath]);

  useEffect(() => {
    if (tab === 'overview') loadOverview();
    if (tab === 'pages') loadPages();
    if (tab === 'log') loadLog();
  }, [tab, projectPath, loadOverview, loadPages, loadLog]);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

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
      const msg = err.message || String(err);
      if (msg.includes('401') || msg.toLowerCase().includes('authorization')) {
        setIngestError(`LLM 认证失败（401）：请前往 Settings 配置有效的 API Key。\n\n${msg}`);
      } else {
        setIngestError(msg);
      }
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
      const msg = err.message || String(err);
      if (msg.includes('401') || msg.toLowerCase().includes('authorization')) {
        setQueryError(`LLM 认证失败（401）：请前往 Settings 配置有效的 API Key。\n\n${msg}`);
      } else {
        setQueryError(msg);
      }
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
    setInitSuccess(false);
    try {
      await wikiApi.init(projectPath, initName);
      await wikiApi.saveProject(projectPath);
      await loadOverview();
      await loadRecent();
      setInitSuccess(true);
    } catch (err: any) {
      setInitError(err.message || String(err));
    } finally {
      setInitLoading(false);
    }
  }

  // Save project
  async function handleSaveProject() {
    try {
      await wikiApi.saveProject(projectPath);
      await loadRecent();
      setSaveMsg('✓ 已保存');
      setTimeout(() => setSaveMsg(''), 2000);
    } catch (err: any) {
      setSaveMsg('✗ 保存失败');
      setTimeout(() => setSaveMsg(''), 3000);
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
      {/* Modals */}
      {showDirPicker && (
        <FsPicker
          mode="dir"
          title="选择 Wiki 项目目录"
          onSelect={(p) => { setProjectPath(p); setShowDirPicker(false); }}
          onClose={() => setShowDirPicker(false)}
        />
      )}
      {showFilePicker && (
        <FsPicker
          mode="file"
          title="选择源文件"
          onSelect={(p) => { setIngestSource(p); setShowFilePicker(false); }}
          onClose={() => setShowFilePicker(false)}
        />
      )}
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}

      <header className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h1>📖 {t('wiki.title')}</h1>
          <button
            className="btn-secondary"
            onClick={() => setShowHelp(true)}
            title="使用帮助"
            style={{ padding: '4px 12px', fontSize: '13px' }}
          >
            ❓ 帮助
          </button>
        </div>
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
            <button className="btn-secondary" onClick={() => setShowDirPicker(true)} title="浏览目录">
              📁
            </button>
            <button className="btn-secondary" onClick={loadOverview} title="刷新">
              🔄
            </button>
          </div>
        </div>

        {/* Recent projects dropdown */}
        {recentProjects.length > 0 && (
          <div style={{ marginTop: '6px', position: 'relative' }}>
            <button
              className="btn-secondary"
              onClick={() => setShowRecent(v => !v)}
              style={{ fontSize: '12px', padding: '3px 10px' }}
            >
              🕒 最近使用 ({recentProjects.length})
            </button>
            {showRecent && (
              <div style={{
                position: 'absolute', top: '28px', left: 0, zIndex: 100,
                background: 'var(--bg-card, #1e1e2e)', border: '1px solid var(--border)',
                borderRadius: '8px', minWidth: '320px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                padding: '4px 0'
              }}>
                {recentProjects.map(p => (
                  <div
                    key={p}
                    onClick={() => { setProjectPath(p); setShowRecent(false); }}
                    style={{
                      padding: '7px 14px', cursor: 'pointer', fontSize: '13px',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    📁 {p}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', marginTop: '10px', alignItems: 'center' }}>
          <button className="btn-primary" onClick={() => setTab('overview')}>
            📋 {t('wiki.init_project')}
          </button>
          <button className="btn-secondary" onClick={handleSaveProject}>
            💾 {t('wiki.save_project')}
          </button>
          {saveMsg && <span style={{ fontSize: '13px', color: saveMsg.startsWith('✓') ? '#10b981' : '#f87171' }}>{saveMsg}</span>}
        </div>
      </div>

      {/* Tabs — unified button style */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {tabs.map(tb => (
          <button
            key={tb.id}
            className={tab === tb.id ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setTab(tb.id)}
            style={{ padding: '6px 14px', fontSize: '13px' }}
          >
            {tb.icon} {t(tb.label)}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === 'overview' && (
        <div className="tab-content">
          {overview && (
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
          )}

          <div className="form-card">
            <h3>🆕 {t('wiki.init_new')}</h3>
            <p className="form-hint">
              初始化会在所选目录下创建 <code>wiki/</code>、<code>raw/sources/</code>、<code>schema.md</code>、<code>purpose.md</code> 等结构。
            </p>
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
              {initSuccess && <div className="alert alert-success">✅ 项目初始化成功！已保存到最近使用。</div>}
              <button type="submit" className="btn-primary" disabled={initLoading}>
                {initLoading ? '⏳...' : `✨ ${t('wiki.init_btn')}`}
              </button>
            </form>
          </div>

          {overview?.overview && (
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
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    value={ingestSource}
                    onChange={e => setIngestSource(e.target.value)}
                    placeholder="C:\Documents\paper.pdf"
                    style={{ flex: 1 }}
                    required
                  />
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setShowFilePicker(true)}
                    title="浏览文件"
                  >
                    📂
                  </button>
                </div>
                <small className="form-hint" style={{ marginTop: '4px' }}>
                  支持：.pdf .docx .txt .md .html .epub .xlsx .pptx .csv .json .py 等 30+ 格式
                </small>
              </div>
              <div className="form-group">
                <label>{t('summarize.output_lang')}</label>
                <select value={ingestLang} onChange={e => setIngestLang(e.target.value)}>
                  {OUTPUT_LANGS.map(l => (
                    <option key={l.code} value={l.code}>{l.name}</option>
                  ))}
                </select>
              </div>
              {ingestError && (
                <div className="alert alert-error" style={{ whiteSpace: 'pre-wrap' }}>
                  {ingestError.includes('401') && (
                    <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>
                      ⚠️ 需要配置 LLM API Key → Settings → LLM Configuration
                    </div>
                  )}
                  {ingestError}
                </div>
              )}
              <button type="submit" className="btn-primary" disabled={ingestLoading}>
                {ingestLoading ? '⏳ LLM 处理中...' : `📥 ${t('wiki.ingest_btn')}`}
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
              {queryError && (
                <div className="alert alert-error" style={{ whiteSpace: 'pre-wrap' }}>
                  {queryError.includes('401') && (
                    <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>
                      ⚠️ 需要配置 LLM API Key → Settings → LLM Configuration
                    </div>
                  )}
                  {queryError}
                </div>
              )}
              <button type="submit" className="btn-primary" disabled={queryLoading}>
                {queryLoading ? '⏳ LLM 思考中...' : `❓ ${t('wiki.query_btn')}`}
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
                {lintLoading ? '⏳ 分析中...' : `🔍 ${t('wiki.lint_btn')}`}
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ margin: 0 }}>📄 {t('wiki.pages_list')}</h3>
                <button className="btn-secondary" onClick={loadPages} style={{ padding: '4px 10px' }}>🔄</button>
              </div>
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
