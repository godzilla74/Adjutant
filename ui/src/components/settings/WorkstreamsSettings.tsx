import { useRef, useState } from 'react'
import { Workstream } from '../../types'
import { api } from '../../api'

interface Props {
  productId: string
  workstreams: Workstream[]
  password: string
  onWorkstreamUpdated: (wsId: number, patch: Partial<Workstream>) => void
}

const SCHEDULES = ['manual', 'hourly', 'daily', 'weekdays', 'weekly'] as const

export default function WorkstreamsSettings({ productId, workstreams, password, onWorkstreamUpdated }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [editMission, setEditMission] = useState('')
  const [editSchedule, setEditSchedule] = useState('manual')
  const [saving, setSaving] = useState<Set<number>>(new Set())
  const [running, setRunning] = useState<Set<number>>(new Set())

  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState('')
  const newNameRef = useRef<HTMLInputElement>(null)

  const toggleExpand = (ws: Workstream) => {
    if (expandedId === ws.id) {
      setExpandedId(null)
    } else {
      setExpandedId(ws.id)
      setEditMission(ws.mission ?? '')
      setEditSchedule(ws.schedule ?? 'manual')
    }
  }

  const saveMission = async (ws: Workstream) => {
    setSaving(prev => new Set(prev).add(ws.id))
    try {
      const patch = { mission: editMission, schedule: editSchedule }
      await api.updateWorkstream(password, ws.id, patch)
      onWorkstreamUpdated(ws.id, patch)
    } finally {
      setSaving(prev => { const n = new Set(prev); n.delete(ws.id); return n })
    }
  }

  const runNow = async (ws: Workstream) => {
    setRunning(prev => new Set(prev).add(ws.id))
    try {
      await api.triggerWorkstreamRun(password, ws.id)
    } finally {
      setRunning(prev => { const n = new Set(prev); n.delete(ws.id); return n })
    }
  }

  const del = async (ws: Workstream) => {
    if (!confirm(`Delete "${ws.name}"?`)) return
    await api.deleteWorkstream(password, ws.id)
    onWorkstreamUpdated(ws.id, { status: 'paused' })
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    const created = await api.createWorkstream(password, productId, newName.trim())
    onWorkstreamUpdated(created.id, created)
    setNewName('')
    setAdding(false)
  }

  const STATUS_COLORS: Record<string, string> = {
    running: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    warn:    'bg-amber-500/20 text-amber-400 border-amber-500/40',
    paused:  'bg-zinc-700/40 text-zinc-500 border-zinc-700',
  }
  const STATUS_CYCLE: Record<string, 'running' | 'warn' | 'paused'> = {
    running: 'warn', warn: 'paused', paused: 'running',
  }

  const cycleStatus = async (ws: Workstream) => {
    const next = STATUS_CYCLE[ws.status]
    await api.updateWorkstream(password, ws.id, { status: next })
    onWorkstreamUpdated(ws.id, { status: next })
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Workstreams</h2>
      <p className="text-xs text-adj-text-muted mb-6">Automated recurring tasks for this product</p>

      <div className="flex flex-col mb-4 border border-adj-border rounded-lg overflow-hidden divide-y divide-adj-border">
        {workstreams.length === 0 && !adding && (
          <div className="px-4 py-3 text-xs text-adj-text-faint">No workstreams yet.</div>
        )}
        {workstreams.map(ws => {
          const isExpanded = expandedId === ws.id
          const isSaving = saving.has(ws.id)
          const isRunning = running.has(ws.id)
          const hasMission = !!(ws.mission?.trim())
          return (
            <div key={ws.id} className="bg-adj-panel">
              {/* Row header */}
              <div className="flex items-center gap-2 px-4 py-2.5 hover:bg-adj-elevated group">
                <button
                  onClick={() => toggleExpand(ws)}
                  className="text-adj-text-faint hover:text-adj-text-muted transition-colors flex-shrink-0"
                >
                  <svg className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
                <span
                  className="flex-1 text-sm text-adj-text-primary truncate cursor-pointer"
                  onClick={() => toggleExpand(ws)}
                >
                  {ws.name}
                  {hasMission && ws.schedule !== 'manual' && (
                    <span className="ml-1.5 text-[10px] text-adj-text-faint">{ws.schedule}</span>
                  )}
                </span>
                <button
                  onClick={() => cycleStatus(ws)}
                  className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors flex-shrink-0 ${STATUS_COLORS[ws.status]}`}
                  title="Click to cycle status"
                >
                  {ws.status === 'running' ? 'Live' : ws.status === 'warn' ? 'Warn' : 'Off'}
                </button>
                <button
                  onClick={() => del(ws)}
                  className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-adj-text-faint hover:text-red-400 transition-all flex-shrink-0"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>

              {/* Expanded mission editor */}
              {isExpanded && (
                <div className="px-4 pb-4 space-y-3 bg-adj-surface border-t border-adj-border">
                  <div className="pt-3">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Mission</label>
                    <textarea
                      rows={4}
                      value={editMission}
                      onChange={e => setEditMission(e.target.value)}
                      placeholder="Every Monday, research trending topics in our space and draft 3 content ideas…"
                      className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent resize-none leading-relaxed"
                    />
                  </div>
                  <div className="flex items-end gap-2">
                    <div className="flex-1">
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Schedule</label>
                      <select
                        value={editSchedule}
                        onChange={e => setEditSchedule(e.target.value)}
                        className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
                      >
                        {SCHEDULES.map(s => (
                          <option key={s} value={s}>
                            {s === 'manual' ? 'Manual only' : s === 'hourly' ? 'Every hour' : s === 'daily' ? 'Daily at 9am' : s === 'weekdays' ? 'Weekdays at 9am' : 'Mondays at 9am'}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      onClick={() => runNow(ws)}
                      disabled={isRunning || (!hasMission && !editMission.trim())}
                      className="px-3 py-2 rounded-md bg-adj-elevated hover:bg-adj-panel text-xs text-adj-text-secondary font-medium transition-colors disabled:opacity-40 whitespace-nowrap border border-adj-border"
                      title={hasMission ? 'Run now' : 'Save a mission first'}
                    >
                      {isRunning ? '…' : '▶ Run now'}
                    </button>
                  </div>
                  {ws.last_run_at && (
                    <p className="text-[11px] text-adj-text-faint">
                      Last run: {new Date(ws.last_run_at).toLocaleString()}
                    </p>
                  )}
                  <button
                    onClick={() => saveMission(ws)}
                    disabled={isSaving}
                    className="w-full py-2 rounded-md bg-adj-accent text-white text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
                  >
                    {isSaving ? 'Saving…' : 'Save mission'}
                  </button>
                </div>
              )}
            </div>
          )
        })}

        {adding && (
          <form onSubmit={create} className="px-4 py-2.5 flex items-center gap-2 bg-adj-panel">
            <input
              ref={newNameRef}
              autoFocus
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Workstream name"
              className="flex-1 bg-adj-elevated border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
            />
            <button type="submit" className="text-xs px-2.5 py-1.5 bg-adj-accent text-white hover:bg-adj-accent-dark rounded transition-colors">Add</button>
            <button type="button" onClick={() => { setAdding(false); setNewName('') }} className="text-xs text-adj-text-faint hover:text-adj-text-muted">✕</button>
          </form>
        )}
      </div>

      {!adding && (
        <button
          onClick={() => setAdding(true)}
          className="w-full border border-dashed border-adj-text-faint rounded-lg py-2.5 text-sm text-adj-text-faint hover:border-adj-accent hover:text-adj-accent transition-colors"
        >
          + Add Workstream
        </button>
      )}
    </div>
  )
}
