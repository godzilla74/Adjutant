// ui/src/components/ActivityCard.tsx
import { useState } from 'react'
import MarkdownContent from './MarkdownContent'
import { ActivityEvent, AgentType } from '../types'

const SUMMARY_PREVIEW_LEN = 300

const AGENT_LABEL: Record<AgentType, string> = {
  research: 'Research Agent',
  general:  'General Agent',
  email:    'Email Agent',
  content:  'Content Agent',
  social:   'Social Agent',
}

const AGENT_ICON: Record<AgentType, string> = {
  research: '🔍',
  general:  '🎯',
  email:    '📧',
  content:  '✍️',
  social:   '📣',
}

const AGENT_COLOR: Record<AgentType, string> = {
  research: 'text-violet-400 bg-violet-950/40',
  general:  'text-sky-400 bg-sky-950/40',
  email:    'text-amber-400 bg-amber-950/40',
  content:  'text-emerald-400 bg-emerald-950/40',
  social:   'text-pink-400 bg-pink-950/40',
}

interface Props {
  event: ActivityEvent
  onViewReport?: (reportId: number) => void
}

export default function ActivityCard({ event, onViewReport }: Props) {
  const [expanded, setExpanded] = useState(false)

  const isRunning    = event.status === 'running'
  const isDone       = event.status === 'done'
  const needsReview  = event.status === 'needs_review'

  // Summary truncation logic
  const summary = event.summary ?? ''
  const isLong  = summary.length > SUMMARY_PREVIEW_LEN
  const displaySummary = isLong && !expanded
    ? summary.slice(0, SUMMARY_PREVIEW_LEN).trimEnd() + '…'
    : summary

  return (
    <div className={[
      'rounded-xl border px-4 py-3 flex flex-col gap-3 text-sm',
      needsReview
        ? 'border-amber-900/60 bg-amber-950/10'
        : 'border-zinc-800/60 bg-zinc-900/40',
      isDone ? 'opacity-70' : '',
    ].join(' ')}>

      {/* Top row: icon + headline + agent badge + status */}
      <div className="flex items-start gap-3">
        <span className="text-base mt-0.5 flex-shrink-0">{AGENT_ICON[event.agent_type]}</span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-zinc-200 leading-snug">{event.headline}</div>
          <span className={`inline-flex items-center gap-1 mt-1 text-xs font-medium px-1.5 py-0.5 rounded ${AGENT_COLOR[event.agent_type]}`}>
            <span className="w-1 h-1 rounded-full bg-current" />
            {AGENT_LABEL[event.agent_type]}
          </span>
        </div>
        <div className="flex-shrink-0 flex flex-col items-end gap-0.5">
          <span className="text-xs text-zinc-600">
            {needsReview
              ? <span className="text-amber-500">⚠ review</span>
              : isRunning
                ? <span className="text-amber-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse inline-block" />
                    running
                  </span>
                : 'done'
            }
          </span>
          {event.created_at && (
            <span className="text-[10px] text-zinc-700">
              {new Date(event.created_at.replace(' ', 'T')).toLocaleString(undefined, {
                month: 'short', day: 'numeric',
                hour: 'numeric', minute: '2-digit',
              })}
            </span>
          )}
        </div>
      </div>

      {/* Output preview (needs_review) */}
      {needsReview && event.output_preview && (
        <div className="rounded-lg bg-zinc-950/60 border-l-2 border-zinc-700 px-3 py-2">
          <MarkdownContent className="text-xs text-zinc-400 leading-relaxed">{event.output_preview}</MarkdownContent>
        </div>
      )}

      {/* Summary (done) */}
      {isDone && event.summary && (
        <div className="text-xs text-zinc-500 leading-relaxed">
          <MarkdownContent>{displaySummary}</MarkdownContent>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-zinc-600 hover:text-zinc-400 underline underline-offset-2 transition-colors"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      )}

      {isDone && event.report_id != null && onViewReport && (
        <button
          onClick={() => onViewReport(event.report_id!)}
          className="text-xs text-sky-600 hover:text-sky-400 transition-colors self-start"
        >
          View Report →
        </button>
      )}
    </div>
  )
}
