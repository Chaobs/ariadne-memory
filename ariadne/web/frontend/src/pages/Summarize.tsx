/**
 * Summarize — LLM-powered document summarization interface
 */

import { useState, useEffect } from 'react';
import { systemApi } from '../api/ariadne';
import { t } from '../i18n';

const LS_KEY = 'ariadne_summarize_result';

interface SummarizeResult {
  summary: string;
  keywords?: string[];
  topics?: string[];
  sources?: string[];
}

const OUTPUT_LANGS = [
  { code: 'en', name: 'English' },
  { code: 'zh_CN', name: '简体中文' },
  { code: 'zh_TW', name: '繁體中文' },
  { code: 'ja', name: '日本語' },
  { code: 'fr', name: 'Français' },
  { code: 'es', name: 'Español' },
  { code: 'ru', name: 'Русский' },
  { code: 'ar', name: 'العربية' },
];

export default function Summarize() {
  const [memory, setMemory] = useState('');
  const [query, setQuery] = useState('');
  const [outputLang, setOutputLang] = useState('en');
  const [systems, setSystems] = useState<{ name: string }[]>([]);
  const [llmConfigured, setLlmConfigured] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SummarizeResult | null>(() => {
    try { const s = sessionStorage.getItem(LS_KEY); return s ? JSON.parse(s) : null; }
    catch { return null; }
  });
  const [error, setError] = useState<string | null>(null);

  // Persist result to sessionStorage
  useEffect(() => {
    if (result) {
      try { sessionStorage.setItem(LS_KEY, JSON.stringify(result)); } catch {}
    }
  }, [result]);

  useEffect(() => {
    systemApi.info().then(info => {
      setSystems(info.systems);
      setLlmConfigured(info.llm_configured);
    }).catch(() => setLlmConfigured(false));
  }, []);

  async function handleSummarize(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await systemApi.summarize(query, memory || undefined, outputLang) as SummarizeResult;
      setResult(res);
    } catch (err: any) {
      const msg = err.message || String(err);
      if (msg.includes('LLM') || msg.includes('No LLM') || msg.includes('not configured')) {
        setError(t('summarize.llm_required'));
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page summarize">
      <header className="page-header">
        <h1>📝 {t('summarize.title')}</h1>
        <p className="subtitle">{t('summarize.description')}</p>
      </header>

      <form className="form-card" onSubmit={handleSummarize}>
        <div className="form-group">
          <label>{t('summarize.memory')}</label>
          <select value={memory} onChange={e => setMemory(e.target.value)}>
            <option value="">{t('common.default')}</option>
            {systems.map(s => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>{t('summarize.query')}</label>
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('summarize.query_hint')}
            rows={4}
            required
          />
        </div>

        <div className="form-group">
          <label>{t('summarize.output_lang')}</label>
          <select value={outputLang} onChange={e => setOutputLang(e.target.value)}>
            {OUTPUT_LANGS.map(l => (
              <option key={l.code} value={l.code}>{l.name}</option>
            ))}
          </select>
        </div>

        {!llmConfigured && (
          <div className="alert alert-warning">
            ⚠️ {t('summarize.llm_required')}
          </div>
        )}

        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !query.trim()}
        >
          {loading ? `⏳ ${t('summarize.generating')}` : `📝 ${t('summarize.submit')}`}
        </button>
      </form>

      {error && (
        <div className="result-card error-result">
          <h3>⚠️ {t('common.error')}</h3>
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="result-panel">
          <h3>📄 {t('summarize.result')}</h3>
          <div className="summary-content">
            <p>{result.summary}</p>
          </div>
          {result.keywords && result.keywords.length > 0 && (
            <div className="summary-section">
              <h4>🏷️ Keywords</h4>
              <div className="keyword-tags">
                {result.keywords.map((kw, i) => (
                  <span key={i} className="keyword-tag">{kw}</span>
                ))}
              </div>
            </div>
          )}
          {result.topics && result.topics.length > 0 && (
            <div className="summary-section">
              <h4>📚 Topics</h4>
              <ul>
                {result.topics.map((topic, i) => (
                  <li key={i}>{topic}</li>
                ))}
              </ul>
            </div>
          )}
          {result.sources && result.sources.length > 0 && (
            <div className="summary-section">
              <h4>📚 Sources ({result.sources.length})</h4>
              <ul>
                {result.sources.slice(0, 10).map((s, i) => (
                  <li key={i}><small>{s}</small></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
