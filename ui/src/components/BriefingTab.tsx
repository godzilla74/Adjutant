import { useEffect, useState } from 'react'
import { api } from '../api'
import type { OrchestratorRun, ReviewItem } from '../types'

interface Props {
  productId: string
  password: string
  reviewItems: ReviewItem[]
  onApprove: (id: number) => void
  onSkip: (id: number) => void
}

function relDate(ts: string) {
  const d = new Date(ts.replace(' ', 'T') + 'Z')
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const STATUS_COLORS: Record<string, string> = {
  applied: 'text-green-400',
  queued:  'text-amber-400',
  skipped: 'text-adj-text-faint',
  error:   'text-red-400',
}

export default function BriefingTab({ productId, password, reviewItems, onApprove, onSkip }: Props) {
  const [runs, setRuns] = useState<OrchestratorRun[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [triggering, setTriggering] = useState(false)

  const load = () => {
    setLoading(true)
    api.getOrchestratorRuns(password, productId)
      .then(setRuns)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [productId, password])

  const trigger = async () => {
    setTriggering(true)
    await api.triggerOrchestrator(password, productId).catch(() => {})
    setTriggering(false)
  }

  const toggleExpand = (id: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Orchestrator-sourced pending review items
  const pendingApprovals = reviewItems.filter(
    r => r.status === 'pending' && r.action_type?.startsWith('orchestrator_')
  )

  const latest = runs[0] ?? null
  const history = runs.slice(1)

  if (loading) return <div className="text-xs text-adj-text-faint p-4">Loading…</div>

  return (
    <div className="flex flex-col gap-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-adj-text-primary">Product Adjutant Briefing</h2>
        <button
          onClick={trigger}
          disabled={triggering}
          className="text-xs px-3 py-1 bg-adj-surface border border-adj-border rounded-full text-adj-text-secondary hover:text-adj-text-primary disabled:opacity-50"
        >
          {triggering ? 'Queuing…' : 'Run now'}
        </button>
      </div>

      {!latest && (
        <p className="text-xs text-adj-text-faint">No runs yet. Enable the Product Adjutant in Settings → Adjutant.</p>
      )}

      {/* Latest run */}
      {latest && (
        <div className="bg-adj-panel border border-adj-border rounded-lg p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-[10px] text-adj-text-faint">
            <span className="uppercase tracking-wider">{latest.triggered_by.replace('_', ' ')}</span>
            <span>·</span>
            <span>{relDate(latest.run_at)}</span>
            {latest.status === 'error' && (
              <span className="text-red-400 ml-auto">Error</span>
            )}
          </div>

          {latest.brief && (
            <p className="text-sm text-adj-text-primary leading-relaxed">{latest.brief}</p>
          )}

          {latest.status === 'error' && latest.error && (
            <p className="text-xs text-red-400 font-mono">{latest.error}</p>
          )}

          {/* Decisions */}
          {latest.decisions.length > 0 && (
            <div className="flex flex-col gap-1 mt-1">
              <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">Decisions</p>
              {latest.decisions.map((d, i) => (
                <div
                  key={i}
                  data-status={d._status}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className={`font-mono ${STATUS_COLORS[d._status] ?? 'text-adj-text-faint'}`}>
                    {d._status === 'applied' ? '✓' : d._status === 'queued' ? '⏳' : d._status === 'error' ? '✗' : '–'}
                  </span>
                  <span className="text-adj-text-secondary font-medium">{d.action}</span>
                  {d.reason && <span className="text-adj-text-faint">— {d.reason}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pending approvals */}
      {pendingApprovals.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">
            Pending Approvals ({pendingApprovals.length})
          </p>
          {pendingApprovals.map(item => (
            <div key={item.id} className="bg-adj-panel border border-amber-500/30 rounded-lg p-3 flex flex-col gap-2">
              <p className="text-xs font-semibold text-adj-text-primary">{item.title.replace(/_/g, ' ')}</p>
              <p className="text-xs text-adj-text-secondary">{item.description.replace(/^\[orchestrator_run:\d+\]\s*/, '')}</p>
              <div className="flex gap-2 mt-1">
                <button
                  onClick={() => onApprove(item.id)}
                  className="px-3 py-1 text-xs bg-green-600 hover:bg-green-500 text-white rounded"
                >
                  Approve
                </button>
                <button
                  onClick={() => onSkip(item.id)}
                  className="px-3 py-1 text-xs bg-adj-surface border border-adj-border hover:border-adj-text-faint text-adj-text-secondary rounded"
                >
                  Skip
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Run history — always shown once a run has occurred */}
      {runs.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">Run history</p>
          {history.length === 0 && (
            <p className="text-xs text-adj-text-faint">No previous runs.</p>
          )}
          {history.map(run => (
            <div key={run.id} className="bg-adj-panel border border-adj-border rounded-lg overflow-hidden">
              <button
                onClick={() => toggleExpand(run.id)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs text-adj-text-secondary hover:text-adj-text-primary"
              >
                <span>{relDate(run.run_at)} · {run.triggered_by.replace('_', ' ')} · {run.decisions.length} decisions</span>
                <span>{expanded.has(run.id) ? '▲' : '▼'}</span>
              </button>
              {expanded.has(run.id) && (
                <div className="px-3 pb-3 flex flex-col gap-1">
                  {run.brief && <p className="text-xs text-adj-text-primary mb-2">{run.brief}</p>}
                  {run.decisions.map((d, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className={STATUS_COLORS[d._status] ?? 'text-adj-text-faint'}>
                        {d._status === 'applied' ? '✓' : d._status === 'queued' ? '⏳' : '–'}
                      </span>
                      <span className="text-adj-text-secondary">{d.action}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
