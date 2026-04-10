// ui/src/components/WorkstreamsPanel.tsx
import { useState, useEffect } from 'react'
import { api } from '../api'
import { Workstream, Objective } from '../types'

interface Props {
  workstreams:          Workstream[]
  objectives:           Objective[]
  password:             string
  onWorkstreamUpdated:  (wsId: number, patch: { name: string; schedule: string; mission: string }) => void
}

const STATUS_DOT: Record<string, string> = {
  running: 'bg-emerald-400 animate-pulse',
  warn:    'bg-amber-400',
  paused:  'bg-zinc-600',
}

const SCHEDULE_LABEL: Record<string, string> = {
  hourly:   'hourly',
  daily:    'daily',
  weekdays: 'weekdays',
  weekly:   'weekly',
  manual:   '',
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60)    return 'just now'
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function timeUntil(iso: string): string {
  const diff = Math.floor((new Date(iso).getTime() - Date.now()) / 1000)
  if (diff <= 0)    return 'now'
  if (diff < 3600)  return `in ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `in ${Math.floor(diff / 3600)}h`
  return `in ${Math.floor(diff / 86400)}d`
}

export default function WorkstreamsPanel({ workstreams, password, onWorkstreamUpdated }: Props) {
  const [expandedWsId, setExpandedWsId] = useState<number | null>(null)
  const [editName,     setEditName]     = useState('')
  const [editSchedule, setEditSchedule] = useState('manual')
  const [editMission,  setEditMission]  = useState('')
  const [saving,       setSaving]       = useState(false)
  const [runningWsId,  setRunningWsId]  = useState<number | null>(null)

  const openEdit = (ws: Workstream) => {
    setExpandedWsId(ws.id)
    setEditName(ws.name)
    setEditSchedule(ws.schedule ?? 'manual')
    setEditMission(ws.mission ?? '')
    setSaving(false)
  }

  const closeEdit = () => {
    setExpandedWsId(null)
    setSaving(false)
  }

  const handleSave = async (wsId: number) => {
    setSaving(true)
    try {
      await api.updateWorkstream(password, wsId, {
        name:     editName,
        schedule: editSchedule,
        mission:  editMission,
      })
      onWorkstreamUpdated(wsId, { name: editName, schedule: editSchedule, mission: editMission })
      closeEdit()
    } catch {
      setSaving(false)
    }
  }

  const handleRunNow = async (wsId: number) => {
    setRunningWsId(wsId)
    try {
      await api.triggerWorkstreamRun(password, wsId)
    } finally {
      setRunningWsId(null)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && expandedWsId !== null) closeEdit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expandedWsId])

  return (
    <aside className="w-48 flex-shrink-0 border-r border-zinc-800/60 bg-zinc-950 flex flex-col">
      <div className="px-3.5 pt-3 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Workstreams
      </div>

      {workstreams.map(ws => {
        const scheduleLabel = ws.schedule ? SCHEDULE_LABEL[ws.schedule] : undefined
        const isOpen = expandedWsId === ws.id
        return (
          <div key={ws.id}>
            <div className="flex items-center gap-2 px-3.5 py-2 hover:bg-zinc-900/60 cursor-default group">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-0.5 self-start ${STATUS_DOT[ws.status] ?? 'bg-zinc-600'}`} />
              <span className="flex-1 min-w-0">
                <span className="text-sm text-zinc-300 block leading-snug truncate">{ws.name}</span>
                <span className="text-[10px] text-zinc-600 leading-none">
                  {ws.next_run_at
                    ? timeUntil(ws.next_run_at)
                    : ws.last_run_at
                      ? timeAgo(ws.last_run_at)
                      : scheduleLabel ?? ''}
                  {scheduleLabel && ws.next_run_at && (
                    <span className="ml-1 opacity-60">{scheduleLabel}</span>
                  )}
                </span>
              </span>
              {/* Hover icon row: play + gear */}
              <div className={`flex items-center gap-0.5 flex-shrink-0 transition-opacity ${isOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                {/* Play / Run Now — only shown when workstream has a mission */}
                {ws.mission?.trim() && (
                  <button
                    title="Run now"
                    onClick={() => handleRunNow(ws.id)}
                    className="w-5 h-5 flex items-center justify-center rounded text-zinc-500 hover:text-emerald-400 hover:bg-zinc-800 transition-colors"
                  >
                    {runningWsId === ws.id ? (
                      <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                    ) : (
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M5 3l14 9-14 9V3z" />
                      </svg>
                    )}
                  </button>
                )}
                {/* Gear / Edit */}
                <button
                  title="Edit workstream"
                  onClick={() => isOpen ? closeEdit() : openEdit(ws)}
                  className={`w-5 h-5 flex items-center justify-center rounded transition-colors ${
                    isOpen
                      ? 'text-zinc-300 bg-zinc-800'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
                  }`}
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Inline edit form */}
            {isOpen && (
              <div className="mx-3 mb-2 p-2.5 bg-zinc-900 border-l-2 border-zinc-700 rounded-r">
                <label className="block text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Name</label>
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded text-[11px] text-zinc-200 px-2 py-1 mb-2 focus:outline-none focus:border-zinc-500"
                />
                <label className="block text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Schedule</label>
                <select
                  value={editSchedule}
                  onChange={e => setEditSchedule(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded text-[11px] text-zinc-200 px-2 py-1 mb-2 focus:outline-none focus:border-zinc-500"
                >
                  <option value="manual">Manual only</option>
                  <option value="hourly">Every hour</option>
                  <option value="daily">Daily at 9am</option>
                  <option value="weekdays">Weekdays at 9am</option>
                  <option value="weekly">Mondays at 9am</option>
                </select>
                <label className="block text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Mission</label>
                <textarea
                  value={editMission}
                  onChange={e => setEditMission(e.target.value)}
                  rows={3}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded text-[11px] text-zinc-200 px-2 py-1 mb-2 focus:outline-none focus:border-zinc-500 resize-none"
                />
                <div className="flex gap-1.5">
                  <button
                    onClick={closeEdit}
                    className="flex-1 text-[10px] text-zinc-400 bg-zinc-800 hover:bg-zinc-700 rounded py-1 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleSave(ws.id)}
                    disabled={saving}
                    className="flex-1 text-[10px] text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded py-1 transition-colors"
                  >
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </aside>
  )
}
