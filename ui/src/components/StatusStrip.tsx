import { useEffect, useRef, useState } from 'react'
import { ActivityEvent, Objective, ReviewItem, Workstream } from '../types'
import { elapsedLabel } from '../utils/time'

type PopoverKey = 'workstreams' | 'agents' | 'reviews' | 'objectives' | null

interface Props {
  workstreams: Workstream[]
  reviewItems: ReviewItem[]
  events: ActivityEvent[]
  objectives: Objective[]
  onResolveReview: (id: number, action: 'approved' | 'skipped') => void
  onCancelAgent: (directiveId: string) => void
  onOpenSettings: (tab: string) => void
}

export default function StatusStrip({
  workstreams, reviewItems, events, objectives,
  onResolveReview, onCancelAgent, onOpenSettings,
}: Props) {
  const [open, setOpen] = useState<PopoverKey>(null)
  const [detailItem, setDetailItem] = useState<ReviewItem | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  const pendingReviews = reviewItems.filter(r => r.status === 'pending')
  const runningAgents  = events.filter(e => e.status === 'running')
  const warnWs         = workstreams.filter(w => w.status === 'warn').length
  const runningWs      = workstreams.filter(w => w.status === 'running').length

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (key: PopoverKey) => setOpen(prev => prev === key ? null : key)

  const handleResolve = (id: number, action: 'approved' | 'skipped') => {
    onResolveReview(id, action)
    setDetailItem(null)
  }

  return (
    <>
      <div ref={ref} className="relative flex items-center gap-1 px-4 h-8 bg-adj-panel border-b border-adj-border flex-shrink-0 text-xs">

        {/* Workstreams pill */}
        <button
          data-testid="pill-workstreams"
          onClick={() => toggle('workstreams')}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'workstreams' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${
            warnWs > 0 ? 'bg-amber-400' : runningWs > 0 ? 'bg-green-400' : 'bg-adj-text-faint'
          }`} />
          <span className="font-semibold text-adj-text-primary">{workstreams.length}</span>
          <span className="text-adj-text-muted">workstreams</span>
        </button>

        <span className="w-px h-3 bg-adj-border" />

        {/* Agents pill */}
        <button
          data-testid="pill-agents"
          onClick={() => toggle('agents')}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'agents' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${runningAgents.length > 0 ? 'bg-blue-400 animate-pulse' : 'bg-adj-text-faint'}`} />
          <span className="font-semibold text-adj-text-primary">{runningAgents.length} active</span>
        </button>

        <span className="w-px h-3 bg-adj-border" />

        {/* Reviews pill */}
        <button
          data-testid="pill-reviews"
          onClick={() => toggle('reviews')}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${
            open === 'reviews' ? 'border-amber-500 bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${pendingReviews.length > 0 ? 'bg-amber-400' : 'bg-adj-text-faint'}`} />
          <span className={`font-semibold ${pendingReviews.length > 0 ? 'text-amber-400' : 'text-adj-text-primary'}`}>
            {pendingReviews.length} review{pendingReviews.length !== 1 ? 's' : ''}
          </span>
        </button>

        <span className="w-px h-3 bg-adj-border" />

        {/* Objectives pill */}
        <button
          data-testid="pill-objectives"
          onClick={() => toggle('objectives')}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'objectives' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
        >
          <span className="text-adj-text-muted">◎</span>
          <span className="font-semibold text-adj-text-primary">{objectives.length}</span>
          <span className="text-adj-text-muted">objectives</span>
        </button>

        {/* Popovers */}
        {open === 'workstreams' && (
          <Popover title="Workstreams" onManage={() => { onOpenSettings('workstreams'); setOpen(null) }} manageLabel="Manage workstreams →">
            {workstreams.map(ws => (
              <div key={ws.id} className="flex items-center gap-2.5 px-3 py-2 bg-adj-base rounded-md">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ws.status === 'running' ? 'bg-green-400' : ws.status === 'warn' ? 'bg-amber-400' : 'bg-adj-text-faint'}`} />
                <span className="text-adj-text-primary text-xs flex-1">{ws.name}</span>
                {ws.schedule && <span className="text-adj-text-muted text-[10px]">{ws.schedule}</span>}
              </div>
            ))}
          </Popover>
        )}

        {open === 'agents' && (
          <Popover title="Active Agents">
            {runningAgents.length === 0 && (
              <p className="text-adj-text-muted text-xs px-3 py-2">No agents running</p>
            )}
            {runningAgents.map(ev => (
              <div key={ev.id} className="flex items-center gap-2.5 px-3 py-2 bg-adj-base rounded-md">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-adj-text-muted capitalize">
                    {ev.agent_type} agent · {elapsedLabel(ev.created_at)}
                  </div>
                  <div className="text-xs text-adj-text-primary truncate">{ev.headline}</div>
                </div>
                <button
                  onClick={() => onCancelAgent(String(ev.id))}
                  className="text-[10px] px-1.5 py-0.5 rounded border border-adj-border text-adj-text-muted hover:text-red-400 hover:border-red-400 transition-colors flex-shrink-0"
                >
                  Cancel
                </button>
              </div>
            ))}
          </Popover>
        )}

        {open === 'reviews' && (
          <Popover title="Pending Reviews" width="w-96">
            {pendingReviews.length === 0 && (
              <p className="text-adj-text-muted text-xs px-3 py-2">No pending reviews</p>
            )}
            {pendingReviews.map(r => (
              <div key={r.id} className={`px-3 py-2 bg-adj-base rounded-md border-l-2 ${r.risk_label === 'high' ? 'border-red-500' : r.risk_label === 'medium' ? 'border-amber-500' : 'border-adj-border'}`}>
                <div className={`text-[9px] font-bold uppercase mb-1 ${r.risk_label === 'high' ? 'text-red-400' : 'text-amber-400'}`}>{r.risk_label} risk</div>
                <div className="text-xs font-medium text-adj-text-primary mb-1">{r.title}</div>
                {r.scheduled_for && <div className="text-[10px] text-adj-text-muted mb-1">Scheduled: {new Date(r.scheduled_for).toLocaleString()}</div>}
                <div className="flex gap-2 mt-1 items-center">
                  <button onClick={() => onResolveReview(r.id, 'approved')} className="text-[10px] px-2 py-0.5 rounded bg-green-900 text-green-400 font-semibold hover:bg-green-800 transition-colors">Approve</button>
                  <button onClick={() => onResolveReview(r.id, 'skipped')}  className="text-[10px] px-2 py-0.5 rounded bg-adj-elevated text-adj-text-muted font-semibold hover:bg-adj-border transition-colors">Skip</button>
                  <button onClick={() => { setDetailItem(r); setOpen(null) }} className="text-[10px] text-adj-accent hover:underline ml-auto">View full →</button>
                </div>
              </div>
            ))}
          </Popover>
        )}

        {open === 'objectives' && (
          <Popover title="Objectives" onManage={() => { onOpenSettings('objectives'); setOpen(null) }} manageLabel="Manage objectives →">
            {objectives.map(obj => (
              <div key={obj.id} className="px-3 py-2 bg-adj-base rounded-md">
                <div className="text-xs text-adj-text-primary mb-1">{obj.text}</div>
                {obj.progress_target != null && (
                  <div className="text-[10px] text-adj-text-muted">{obj.progress_current} / {obj.progress_target}</div>
                )}
              </div>
            ))}
          </Popover>
        )}
      </div>

      {/* Review detail modal */}
      {detailItem && (
        <ReviewDetailModal
          item={detailItem}
          onResolve={handleResolve}
          onClose={() => setDetailItem(null)}
        />
      )}
    </>
  )
}

function ReviewDetailModal({ item, onResolve, onClose }: {
  item: ReviewItem
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  onClose: () => void
}) {
  const emailPayload = item.action_type === 'email' && item.payload
    ? (() => { try { return JSON.parse(item.payload!) } catch { return null } })()
    : null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-adj-surface border border-adj-border rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col mx-4"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-adj-border">
          <div className="flex-1 min-w-0 pr-4">
            <div className={`text-[10px] font-bold uppercase mb-1 ${item.risk_label === 'high' ? 'text-red-400' : 'text-amber-400'}`}>
              {item.risk_label} risk{item.action_type ? ` · ${item.action_type}` : ''}
            </div>
            <div className="text-sm font-semibold text-adj-text-primary">{item.title}</div>
          </div>
          <button onClick={onClose} className="text-adj-text-muted hover:text-adj-text-primary text-lg leading-none flex-shrink-0">✕</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {emailPayload ? (
            <>
              <Field label="To" value={emailPayload.to} />
              <Field label="Subject" value={emailPayload.subject} />
              <div>
                <div className="text-[10px] font-semibold text-adj-text-muted uppercase tracking-wide mb-1">Body</div>
                <div className="text-sm text-adj-text-primary whitespace-pre-wrap bg-adj-base rounded-lg px-3 py-3 border border-adj-border leading-relaxed">
                  {emailPayload.body}
                </div>
              </div>
              {emailPayload.thread_id && <Field label="Thread" value={emailPayload.thread_id} />}
            </>
          ) : (
            <div className="text-sm text-adj-text-primary whitespace-pre-wrap leading-relaxed">
              {item.description || <span className="text-adj-text-muted italic">No description provided.</span>}
            </div>
          )}
          {item.scheduled_for && (
            <div className="text-xs text-adj-text-muted">
              Scheduled for: {new Date(item.scheduled_for).toLocaleString()}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-5 py-4 border-t border-adj-border">
          <button
            onClick={() => onResolve(item.id, 'approved')}
            className="px-4 py-1.5 rounded-lg bg-green-900 text-green-400 text-sm font-semibold hover:bg-green-800 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={() => onResolve(item.id, 'skipped')}
            className="px-4 py-1.5 rounded-lg bg-adj-elevated text-adj-text-muted text-sm font-semibold hover:bg-adj-border transition-colors"
          >
            Skip
          </button>
          <button
            onClick={onClose}
            className="ml-auto px-4 py-1.5 rounded-lg border border-adj-border text-adj-text-muted text-sm hover:bg-adj-elevated transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-adj-text-muted uppercase tracking-wide mb-0.5">{label}</div>
      <div className="text-sm text-adj-text-primary">{value}</div>
    </div>
  )
}

function Popover({ title, children, onManage, manageLabel = 'Manage →', width = 'w-72' }: {
  title: string
  children: React.ReactNode
  onManage?: () => void
  manageLabel?: string
  width?: string
}) {
  return (
    <div className={`absolute top-full left-4 mt-1 ${width} bg-adj-surface border border-adj-border rounded-xl shadow-2xl z-50 overflow-hidden`}>
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-adj-border">
        <span className="text-xs font-semibold text-adj-text-primary">{title}</span>
        {onManage && (
          <button onClick={onManage} className="text-[10px] text-adj-accent hover:underline">{manageLabel}</button>
        )}
      </div>
      <div className="p-2 flex flex-col gap-1.5 max-h-[32rem] overflow-y-auto">{children}</div>
    </div>
  )
}
