/**
 * Home — Dashboard with quick stats and recent activity with full i18n
 */

import { useEffect, useState } from 'react';
import { systemApi } from '../api/ariadne';
import { t } from '../i18n';

export default function Home() {
  const [info, setInfo] = useState<{ version: string; total_systems: number; llm_configured: boolean } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemApi.info().then(setInfo).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">{t('common.loading')}</div>;

  return (
    <div className="page home">
      <header className="page-header">
        <h1>🧵 {t('home.title')}</h1>
        <p className="subtitle">{t('home.subtitle')}</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-icon">💾</span>
          <div className="stat-body">
            <span className="stat-value">{info?.total_systems ?? 0}</span>
            <span className="stat-label">{t('home.memory_systems')}</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🤖</span>
          <div className="stat-body">
            <span className={`stat-value ${info?.llm_configured ? 'ok' : 'warn'}`}>
              {info?.llm_configured ? t('home.llm_online') : t('home.llm_not_set')}
            </span>
            <span className="stat-label">{t('home.llm_status')}</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📦</span>
          <div className="stat-body">
            <span className="stat-value">{info?.version}</span>
            <span className="stat-label">{t('home.version')}</span>
          </div>
        </div>
      </div>

      <section className="quick-actions">
        <h2>{t('home.quick_actions')}</h2>
        <div className="action-grid">
          <a href="/search" className="action-card">
            <span>🔍</span>
            <span>{t('home.action_search')}</span>
          </a>
          <a href="/ingest" className="action-card">
            <span>📥</span>
            <span>{t('home.action_ingest')}</span>
          </a>
          <a href="/memory" className="action-card">
            <span>💾</span>
            <span>{t('home.action_memory')}</span>
          </a>
          <a href="/graph" className="action-card">
            <span>🕸️</span>
            <span>{t('home.action_graph')}</span>
          </a>
          <a href="/summarize" className="action-card">
            <span>📝</span>
            <span>{t('home.action_summarize')}</span>
          </a>
        </div>
      </section>
    </div>
  );
}
