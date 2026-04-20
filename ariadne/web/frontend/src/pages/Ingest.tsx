/**
 * Ingest — Enhanced file ingestion with real-time SSE progress tracking
 * Supports: single file, multiple files, folder, remove/clear, recursive/verbose options
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
  reason?: string;
  result?: {
    docs_added: number;
    skipped: number;
    errors: Array<{ file: string; error: string }>;
    total_files: number;
  };
}

interface SelectedFile {
  name: string;
  file?: File;
  path?: string;  // For folder entries
  isDirectory?: boolean;
}

interface ProcessedFile {
  name: string;
  status: 'success' | 'error' | 'skip' | 'progress';
  message?: string;
}

export default function Ingest() {
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [memory, setMemory] = useState('');
  const [enrich, setEnrich] = useState(false);
  const [recursive, setRecursive] = useState(true);
  const [verbose, setVerbose] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState('');
  const [result, setResult] = useState<any>(null);
  const [systems, setSystems] = useState<{ name: string }[]>([]);
  const [processedFiles, setProcessedFiles] = useState<ProcessedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Load memory systems on mount
  if (systems.length === 0) {
    systemApi.info().then(info => setSystems(info.systems)).catch(() => {});
  }

  function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files).map(f => ({
        name: f.name,
        file: f,
      }));
      setSelectedFiles(prev => {
        const existing = new Set(prev.map(f => f.name));
        return [...prev, ...newFiles.filter(f => !existing.has(f.name))];
      });
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleFolder(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      // webkitdirectory provides File objects with fullPath
      const newEntries: SelectedFile[] = Array.from(e.target.files).map(f => ({
        name: (f as any).webkitRelativePath || f.name,
        file: f,
      }));
      setSelectedFiles(prev => {
        const existing = new Set(prev.map(f => f.name));
        return [...prev, ...newEntries.filter(f => !existing.has(f.name))];
      });
    }
    if (folderInputRef.current) folderInputRef.current.value = '';
  }

  function removeFile(name: string) {
    setSelectedFiles(prev => prev.filter(f => f.name !== name));
  }

  function clearAll() {
    setSelectedFiles([]);
    setResult(null);
    setProcessedFiles([]);
  }

  function removeSelected() {
    const checkboxes = document.querySelectorAll<HTMLInputElement>('.file-select-checkbox:checked');
    const toRemove = new Set<string>();
    checkboxes.forEach(cb => {
      const name = cb.getAttribute('data-name');
      if (name) toRemove.add(name);
    });
    setSelectedFiles(prev => prev.filter(f => !toRemove.has(f.name)));
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (selectedFiles.length === 0) return;
    setLoading(true);
    setProgress(0);
    setResult(null);
    setProcessedFiles([]);

    try {
      const files = selectedFiles.map(sf => sf.file).filter((f): f is File => !!f);
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
              { name: event.file!, status: 'progress', message: `Processing... ${event.progress}%` },
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
            { name: event.file!, status: 'skip', message: event.reason || 'Skipped' },
          ]);
        } else if (event.type === 'complete') {
          setProgress(100);
          setPhase('');
          setResult(event.result);
        }
      }
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      alert(String(err));
    } finally {
      setLoading(false);
      setTimeout(() => { setProgress(0); setPhase(''); }, 2000);
    }
  }

  const hasFiles = selectedFiles.length > 0;

  return (
    <div className="page ingest">
      <header className="page-header">
        <h1>📥 {t('ingest.title')}</h1>
      </header>

      <form className="form-card" onSubmit={handleUpload}>
        {/* File/Folder Selection */}
        <div className="form-group">
          <label>{t('ingest.select_files')}</label>
          <div className="file-input-buttons">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
            >
              📄 {t('ingest.select_file')}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => folderInputRef.current?.click()}
              disabled={loading}
            >
              📁 {t('ingest.select_folder')}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={clearAll}
              disabled={loading || !hasFiles}
            >
              🗑️ {t('ingest.clear_all')}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={removeSelected}
              disabled={loading || !hasFiles}
            >
              ✕ {t('ingest.remove_selected')}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFiles}
            accept=".md,.txt,.pdf,.docx,.pptx,.xlsx,.csv,.json,.mm,.html,.ipynb,.msg,.epub,.py,.java,.cpp,.js,.ts,.c,.h,.hpp,.go,.rs,.rb,.php,.swift,.kt,.scala,.bib,.ris,.eml,.mbox,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp,.mp4,.avi,.mkv,.mov,.mp3,.wav,.m4a,.flac,.ogg,.html,.htm,.rss,.xml,.odt,.ods,.odp,.rtf"
            style={{ display: 'none' }}
          />
          <input
            ref={folderInputRef}
            type="file"
            /* @ts-ignore */
            webkitdirectory="webkitdirectory"
            directory="directory"
            multiple
            onChange={handleFolder}
            style={{ display: 'none' }}
          />
          <p className="input-hint">{t('ingest.drag_hint_files')}</p>
        </div>

        {/* File List */}
        {selectedFiles.length > 0 && (
          <div className="file-list-panel">
            <div className="file-list-header">
              <span>{selectedFiles.length} {t('ingest.files_selected')}</span>
            </div>
            <div className="file-chips-scroll">
              {selectedFiles.map((sf) => (
                <div key={sf.name} className="file-chip-item">
                  <input
                    type="checkbox"
                    className="file-select-checkbox"
                    data-name={sf.name}
                    onChange={() => {}}
                  />
                  <span className="file-chip-icon">📄</span>
                  <span className="file-chip-name" title={sf.name}>{sf.name}</span>
                  {!loading && (
                    <button
                      type="button"
                      className="file-chip-remove"
                      onClick={() => removeFile(sf.name)}
                      title={t('ingest.removed')}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Options Row */}
        <div className="form-row">
          <div className="form-group">
            <label>{t('ingest.memory_system')}</label>
            <select value={memory} onChange={e => setMemory(e.target.value)} disabled={loading}>
              <option value="">{t('common.default')}</option>
              {systems.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={recursive}
                onChange={e => setRecursive(e.target.checked)}
                disabled={loading}
              />
              {t('ingest.recursive')}
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={enrich}
                onChange={e => setEnrich(e.target.checked)}
                disabled={loading}
              />
              {t('ingest.enrich_graph')}
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={verbose}
                onChange={e => setVerbose(e.target.checked)}
                disabled={loading}
              />
              {t('ingest.verbose')}
            </label>
          </div>
        </div>

        {/* Progress */}
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

        <button
          type="submit"
          className="btn-primary"
          disabled={loading || selectedFiles.length === 0}
        >
          {loading
            ? `⏳ ${t('ingest.processing')}`
            : `📥 ${t('ingest.submit')} ${selectedFiles.length > 0 ? `(${selectedFiles.length})` : ''}`}
        </button>
      </form>

      {/* Processing Log */}
      {processedFiles.length > 0 && (
        <div className="result-panel">
          <h3>📋 {t('ingest.processing_log')}</h3>
          <div className="file-log">
            {processedFiles.map((f, i) => (
              <div key={i} className={`file-log-item ${f.status}`}>
                <span className="file-log-icon">
                  {f.status === 'success' ? '✅' :
                   f.status === 'error' ? '❌' :
                   f.status === 'skip' ? '⏭️' : '🔄'}
                </span>
                <span className="file-log-name">{f.name}</span>
                {f.message && <span className="file-log-msg">{f.message}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result Summary */}
      {result && (
        <div className="result-panel">
          <h3>📊 {t('ingest.result')}</h3>
          <div className="result-stats">
            <div className="stat-item">
              <span className="stat-num success">{result.docs_added}</span>
              <span className="stat-lbl">{t('ingest.added')}</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">{result.skipped}</span>
              <span className="stat-lbl">{t('ingest.skipped')}</span>
            </div>
            <div className="stat-item">
              <span className="stat-num">{result.total_files}</span>
              <span className="stat-lbl">{t('ingest.total_files')}</span>
            </div>
          </div>
          {result.errors?.length > 0 && (
            <div className="errors">
              <h4>⚠️ {t('ingest.errors')}:</h4>
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
