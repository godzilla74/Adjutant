// ui/src/components/WorkstreamsPanel.tsx
import { Workstream, Objective } from '../types'

interface Props {
  workstreams: Workstream[]
  objectives: Objective[]
}

const STATUS_DOT: Record<string, string> = {
  running: 'bg-emerald-400 animate-pulse',
  warn:    'bg-amber-400',
  paused:  'bg-zinc-600',
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

export default function WorkstreamsPanel({ workstreams, objectives }: Props) {
  return (
    <aside className="w-48 flex-shrink-0 border-r border-zinc-800/60 bg-zinc-950 flex flex-col">
      <div className="px-3.5 pt-3 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Workstreams
      </div>

      {workstreams.map(ws => (
        <div
          key={ws.id}
          className="flex items-center gap-2 px-3.5 py-2 hover:bg-zinc-900/60 cursor-default"
        >
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[ws.status] ?? 'bg-zinc-600'}`} />
          <span className="text-sm text-zinc-300 flex-1">{ws.name}</span>
        </div>
      ))}

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
