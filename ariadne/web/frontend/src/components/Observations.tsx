/**
 * Observations Panel Component
 * 
 * Displays real-time observations from session memory hooks.
 * Subscribes to SSE events for live updates.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { SSEEvent, ObservationData, SummaryData, getSSEClient, closeSSEClient } from '../api/sse';
import { useTranslation } from 'react-i18next';

// Type colors mapping
const TYPE_COLORS: Record<string, string> = {
  bugfix: '#dc3545',
  feature: '#28a745',
  refactor: '#ffc107',
  change: '#17a2b8',
  general: '#6c757d',
};

interface ObservationsPanelProps {
  sessionId?: string;
  maxItems?: number;
}

export const ObservationsPanel: React.FC<ObservationsPanelProps> = ({
  sessionId,
  maxItems = 50,
}) => {
  const { t } = useTranslation();
  const [observations, setObservations] = useState<ObservationData[]>([]);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SSE event handlers
  const handleNewObservation = useCallback((event: SSEEvent) => {
    if (event.data && typeof event.data === 'object') {
      const obs = event.data as unknown as ObservationData;
      setObservations((prev) => {
        const updated = [obs, ...prev];
        return updated.slice(0, maxItems);
      });
    }
  }, [maxItems]);

  const handleNewSummary = useCallback((event: SSEEvent) => {
    if (event.data) {
      setSummary(event.data as unknown as SummaryData);
    }
  }, []);

  const handleConnected = useCallback(() => {
    setConnected(true);
    setError(null);
  }, []);

  const handleError = useCallback(() => {
    setConnected(false);
    setError('Connection error');
  }, []);

  // Set up SSE subscription
  useEffect(() => {
    const client = getSSEClient(sessionId);

    // Register handlers
    const unsubConnected = client.on('connected', handleConnected);
    const unsubObs = client.on('new_observation', handleNewObservation);
    const unsubSummary = client.on('new_summary', handleNewSummary);
    const unsubError = client.on('error', handleError);

    // Connect
    client.connect();

    // Cleanup
    return () => {
      unsubConnected();
      unsubObs();
      unsubSummary();
      unsubError();
    };
  }, [sessionId, handleConnected, handleNewObservation, handleNewSummary, handleError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeSSEClient();
    };
  }, []);

  const formatTime = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString();
    } catch {
      return isoString;
    }
  };

  const getTypeColor = (type: string): string => {
    return TYPE_COLORS[type] || TYPE_COLORS.general;
  };

  return (
    <div className="observations-panel">
      {/* Header */}
      <div className="observations-header">
        <h3>{t('observations.title', 'Session Observations')}</h3>
        <span className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? t('observations.connected', 'Live') : t('observations.connecting', 'Connecting...')}
        </span>
      </div>

      {/* Error message */}
      {error && (
        <div className="observations-error">
          {error}
        </div>
      )}

      {/* Summary section */}
      {summary && (
        <div className="observations-summary">
          <h4>{t('observations.summary', 'Session Summary')}</h4>
          <p>{summary.narrative}</p>
          {summary.key_decisions && summary.key_decisions.length > 0 && (
            <div className="summary-decisions">
              <strong>{t('observations.keyDecisions', 'Key Decisions')}:</strong>
              <ul>
                {summary.key_decisions.map((decision, idx) => (
                  <li key={idx}>{decision}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Observations list */}
      <div className="observations-list">
        {observations.length === 0 ? (
          <div className="observations-empty">
            {t('observations.empty', 'No observations yet. Start a session to capture work progress.')}
          </div>
        ) : (
          observations.map((obs) => (
            <div key={obs.id} className="observation-item">
              <div className="observation-header">
                <span
                  className="observation-type"
                  style={{ backgroundColor: getTypeColor(obs.obs_type) }}
                >
                  {obs.obs_type}
                </span>
                <span className="observation-time">
                  {formatTime(obs.created_at)}
                </span>
              </div>
              <div className="observation-summary">
                {obs.summary}
              </div>
              {obs.detail && (
                <div className="observation-detail">
                  {obs.detail}
                </div>
              )}
              {obs.files && obs.files.length > 0 && (
                <div className="observation-files">
                  {obs.files.map((file, idx) => (
                    <span key={idx} className="file-tag">
                      {file}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// Hook for using observations in other components
export function useObservations(sessionId?: string) {
  const [observations, setObservations] = useState<ObservationData[]>([]);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const client = getSSEClient(sessionId);

    const unsubConnected = client.on('connected', () => setConnected(true));
    const unsubObs = client.on('new_observation', (event) => {
      if (event.data) {
        setObservations((prev) => [event.data as unknown as ObservationData, ...prev]);
      }
    });
    const unsubSummary = client.on('new_summary', (event) => {
      if (event.data) {
        setSummary(event.data as unknown as SummaryData);
      }
    });

    client.connect();

    return () => {
      unsubConnected();
      unsubObs();
      unsubSummary();
    };
  }, [sessionId]);

  return { observations, summary, connected };
}

export default ObservationsPanel;
