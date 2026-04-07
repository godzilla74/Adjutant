// ui/src/components/ProductRail.tsx
import { Product } from '../types'

interface Props {
  products: Product[]
  activeProductId: string   // may be '__overview__' when overview is active
  onSwitch: (productId: string) => void
  onOverview: () => void
}

export default function ProductRail({ products, activeProductId, onSwitch, onOverview }: Props) {
  const overviewActive = activeProductId === '__overview__'

  return (
    <nav className="w-14 flex-shrink-0 border-r border-zinc-800/60 bg-zinc-950 flex flex-col items-center py-3 gap-1.5">

      {/* Overview "All" button */}
      <button
        onClick={onOverview}
        title="All products"
        className={[
          'relative w-9 h-9 rounded-xl flex items-center justify-center',
          'text-xs font-bold transition-all duration-150 cursor-pointer mb-1',
          overviewActive
            ? 'bg-zinc-700 text-zinc-100 border-2 border-zinc-500 scale-105'
            : 'bg-zinc-800 text-zinc-500 border-2 border-transparent opacity-60 hover:opacity-100 hover:scale-105',
        ].join(' ')}
      >
        {overviewActive && (
          <span className="absolute -left-3 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full bg-zinc-400" />
        )}
        ⊞
      </button>

      {/* Divider */}
      <div className="w-6 h-px bg-zinc-800 mb-1" />

      {/* Product buttons */}
      {products.map(product => {
        const isActive = product.id === activeProductId
        return (
          <button
            key={product.id}
            onClick={() => onSwitch(product.id)}
            aria-current={isActive ? 'true' : undefined}
            title={product.name}
            className={[
              'relative w-9 h-9 rounded-xl flex items-center justify-center',
              'text-xs font-bold transition-all duration-150 cursor-pointer',
              isActive
                ? 'scale-105'
                : 'opacity-50 hover:opacity-80 hover:scale-105',
            ].join(' ')}
            style={{
              backgroundColor: isActive ? `${product.color}22` : '#27272a',
              color: product.color,
              border: isActive ? `2px solid ${product.color}` : '2px solid transparent',
            }}
          >
            {isActive && (
              <span
                className="absolute -left-3 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full"
                style={{ backgroundColor: product.color }}
              />
            )}
            {product.icon_label}
          </button>
        )
      })}
    </nav>
  )
}
