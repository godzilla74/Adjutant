import { useEffect, useRef, useState } from 'react'
import { ActivityEvent, Objective, ReviewItem, Workstream } from '../types'

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
  const ref = useRef<HTMLDivElement>(null)

  const pendingReviews = reviewItems.filter(r => r.status === 'pending')
  const runningAgents  = events.filter(e => e.status === 'running')
  const warnWs         = workstreams.filter(w => w.status === 'warn').length

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (key: PopoverKey) => setOpen(prev => prev === key ? null : key)

  return (
    <div ref={ref} className="relative flex items-center gap-1 px-4 h-8 bg-adj-panel border-b border-adj-border flex-shrink-0 text-xs">

      {/* Workstreams pill */}
      <button
        data-testid="pill-workstreams"
        onClick={() => toggle('workstreams')}
        className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border transition-colors ${open === 'workstreams' ? 'border-adj-accent bg-adj-elevated' : 'border-transparent hover:bg-adj-elevated'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${warnWs > 0 ? 'bg-amber-400' : 'bg-green-400'}`} />
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
        <Popover title="Workstreams" onManage={() => { onOpenSettings('workstreams'); setOpen(null) }}>
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
                <div className="text-[10px] text-adj-text-muted capitalize">{ev.agent_type} agent</div>
                <div className="text-xs text-adj-text-primary truncate">{ev.headline}</div>
              </div>
            </div>
          ))}
        </Popover>
      )}

      {open === 'reviews' && (
        <Popover title="Pending Reviews">
          {pendingReviews.length === 0 && (
            <p className="text-adj-text-muted text-xs px-3 py-2">No pending reviews</p>
          )}
          {pendingReviews.map(r => (
            <div key={r.id} className={`px-3 py-2 bg-adj-base rounded-md border-l-2 ${r.risk_label === 'high' ? 'border-red-500' : r.risk_label === 'medium' ? 'border-amber-500' : 'border-adj-border'}`}>
              <div className={`text-[9px] font-bold uppercase mb-1 ${r.risk_label === 'high' ? 'text-red-400' : 'text-amber-400'}`}>{r.risk_label} risk</div>
              <div className="text-xs text-adj-text-primary mb-2">{r.title}</div>
              <div className="flex gap-2">
                <button onClick={() => onResolveReview(r.id, 'approved')} className="text-[10px] px-2 py-0.5 rounded bg-green-900 text-green-400 font-semibold hover:bg-green-800 transition-colors">Approve</button>
                <button onClick={() => onResolveReview(r.id, 'skipped')}  className="text-[10px] px-2 py-0.5 rounded bg-adj-elevated text-adj-text-muted font-semibold hover:bg-adj-border transition-colors">Skip</button>
              </div>
            </div>
          ))}
        </Popover>
      )}

      {open === 'objectives' && (
        <Popover title="Objectives" onManage={() => { onOpenSettings('objectives'); setOpen(null) }}>
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
  )
}

function Popover({ title, children, onManage }: { title: string; children: React.ReactNode; onManage?: () => void }) {
  return (
    <div className="absolute top-full left-4 mt-1 w-72 bg-adj-surface border border-adj-border rounded-xl shadow-2xl z-50 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-adj-border">
        <span className="text-xs font-semibold text-adj-text-primary">{title}</span>
        {onManage && (
          <button onClick={onManage} className="text-[10px] text-adj-accent hover:underline">Manage →</button>
        )}
      </div>
      <div className="p-2 flex flex-col gap-1.5 max-h-72 overflow-y-auto">{children}</div>
    </div>
  )
}
