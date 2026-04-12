// ui/src/components/ObjectivesPanel.tsx
import { Objective } from '../types'

interface Props {
  objectives: Objective[]
  onToggleAutonomous: (objectiveId: number, autonomous: boolean) => void
}

function formatNextRun(next_run_at: string | null): string {
  if (!next_run_at) return ''
  // SQLite stores "YYYY-MM-DD HH:MM:SS" — parse as local time
  const next = new Date(next_run_at.replace(' ', 'T'))
  const diffMs = next.getTime() - Date.now()
  if (diffMs <= 0) return 'soon'
  const diffH = diffMs / (1000 * 60 * 60)
  if (diffH < 1) return `in ${Math.round(diffH * 60)}m`
  return `in ${diffH.toFixed(1).replace('.0', '')}h`
}

function ObjectiveRow({ obj, onToggleAutonomous }: { obj: Objective; onToggleAutonomous: Props['onToggleAutonomous'] }) {
  const progress = obj.progress_target != null
    ? `${obj.progress_current} / ${obj.progress_target}`
    : `${obj.progress_current} so far`

  const isAuto    = (obj.autonomous ?? 0) === 1
  const isBlocked = isAuto && (obj.blocked_by_review_id ?? null) != null
  const isRunning = isAuto && !isBlocked && (obj.next_run_at ?? null) != null

  const robotColor = isBlocked
    ? 'text-amber-400'
    : isRunning
    ? 'text-indigo-400'
    : 'text-zinc-700 hover:text-zinc-500'

  const statusText = isBlocked
    ? 'awaiting review'
    : isRunning
    ? formatNextRun(obj.next_run_at ?? null)
    : ''

  return (
    <div className="px-3.5 py-1.5 flex items-start gap-2">
      <button
        onClick={() => onToggleAutonomous(obj.id, !isAuto)}
        title={isAuto ? 'Disable autonomous mode' : 'Enable autonomous mode'}
        className={`flex-shrink-0 mt-0.5 text-sm transition-colors ${robotColor}`}
      >
        🤖
      </button>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-zinc-500 leading-snug">{obj.text}</div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-zinc-600">{progress}</span>
          {statusText && (
            <span className={`text-[10px] ${isBlocked ? 'text-amber-500' : 'text-indigo-400'}`}>
              {statusText}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ObjectivesPanel({ objectives, onToggleAutonomous }: Props) {
  if (objectives.length === 0) return null
  return (
    <div className="border-t border-zinc-800/60 pt-2">
      <div className="px-3.5 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Objectives
      </div>
      {objectives.map(obj => (
        <ObjectiveRow key={obj.id} obj={obj} onToggleAutonomous={onToggleAutonomous} />
      ))}
    </div>
  )
}
