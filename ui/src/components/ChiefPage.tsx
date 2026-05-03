import { useEffect, useState } from 'react'
import { ReviewItem, HCARun, HCAConfig } from '../types'
import { api } from '../api'
import MarkdownContent from './MarkdownContent'

interface Props {
  password: string
  reviewItems: ReviewItem[]
  onResolveReview: (id: number, action: 'approved' | 'skipped') => void
  onOpenSettings: () => void
}

function relDate(ts: string) {
  const diff = Date.now() - new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function relNext(ts: string | null) {
  if (!ts) return null
  const diff = new Date(ts.replace(' ', 'T') + (ts.includes('Z') ? '' : 'Z')).getTime() - Date.now()
  if (diff <= 0) return 'due now'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `in ${mins}m`
  return `in ${Math.floor(mins / 60)}h`
}

const REVIEW_COLORS: Record<string, string> = {
  social_post:      'border-l-amber-500 bg-amber-950/10',
  hca_new_product:  'border-l-purple-500 bg-purple-950/10',
  send_email:       'border-l-red-400 bg-red-950/10',
}

export default function ChiefPage({ password, reviewItems, onResolveReview, onOpenSettings }: Props) {
  const [runs, setRuns]             = useState<HCARun[]>([])
  const [config, setConfig]         = useState<HCAConfig | null>(null)
  const [triggering, setTriggering] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.getHCARuns(password, 10),
      api.getHCAConfig(password),
    ]).then(([r, c]) => {
      if (!cancelled) { setRuns(r); setConfig(c) }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [password])

  const triggerRun = async () => {
    setTriggering(true)
    try { await api.triggerHCA(password) } finally { setTriggering(false) }
  }

  const latestRun    = runs[0] ?? null
  const pendingItems = reviewItems.filter(r => r.status === 'pending')

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-adj-base">

      {/* Page header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-adj-border flex-shrink-0">
        <div>
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Chief Adjutant</h1>
          <p className="text-[11px] text-adj-text-faint mt-0.5">
            {config?.last_run_at ? `Last ran ${relDate(config.last_run_at)}` : 'Never run'}
            {config?.next_run_at ? ` · next ${relNext(config.next_run_at)}` : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={triggerRun}
            disabled={triggering}
            className="text-[11px] text-adj-accent border border-adj-accent/40 bg-adj-accent/10 rounded-md px-3 py-1.5 hover:bg-adj-accent/20 transition-colors disabled:opacity-50"
          >
            {triggering ? 'Queuing…' : 'Run now'}
          </button>
          <button
            onClick={onOpenSettings}
            className="text-[11px] text-adj-text-faint border border-adj-border bg-adj-elevated rounded-md px-3 py-1.5 hover:text-adj-text-secondary transition-colors"
          >
            Configure
          </button>
        </div>
      </div>

      {/* Two-column body */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left: review queue */}
        <div className="flex-1 overflow-y-auto border-r border-adj-border px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] text-adj-text-faint uppercase tracking-widest">Pending Reviews</span>
            {pendingItems.length > 0 && (
              <span className="text-[9px] text-amber-400 bg-amber-950/30 border border-amber-900/40 rounded-full px-1.5 py-0.5 font-medium">
                {pendingItems.length}
              </span>
            )}
          </div>

          {pendingItems.length === 0 && (
            <p className="text-[12px] text-adj-text-faint">No pending reviews.</p>
          )}

          <div className="space-y-3">
            {pendingItems.map(item => (
              <div
                key={item.id}
                className={`bg-adj-panel border border-adj-border border-l-2 rounded-lg px-4 py-3 ${REVIEW_COLORS[item.action_type ?? ''] ?? 'border-l-adj-border'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-medium text-adj-text-primary">{item.title}</span>
                  <span className="text-[10px] text-adj-text-faint">{relDate(item.created_at)}</span>
                </div>
                <p className="text-[11px] text-adj-text-secondary leading-relaxed mb-3 line-clamp-3">{item.description}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => onResolveReview(item.id, 'approved')}
                    className="text-[10px] text-green-400 bg-green-950/30 border border-green-900/40 rounded px-2.5 py-1 hover:bg-green-950/60 transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => onResolveReview(item.id, 'skipped')}
                    className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2.5 py-1 hover:text-adj-text-secondary transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: briefing + run history */}
        <div className="w-72 flex-shrink-0 overflow-y-auto px-4 py-4">

          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Latest Briefing</div>
          {latestRun ? (
            <div className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3 mb-4">
              <div className="text-[11px] text-adj-text-secondary leading-relaxed">
                <MarkdownContent>{latestRun.brief}</MarkdownContent>
              </div>
              <div className="text-[10px] text-adj-text-faint mt-2 pt-2 border-t border-adj-border">
                {relDate(latestRun.run_at)}
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-adj-text-faint mb-4">No runs yet.</p>
          )}

          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Run History</div>
          <div className="space-y-1.5">
            {runs.map(run => (
              <div key={run.id} className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[11px] text-adj-text-secondary">Run #{run.id}</span>
                <span className="text-[10px] text-adj-text-faint">{relDate(run.run_at)}</span>
              </div>
            ))}
            {runs.length === 0 && <p className="text-[11px] text-adj-text-faint">No run history.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
