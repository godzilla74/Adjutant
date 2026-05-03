import { Product, ProductState } from '../types'

interface Props {
  products: Product[]
  productStates: Record<string, ProductState>
  onSelect: (productId: string) => void
  onNewProduct: () => void
}

export default function ProductPicker({ products, productStates, onSelect, onNewProduct }: Props) {
  return (
    <div className="flex-1 overflow-y-auto bg-adj-base">
      <div className="max-w-2xl mx-auto px-6 py-5">

        <div className="flex items-center justify-between mb-5">
          <h1 className="text-[15px] font-semibold text-adj-text-primary tracking-tight">Products</h1>
          <button
            onClick={onNewProduct}
            className="text-[11px] text-adj-accent border border-adj-accent/40 bg-adj-accent/10 rounded-md px-3 py-1.5 hover:bg-adj-accent/20 transition-colors"
          >
            + New product
          </button>
        </div>

        <div className="space-y-2">
          {products.map(product => {
            const state = productStates[product.id]
            const wsCount = state?.workstreams.length ?? 0
            const runningCount = state?.workstreams.filter(w => w.status === 'running').length ?? 0
            return (
              <button
                key={product.id}
                type="button"
                onClick={() => onSelect(product.id)}
                className="w-full text-left bg-adj-panel border border-adj-border rounded-lg px-4 py-3 hover:border-adj-accent/40 hover:bg-adj-elevated transition-colors flex items-center gap-4"
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: product.color }}
                >
                  {product.icon_label}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-adj-text-primary">{product.name}</div>
                  <div className="text-[11px] text-adj-text-faint mt-0.5">
                    {wsCount === 0 ? 'No workstreams' : `${wsCount} workstream${wsCount !== 1 ? 's' : ''}`}
                    {runningCount > 0 && <span className="ml-2 text-green-400">· {runningCount} running</span>}
                  </div>
                </div>
                <span className="text-adj-text-faint text-sm flex-shrink-0">›</span>
              </button>
            )
          })}
          {products.length === 0 && (
            <p className="text-[12px] text-adj-text-faint text-center py-8">No products yet. Create one to get started.</p>
          )}
        </div>
      </div>
    </div>
  )
}
