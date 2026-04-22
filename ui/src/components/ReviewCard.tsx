// ui/src/components/ReviewCard.tsx
import { useEffect, useRef, useState } from 'react'
import { ReviewItem } from '../types'
import MarkdownContent from './MarkdownContent'

interface Props {
  item: ReviewItem
  onResolve: (id: number, action: 'approved' | 'skipped') => void
  onCancelAutoApprove?: (id: number) => void
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return 'approving…'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatScheduled(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function ReviewCard({ item, onResolve, onCancelAutoApprove }: Props) {
  const [modalOpen, setModalOpen] = useState(false)
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

  return (
    <>
      <div className={`rounded-xl border p-3 flex flex-col gap-2.5 ${
        isWindow
          ? 'border-yellow-800/50 bg-yellow-950/10'
          : 'border-amber-900/50 bg-amber-950/10'
      }`}>
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-semibold text-zinc-200 leading-snug">{item.title}</div>
          {item.description && (
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="flex-shrink-0 text-[10px] text-zinc-500 hover:text-zinc-300 border border-zinc-700/50 hover:border-zinc-500 rounded px-1.5 py-0.5 transition-colors"
            >
              View
            </button>
          )}
        </div>
        {item.risk_label && (
          <div className="flex items-center gap-1 text-xs text-amber-500">
            <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
            {item.risk_label}
          </div>
        )}
        {item.scheduled_for && (
          <div className="flex items-center gap-1 text-xs text-sky-400">
            <span className="w-1 h-1 rounded-full bg-sky-400 flex-shrink-0" />
            Scheduled: {formatScheduled(item.scheduled_for)}
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

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="relative bg-adj-panel border border-adj-border rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3 border-b border-adj-border flex-shrink-0">
              <div>
                <div className="text-xs text-amber-500 font-medium mb-1">{item.risk_label}</div>
                <div className="text-sm font-semibold text-zinc-100 leading-snug">{item.title}</div>
                {item.scheduled_for && (
                  <div className="text-xs text-sky-400 mt-1">
                    Scheduled: {formatScheduled(item.scheduled_for)}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-zinc-500 hover:text-zinc-300 text-lg leading-none flex-shrink-0 mt-0.5"
              >
                ×
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4 text-sm text-adj-text-secondary leading-relaxed">
              <MarkdownContent>{item.description}</MarkdownContent>
            </div>
            <div className="flex gap-2 px-5 py-4 border-t border-adj-border flex-shrink-0">
              <button
                type="button"
                onClick={() => { onResolve(item.id, 'approved'); setModalOpen(false) }}
                className="flex-1 rounded-lg bg-emerald-900/50 border border-emerald-700/60 text-emerald-400 text-xs font-semibold py-2 hover:bg-emerald-900/80 transition-colors"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => { onResolve(item.id, 'skipped'); setModalOpen(false) }}
                className="rounded-lg bg-zinc-800/60 border border-zinc-700/40 text-zinc-500 text-xs px-4 py-2 hover:bg-zinc-700/60 transition-colors"
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
