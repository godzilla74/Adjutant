import { useEffect, useRef, useState } from 'react'
import { Product } from '../types'

interface Props {
  products: Product[]
  activeProductId: string
  onSelect: (id: string) => void
  onNewProduct: () => void
}

export default function ProductDropdown({ products, activeProductId, onSelect, onNewProduct }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const active = products.find(p => p.id === activeProductId)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClickOutside)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClickOutside)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-adj-panel border border-adj-border text-adj-text-primary text-sm font-medium hover:border-adj-accent transition-colors"
      >
        {active && (
          <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: active.color }} />
        )}
        <span>{active?.name ?? 'Select product'}</span>
        <span className="text-adj-text-faint text-xs ml-1">▾</span>
      </button>

      {open && (
        <div id="product-listbox" role="listbox" aria-labelledby="products-label" className="absolute top-full left-0 mt-1 w-52 bg-adj-surface border border-adj-border rounded-lg shadow-xl z-50 overflow-hidden">
          <div id="products-label" className="px-3 py-2 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
            Your Products
          </div>
          {products.map(p => (
            <button
              key={p.id}
              role="option"
              aria-selected={p.id === activeProductId}
              data-testid={`product-item-${p.id}`}
              onClick={() => { onSelect(p.id); setOpen(false) }}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left hover:bg-adj-elevated transition-colors"
            >
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: p.color }} />
              <span className={p.id === activeProductId ? 'text-adj-text-primary font-medium' : 'text-adj-text-secondary'}>
                {p.name}
              </span>
              {p.id === activeProductId && (
                <span className="ml-auto text-adj-accent text-xs">✓</span>
              )}
            </button>
          ))}
          <div className="border-t border-adj-border" />
          <button
            onClick={() => { onNewProduct(); setOpen(false) }}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-adj-accent font-semibold hover:bg-adj-elevated transition-colors"
          >
            <span className="w-4 h-4 rounded border border-dashed border-adj-accent flex items-center justify-center text-base leading-none">+</span>
            New Product
          </button>
        </div>
      )}
    </div>
  )
}
