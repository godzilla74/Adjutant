import { useState } from 'react'
import { Objective } from '../../types'
import { api } from '../../api'

interface Props {
  productId: string
  objectives: Objective[]
  password: string
  onObjectiveUpdated: (objId: number, patch: Partial<Objective>) => void
}

export default function ObjectivesSettings({ productId, objectives, password, onObjectiveUpdated }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<{ text: string; cur: string; tgt: string; autonomous: number }>({
    text: '', cur: '', tgt: '', autonomous: 0,
  })

  const [adding, setAdding] = useState(false)
  const [newText, setNewText] = useState('')
  const [newCur, setNewCur] = useState('0')
  const [newTgt, setNewTgt] = useState('')

  const startEdit = (obj: Objective) => {
    setEditingId(obj.id)
    setForm({
      text: obj.text,
      cur: String(obj.progress_current),
      tgt: obj.progress_target != null ? String(obj.progress_target) : '',
      autonomous: obj.autonomous ?? 0,
    })
  }

  const saveEdit = async (obj: Objective) => {
    const cur = parseInt(form.cur)
    if (isNaN(cur)) { setEditingId(null); return }
    const tgt = form.tgt.trim() ? parseInt(form.tgt) : null
    const patch: Partial<Objective> = {
      text: form.text,
      progress_current: cur,
      autonomous: form.autonomous,
      ...(tgt !== null ? { progress_target: tgt } : { progress_target: null }),
    }
    await api.updateObjective(password, obj.id, {
      text: form.text,
      progress_current: cur,
      progress_target: tgt,
      autonomous: form.autonomous,
    })
    onObjectiveUpdated(obj.id, patch)
    setEditingId(null)
  }

  const del = async (obj: Objective) => {
    if (!confirm(`Delete "${obj.text}"?`)) return
    await api.deleteObjective(password, obj.id)
    // Signal deletion by passing a sentinel — parent will filter by id
    onObjectiveUpdated(obj.id, { id: obj.id } as Partial<Objective>)
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newText.trim()) return
    const cur = parseInt(newCur) || 0
    const tgt = newTgt.trim() ? parseInt(newTgt) || undefined : undefined
    const created = await api.createObjective(password, productId, newText.trim(), cur, tgt)
    onObjectiveUpdated(created.id, created)
    setNewText(''); setNewCur('0'); setNewTgt('')
    setAdding(false)
  }

  const pct = (obj: Objective) => {
    if (obj.progress_target == null || obj.progress_target <= 0) return null
    return Math.min(100, Math.round((obj.progress_current / obj.progress_target) * 100))
  }

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Objectives</h2>
      <p className="text-xs text-adj-text-muted mb-6">Key results and goals for this product</p>

      <div className="flex flex-col gap-2 mb-4">
        {objectives.length === 0 && !adding && (
          <p className="text-xs text-adj-text-faint py-2">No objectives yet.</p>
        )}
        {objectives.map(obj => (
          <div key={obj.id} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3 group">
            {editingId === obj.id ? (
              <div className="space-y-2">
                <input
                  className="w-full bg-adj-elevated border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
                  value={form.text}
                  onChange={e => setForm(f => ({ ...f, text: e.target.value }))}
                  placeholder="Objective description"
                />
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={form.cur}
                    onChange={e => setForm(f => ({ ...f, cur: e.target.value }))}
                    className="w-20 bg-adj-elevated border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent"
                    placeholder="Current"
                  />
                  <span className="text-adj-text-faint text-xs">/</span>
                  <input
                    type="number"
                    value={form.tgt}
                    onChange={e => setForm(f => ({ ...f, tgt: e.target.value }))}
                    className="w-20 bg-adj-elevated border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent"
                    placeholder="Target"
                  />
                  <button
                    onClick={() => saveEdit(obj)}
                    className="text-xs px-2 py-1 bg-adj-accent text-white hover:bg-adj-accent-dark rounded transition-colors"
                  >✓</button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="text-xs text-adj-text-faint hover:text-adj-text-muted"
                  >✕</button>
                </div>
                <div className="mb-3 flex items-center gap-3">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">Autonomous</label>
                  <button
                    onClick={() => setForm(f => ({ ...f, autonomous: f.autonomous === 1 ? 0 : 1 }))}
                    className={`w-8 h-4 rounded-full transition-colors flex-shrink-0 ${form.autonomous === 1 ? 'bg-adj-accent' : 'bg-adj-border'}`}
                    role="switch"
                    aria-checked={form.autonomous === 1}
                  >
                    <span className={`block w-3 h-3 rounded-full bg-white shadow transition-transform mx-0.5 ${form.autonomous === 1 ? 'translate-x-4' : 'translate-x-0'}`} />
                  </button>
                  <span className="text-xs text-adj-text-muted">{form.autonomous === 1 ? 'Runs automatically' : 'Requires approval'}</span>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-start gap-2">
                  <span className="flex-1 text-sm text-adj-text-primary leading-snug">{obj.text}</span>
                  {obj.autonomous === 1 && <span className="text-[9px] text-adj-accent font-semibold">AUTO</span>}
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                    <button onClick={() => startEdit(obj)} className="text-xs text-adj-accent hover:underline">Edit</button>
                    <button onClick={() => del(obj)} className="text-xs text-red-400 hover:underline">Delete</button>
                  </div>
                </div>
                <div className="mt-2">
                  {pct(obj) !== null && (
                    <div className="h-1 bg-adj-elevated rounded-full mb-1.5 overflow-hidden">
                      <div className="h-full bg-adj-accent rounded-full transition-all" style={{ width: `${pct(obj)}%` }} />
                    </div>
                  )}
                  <button
                    onClick={() => startEdit(obj)}
                    className="text-xs text-adj-text-faint hover:text-adj-text-muted transition-colors tabular-nums"
                  >
                    {obj.progress_current}
                    {obj.progress_target != null ? ` / ${obj.progress_target}` : ''}
                    {pct(obj) !== null && <span className="ml-1 opacity-60">{pct(obj)}%</span>}
                    <span className="ml-1 opacity-40">edit</span>
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {adding ? (
        <form onSubmit={create} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3 space-y-2">
          <input
            autoFocus
            type="text"
            value={newText}
            onChange={e => setNewText(e.target.value)}
            placeholder="Objective description"
            className="w-full bg-adj-elevated border border-adj-border rounded px-3 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
          />
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={newCur}
              onChange={e => setNewCur(e.target.value)}
              placeholder="Start"
              className="w-20 bg-adj-elevated border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
            />
            <span className="text-adj-text-faint text-xs">/</span>
            <input
              type="number"
              value={newTgt}
              onChange={e => setNewTgt(e.target.value)}
              placeholder="Target"
              className="w-20 bg-adj-elevated border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
            />
            <button type="submit" className="flex-1 text-xs py-1.5 bg-adj-accent text-white hover:bg-adj-accent-dark rounded transition-colors">Add</button>
            <button type="button" onClick={() => { setAdding(false); setNewText('') }} className="text-xs text-adj-text-faint hover:text-adj-text-muted">✕</button>
          </div>
        </form>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="w-full border border-dashed border-adj-text-faint rounded-lg py-2.5 text-sm text-adj-text-faint hover:border-adj-accent hover:text-adj-accent transition-colors"
        >
          + Add Objective
        </button>
      )}
    </div>
  )
}
