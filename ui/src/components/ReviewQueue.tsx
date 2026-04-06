// ui/src/components/ReviewQueue.tsx
import { ReviewItem } from '../types'
import ReviewCard from './ReviewCard'

interface Props {
  items: ReviewItem[]
  onResolve: (id: number, action: 'approved' | 'skipped') => void
}

export default function ReviewQueue({ items, onResolve }: Props) {
  return (
    <aside className="w-72 flex-shrink-0 border-l border-zinc-800/60 flex flex-col bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between flex-shrink-0">
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Needs Review</span>
        {items.length > 0 && (
          <span className="text-xs font-bold bg-amber-900/50 text-amber-400 px-2 py-0.5 rounded-full">
            {items.length}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2.5">
        {items.length === 0 ? (
          <div className="text-xs text-zinc-700 text-center mt-8 leading-relaxed px-2">
            Nothing pending.<br />Hannah will surface items<br />that need your sign-off.
          </div>
        ) : (
          items.map(item => (
            <ReviewCard key={item.id} item={item} onResolve={onResolve} />
          ))
        )}
      </div>
    </aside>
  )
}
