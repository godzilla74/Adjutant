import { AppEvent, AgentType } from '../types'

const AGENT_LABELS: Record<AgentType, string> = {
  research: 'Research Agent',
  general: 'General Agent',
  email: 'Email Agent',
}

const AGENT_COLORS: Record<AgentType, string> = {
  research: 'text-violet-400',
  general: 'text-sky-400',
  email: 'text-amber-400',
}

interface Props { event: AppEvent }

export default function EventItem({ event }: Props) {
  if (event.type === 'user_message') {
    return (
      <div className="flex flex-col items-end gap-1">
        <span className="text-xs text-zinc-500">You</span>
        <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-sky-600 px-4 py-2.5 text-sm text-white">
          {event.content}
        </div>
      </div>
    )
  }

  if (event.type === 'hannah_message') {
    return (
      <div className="flex flex-col items-start gap-1">
        <span className="text-xs text-zinc-500">Hannah</span>
        <div className="max-w-2xl rounded-2xl rounded-tl-sm bg-zinc-800 px-4 py-2.5 text-sm text-zinc-100 whitespace-pre-wrap">
          {event.content}
        </div>
      </div>
    )
  }

  if (event.type === 'task') {
    const label = AGENT_LABELS[event.agentType]
    const color = AGENT_COLORS[event.agentType]
    return (
      <div className="flex items-start gap-3 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm">
        <div className="mt-0.5 shrink-0">
          {event.status === 'running' ? (
            <span className="block w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
          ) : (
            <span className="block w-2.5 h-2.5 rounded-full bg-emerald-400" />
          )}
        </div>
        <div className="flex flex-col gap-1 min-w-0">
          <span className={`text-xs font-medium ${color}`}>{label}</span>
          <span className="text-zinc-300 truncate">{event.description}</span>
          {event.status === 'done' && event.summary && (
            <span className="text-xs text-zinc-500 mt-0.5">{event.summary}</span>
          )}
        </div>
        <span className="ml-auto shrink-0 text-xs text-zinc-600">
          {event.status === 'running' ? 'running…' : 'done'}
        </span>
      </div>
    )
  }

  return null
}
