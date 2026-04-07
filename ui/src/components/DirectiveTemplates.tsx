// ui/src/components/DirectiveTemplates.tsx
import { useState } from 'react'

interface Template {
  id: string
  label: string
  content: string
}

const DEFAULTS: Template[] = [
  { id: 'email',  label: 'Check email',   content: 'Check and summarize recent emails' },
  { id: 'status', label: 'Weekly status', content: 'Give me a full status update on all active workstreams and objectives' },
  { id: 'growth', label: 'Growth ideas',  content: 'Research and suggest three growth initiatives we should prioritize this week' },
]

function storageKey(productId: string) {
  return `directive_templates_${productId}`
}

function loadTemplates(productId: string): Template[] {
  try {
    const raw = localStorage.getItem(storageKey(productId))
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return [...DEFAULTS]
}

function saveTemplates(productId: string, templates: Template[]) {
  localStorage.setItem(storageKey(productId), JSON.stringify(templates))
}

interface Props {
  productId: string
  onSelect: (content: string) => void
}

export default function DirectiveTemplates({ productId, onSelect }: Props) {
  const [templates, setTemplates] = useState<Template[]>(() => loadTemplates(productId))
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')

  const update = (next: Template[]) => {
    setTemplates(next)
    saveTemplates(productId, next)
  }

  const addTemplate = () => {
    const label = draft.trim()
    if (!label) { setAdding(false); setDraft(''); return }
    const t: Template = { id: crypto.randomUUID(), label, content: label }
    update([...templates, t])
    setAdding(false)
    setDraft('')
  }

  const removeTemplate = (id: string) => {
    update(templates.filter(t => t.id !== id))
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-5 pt-2 pb-1">
      {templates.map(t => (
        <div key={t.id} className="group flex items-center gap-0.5">
          <button
            onClick={() => onSelect(t.content)}
            className="text-[11px] text-zinc-500 hover:text-zinc-300 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 px-2 py-0.5 rounded-full transition-colors"
          >
            {t.label}
          </button>
          <button
            onClick={() => removeTemplate(t.id)}
            title="Remove template"
            className="text-zinc-700 hover:text-red-500 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity ml-0.5"
          >
            ×
          </button>
        </div>
      ))}

      {adding ? (
        <input
          autoFocus
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') addTemplate()
            if (e.key === 'Escape') { setAdding(false); setDraft('') }
          }}
          placeholder="Template text…"
          className="text-[11px] bg-zinc-900 border border-zinc-700 text-zinc-300 px-2 py-0.5 rounded-full focus:outline-none focus:ring-1 focus:ring-blue-600 w-44"
        />
      ) : (
        <button
          onClick={() => setAdding(true)}
          title="Add template"
          className="text-[11px] text-zinc-700 hover:text-zinc-400 px-1.5 py-0.5 rounded-full border border-dashed border-zinc-800 hover:border-zinc-600 transition-colors"
        >
          + add
        </button>
      )}
    </div>
  )
}
