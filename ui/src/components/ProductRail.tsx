// ui/src/components/ProductRail.tsx
import { Product } from '../types'

interface Props {
  products: Product[]
  activeProductId: string
  onSwitch: (productId: string) => void
}

export default function ProductRail({ products, activeProductId, onSwitch }: Props) {
  return (
    <nav className="w-14 flex-shrink-0 border-r border-zinc-800/60 bg-zinc-950 flex flex-col items-center py-3 gap-1.5">
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
