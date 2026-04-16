// ui/src/components/ReviewCard.tsx
import { useEffect, useRef, useState } from 'react'
import { ReviewItem } from '../types'

interface Props {
  item: ReviewItem
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  onCancelAutoApprove?: (id: number) => void
}

const TRUNCATE_AT = 120

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return 'approving…'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function ReviewCard({ item, onResolve, onCancelAutoApprove }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!item.auto_approve_at) { setSecondsLeft(null); return }
    const tick = () => {
      const diff = Math.max(0, Math.floor(
        (new Date(item.auto_approve_at!).getTime() - Date.now()) / 1000
      ))
      setSecondsLeft(diff)
      if (diff === 0 && intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
    tick()
    intervalRef.current = setInterval(tick, 1000)
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current)
    }
  }, [item.auto_approve_at])

  const isWindow = secondsLeft !== null
  const long = item.description && item.description.length > TRUNCATE_AT
  const displayDesc = long && !expanded
    ? item.description.slice(0, TRUNCATE_AT).trimEnd() + '…'
    : item.description

  return (
    <div className={`rounded-xl border p-3 flex flex-col gap-2.5 ${
      isWindow
        ? 'border-yellow-800/50 bg-yellow-950/10'
        : 'border-amber-900/50 bg-amber-950/10'
    }`}>
      <div className="text-sm font-semibold text-zinc-200 leading-snug">{item.title}</div>
      <div className="text-xs text-zinc-400 leading-relaxed">
        {displayDesc}
        {long && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="ml-1 text-zinc-600 hover:text-zinc-400 underline underline-offset-2"
          >
            {expanded ? 'less' : 'more'}
          </button>
        )}
      </div>
      {item.risk_label && (
        <div className="flex items-center gap-1 text-xs text-amber-500">
          <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
          {item.risk_label}
        </div>
      )}
      {isWindow && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-yellow-500 font-mono">
            Auto-approving in {formatCountdown(secondsLeft ?? 0)}
          </span>
          {onCancelAutoApprove && (
            <button
              type="button"
              onClick={() => onCancelAutoApprove(item.id)}
              className="text-xs text-zinc-500 hover:text-red-400 transition-colors underline underline-offset-2"
            >
              Cancel
            </button>
          )}
        </div>
      )}
      <div className="flex gap-2 mt-0.5">
        <button
          type="button"
          onClick={() => onResolve(item.id, 'approved')}
          className="flex-1 rounded-lg bg-emerald-900/50 border border-emerald-700/60 text-emerald-400 text-xs font-semibold py-1.5 hover:bg-emerald-900/80 transition-colors"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onResolve(item.id, 'skipped')}
          className="rounded-lg bg-zinc-800/60 border border-zinc-700/40 text-zinc-500 text-xs px-3 py-1.5 hover:bg-zinc-700/60 transition-colors"
        >
          Skip
        </button>
      </div>
    </div>
  )
}
