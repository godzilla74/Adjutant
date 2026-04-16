// ui/src/components/ReviewQueue.tsx
import { useEffect, useRef, useState } from 'react'
import { DirectiveItem, ReviewItem } from '../types'
import ReviewCard from './ReviewCard'

interface Props {
  items: ReviewItem[]
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  queued: DirectiveItem[]
  onCancelQueued: (id: string) => void
  agentName: string
  onCancelAutoApprove: (id: number) => void
}

function truncate(s: string, max = 52) {
  return s.length > max ? s.slice(0, max).trimEnd() + '…' : s
}

function QueuedStack({ queued, onCancel }: { queued: DirectiveItem[]; onCancel: (id: string) => void }) {
  const [leaving, setLeaving] = useState<DirectiveItem | null>(null)
  const prev0Ref = useRef<DirectiveItem | null>(null)

  // Detect when the front of the queue changes — animate the departing card
  useEffect(() => {
    const prev = prev0Ref.current
    const curr = queued[0] ?? null
    if (prev && (!curr || curr.id !== prev.id)) {
      setLeaving(prev)
      const t = setTimeout(() => setLeaving(null), 380)
      return () => clearTimeout(t)
    }
    prev0Ref.current = curr
  }, [queued])

  const visible = queued.slice(0, 4) // show max 4 cards deep

  if (queued.length === 0 && !leaving) return null

  return (
    <div className="px-3 pb-4 flex-shrink-0">
      <div className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-3 px-1">
        Queued
      </div>

      {/* Stack container — relative so cards can overlap */}
      <div
        className="relative"
        style={{ height: `${52 + Math.min(visible.length - 1, 3) * 10}px` }}
      >
        {/* Ghost card flying out */}
        {leaving && (
          <div
            key={`leaving-${leaving.id}`}
            className="absolute inset-x-0 top-0 rounded-lg border border-blue-700/30 bg-zinc-900 px-3 py-2.5 text-xs text-zinc-400"
            style={{
              animation: 'pop-up 380ms ease-out forwards',
              zIndex: 20,
            }}
          >
            {truncate(leaving.content)}
          </div>
        )}

        {/* Stacked cards — rendered back-to-front so index 0 is on top */}
        {[...visible].reverse().map((d, revIdx) => {
          const idx = visible.length - 1 - revIdx // actual position in queue
          const scale = 1 - idx * 0.04
          const ty = idx * 10
          const opacity = Math.max(0.35, 1 - idx * 0.2)
          const isTop = idx === 0

          return (
            <div
              key={d.id}
              className={`absolute inset-x-0 top-0 rounded-lg border bg-zinc-900 px-3 py-2.5 transition-all duration-300 ${
                isTop
                  ? 'border-zinc-700/60 shadow-sm'
                  : 'border-zinc-800/50'
              }`}
              style={{
                transform: `translateY(${ty}px) scale(${scale})`,
                opacity,
                zIndex: visible.length - idx,
                transformOrigin: 'top center',
              }}
            >
              <div className="flex items-start gap-1.5">
                <span className="text-[10px] text-zinc-700 flex-shrink-0 pt-0.5 font-mono">
                  {idx + 1}
                </span>
                <span className="text-xs text-zinc-400 flex-1 leading-snug">{truncate(d.content)}</span>
                {isTop && (
                  <button
                    onClick={() => onCancel(d.id)}
                    title="Cancel"
                    className="flex-shrink-0 text-zinc-700 hover:text-red-400 transition-colors leading-none"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {queued.length > 4 && (
        <div className="text-center text-[10px] text-zinc-700 mt-2">
          +{queued.length - 4} more
        </div>
      )}
    </div>
  )
}

export default function ReviewQueue({ items, onResolve, queued, onCancelQueued, agentName, onCancelAutoApprove }: Props) {
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
            Nothing pending.<br />{agentName} will surface items<br />that need your sign-off.
          </div>
        ) : (
          items.map(item => (
            <ReviewCard
              key={item.id}
              item={item}
              onResolve={onResolve}
              onCancelAutoApprove={onCancelAutoApprove}
            />
          ))
        )}
      </div>

      {/* Queued directives stack — pinned to bottom */}
      {(queued.length > 0) && (
        <>
          <div className="border-t border-zinc-800/60" />
          <QueuedStack queued={queued} onCancel={onCancelQueued} />
        </>
      )}
    </aside>
  )
}
