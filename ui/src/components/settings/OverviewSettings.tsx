import { useEffect, useState } from 'react'
import { Product, ProductConfig } from '../../types'
import { api } from '../../api'

interface Props {
  product: Product | undefined
  password: string
  onRefresh: () => void
  onProductUpdated: (updates: { name?: string; icon_label?: string; color?: string }) => void
}

const COLORS = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444','#8b5cf6','#06b6d4']

export default function OverviewSettings({ product, password, onRefresh, onProductUpdated }: Props) {
  const [config, setConfig] = useState<Partial<ProductConfig>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!product) return
    api.getProductConfig(password, product.id).then(setConfig).catch(() => {})
  }, [product?.id, password])

  if (!product) return <p className="text-adj-text-muted text-sm">No product selected.</p>

  const save = async () => {
    setSaving(true)
    try {
      await api.updateProductConfig(password, product.id, config)
      onProductUpdated({
        name: config.name,
        icon_label: config.icon_label,
        color: config.color,
      })
      onRefresh()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const field = (label: string, key: keyof ProductConfig, placeholder = '') => (
    <div className="mb-4">
      <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">{label}</label>
      <input
        className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors"
        value={(config[key] as string) ?? ''}
        onChange={e => setConfig(c => ({ ...c, [key]: e.target.value }))}
        placeholder={placeholder}
      />
    </div>
  )

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Product Overview</h2>
      <p className="text-xs text-adj-text-muted mb-6">Identity and brand voice for {product.name}</p>

      <div className="flex gap-3 mb-4">
        <div className="flex-1">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Product Name</label>
          <input
            className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors"
            value={config.name ?? product.name}
            onChange={e => setConfig(c => ({ ...c, name: e.target.value }))}
          />
        </div>
        <div className="w-20">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Icon</label>
          <input
            className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-center text-adj-text-primary focus:outline-none focus:border-adj-accent"
            value={config.icon_label ?? product.icon_label}
            onChange={e => setConfig(c => ({ ...c, icon_label: e.target.value }))}
            maxLength={4}
          />
        </div>
      </div>

      <div className="mb-4">
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Color</label>
        <div className="flex gap-2">
          {COLORS.map(c => (
            <button
              key={c}
              onClick={() => setConfig(prev => ({ ...prev, color: c }))}
              className="w-6 h-6 rounded-full transition-transform hover:scale-110"
              style={{
                background: c,
                outline: (config.color ?? product.color) === c ? '2px solid white' : 'none',
                outlineOffset: '2px',
              }}
            />
          ))}
        </div>
      </div>

      {field('Brand Voice', 'brand_voice', 'e.g. Professional but approachable')}
      {field('Tone', 'tone', 'e.g. Confident, friendly')}
      {field('Writing Style', 'writing_style', 'e.g. Conversational, data-driven')}
      {field('Target Audience', 'target_audience', 'e.g. Small business owners')}
      {field('Hashtags', 'hashtags', '#brand #product')}

      <div className="mb-4">
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Brand Notes</label>
        <textarea
          className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors h-24 resize-none"
          value={config.brand_notes ?? ''}
          onChange={e => setConfig(c => ({ ...c, brand_notes: e.target.value }))}
          placeholder="Any additional brand context..."
        />
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
      >
        {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
      </button>
    </div>
  )
}
