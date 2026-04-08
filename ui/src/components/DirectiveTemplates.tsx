// ui/src/components/DirectiveTemplates.tsx
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

interface Template {
  id: number
  label: string
  content: string
}

// localStorage used only to avoid a blank flash on load — server is the source of truth
function cacheKey(productId: string) { return `dt_cache_${productId}` }
function readCache(productId: string): Template[] {
  try { return JSON.parse(localStorage.getItem(cacheKey(productId)) ?? '[]') } catch { return [] }
}
function writeCache(productId: string, templates: Template[]) {
  localStorage.setItem(cacheKey(productId), JSON.stringify(templates))
}

interface FormState {
  mode: 'add' | 'edit'
  id?: number
  label: string
  content: string
}

interface Props {
  productId: string
  password: string
  onSelect: (content: string) => void
}

export default function DirectiveTemplates({ productId, password, onSelect }: Props) {
  const [templates, setTemplates] = useState<Template[]>(() => readCache(productId))
  const [form, setForm]           = useState<FormState | null>(null)
  const [saving, setSaving]       = useState(false)
  const labelRef = useRef<HTMLInputElement>(null)

  // Load from server on mount / product switch
  useEffect(() => {
    api.getTemplates(password, productId).then(rows => {
      setTemplates(rows)
      writeCache(productId, rows)
    }).catch(() => { /* offline — keep cache */ })
  }, [productId, password])

  const openAdd = () => {
    setForm({ mode: 'add', label: '', content: '' })
    setTimeout(() => labelRef.current?.focus(), 0)
  }

  const openEdit = (t: Template) => {
    setForm({ mode: 'edit', id: t.id, label: t.label, content: t.content })
    setTimeout(() => labelRef.current?.focus(), 0)
  }

  const saveForm = async () => {
    if (!form || saving) return
    const label   = form.label.trim()
    const content = form.content.trim()
    if (!label || !content) return

    setSaving(true)
    try {
      if (form.mode === 'add') {
        const created = await api.createTemplate(password, productId, label, content)
        const next = [...templates, created]
        setTemplates(next)
        writeCache(productId, next)
      } else if (form.id !== undefined) {
        await api.updateTemplate(password, form.id, label, content)
        const next = templates.map(t => t.id === form.id ? { ...t, label, content } : t)
        setTemplates(next)
        writeCache(productId, next)
      }
      setForm(null)
    } catch (err) {
      console.error('Failed to save template:', err)
    } finally {
      setSaving(false)
    }
  }

  const cancelForm = () => setForm(null)

  const removeTemplate = async (id: number) => {
    if (form?.id === id) setForm(null)
    const next = templates.filter(t => t.id !== id)
    setTemplates(next)
    writeCache(productId, next)
    try {
      await api.deleteTemplate(password, id)
    } catch (err) {
      console.error('Failed to delete template:', err)
    }
  }

  return (
    <div className="flex flex-col px-5 pt-2 pb-1 gap-2">

      {/* Chips row */}
      <div className="flex flex-wrap items-center gap-1.5">
        {templates.map(t => (
          <div key={t.id} className="flex items-center gap-0.5">
            <button
              onClick={() => onSelect(t.content)}
              title={t.content}
              className="text-[11px] text-zinc-500 hover:text-zinc-300 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 px-2 py-0.5 rounded-full transition-colors"
            >
              {t.label}
            </button>
            <button
              onClick={() => openEdit(t)}
              title="Edit template"
              className="text-zinc-700 hover:text-zinc-400 text-[10px] px-0.5 transition-colors"
            >
              ✎
            </button>
            <button
              onClick={() => removeTemplate(t.id)}
              title="Remove template"
              className="text-zinc-700 hover:text-red-500 text-[10px] px-0.5 transition-colors"
            >
              ×
            </button>
          </div>
        ))}

        {!form && (
          <button
            onClick={openAdd}
            title="Add template"
            className="text-[11px] text-zinc-700 hover:text-zinc-400 px-1.5 py-0.5 rounded-full border border-dashed border-zinc-800 hover:border-zinc-600 transition-colors"
          >
            + add
          </button>
        )}
      </div>

      {/* Add / Edit form */}
      {form && (
        <div className="flex items-start gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2">
          <div className="flex flex-col gap-1.5 flex-1 min-w-0">
            <input
              ref={labelRef}
              value={form.label}
              onChange={e => setForm(f => f ? { ...f, label: e.target.value } : f)}
              onKeyDown={e => { if (e.key === 'Escape') cancelForm() }}
              placeholder="Chip name (short)…"
              className="text-[11px] bg-zinc-950 border border-zinc-700 text-zinc-300 rounded px-2 py-1 w-36 focus:outline-none focus:ring-1 focus:ring-blue-600 placeholder-zinc-700"
            />
            <input
              value={form.content}
              onChange={e => setForm(f => f ? { ...f, content: e.target.value } : f)}
              onKeyDown={e => {
                if (e.key === 'Enter') saveForm()
                if (e.key === 'Escape') cancelForm()
              }}
              placeholder="Full directive text…"
              className="text-[11px] bg-zinc-950 border border-zinc-700 text-zinc-300 rounded px-2 py-1 w-full focus:outline-none focus:ring-1 focus:ring-blue-600 placeholder-zinc-700"
            />
          </div>
          <div className="flex gap-1 flex-shrink-0 pt-0.5">
            <button
              onClick={saveForm}
              disabled={saving || !form.label.trim() || !form.content.trim()}
              className="text-[11px] bg-blue-600/20 border border-blue-600/40 text-blue-400 px-2 py-1 rounded hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? '…' : form.mode === 'add' ? 'Add' : 'Save'}
            </button>
            <button
              onClick={cancelForm}
              className="text-[11px] text-zinc-600 hover:text-zinc-400 px-2 py-1 rounded hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
