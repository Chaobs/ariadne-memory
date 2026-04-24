/**
 * Session — Real-time session memory observations with SSE
 * 
 * Displays live observations captured during AI agent sessions,
 * including tool usage, user prompts, and generated summaries.
 */

import { useState, useEffect } from 'react';
import { ObservationsPanel, useObservations } from '../components/Observations';
import { t } from '../i18n';

export default function Session() {
  const [sessionId, setSessionId] = useState<string>('');
  const { observations, summary, connected } = useObservations(sessionId || undefined);

  return (
    <div className="page session">
      <header className="page-header">
        <h1>🧠 {t('session.title', 'Session Memory')}</h1>
        <div className="session-controls">
          <input
            type="text"
            placeholder={t('session.sessionIdPlaceholder', 'Session ID (optional)')}
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="session-input"
          />
          <span className={`connection-indicator ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '🟢 Live' : '⚪ Connecting...'}
          </span>
        </div>
      </header>

      <div className="session-stats">
        <div className="stat-card">
          <span className="stat-value">{observations.length}</span>
          <span className="stat-label">{t('session.observations', 'Observations')}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{summary ? '1' : '0'}</span>
          <span className="stat-label">{t('session.summaries', 'Summaries')}</span>
        </div>
        <div className="stat-card">
          <span className={`stat-value ${connected ? 'connected' : ''}`}>
            {connected ? '✓' : '—'}
          </span>
          <span className="stat-label">{t('session.sseStatus', 'SSE Status')}</span>
        </div>
      </div>

      <ObservationsPanel sessionId={sessionId || undefined} maxItems={50} />

      <div className="session-help">
        <h3>{t('session.howItWorks', 'How It Works')}</h3>
        <p>{t('session.description', 
          'Session Memory captures observations from your AI agent sessions in real-time. ' +
          'When connected via SSE, new observations appear instantly without page refresh.'
        )}</p>
        <h4>{t('session.availableCommands', 'Available CLI Commands')}</h4>
        <pre className="code-block">{`# Start a new session
ariadne session start --platform openclaw

# Record an observation manually
echo '{"session_id": "abc", "tool_name": "read_file"}' | ariadne hook run --event post_tool

# List recent sessions
ariadne session list --limit 10

# Search observations
ariadne session search "bug fix"

# End session and generate summary
ariadne session end <session_id>

# Check session statistics
ariadne session stats`}</pre>
      </div>
    </div>
  );
}
