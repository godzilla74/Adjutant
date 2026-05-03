import { useState } from 'react'
import { Workstream } from '../types'
import { api } from '../api'

interface Props {
  workstream: Workstream
  password: string
  onStatusChange: (wsId: number, status: 'running' | 'paused') => void
}

function relTime(ts: string | null | undefined) {
  if (!ts) return null
  const diff = Date.now() - new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

const STATUS_STYLES: Record<string, string> = {
  running: 'bg-green-950/40 border-green-900/40 text-green-400',
  warn:    'bg-amber-950/40 border-amber-900/40 text-amber-400',
  paused:  'bg-adj-elevated border-adj-border text-adj-text-faint',
}

export default function WorkstreamChip({ workstream, password, onStatusChange }: Props) {
  const [saving, setSaving] = useState(false)

  const toggle = async () => {
    const next = workstream.status === 'paused' ? 'running' : 'paused'
    setSaving(true)
    try {
      await api.updateWorkstream(password, workstream.id, { status: next })
      onStatusChange(workstream.id, next)
    } finally {
      setSaving(false)
    }
  }

  const lastRun = relTime(workstream.last_run_at)

  return (
    <div className={`flex items-center gap-1.5 border rounded-md px-2 py-1 text-[11px] ${STATUS_STYLES[workstream.status] ?? STATUS_STYLES.paused}`}>
      <span className="truncate max-w-[120px]">{workstream.name}</span>
      {lastRun && <span className="text-[10px] opacity-60 flex-shrink-0">{lastRun}</span>}
      <button
        title={workstream.status === 'paused' ? 'Resume' : 'Pause'}
        onClick={toggle}
        disabled={saving}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity ml-0.5 disabled:opacity-30"
      >
        {workstream.status === 'paused' ? '▶' : '⏸'}
      </button>
    </div>
  )
}
