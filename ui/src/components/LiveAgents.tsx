// ui/src/components/LiveAgents.tsx
import { useEffect, useState } from 'react'
import { ActivityEvent, DirectiveItem } from '../types'

const AGENT_COLOR: Record<string, string> = {
  research: 'text-violet-400 border-violet-800/50 bg-violet-950/30',
  general:  'text-sky-400   border-sky-800/50    bg-sky-950/30',
  email:    'text-amber-400 border-amber-800/50  bg-amber-950/30',
  content:  'text-emerald-400 border-emerald-800/50 bg-emerald-950/30',
  social:   'text-pink-400  border-pink-800/50   bg-pink-950/30',
}

const AGENT_ICON: Record<string, string> = {
  research: '🔍',
  general:  '🎯',
  email:    '📧',
  content:  '✍️',
  social:   '📣',
}

function elapsed(createdAt: string): string {
  const ms = Date.now() - new Date(createdAt.replace(' ', 'T')).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

function truncate(s: string, max = 60) {
  return s.length > max ? s.slice(0, max).trimEnd() + '…' : s
}

interface Props {
  events: ActivityEvent[]
  currentDirective: DirectiveItem | null
  onCancelDirective: (id: string) => void
}

export default function LiveAgents({ events, currentDirective, onCancelDirective }: Props) {
  const running = events.filter(e => e.status === 'running')
  const [, tick] = useState(0)

  // Show bar if there's an active directive OR agents are still running.
  // This prevents the bar from vanishing when Stop is clicked while agents are mid-flight.
  const isVisible = !!currentDirective || running.length > 0

  useEffect(() => {
    if (!isVisible) return
    const id = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [isVisible])

  if (!isVisible) return null

  return (
    <div className="flex-shrink-0 border-b border-zinc-800/60 bg-zinc-950 px-4 py-2.5 flex flex-col gap-2">

      {/* Header row */}
      <div className="flex items-center gap-2">
        {currentDirective ? (
          <>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
            <span className="text-xs text-zinc-400 flex-1 min-w-0 truncate">
              {truncate(currentDirective.content)}
            </span>
            <button
              onClick={() => onCancelDirective(currentDirective.id)}
              className="flex-shrink-0 flex items-center gap-1 text-[10px] font-medium text-zinc-600 hover:text-red-400 hover:bg-zinc-800 px-2 py-0.5 rounded transition-colors"
              title="Cancel this directive"
            >
              <span>■</span> Stop
            </button>
          </>
        ) : (
          // Directive was stopped but agents are still finishing
          <>
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse flex-shrink-0" />
            <span className="text-xs text-zinc-500 flex-1 min-w-0">
              Agents finishing up…
            </span>
          </>
        )}
      </div>

      {/* Running agents */}
      {running.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {running.map(ev => (
            <div
              key={ev.id}
              className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 text-xs ${AGENT_COLOR[ev.agent_type] ?? AGENT_COLOR.general}`}
            >
              <span className="flex-shrink-0 mt-0.5">{AGENT_ICON[ev.agent_type] ?? '🎯'}</span>
              <div className="flex-1 min-w-0">
                <div className="font-medium leading-snug truncate">{ev.headline}</div>
              </div>
              <span className="flex-shrink-0 font-mono text-zinc-600 text-[10px] mt-0.5">
                {elapsed(ev.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}

      {running.length === 0 && currentDirective && (
        <div className="text-[10px] text-zinc-700 flex items-center gap-1.5">
          <span className="w-1 h-1 rounded-full bg-zinc-700 animate-pulse" />
          Hannah is thinking…
        </div>
      )}
    </div>
  )
}
