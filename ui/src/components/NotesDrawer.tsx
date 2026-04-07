// ui/src/components/NotesDrawer.tsx
import { useEffect, useState } from 'react'
import { api } from '../api'

interface Props {
  productId: string
  password: string
  onClose: () => void
}

export default function NotesDrawer({ productId, password, onClose }: Props) {
  const [content,   setContent]   = useState('')
  const [updatedAt, setUpdatedAt] = useState('')
  const [saving,    setSaving]    = useState(false)

  useEffect(() => {
    api.getNotes(password, productId).then(n => {
      setContent(n.content)
      setUpdatedAt(n.updated_at)
    })
  }, [productId, password])

  async function save() {
    setSaving(true)
    try {
      const result = await api.updateNotes(password, productId, content)
      setUpdatedAt(result.updated_at)
    } finally {
      setSaving(false)
    }
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
          <span className="text-sm font-semibold text-zinc-100">Notes</span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col p-4 gap-3 overflow-hidden">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Scratchpad for this product — context, reminders, ideas…"
            className="flex-1 w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-600 resize-none leading-relaxed"
          />
          <div className="flex items-center justify-between">
            {updatedAt ? (
              <span className="text-[11px] text-zinc-600">
                Saved {new Date(updatedAt.replace(' ', 'T')).toLocaleString()}
              </span>
            ) : (
              <span />
            )}
            <button
              onClick={save}
              disabled={saving}
              className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 font-medium transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
