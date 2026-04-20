/**
 * Settings — LLM configuration and language settings with full i18n
 */

import { useState, useEffect } from 'react';
import { configApi } from '../api/ariadne';
import { setLocale, LOCALES, t, type Locale } from '../i18n';

// Flag image map — PNG files in /assets/flags/, 24x24px
const FLAG_MAP: Record<string, string> = {
  en: '/assets/flags/en.png',
  zh_CN: '/assets/flags/zh_CN.png',
  zh_TW: '/assets/flags/zh_TW.png',
  ja: '/assets/flags/ja.png',
  fr: '/assets/flags/fr.png',
  es: '/assets/flags/es.png',
  ru: '/assets/flags/ru.png',
  ar: '/assets/flags/ar.png',
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
              <img src={FLAG_MAP[lang.code] ?? '/assets/flags/en.png'} alt={lang.code} className="flag-icon" /> {lang.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
