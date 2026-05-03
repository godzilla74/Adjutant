import { useEffect, useState } from 'react'
import { api } from '../api'
import type { HCARun, HCADirective, ReviewItem } from '../types'

interface Props {
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

const DECISION_COLORS: Record<string, string> = {
  applied: 'text-green-400',
  queued:  'text-amber-400',
  skipped: 'text-adj-text-faint',
  error:   'text-red-400',
}

export default function HCABriefingPanel({ password, reviewItems, onApprove, onSkip }: Props) {
  const [runs, setRuns] = useState<HCARun[]>([])
  const [directives, setDirectives] = useState<HCADirective[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [triggering, setTriggering] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.getHCARuns(password),
      api.getHCADirectives(password),
    ]).then(([r, d]) => {
      setRuns(r)
      setDirectives(d)
    }).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [password])

  const trigger = async () => {
    setTriggering(true)
    try {
      await api.triggerHCA(password).catch(() => {})
      await new Promise(res => setTimeout(res, 2000))
    } finally {
      setTriggering(false)
    }
  }

  const retireDirective = async (id: number) => {
    try {
      await api.deleteHCADirective(password, id)
      setDirectives(prev => prev.filter(d => d.id !== id))
    } catch {
      // silent fail — directive remains visible
    }
  }

  const pendingProposals = reviewItems.filter(r => r.action_type === 'hca_new_product' && r.status === 'pending')

  const toggleExpand = (id: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const latestRun = runs[0]

  return (
    <div className="flex flex-col gap-6 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-adj-text-primary">Chief Adjutant</h2>
        <button
          onClick={trigger}
          disabled={triggering}
          className="px-2.5 py-1 text-[10px] bg-adj-panel border border-adj-border rounded text-adj-text-muted hover:text-adj-text-primary disabled:opacity-50"
        >
          {triggering ? 'Running…' : 'Run Now'}
        </button>
      </div>

      {/* Latest Run */}
      {loading ? (
        <div className="text-xs text-adj-text-faint">Loading…</div>
      ) : latestRun ? (
        <div className="bg-adj-panel border border-adj-border rounded p-3 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-[10px] text-adj-text-muted">
            <span className="uppercase tracking-wider">{latestRun.triggered_by}</span>
            <span>·</span>
            <span>{relDate(latestRun.run_at)}</span>
            <span>·</span>
            <span className={latestRun.status === 'error' ? 'text-red-400' : 'text-green-400'}>
              {latestRun.status}
            </span>
          </div>
          <p className="text-xs text-adj-text-primary leading-relaxed">{latestRun.brief}</p>
          {latestRun.decisions.length > 0 && (
            <div className="flex flex-col gap-1">
              <div className="text-[10px] text-adj-text-muted uppercase tracking-wider">Decisions</div>
              {latestRun.decisions.map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-[10px]">
                  <span className={`font-mono ${DECISION_COLORS[d._status] || 'text-adj-text-faint'}`}>
                    {d._status}
                  </span>
                  <span className="text-adj-text-muted font-mono">{d.action}</span>
                  {d.product_id && <span className="text-adj-text-faint">→ {d.product_id}</span>}
                  {d.reason && <span className="text-adj-text-faint truncate">{d.reason}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="text-xs text-adj-text-faint">No runs yet.</div>
      )}

      {/* Pending Proposals */}
      {pendingProposals.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
            Pending Proposals ({pendingProposals.length})
          </div>
          {pendingProposals.map(item => (
            <div key={item.id} className="bg-adj-panel border border-amber-500/30 rounded p-3 flex flex-col gap-2">
              <div className="text-xs font-medium text-adj-text-primary">{item.title}</div>
              {item.description && (
                <div className="text-[10px] text-adj-text-muted">{item.description}</div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => onApprove(item.id)}
                  className="px-2.5 py-1 text-[10px] bg-green-600 hover:bg-green-500 text-white rounded"
                >
                  Approve
                </button>
                <button
                  onClick={() => onSkip(item.id)}
                  className="px-2.5 py-1 text-[10px] bg-adj-surface border border-adj-border rounded text-adj-text-muted hover:text-adj-text-primary"
                >
                  Skip
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Active Directives */}
      {directives.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">
            Active Directives
          </div>
          {directives.map(d => (
            <div key={d.id} className="bg-adj-panel border border-adj-border rounded p-3 flex items-start justify-between gap-3">
              <div className="flex flex-col gap-1 flex-1 min-w-0">
                <div className="text-[10px] text-adj-text-faint">
                  {d.product_id ? `→ ${d.product_id}` : 'All products'}
                </div>
                <div className="text-xs text-adj-text-primary">{d.content}</div>
              </div>
              <button
                onClick={() => retireDirective(d.id)}
                className="text-[10px] text-adj-text-faint hover:text-red-400 shrink-0"
              >
                Retire
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Run History */}
      {runs.length > 1 && (
        <div className="flex flex-col gap-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">
            Run History
          </div>
          {runs.slice(1).map(run => (
            <div key={run.id}>
              <button
                className="w-full flex items-center gap-2 text-[10px] text-adj-text-muted hover:text-adj-text-primary py-1"
                onClick={() => toggleExpand(run.id)}
              >
                <span>{expanded.has(run.id) ? '▾' : '▸'}</span>
                <span>{relDate(run.run_at)}</span>
                <span className="uppercase tracking-wider">{run.triggered_by}</span>
                <span className={run.status === 'error' ? 'text-red-400' : 'text-adj-text-faint'}>
                  {run.status}
                </span>
                <span>{run.decisions.length} decisions</span>
              </button>
              {expanded.has(run.id) && (
                <div className="pl-4 pb-2 text-[10px] text-adj-text-muted leading-relaxed">
                  {run.brief || '(no brief)'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
