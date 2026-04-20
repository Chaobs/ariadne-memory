/**
 * Home — Dashboard with quick stats and recent activity
 */

import { useEffect, useState } from 'react';
import { systemApi } from '../api/ariadne';

export default function Home() {
  const [info, setInfo] = useState<{ version: string; total_systems: number; llm_configured: boolean } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemApi.info().then(setInfo).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">Loading...</div>;

  return (
    <div className="page home">
      <header className="page-header">
        <h1>🧵 Ariadne Memory System</h1>
        <p className="subtitle">Cross-source AI memory &amp; knowledge weaving</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-icon">💾</span>
          <div className="stat-body">
            <span className="stat-value">{info?.total_systems ?? 0}</span>
            <span className="stat-label">Memory Systems</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🤖</span>
          <div className="stat-body">
            <span className={`stat-value ${info?.llm_configured ? 'ok' : 'warn'}`}>
              {info?.llm_configured ? 'Online' : 'Not Set'}
            </span>
            <span className="stat-label">LLM Status</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📦</span>
          <div className="stat-body">
            <span className="stat-value">{info?.version}</span>
            <span className="stat-label">Version</span>
          </div>
        </div>
      </div>

      <section className="quick-actions">
        <h2>Quick Actions</h2>
        <div className="action-grid">
          <a href="/search" className="action-card">
            <span>🔍</span>
            <span>Semantic Search</span>
          </a>
          <a href="/ingest" className="action-card">
            <span>📥</span>
            <span>Ingest Files</span>
          </a>
          <a href="/memory" className="action-card">
            <span>💾</span>
            <span>Manage Memory</span>
          </a>
          <a href="/graph" className="action-card">
            <span>🕸️</span>
            <span>Knowledge Graph</span>
          </a>
        </div>
      </section>
    </div>
  );
}