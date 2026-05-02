import { useEffect, useState } from 'react'
import { Signal } from '../../types'
import { api } from '../../api'

interface Props {
  productId: string
  password: string
}

const CONTENT_LABELS: Record<string, string> = {
  run_report: 'Report',
  social_draft: 'Draft',
  objective: 'Objective',
  note: 'Note',
  activity_event: 'Activity',
}

function relDate(iso: string) {
  const d = new Date(iso.replace(' ', 'T'))
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function SignalsSettings({ productId, password }: Props) {
  const [signals, setSignals] = useState<Signal[]>([])
  const [includeConsumed, setIncludeConsumed] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [productId, includeConsumed])

  async function load() {
    setLoading(true)
    try {
      setSignals(await api.getSignals(password, productId, '', includeConsumed))
    } finally {
      setLoading(false)
    }
  }

  async function consume(signal: Signal) {
    await api.consumeSignal(password, productId, signal.id)
    load()
  }

  async function unconsume(signal: Signal) {
    await api.unconsumeSignal(password, productId, signal.id)
    load()
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-base font-bold text-adj-text-primary">Signals</h2>
        <label className="flex items-center gap-1.5 text-xs text-adj-text-muted cursor-pointer">
          <input
            type="checkbox"
            aria-label="Show consumed"
            checked={includeConsumed}
            onChange={e => setIncludeConsumed(e.target.checked)}
            className="accent-adj-accent"
          />
          Show consumed
        </label>
      </div>
      <p className="text-xs text-adj-text-muted mb-6">
        Agent-identified opportunities. Consume a signal once you've acted on it.
      </p>

      {loading && <div className="text-xs text-adj-text-faint py-4">Loading…</div>}

      {!loading && signals.length === 0 && (
        <div className="text-xs text-adj-text-faint py-8 text-center">
          {includeConsumed ? 'No signals yet.' : 'No pending signals.'}
        </div>
      )}

      {!loading && signals.length > 0 && (
        <div className="flex flex-col border border-adj-border rounded-lg overflow-hidden divide-y divide-adj-border">
          {signals.map(sig => (
            <div
              key={sig.id}
              className={`px-4 py-3 flex items-start gap-3 ${sig.consumed_at ? 'bg-adj-surface opacity-60' : 'bg-adj-panel'}`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-adj-elevated border border-adj-border text-adj-accent">
                    {sig.tag_name}
                  </span>
                  <span className="text-[10px] text-adj-text-faint">
                    {CONTENT_LABELS[sig.content_type] ?? sig.content_type} #{sig.content_id}
                  </span>
                  <span className="text-[10px] text-adj-text-faint ml-auto">{relDate(sig.created_at)}</span>
                </div>
                {sig.note && (
                  <p className="text-xs text-adj-text-secondary leading-relaxed">{sig.note}</p>
                )}
                {sig.consumed_at && (
                  <p className="text-[10px] text-adj-text-faint mt-1">Consumed {relDate(sig.consumed_at)}</p>
                )}
              </div>
              {sig.consumed_at ? (
                <button
                  onClick={() => unconsume(sig)}
                  className="flex-shrink-0 px-2.5 py-1 rounded text-[10px] font-medium bg-adj-elevated border border-adj-border text-adj-text-muted hover:border-adj-accent hover:text-adj-accent transition-colors"
                >
                  Re-open
                </button>
              ) : (
                <button
                  onClick={() => consume(sig)}
                  className="flex-shrink-0 px-2.5 py-1 rounded text-[10px] font-medium bg-adj-elevated border border-adj-border text-adj-text-muted hover:border-emerald-500 hover:text-emerald-400 transition-colors"
                >
                  Consume
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
