// ui/src/components/DirectiveHistoryDrawer.tsx
import { useEffect, useState } from 'react'
import { api } from '../api'
import { DirectiveHistoryItem } from '../types'

interface Props {
  productId: string
  password: string
  onClose: () => void
  onSelect: (content: string) => void
}

const parseTs = (ts: string) => new Date(ts.replace(' ', 'T'))

export default function DirectiveHistoryDrawer({ productId, password, onClose, onSelect }: Props) {
  const [items, setItems] = useState<DirectiveHistoryItem[]>([])

  useEffect(() => {
    api.getDirectiveHistory(password, productId).then(setItems)
  }, [productId, password])

  function use(content: string) {
    onSelect(content)
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-80 bg-zinc-950 border-l border-zinc-800/60 flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">

        {/* Header */}
        <div className="flex items-center justify-between px-4 h-12 border-b border-zinc-800/60 flex-shrink-0">
          <span className="text-sm font-semibold text-zinc-100">Directive History</span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {items.length === 0 && (
            <div className="px-4 py-6 text-xs text-zinc-600 text-center">No directives sent yet.</div>
          )}
          {items.map(item => (
            <div key={item.id} className="border-b border-zinc-800/40 px-4 py-3 hover:bg-zinc-900/40 group">
              <p className="text-sm text-zinc-200 leading-snug line-clamp-3">{item.content}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[11px] text-zinc-600">
                  {parseTs(item.created_at).toLocaleString()}
                </span>
                <button
                  onClick={() => use(item.content)}
                  className="text-xs px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors opacity-0 group-hover:opacity-100"
                >
                  Use
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  )
}
