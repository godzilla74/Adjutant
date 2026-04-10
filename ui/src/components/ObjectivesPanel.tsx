// ui/src/components/ObjectivesPanel.tsx
import { Objective } from '../types'

interface Props {
  objectives: Objective[]
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

export default function ObjectivesPanel({ objectives }: Props) {
  if (objectives.length === 0) return null
  return (
    <div className="border-t border-zinc-800/60 pt-2">
      <div className="px-3.5 pb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
        Objectives
      </div>
      {objectives.map(obj => <ObjectiveRow key={obj.id} obj={obj} />)}
    </div>
  )
}
