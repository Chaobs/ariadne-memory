/**
 * Settings — LLM configuration and language settings with full i18n
 */

import { useState, useEffect } from 'react';
import { configApi } from '../api/ariadne';
import { setLocale, LOCALES, t, type Locale } from '../i18n';

// Flag emoji map — using locale's built-in emoji flag (no external files needed)
// Falls back to locale code text if flag is not available.
const FLAG_FALLBACK: Record<string, string> = {
  en: '🇺🇸',
  zh_CN: '🇨🇳',
  zh_TW: '🇭🇰',
  ja: '🇯🇵',
  fr: '🇫🇷',
  es: '🇪🇸',
  ru: '🇷🇺',
  ar: '🇸🇦',
};

export default function Settings() {
  const [provider, setProvider] = useState('deepseek');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [providers, setProviders] = useState<any[]>([]);
  const [currentLocale, setCurrentLocale] = useState<Locale>('en');
  const [saving, setSaving] = useState(false);
  const [fullConfig, setFullConfig] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    // Get initial locale from localStorage
    const saved = localStorage.getItem('ariadne_locale') as Locale | null;
    if (saved && LOCALES.some(l => l.code === saved)) {
      setCurrentLocale(saved);
    }

    configApi.providers().then((p: any) => setProviders(p.providers || [])).catch(console.error);
    configApi.get().then((c: any) => {
      const llm = c.config?.llm || {};
      setProvider(llm.provider || 'deepseek');
      setModel(llm.model || '');
      setApiKey(llm.api_key || '');
      setBaseUrl(llm.base_url || '');
      setFullConfig(c.config || {});
    }).catch(console.error);
  }, []);

  // Re-render when locale changes
  useEffect(() => {
    function handleLocaleChange() {
      const saved = localStorage.getItem('ariadne_locale') as Locale | null;
      if (saved && LOCALES.some(l => l.code === saved)) {
        setCurrentLocale(saved);
      }
    }
    window.addEventListener('localechange', handleLocaleChange);
    return () => window.removeEventListener('localechange', handleLocaleChange);
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setTestResult(null);
    try {
      await configApi.configureLLM(provider, model, apiKey, baseUrl || undefined);
      const res = await configApi.testLLM();
      setTestResult(res);
    } catch (err) {
      setTestResult({ success: false, message: String(err) });
    } finally {
      setSaving(false);
    }
  }

  async function handleLanguage(lang: Locale) {
    try {
      // Update backend
      await configApi.setLanguage(lang);
      // Update frontend i18n state
      setLocale(lang);
      setCurrentLocale(lang);
    } catch (err) { console.error(err); }
  }

  return (
    <div className="page settings">
      <header className="page-header">
        <h1>⚙️ {t('settings.title')}</h1>
      </header>

      <form className="form-card" onSubmit={handleSave}>
        <h2>{t('settings.llm')}</h2>

        <div className="form-group">
          <label>Provider</label>
          <select value={provider} onChange={e => setProvider(e.target.value)}>
            {providers.map(p => (
              <option key={p.code} value={p.code}>{p.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Model</label>
          <input
            type="text"
            placeholder="e.g., deepseek-chat"
            value={model}
            onChange={e => setModel(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>API Key</label>
          <input
            type="password"
            placeholder="sk-..."
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Base URL (optional)</label>
          <input
            type="url"
            placeholder="https://api.deepseek.com"
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
          />
        </div>

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? t('common.loading') : `${t('settings.save')} & ${t('settings.test')}`}
        </button>

        {testResult && (
          <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
            {testResult.success ? '✓' : '✗'} {testResult.message}
          </div>
        )}
      </form>

      <div className="form-card">
        <h2>{t('settings.language')}</h2>
        <div className="lang-grid">
          {LOCALES.map(lang => (
            <button
              key={lang.code}
              className={`lang-btn ${currentLocale === lang.code ? 'active' : ''}`}
              onClick={() => handleLanguage(lang.code)}
            >
              <span className="flag-icon">{lang.flag || FLAG_FALLBACK[lang.code] || lang.code}</span> {lang.name}
            </button>
          ))}
        </div>
      </div>

      {/* Full Configuration View */}
      {fullConfig && (
        <div className="form-card">
          <h2>📋 {t('settings.full_config') || 'Full Configuration'}</h2>
          <p style={{ color: 'var(--text-dim)', marginBottom: '12px', fontSize: '0.85rem' }}>
            Read-only view of all configuration values
          </p>
          <details open>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '8px' }}>LLM</summary>
            <pre style={{ fontSize: '0.8rem', background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(fullConfig.llm || {}, null, 2)}
            </pre>
          </details>
          <details style={{ marginTop: '8px' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '8px' }}>Locale</summary>
            <pre style={{ fontSize: '0.8rem', background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(fullConfig.locale || {}, null, 2)}
            </pre>
          </details>
          <details style={{ marginTop: '8px' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '8px' }}>Advanced</summary>
            <pre style={{ fontSize: '0.8rem', background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(fullConfig.advanced || {}, null, 2)}
            </pre>
          </details>
          <details style={{ marginTop: '8px' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '8px' }}>Plugins</summary>
            <pre style={{ fontSize: '0.8rem', background: 'var(--bg-secondary)', padding: '8px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(fullConfig.plugins || {}, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
