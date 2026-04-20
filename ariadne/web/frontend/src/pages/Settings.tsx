/**
 * Settings — LLM configuration and language settings
 */

import { useState, useEffect } from 'react';
import { configApi } from '../api/ariadne';

export default function Settings() {
  const [provider, setProvider] = useState('deepseek');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [providers, setProviders] = useState<any[]>([]);
  const [locale, setLocale] = useState('en');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    configApi.providers().then((p: any) => setProviders(p.providers || [])).catch(console.error);
    configApi.get().then((c: any) => {
      const llm = c.config?.llm || {};
      setProvider(llm.provider || 'deepseek');
      setModel(llm.model || '');
      setApiKey(llm.api_key || '');
      setBaseUrl(llm.base_url || '');
    }).catch(console.error);
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

  async function handleLanguage(lang: string) {
    try {
      await configApi.setLanguage(lang);
      setLocale(lang);
    } catch (err) { console.error(err); }
  }

  return (
    <div className="page settings">
      <header className="page-header">
        <h1>⚙️ Settings</h1>
      </header>

      <form className="form-card" onSubmit={handleSave}>
        <h2>LLM Configuration</h2>

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
          {saving ? 'Saving...' : 'Save & Test'}
        </button>

        {testResult && (
          <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
            {testResult.success ? '✓' : '✗'} {testResult.message}
          </div>
        )}
      </form>

      <div className="form-card">
        <h2>Language</h2>
        <div className="lang-grid">
          {[
            { code: 'en', name: 'English' },
            { code: 'zh_CN', name: '简体中文' },
            { code: 'zh_TW', name: '繁體中文' },
            { code: 'ja', name: '日本語' },
            { code: 'fr', name: 'Français' },
            { code: 'es', name: 'Español' },
            { code: 'ru', name: 'Русский' },
            { code: 'ar', name: 'العربية' },
          ].map(lang => (
            <button
              key={lang.code}
              className={`lang-btn ${locale === lang.code ? 'active' : ''}`}
              onClick={() => handleLanguage(lang.code)}
            >
              {lang.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}