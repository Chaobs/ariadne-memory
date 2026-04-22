/**
 * Memory — Memory system management (CRUD, rename, merge, export, import) with full i18n
 */

import { useEffect, useState, useRef } from 'react';
import { memoryApi, type MemoryInfo } from '../api/ariadne';
import { t } from '../i18n';

export default function Memory() {
  const [systems, setSystems] = useState<MemoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [mergeFrom, setMergeFrom] = useState<string[]>([]);
  const [mergeTo, setMergeTo] = useState('');
  const [deleteSources, setDeleteSources] = useState(false);
  const [tab, setTab] = useState<'list' | 'create' | 'merge' | 'import'>('list');
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameNewName, setRenameNewName] = useState('');
  const [importing, setImporting] = useState(false);
  const [detailTarget, setDetailTarget] = useState<MemoryInfo | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function load() {
    memoryApi.list().then(setSystems).catch(console.error).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await memoryApi.create(newName, newDesc);
      setNewName(''); setNewDesc('');
      setTab('list');
      load();
    } catch (err) { alert(String(err)); }
  }

  async function handleDelete(name: string) {
    if (!confirm(t('memory.confirm_delete'))) return;
    try {
      await memoryApi.delete(name);
      load();
    } catch (err) { alert(String(err)); }
  }

  async function handleClear(name: string) {
    if (!confirm(t('memory.confirm_clear') || `Clear all documents from '${name}'?`)) return;
    try {
      await memoryApi.clear(name);
      load();
    } catch (err) { alert(String(err)); }
  }

  async function handleShowDetail(name: string) {
    try {
      const info = await memoryApi.getInfo(name);
      setDetailTarget(info);
    } catch (err) { alert(String(err)); }
  }

  async function handleRename() {
    if (!renameTarget || !renameNewName.trim()) return;
    if (renameNewName === renameTarget) { setRenameTarget(null); return; }
    try {
      await memoryApi.rename(renameTarget, renameNewName);
      setRenameTarget(null);
      setRenameNewName('');
      load();
    } catch (err) { alert(String(err)); }
  }

  async function handleExport(name: string) {
    try {
      const url = `/api/memory/${encodeURIComponent(name)}/export`;
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) { alert(String(err)); }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    // Extract suggested name from file name (remove .zip extension)
    const suggestedName = file.name.replace(/\.zip$/i, '');
    const importName = window.prompt(t('memory.confirm_rename').replace('新名称', '导入名称') + `\n(${suggestedName})`, suggestedName);
    if (!importName) {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`/api/memory/import?name=${encodeURIComponent(importName)}`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Import failed' }));
        throw new Error(err.detail || 'Import failed');
      }
      load();
      setTab('list');
    } catch (err) { alert(String(err)); }
    finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleMerge(e: React.FormEvent) {
    e.preventDefault();
    if (!mergeTo.trim() || mergeFrom.length === 0) return;
    try {
      await memoryApi.merge(mergeFrom, mergeTo, deleteSources);
      setMergeFrom([]); setMergeTo(''); setDeleteSources(false);
      setTab('list');
      load();
    } catch (err) { alert(String(err)); }
  }

  function toggleMerge(name: string) {
    setMergeFrom(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  }

  if (loading) return <div className="page-loading">{t('common.loading')}</div>;

  return (
    <div className="page memory">
      <header className="page-header">
        <h1>💾 {t('memory.title')}</h1>
        <div className="tabs">
          <button className={tab === 'list' ? 'active' : ''} onClick={() => setTab('list')}>{t('memory.documents')}</button>
          <button className={tab === 'create' ? 'active' : ''} onClick={() => setTab('create')}>{t('memory.create')}</button>
          <button className={tab === 'merge' ? 'active' : ''} onClick={() => setTab('merge')}>{t('memory.merge')}</button>
          <button className={tab === 'import' ? 'active' : ''} onClick={() => setTab('import')}>{t('memory.import')}</button>
        </div>
      </header>

      {tab === 'list' && (
        <div>
          {systems.length === 0 ? (
            <div className="empty-state">
              <p>{t('memory.empty')}</p>
              <button className="btn-primary" onClick={() => setTab('create')}>{t('memory.create')} +</button>
            </div>
          ) : (
            <table className="systems-table">
              <thead>
                <tr>
                  <th>{t('memory.title')}</th>
                  <th>{t('memory.documents')}</th>
                  <th>{t('memory.created')}</th>
                  <th>{t('memory.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {systems.map(s => (
                  <tr key={s.name}>
                    <td>
                      <strong>{s.name}</strong>
                      {s.description && (
                        <><br /><small>{s.description}</small></>
                      )}
                    </td>
                    <td>{s.document_count}</td>
                    <td>{s.created_at || '—'}</td>
                    <td className="action-buttons">
                      <button
                        className="btn-icon"
                        title={t('memory.info') || 'Details'}
                        onClick={() => handleShowDetail(s.name)}
                      >
                        ℹ️
                      </button>
                      <button
                        className="btn-icon"
                        title={t('memory.rename')}
                        onClick={() => { setRenameTarget(s.name); setRenameNewName(s.name); }}
                      >
                        ✏️
                      </button>
                      <button
                        className="btn-icon"
                        title={t('memory.export')}
                        onClick={() => handleExport(s.name)}
                      >
                        📤
                      </button>
                      <button
                        className="btn-icon"
                        title={t('memory.clear') || 'Clear'}
                        onClick={() => handleClear(s.name)}
                      >
                        🧹
                      </button>
                      <button
                        className="btn-icon btn-danger"
                        title={t('memory.delete')}
                        onClick={() => handleDelete(s.name)}
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'create' && (
        <form className="form-card" onSubmit={handleCreate}>
          <h2>{t('memory.create')}</h2>
          <div className="form-group">
            <input
              type="text"
              placeholder={t('memory.new_name')}
              value={newName}
              onChange={e => setNewName(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <input
              type="text"
              placeholder={t('memory.import_hint')}
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
            />
          </div>
          <button type="submit" className="btn-primary">{t('memory.create')}</button>
        </form>
      )}

      {tab === 'merge' && (
        <form className="form-card" onSubmit={handleMerge}>
          <h2>{t('memory.merge')}</h2>
          <p>{t('memory.documents')}:</p>
          <div className="checkbox-list">
            {systems.map(s => (
              <label key={s.name}>
                <input
                  type="checkbox"
                  checked={mergeFrom.includes(s.name)}
                  onChange={() => toggleMerge(s.name)}
                />
                {s.name} ({s.document_count} {t('memory.documents')})
              </label>
            ))}
          </div>
          <div className="form-group">
            <input
              type="text"
              placeholder={t('memory.new_name')}
              value={mergeTo}
              onChange={e => setMergeTo(e.target.value)}
              required
            />
          </div>
          <label className="checkbox-label" style={{ marginBottom: '12px' }}>
            <input
              type="checkbox"
              checked={deleteSources}
              onChange={e => setDeleteSources(e.target.checked)}
            />
            {t('memory.delete_sources') || 'Delete sources after merge'}
          </label>
          <button type="submit" className="btn-primary" disabled={mergeFrom.length === 0}>
            {t('memory.merge')} ({mergeFrom.length} → {mergeTo || '?'})
          </button>
        </form>
      )}

      {tab === 'import' && (
        <div className="form-card">
          <h2>{t('memory.import')}</h2>
          <p>{t('memory.import_hint')}</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleImport}
            disabled={importing}
          />
          {importing && <p>{t('common.loading')}...</p>}
        </div>
      )}

      {/* Rename Modal */}
      {renameTarget && (
        <div className="modal-overlay" onClick={() => setRenameTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>✏️ {t('memory.rename')}</h3>
            <p>{t('memory.confirm_rename')}</p>
            <input
              type="text"
              value={renameNewName}
              onChange={e => setRenameNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRename()}
              autoFocus
            />
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setRenameTarget(null)}>
                {t('common.cancel')}
              </button>
              <button className="btn-primary" onClick={handleRename}>
                {t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {detailTarget && (
        <div className="modal-overlay" onClick={() => setDetailTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>ℹ️ {detailTarget.name}</h3>
            <div style={{ textAlign: 'left', lineHeight: 1.8 }}>
              <p><strong>{t('memory.documents') || 'Documents'}:</strong> {detailTarget.document_count}</p>
              <p><strong>Path:</strong> <small>{detailTarget.path}</small></p>
              <p><strong>{t('memory.created') || 'Created'}:</strong> {detailTarget.created_at || '—'}</p>
              <p><strong>Updated:</strong> {detailTarget.updated_at || '—'}</p>
              {detailTarget.description && <p><strong>Description:</strong> {detailTarget.description}</p>}
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setDetailTarget(null)}>
                {t('common.cancel') || 'Close'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
