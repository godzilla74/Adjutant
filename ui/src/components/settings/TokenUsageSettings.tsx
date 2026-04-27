import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface UsageSummary {
  period_days: number
  totals: {
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }
  by_call_type: Record<string, {
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }>
  by_day: Array<{
    date: string
    input_tokens: number
    output_tokens: number
    cache_read_tokens: number
    cache_creation_tokens: number
  }>
}

interface Props {
  password: string
}

const PERIODS = [7, 30, 90] as const
type Period = (typeof PERIODS)[number]

const CALL_TYPES = ['agent', 'compaction', 'prescreener'] as const

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function TokenUsageSettings({ password }: Props) {
  const [period, setPeriod] = useState<Period>(30)
  const [data, setData] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const genRef = useRef(0)

  useEffect(() => {
    const gen = ++genRef.current
    setLoading(true)
    setError(null)
    api.getTokenUsage(password, period)
      .then(d => { if (gen === genRef.current) setData(d) })
      .catch(() => { if (gen === genRef.current) setError('Failed to load usage data.') })
      .finally(() => { if (gen === genRef.current) setLoading(false) })
  }, [password, period])

  const totalInput = data?.totals.input_tokens ?? 0
  const totalCacheRead = data?.totals.cache_read_tokens ?? 0
  const cacheHitRate = totalInput + totalCacheRead > 0
    ? (totalCacheRead / (totalInput + totalCacheRead)) * 100
    : 0

  const labelCls = 'block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5'

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Usage</h2>
      <p className="text-xs text-adj-text-muted mb-6">Token consumption by the agent and its helpers</p>

      {/* Period selector */}
      <div className="flex gap-2 mb-6">
        {PERIODS.map(p => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
              period === p
                ? 'bg-adj-accent text-white'
                : 'bg-adj-panel border border-adj-border text-adj-text-muted hover:text-adj-text-secondary'
            }`}
          >
            {p}d
          </button>
        ))}
      </div>

      {loading && <p className="text-adj-text-muted text-sm">Loading…</p>}

      {!loading && error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      {!loading && data && (
        <div className="flex flex-col gap-6">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Input tokens</div>
              <div className="text-lg font-bold text-adj-text-primary">{fmt(data.totals.input_tokens)}</div>
            </div>
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Output tokens</div>
              <div className="text-lg font-bold text-adj-text-primary">{fmt(data.totals.output_tokens)}</div>
            </div>
            <div className="bg-adj-panel border border-adj-border rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-adj-text-muted mb-1">Cache hit rate</div>
              <div className="text-lg font-bold text-adj-text-primary">{cacheHitRate.toFixed(1)}%</div>
            </div>
          </div>

          {/* Breakdown by call type */}
          <div>
            <div className={labelCls}>By call type</div>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-adj-text-muted">
                  <th className="text-left py-1.5 pr-4 font-semibold">Type</th>
                  <th className="text-right py-1.5 px-2 font-semibold">Input</th>
                  <th className="text-right py-1.5 px-2 font-semibold">Output</th>
                  <th className="text-right py-1.5 pl-2 font-semibold">Cached</th>
                </tr>
              </thead>
              <tbody>
                {CALL_TYPES.map(ct => {
                  const row = data.by_call_type[ct] ?? {
                    input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_creation_tokens: 0,
                  }
                  return (
                    <tr key={ct} className="border-t border-adj-border/50">
                      <td className="py-2 pr-4 capitalize text-adj-text-primary">{ct}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.input_tokens)}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.output_tokens)}</td>
                      <td className="py-2 pl-2 text-right tabular-nums text-adj-text-secondary">{fmt(row.cache_read_tokens)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
