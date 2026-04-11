// ui/src/components/OverviewPanel.tsx
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ProductOverview } from '../types'

interface Props {
  password: string
  onSelectProduct: (productId: string) => void
}

function StatusDots({ running, warn, paused }: { running: number; warn: number; paused: number }) {
  const dots: { color: string; count: number }[] = [
    { color: 'bg-emerald-500', count: running },
    { color: 'bg-amber-400',   count: warn    },
    { color: 'bg-zinc-700',    count: paused  },
  ]
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {dots.flatMap(({ color, count }) =>
        Array.from({ length: count }, (_, i) => (
          <span key={`${color}-${i}`} className={`w-2 h-2 rounded-full ${color}`} />
        ))
      )}
      {running + warn + paused === 0 && (
        <span className="text-xs text-zinc-700">No workstreams</span>
      )}
    </div>
  )
}

export default function OverviewPanel({ password, onSelectProduct }: Props) {
  const [products, setProducts] = useState<ProductOverview[]>([])
  const [sending, setSending] = useState(false)
  const [sent,    setSent]    = useState(false)

  useEffect(() => {
    api.getOverview(password).then(setProducts)
  }, [password])

  async function sendDigest() {
    if (sending || sent) return
    setSending(true)
    try {
      await api.sendDigest(password)
      setSent(true)
      setTimeout(() => setSent(false), 5000)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest">All Products</h2>
        <button
          onClick={sendDigest}
          disabled={sending || sent}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-all disabled:cursor-default ${
            sent
              ? 'bg-emerald-900/50 border border-emerald-700/50 text-emerald-400'
              : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 disabled:opacity-50'
          }`}
        >
          {sent ? (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Digest sent
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {sending ? 'Sending…' : 'Send Digest'}
            </>
          )}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {products.map(p => (
          <button
            key={p.id}
            onClick={() => onSelectProduct(p.id)}
            className="text-left bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-600 hover:bg-zinc-800/60 transition-all group"
          >
            {/* Product header */}
            <div className="flex items-center gap-3 mb-3">
              <span
                className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{ backgroundColor: `${p.color}22`, color: p.color, border: `2px solid ${p.color}66` }}
              >
                {p.icon_label}
              </span>
              <span className="font-semibold text-zinc-100 text-sm leading-tight group-hover:text-white transition-colors">
                {p.name}
              </span>
            </div>

            {/* Workstream status dots */}
            <StatusDots running={p.running_ws} warn={p.warn_ws} paused={p.paused_ws} />

            {/* Badges row */}
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              {p.running_agents > 0 && (
                <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {p.running_agents} running
                </span>
              )}
              {p.pending_reviews > 0 && (
                <span className="text-[11px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full">
                  {p.pending_reviews} pending
                </span>
              )}
              {p.running_agents === 0 && p.pending_reviews === 0 && (
                <span className="text-[11px] text-zinc-700">Idle</span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
