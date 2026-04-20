/**
 * Memory — Memory system management (CRUD, merge)
 */

import { useEffect, useState } from 'react';
import { memoryApi, type MemoryInfo } from '../api/ariadne';

export default function Memory() {
  const [systems, setSystems] = useState<MemoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [mergeFrom, setMergeFrom] = useState<string[]>([]);
  const [mergeTo, setMergeTo] = useState('');
  const [tab, setTab] = useState<'list' | 'create' | 'merge'>('list');

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
    if (!confirm(`Delete memory system "${name}"?`)) return;
    try {
      await memoryApi.delete(name);
      load();
    } catch (err) { alert(String(err)); }
  }

  async function handleMerge(e: React.FormEvent) {
    e.preventDefault();
    if (!mergeTo.trim() || mergeFrom.length === 0) return;
    try {
      await memoryApi.merge(mergeFrom, mergeTo);
      setMergeFrom([]); setMergeTo('');
      setTab('list');
      load();
    } catch (err) { alert(String(err)); }
  }

  function toggleMerge(name: string) {
    setMergeFrom(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  }

  if (loading) return <div className="page-loading">Loading...</div>;

  return (
    <div className="page memory">
      <header className="page-header">
        <h1>💾 Memory Systems</h1>
        <div className="tabs">
          <button className={tab === 'list' ? 'active' : ''} onClick={() => setTab('list')}>List</button>
          <button className={tab === 'create' ? 'active' : ''} onClick={() => setTab('create')}>Create</button>
          <button className={tab === 'merge' ? 'active' : ''} onClick={() => setTab('merge')}>Merge</button>
        </div>
      </header>

      {tab === 'list' && (
        <table className="systems-table">
          <thead>
            <tr><th>Name</th><th>Documents</th><th>Created</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {systems.map(s => (
              <tr key={s.name}>
                <td><strong>{s.name}</strong><br /><small>{s.description}</small></td>
                <td>{s.document_count}</td>
                <td>{s.created_at || '—'}</td>
                <td>
                  <button className="btn-danger" onClick={() => handleDelete(s.name)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'create' && (
        <form className="form-card" onSubmit={handleCreate}>
          <h2>Create Memory System</h2>
          <input
            type="text"
            placeholder="Name"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={e => setNewDesc(e.target.value)}
          />
          <button type="submit" className="btn-primary">Create</button>
        </form>
      )}

      {tab === 'merge' && (
        <form className="form-card" onSubmit={handleMerge}>
          <h2>Merge Memory Systems</h2>
          <p>Select sources to merge:</p>
          <div className="checkbox-list">
            {systems.map(s => (
              <label key={s.name}>
                <input
                  type="checkbox"
                  checked={mergeFrom.includes(s.name)}
                  onChange={() => toggleMerge(s.name)}
                />
                {s.name} ({s.document_count} docs)
              </label>
            ))}
          </div>
          <input
            type="text"
            placeholder="New memory system name"
            value={mergeTo}
            onChange={e => setMergeTo(e.target.value)}
            required
          />
          <button type="submit" className="btn-primary" disabled={mergeFrom.length === 0}>
            Merge ({mergeFrom.length} → {mergeTo || '?'})
          </button>
        </form>
      )}
    </div>
  );
}