// ui/src/components/WorkstreamsPanel.tsx
import { Workstream, Objective } from '../types'

interface Props {
  workstreams: Workstream[]
  objectives:  Objective[]
  onRunNow?:   (wsId: number) => void
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
  manual:   '', // manual = no auto-schedule label; show nothing
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

function ObjectiveRow({ obj }: { obj: Objective }) {
  const progress = obj.progress_target != null
    ? `${obj.progress_current} / ${obj.progress_target}`
    : `${obj.progress_current} so far`
  return (
    <div className="px-3.5 py-1.5">
      <div className="text-xs text-zinc-500 leading-snug">{obj.text}</div>
      <div className="text-xs text-zinc-600 mt-0.5">{progress}</div>
    </div>
  )
}

export default function WorkstreamsPanel({ workstreams, objectives, onRunNow }: Props) {
  return (
    <aside className="w-48 flex-shrink-0 border-r border-zinc-800/60 bg-zinc-950 flex flex-col">
      <div className="px-3.5 pt-3 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Workstreams
      </div>

      {workstreams.map(ws => {
        const hasMission = !!(ws.mission?.trim())
        const scheduleLabel = ws.schedule ? SCHEDULE_LABEL[ws.schedule] : undefined
        return (
          <div
            key={ws.id}
            className="flex items-center gap-2 px-3.5 py-2 hover:bg-zinc-900/60 cursor-default group"
          >
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
            {hasMission && onRunNow && (
              <button
                onClick={() => onRunNow(ws.id)}
                title="Run now"
                className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-zinc-500 hover:text-emerald-400 transition-all flex-shrink-0"
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
              </button>
            )}
          </div>
        )
      })}

      {objectives.length > 0 && (
        <>
          <div className="mx-3.5 my-2 h-px bg-zinc-800/60" />
          <div className="px-3.5 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
            Objectives
          </div>
          {objectives.map(obj => <ObjectiveRow key={obj.id} obj={obj} />)}
        </>
      )}
    </aside>
  )
}
