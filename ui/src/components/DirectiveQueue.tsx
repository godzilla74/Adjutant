// ui/src/components/DirectiveQueue.tsx
import { useEffect, useRef, useState } from 'react'
import { DirectiveItem } from '../types'

interface Props {
  current: DirectiveItem | null
  queued: DirectiveItem[]
  onCancel: (directiveId: string) => void
}

function truncate(s: string, max = 72) {
  return s.length > max ? s.slice(0, max).trimEnd() + '…' : s
}

export default function DirectiveQueue({ current, queued, onCancel }: Props) {
  const prevCurrentRef = useRef<DirectiveItem | null>(null)
  const [recentlyCompleted, setRecentlyCompleted] = useState<DirectiveItem[]>([])

  // Track when a directive finishes — show it briefly as "done"
  useEffect(() => {
    const prev = prevCurrentRef.current
    if (prev && (!current || current.id !== prev.id)) {
      setRecentlyCompleted(c => [...c, prev])
      const timer = setTimeout(() => {
        setRecentlyCompleted(c => c.filter(d => d.id !== prev.id))
      }, 3000)
      return () => clearTimeout(timer)
    }
    prevCurrentRef.current = current
  }, [current])

  const hasContent = current || queued.length > 0 || recentlyCompleted.length > 0
  if (!hasContent) return null

  return (
    <div className="border-t border-zinc-800/60 bg-zinc-900/40 px-4 py-2 flex flex-col gap-1.5">

      {/* Recently completed */}
      {recentlyCompleted.map(d => (
        <div key={d.id} className="flex items-center gap-2">
          <span className="text-emerald-500 text-[10px] flex-shrink-0">✓</span>
          <span className="text-xs text-zinc-600 flex-1 min-w-0 truncate">{truncate(d.content)}</span>
          <span className="text-[10px] text-zinc-700 flex-shrink-0">done</span>
        </div>
      ))}

      {/* Currently running */}
      {current && (
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
          <span className="text-xs text-zinc-300 flex-1 min-w-0 truncate">{truncate(current.content)}</span>
          <span className="text-[10px] text-zinc-500 flex-shrink-0">running</span>
          <button
            onClick={() => onCancel(current.id)}
            title="Cancel"
            className="w-4 h-4 flex items-center justify-center rounded text-zinc-600 hover:text-red-400 hover:bg-zinc-800 transition-colors flex-shrink-0"
          >
            ✕
          </button>
        </div>
      )}

      {/* Queued */}
      {queued.map((d, i) => (
        <div key={d.id} className="flex items-center gap-2">
          <span className="w-4 text-center text-[10px] text-zinc-700 flex-shrink-0">{i + 1}</span>
          <span className="text-xs text-zinc-500 flex-1 min-w-0 truncate">{truncate(d.content)}</span>
          <span className="text-[10px] text-zinc-700 flex-shrink-0">queued</span>
          <button
            onClick={() => onCancel(d.id)}
            title="Cancel"
            className="w-4 h-4 flex items-center justify-center rounded text-zinc-600 hover:text-red-400 hover:bg-zinc-800 transition-colors flex-shrink-0"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
