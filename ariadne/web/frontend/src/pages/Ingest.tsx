/**
 * Ingest — File ingestion interface with real-time SSE progress tracking
 */

import { useState, useRef } from 'react';
import { ingestWithProgress, systemApi } from '../api/ariadne';
import { t } from '../i18n';

interface IngestEvent {
  type: 'progress' | 'success' | 'error' | 'skip' | 'complete';
  file?: string;
  progress?: number;
  phase?: string;
  docs?: number;
  error?: string;
  result?: {
    docs_added: number;
    skipped: number;
    errors: Array<{ file: string; error: string }>;
    total_files: number;
  };
}

interface ProcessedFile {
  name: string;
  status: 'success' | 'error' | 'skip' | 'progress';
  message?: string;
}

export default function Ingest() {
  const [files, setFiles] = useState<File[]>([]);
  const [memory, setMemory] = useState('');
  const [enrich, setEnrich] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState('');
  const [result, setResult] = useState<any>(null);
  const [systems, setSystems] = useState<{ name: string }[]>([]);
  const [processedFiles, setProcessedFiles] = useState<ProcessedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  systemApi.info().then(info => setSystems(info.systems)).catch(console.error);

  function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) setFiles(Array.from(e.target.files));
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    setLoading(true);
    setProgress(0);
    setResult(null);
    setProcessedFiles([]);

    try {
      const iter = ingestWithProgress(files, memory || undefined, enrich);
      let event: IngestEvent;

      while (true) {
        const { value, done } = await iter.next();
        event = value as IngestEvent;
        if (done) break;

        if (event.type === 'progress') {
          setProgress(event.progress ?? 0);
          setPhase(event.phase ?? 'processing');
          if (event.file) {
            setProcessedFiles(prev => [
              ...prev.filter(f => f.name !== event.file),
              { name: event.file!, status: 'progress' as const, message: `Processing... ${event.progress}%` },
            ]);
          }
        } else if (event.type === 'success') {
          setProcessedFiles(prev => [
            ...prev.filter(f => f.name !== event.file),
            { name: event.file!, status: 'success', message: `+${event.docs} docs` },
          ]);
        } else if (event.type === 'error') {
          setProcessedFiles(prev => [
            ...prev.filter(f => f.name !== event.file),
            { name: event.file!, status: 'error', message: event.error },
          ]);
        } else if (event.type === 'skip') {
          setProcessedFiles(prev => [
            ...prev.filter(f => f.name !== event.file),
            { name: event.file!, status: 'skip', message: 'Skipped' },
          ]);
        } else if (event.type === 'complete') {
          setProgress(100);
          setPhase('');
          setResult(event.result);
        }
      }
      setFiles([]);
      if (inputRef.current) inputRef.current.value = '';
    } catch (err: any) {
      alert(String(err));
    } finally {
      setLoading(false);
      setTimeout(() => { setProgress(0); setPhase(''); }, 1500);
    }
  }

  return (
    <div className="page ingest">
      <header className="page-header">
        <h1>📥 {t('ingest.title')}</h1>
      </header>

      <form className="form-card" onSubmit={handleUpload}>
        <div className="form-group">
          <label>{t('ingest.select_files')}</label>
          <input
            ref={inputRef}
            type="file"
            multiple
            onChange={handleFiles}
            accept=".md,.txt,.pdf,.docx,.pptx,.xlsx,.csv,.json,.mm,.html,.ipynb,.msg,.epub,.py,.java,.cpp,.js,.ts"
          />
          {files.length > 0 && (
            <div className="file-list">
              {files.map((f, i) => (
                <span key={i} className="file-chip">{f.name}</span>
              ))}
            </div>
          )}
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>{t('ingest.memory_system')}</label>
            <select value={memory} onChange={e => setMemory(e.target.value)}>
              <option value="">{t('common.default')}</option>
              {systems.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input type="checkbox" checked={enrich} onChange={e => setEnrich(e.target.checked)} />
              {t('ingest.enrich_graph')}
            </label>
          </div>
        </div>

        {loading && (
          <div className="ingest-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="progress-text">
              {phase === 'processing' ? `${t('ingest.processing')} ${progress}%` :
               progress === 100 ? t('ingest.complete') :
               t('ingest.uploading')}
            </div>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={loading || files.length === 0}>
          {loading ? '⏳ ' + t('ingest.processing') : `📥 ${t('ingest.submit')} ${files.length > 0 ? `(${files.length})` : ''}`}
        </button>
      </form>

      {processedFiles.length > 0 && (
        <div className="result-panel">
          <h3>Processing Log</h3>
          <div className="file-log">
            {processedFiles.map((f, i) => (
              <div key={i} className={`file-log-item ${f.status}`}>
                <span className="file-log-icon">
                  {f.status === 'success' ? '✅' : f.status === 'error' ? '❌' : f.status === 'skip' ? '⏭️' : '🔄'}
                </span>
                <span className="file-log-name">{f.name}</span>
                {f.message && <span className="file-log-msg">{f.message}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div className="result-panel">
          <h3>Ingest Result</h3>
          <p><strong>{t('ingest.added')}:</strong> {result.docs_added}</p>
          <p><strong>{t('ingest.skipped')}:</strong> {result.skipped}</p>
          <p><strong>{t('ingest.total_files')}:</strong> {result.total_files}</p>
          {result.errors?.length > 0 && (
            <div className="errors">
              <h4>{t('ingest.errors')}:</h4>
              {result.errors.map((e: any, i: number) => (
                <div key={i} className="error-item">
                  <strong>{e.file}</strong>: {e.error}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
