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

  useEffect(() => {
    api.getOverview(password).then(setProducts)
  }, [password])

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest mb-4">All Products</h2>
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
