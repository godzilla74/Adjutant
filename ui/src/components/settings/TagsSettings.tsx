import { useEffect, useState } from 'react'
import { Tag } from '../../types'
import { api } from '../../api'

interface Props {
  password: string
}

export default function TagsSettings({ password }: Props) {
  const [tags, setTags] = useState<Tag[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    setTags(await api.listTags(password))
  }

  function startEdit(tag: Tag) {
    setEditingId(tag.id)
    setEditName(tag.name)
    setEditDesc(tag.description)
  }

  async function saveEdit(tag: Tag) {
    await api.updateTag(password, tag.id, { name: editName, description: editDesc })
    setEditingId(null)
    load()
  }

  async function del(tag: Tag) {
    if (!confirm(`Delete tag "${tag.name}"? This removes all signals tagged with it.`)) return
    await api.deleteTag(password, tag.id)
    load()
  }

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    await api.createTag(password, newName.trim(), newDesc.trim())
    setNewName('')
    setNewDesc('')
    setAdding(false)
    load()
  }

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Tags</h2>
      <p className="text-xs text-adj-text-muted mb-6">
        Global tag library. Agents and humans use these to signal opportunities across workstreams.
      </p>

      <div className="flex flex-col mb-4 border border-adj-border rounded-lg overflow-hidden divide-y divide-adj-border">
        {tags.length === 0 && !adding && (
          <div className="px-4 py-3 text-xs text-adj-text-faint">No tags yet.</div>
        )}
        {tags.map(tag => (
          <div key={tag.id} className="bg-adj-panel">
            {editingId === tag.id ? (
              <div className="px-4 py-3 space-y-2 bg-adj-surface">
                <input
                  autoFocus
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="w-full bg-adj-panel border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
                  placeholder="namespace:tag"
                />
                <input
                  value={editDesc}
                  onChange={e => setEditDesc(e.target.value)}
                  placeholder="Description"
                  className="w-full bg-adj-panel border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => saveEdit(tag)}
                    className="px-3 py-1.5 rounded bg-adj-accent text-white text-xs font-semibold hover:bg-adj-accent-dark transition-colors"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1.5 rounded text-xs text-adj-text-muted hover:text-adj-text-secondary"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-adj-elevated group">
                <button
                  onClick={() => startEdit(tag)}
                  className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-adj-elevated border border-adj-border text-adj-accent hover:border-adj-accent transition-colors"
                >
                  {tag.name}
                </button>
                <span className="flex-1 text-xs text-adj-text-muted truncate">{tag.description}</span>
                <button
                  aria-label="Delete tag"
                  onClick={() => del(tag)}
                  className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-adj-text-faint hover:text-red-400 transition-all flex-shrink-0"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        ))}

        {adding && (
          <form onSubmit={create} className="px-4 py-3 space-y-2 bg-adj-panel">
            <input
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="namespace:tag e.g. social:linkedin"
              className="w-full bg-adj-elevated border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
            />
            <input
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="w-full bg-adj-elevated border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
            />
            <div className="flex gap-2">
              <button type="submit" className="px-3 py-1.5 rounded bg-adj-accent text-white text-xs font-semibold hover:bg-adj-accent-dark transition-colors">Add</button>
              <button type="button" onClick={() => { setAdding(false); setNewName(''); setNewDesc('') }} className="text-xs text-adj-text-faint hover:text-adj-text-muted">Cancel</button>
            </div>
          </form>
        )}
      </div>

      {!adding && (
        <button
          onClick={() => setAdding(true)}
          className="w-full border border-dashed border-adj-text-faint rounded-lg py-2.5 text-sm text-adj-text-faint hover:border-adj-accent hover:text-adj-accent transition-colors"
        >
          + Add Tag
        </button>
      )}
    </div>
  )
}
