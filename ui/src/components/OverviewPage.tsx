import { useEffect, useState } from 'react'
import { Product, ProductState, ProductOverview } from '../types'
import { api } from '../api'
import WorkstreamChip from './WorkstreamChip'

interface Props {
  products: Product[]
  productStates: Record<string, ProductState>
  password: string
  onOpenProduct: (productId: string) => void
}

export default function OverviewPage({ products, productStates, password, onOpenProduct }: Props) {
  const [overview, setOverview] = useState<ProductOverview[]>([])

  useEffect(() => {
    api.getOverview(password).then(setOverview).catch(() => {})
  }, [password])

  const totalRunning  = overview.reduce((n, p) => n + p.running_ws, 0)
  const totalReviews  = overview.reduce((n, p) => n + p.pending_reviews, 0)
  const totalAgents   = overview.reduce((n, p) => n + p.running_agents, 0)

  return (
    <div className="flex-1 overflow-y-auto bg-adj-base">
      <div className="max-w-4xl mx-auto px-6 py-5">

        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Overview</h1>
          <p className="text-[11px] text-adj-text-faint mt-0.5">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })} · {products.length} product{products.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'Workstreams', value: totalRunning, sub: 'running', color: 'text-green-400' },
            { label: 'Reviews', value: totalReviews, sub: 'pending', color: 'text-amber-400' },
            { label: 'Agents', value: totalAgents, sub: 'active', color: 'text-blue-400' },
          ].map(stat => (
            <div key={stat.label} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3">
              <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-1">{stat.label}</div>
              <div className={`text-xl font-semibold ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-adj-text-faint mt-0.5">{stat.sub}</div>
            </div>
          ))}
        </div>

        {/* Product cards */}
        <div className="space-y-3">
          <div className="text-[10px] text-adj-text-faint uppercase tracking-widest mb-2">Products & Workstreams</div>
          {products.map(product => {
            const state = productStates[product.id]
            const workstreams = state?.workstreams ?? []
            return (
              <div key={product.id} className="bg-adj-panel border border-adj-border rounded-lg px-4 py-3">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[13px] font-medium text-adj-text-primary">{product.name}</span>
                  <button
                    onClick={() => onOpenProduct(product.id)}
                    className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors"
                  >
                    Open workspace →
                  </button>
                </div>
                {workstreams.length === 0 ? (
                  <p className="text-[11px] text-adj-text-faint">No workstreams</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {workstreams.map(ws => (
                      <WorkstreamChip
                        key={ws.id}
                        workstream={ws}
                        password={password}
                        onStatusChange={() => {}}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {products.length === 0 && (
            <p className="text-[12px] text-adj-text-faint">No products yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
