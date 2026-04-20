/**
 * Ingest — File ingestion interface with progress tracking
 */

import { useState, useRef } from 'react';
import { ingestApi, systemApi } from '../api/ariadne';

export default function Ingest() {
  const [files, setFiles] = useState<File[]>([]);
  const [memory, setMemory] = useState('');
  const [enrich, setEnrich] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [systems, setSystems] = useState<{ name: string }[]>([]);
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

    // Simulate progress (since fetch doesn't expose upload progress easily)
    const progressInterval = setInterval(() => {
      setProgress(p => Math.min(p + 15, 85));
    }, 200);

    try {
      const res = await ingestApi.files(files, memory || undefined, enrich);
      clearInterval(progressInterval);
      setProgress(100);
      setResult(res);
      setFiles([]);
      if (inputRef.current) inputRef.current.value = '';
    } catch (err: any) {
      clearInterval(progressInterval);
      alert(String(err));
    } finally {
      setLoading(false);
      setTimeout(() => setProgress(0), 800);
    }
  }

  return (
    <div className="page ingest">
      <header className="page-header">
        <h1>📥 Ingest Files</h1>
      </header>

      <form className="form-card" onSubmit={handleUpload}>
        <div className="form-group">
          <label>Files</label>
          <input
            ref={inputRef}
            type="file"
            multiple
            onChange={handleFiles}
            accept=".md,.txt,.pdf,.docx,.pptx,.xlsx,.csv,.json,.mm,.html,.ipynb,.msg,.epub"
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
            <label>Memory System</label>
            <select value={memory} onChange={e => setMemory(e.target.value)}>
              <option value="">Default</option>
              {systems.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input type="checkbox" checked={enrich} onChange={e => setEnrich(e.target.checked)} />
              Enrich Knowledge Graph
            </label>
          </div>
        </div>

        {loading && progress > 0 && (
          <div className="ingest-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="progress-text">
              {progress < 100 ? `Uploading... ${progress}%` : 'Processing...'}
            </div>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={loading || files.length === 0}>
          {loading ? '⏳ Ingesting...' : `📥 Ingest ${files.length} file(s)`}
        </button>
      </form>

      {result && (
        <div className="result-panel">
          <h3>Ingest Result</h3>
          <p><strong>Added:</strong> {result.docs_added}</p>
          <p><strong>Skipped:</strong> {result.skipped}</p>
          <p><strong>Total files:</strong> {result.total_files}</p>
          {result.errors?.length > 0 && (
            <div className="errors">
              <h4>Errors:</h4>
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
