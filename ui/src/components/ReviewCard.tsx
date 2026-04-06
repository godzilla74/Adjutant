// ui/src/components/ReviewCard.tsx
import { ReviewItem } from '../types'

interface Props {
  item: ReviewItem
  onResolve: (id: number, action: 'approved' | 'skipped') => void
}

export default function ReviewCard({ item, onResolve }: Props) {
  return (
    <div className="rounded-xl border border-amber-900/50 bg-amber-950/10 p-3 flex flex-col gap-2.5">
      <div className="text-sm font-semibold text-zinc-200 leading-snug">{item.title}</div>
      <div className="text-xs text-zinc-400 leading-relaxed">{item.description}</div>
      <div className="flex items-center gap-1 text-xs text-amber-500">
        <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
        {item.risk_label}
      </div>
      <div className="flex gap-2 mt-0.5">
        <button
          onClick={() => onResolve(item.id, 'approved')}
          className="flex-1 rounded-lg bg-emerald-900/50 border border-emerald-700/60 text-emerald-400 text-xs font-semibold py-1.5 hover:bg-emerald-900/80 transition-colors"
        >
          Approve
        </button>
        <button
          onClick={() => onResolve(item.id, 'approved')}
          className="flex-1 rounded-lg bg-blue-900/30 border border-blue-700/50 text-blue-400 text-xs font-semibold py-1.5 hover:bg-blue-900/50 transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => onResolve(item.id, 'skipped')}
          className="rounded-lg bg-zinc-800/60 border border-zinc-700/40 text-zinc-500 text-xs px-3 py-1.5 hover:bg-zinc-700/60 transition-colors"
        >
          Skip
        </button>
      </div>
    </div>
  )
}
