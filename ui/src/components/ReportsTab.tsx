// ui/src/components/ReportsTab.tsx
import { useEffect, useState } from 'react'
import MarkdownContent from './MarkdownContent'
import { RunReport } from '../types'

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
  }

  async function handleDelete(id: number) {
    await fetch(`/api/products/${productId}/reports/${id}`, { method: 'DELETE', headers })
    setConfirmDelete(null)
    if (selected?.id === id) setSelected(null)
    setReports(prev => prev.filter(r => r.id !== id))
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
