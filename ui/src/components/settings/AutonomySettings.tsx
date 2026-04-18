import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  productId: string
  password: string
}

const ACTION_TYPES: [string, string][] = [
  ['social_post',  'Social posts'],
  ['email',        'Emails'],
  ['agent_review', 'Agent reviews'],
]

export default function AutonomySettings({ productId, password }: Props) {
  const [masterTier, setMasterTier] = useState<string | null>(null)
  const [masterWindow, setMasterWindow] = useState<number>(10)
  const [actionTiers, setActionTiers] = useState<Record<string, { tier: string; window_minutes: number }>>({
    social_post:  { tier: 'approve', window_minutes: 10 },
    email:        { tier: 'approve', window_minutes: 10 },
    agent_review: { tier: 'approve', window_minutes: 10 },
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getAutonomySettings(password, productId).then(settings => {
      setMasterTier(settings.master_tier)
      setMasterWindow(settings.master_window_minutes ?? 10)
      const tiers: Record<string, { tier: string; window_minutes: number }> = {
        social_post:  { tier: 'approve', window_minutes: 10 },
        email:        { tier: 'approve', window_minutes: 10 },
        agent_review: { tier: 'approve', window_minutes: 10 },
      }
      for (const o of settings.action_overrides) {
        tiers[o.action_type] = { tier: o.tier, window_minutes: o.window_minutes ?? 10 }
      }
      setActionTiers(tiers)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [productId, password])

  const save = async () => {
    setSaving(true)
    try {
      await api.updateAutonomySettings(password, productId, {
        master_tier: masterTier,
        master_window_minutes: masterTier === 'window' ? masterWindow : null,
        action_overrides: Object.entries(actionTiers).map(([action_type, cfg]) => ({
          action_type,
          tier: cfg.tier,
          window_minutes: cfg.tier === 'window' ? cfg.window_minutes : null,
        })),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="max-w-4xl">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Autonomy</h2>
      <p className="text-xs text-adj-text-muted mb-6">Control how much the agent acts without your approval</p>

      {/* Master override */}
      <div className="mb-6">
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Master override</label>
        <div className="flex items-center gap-2">
          <select
            value={masterTier ?? ''}
            onChange={e => setMasterTier(e.target.value || null)}
            className="flex-1 bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
          >
            <option value="">Per action type</option>
            <option value="approve">Approve (always block)</option>
            <option value="window">Window (auto after delay)</option>
            <option value="auto">Auto (never block)</option>
          </select>
          {masterTier === 'window' && (
            <input
              type="number"
              min={1}
              value={masterWindow}
              onChange={e => setMasterWindow(Number(e.target.value))}
              className="w-20 bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
              placeholder="min"
            />
          )}
        </div>
        {masterTier && (
          <button
            onClick={() => setMasterTier(null)}
            className="mt-1.5 text-xs text-adj-text-faint hover:text-adj-text-muted underline underline-offset-2"
          >
            Clear override
          </button>
        )}
      </div>

      {/* Per-action table */}
      <div className={masterTier ? 'opacity-50 pointer-events-none' : ''}>
        <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">Per action type</label>
        <div className="flex flex-col gap-2">
          {ACTION_TYPES.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 bg-adj-panel border border-adj-border rounded-md px-3 py-2">
              <span className="text-xs text-adj-text-secondary w-28 flex-shrink-0">{label}</span>
              <select
                value={actionTiers[key]?.tier ?? 'approve'}
                onChange={e => setActionTiers(prev => ({
                  ...prev,
                  [key]: { ...prev[key], tier: e.target.value },
                }))}
                className="flex-1 bg-adj-elevated border border-adj-border rounded px-2 py-1.5 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent"
              >
                <option value="approve">Approve</option>
                <option value="window">Window</option>
                <option value="auto">Auto</option>
              </select>
              {actionTiers[key]?.tier === 'window' && (
                <input
                  type="number"
                  min={1}
                  value={actionTiers[key]?.window_minutes ?? 10}
                  onChange={e => setActionTiers(prev => ({
                    ...prev,
                    [key]: { ...prev[key], window_minutes: Number(e.target.value) },
                  }))}
                  className="w-16 bg-adj-elevated border border-adj-border rounded px-2 py-1.5 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent"
                  placeholder="min"
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
        >
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
