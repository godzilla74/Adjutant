// ui/src/components/ReportsTab.tsx
import { useEffect, useState } from 'react'
import MarkdownContent from './MarkdownContent'
import { RunReport, Tag } from '../types'
import { api } from '../api'

interface Props {
  productId: string
  password: string
  initialReportId?: number | null
}

export default function ReportsTab({ productId, password, initialReportId }: Props) {
  const [reports,       setReports]       = useState<RunReport[]>([])
  const [selected,      setSelected]      = useState<RunReport | null>(null)
  const [loading,       setLoading]       = useState(true)
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null)
  const [tagging,       setTagging]       = useState(false)
  const [tags,          setTags]          = useState<Tag[]>([])
  const [tagId,         setTagId]         = useState<number | null>(null)
  const [tagNote,       setTagNote]       = useState('')
  const [tagSaving,     setTagSaving]     = useState(false)

  const headers = { 'X-Agent-Password': password }

  async function fetchReports() {
    try {
      const res = await fetch(`/api/products/${productId}/reports`, { headers })
      if (res.ok) setReports(await res.json())
    } finally {
      setLoading(false)
    }
  }

  async function openReport(id: number) {
    const res = await fetch(`/api/products/${productId}/reports/${id}`, { headers })
    if (res.ok) setSelected(await res.json())
    setTagging(false)
  }

  async function handleDelete(id: number) {
    await fetch(`/api/products/${productId}/reports/${id}`, { method: 'DELETE', headers })
    setConfirmDelete(null)
    if (selected?.id === id) setSelected(null)
    setReports(prev => prev.filter(r => r.id !== id))
  }

  async function startTagging() {
    const loaded = await api.listTags(password)
    setTags(loaded)
    setTagId(loaded[0]?.id ?? null)
    setTagNote('')
    setTagging(true)
  }

  async function submitTag(e: React.FormEvent) {
    e.preventDefault()
    if (!selected || tagId === null) return
    setTagSaving(true)
    try {
      await api.createSignal(password, productId, tagId, 'run_report', selected.id, tagNote)
      setTagging(false)
      setTagNote('')
    } finally {
      setTagSaving(false)
    }
  }

  useEffect(() => { fetchReports() }, [productId])

  useEffect(() => {
    if (initialReportId != null && reports.length > 0) {
      openReport(initialReportId)
    }
  }, [initialReportId, reports])

  if (selected) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelected(null)}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            ← Back
          </button>
          <div className="flex-1 min-w-0">
            <div className="font-medium text-zinc-200 truncate">{selected.workstream_name}</div>
            <div className="text-xs text-zinc-600">
              {new Date(selected.created_at.replace(' ', 'T')).toLocaleString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric',
                hour: 'numeric', minute: '2-digit',
              })}
            </div>
          </div>
          {!tagging && (
            <button
              onClick={startTagging}
              className="text-xs px-2.5 py-1.5 rounded border border-zinc-700 text-zinc-400 hover:border-adj-accent hover:text-adj-accent transition-colors flex-shrink-0"
            >
              🏷 Tag this report
            </button>
          )}
          {confirmDelete === selected.id ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-400">Delete this report?</span>
              <button
                onClick={() => handleDelete(selected.id)}
                className="text-red-400 hover:text-red-300 transition-colors"
              >
                Yes
              </button>
              <button
                onClick={() => setConfirmDelete(null)}
                className="text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(selected.id)}
              className="text-xs text-zinc-600 hover:text-red-400 transition-colors"
            >
              Delete
            </button>
          )}
        </div>

        {tagging && (
          <form onSubmit={submitTag} className="rounded-xl border border-adj-border bg-adj-surface px-4 py-3 space-y-2">
            <p className="text-xs font-semibold text-adj-text-primary mb-2">Tag this report</p>
            <select
              value={tagId ?? ''}
              onChange={e => setTagId(Number(e.target.value))}
              className="w-full bg-adj-panel border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
            >
              {tags.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <textarea
              rows={2}
              value={tagNote}
              onChange={e => setTagNote(e.target.value)}
              placeholder="Handoff note — what's the opportunity? (optional)"
              className="w-full bg-adj-panel border border-adj-border rounded px-2.5 py-1.5 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent resize-none"
            />
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={tagSaving || tagId === null}
                className="px-3 py-1.5 rounded bg-adj-accent text-white text-xs font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {tagSaving ? 'Saving…' : 'Tag it'}
              </button>
              <button
                type="button"
                onClick={() => setTagging(false)}
                className="text-xs text-adj-text-faint hover:text-adj-text-muted"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 px-4 py-4 text-sm text-zinc-300 leading-relaxed">
          {selected.full_output
            ? <MarkdownContent>{selected.full_output}</MarkdownContent>
            : <p className="text-zinc-600 italic">No output recorded.</p>
          }
        </div>
      </div>
    )
  }

  if (loading) {
    return <div className="text-sm text-zinc-600 py-4">Loading reports…</div>
  }

  if (reports.length === 0) {
    return (
      <div className="text-sm text-zinc-600 py-8 text-center">
        No reports yet. Scheduled workstream runs will appear here.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {reports.map(report => (
        <div
          key={report.id}
          className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 px-4 py-3 cursor-pointer hover:border-zinc-700/60 transition-colors"
          onClick={() => openReport(report.id)}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="font-medium text-zinc-200 text-sm">{report.workstream_name}</div>
              <div className="text-xs text-zinc-600 mt-0.5">
                {new Date(report.created_at.replace(' ', 'T')).toLocaleString(undefined, {
                  month: 'short', day: 'numeric', year: 'numeric',
                  hour: 'numeric', minute: '2-digit',
                })}
              </div>
              {report.preview && (
                <div className="text-xs text-zinc-500 mt-1.5 leading-relaxed">{report.preview}</div>
              )}
            </div>
            {confirmDelete === report.id ? (
              <div className="flex items-center gap-2 text-xs flex-shrink-0" onClick={e => e.stopPropagation()}>
                <span className="text-zinc-400">Delete?</span>
                <button onClick={() => handleDelete(report.id)} className="text-red-400 hover:text-red-300 transition-colors">Yes</button>
                <button onClick={() => setConfirmDelete(null)} className="text-zinc-500 hover:text-zinc-300 transition-colors">No</button>
              </div>
            ) : (
              <button
                onClick={e => { e.stopPropagation(); setConfirmDelete(report.id) }}
                className="text-xs text-zinc-700 hover:text-red-400 transition-colors flex-shrink-0"
              >
                Delete
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
