import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { OrchestratorConfig } from '../../types'
import ChannelSelect from './ChannelSelect'

interface Props {
  productId: string
  password: string
}

const ACTION_LABELS: [keyof OrchestratorConfig['autonomy_settings'], string][] = [
  ['route_signal',          'Route signal'],
  ['update_mission',        'Update mission'],
  ['update_schedule',       'Update schedule'],
  ['update_subscriptions',  'Update subscriptions'],
  ['create_objective',      'Create objective'],
  ['consume_signal',        'Consume signal'],
  ['pause_workstream',      'Pause workstream'],
  ['create_workstream',     'Create workstream'],
  ['external_action',       'External action'],
  ['capability_gap',        'Capability gap'],
]

export default function OrchestratorSettings({ productId, password }: Props) {
  const [config, setConfig] = useState<OrchestratorConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.getOrchestratorConfig(password, productId)
      .then(setConfig)
      .catch(() => {})
  }, [productId, password])

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      const updated = await api.updateOrchestratorConfig(password, productId, {
        enabled: config.enabled,
        schedule: config.schedule,
        signal_threshold: config.signal_threshold,
        autonomy_settings: config.autonomy_settings,
        slack_channel_id: config.slack_channel_id,
        discord_channel_id: config.discord_channel_id,
        telegram_chat_id: config.telegram_chat_id,
      })
      setConfig(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return <div className="text-xs text-adj-text-faint p-4">Loading…</div>

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-3">
          Product Adjutant
        </h3>

        {/* Enable toggle */}
        <label className="flex items-center gap-3 cursor-pointer mb-4">
          <input
            type="checkbox"
            checked={config.enabled === 1}
            onChange={e => setConfig({ ...config, enabled: e.target.checked ? 1 : 0 })}
            className="w-4 h-4 accent-adj-accent"
          />
          <span className="text-sm text-adj-text-primary">Enabled</span>
        </label>

        {/* Schedule */}
        <div className="mb-4">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Schedule
          </label>
          <input
            type="text"
            value={config.schedule}
            onChange={e => setConfig({ ...config, schedule: e.target.value })}
            placeholder="daily at 8am"
            className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
          />
        </div>

        {/* Signal threshold */}
        <div className="mb-6">
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Signal threshold (auto-trigger)
          </label>
          <input
            type="number"
            min={1}
            value={config.signal_threshold}
            onChange={e => setConfig({ ...config, signal_threshold: Number(e.target.value) })}
            className="w-24 bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
          />
        </div>

        {/* Autonomy toggles */}
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">
            Autonomy per action
          </label>
          <div className="flex flex-col gap-2">
            {ACTION_LABELS.map(([key, label]) => (
              <div key={key} className="flex items-center gap-3 bg-adj-panel border border-adj-border rounded-md px-3 py-2">
                <span className="text-xs text-adj-text-secondary w-40 flex-shrink-0">{label}</span>
                <select
                  value={config.autonomy_settings[key] ?? 'autonomous'}
                  onChange={e => setConfig({
                    ...config,
                    autonomy_settings: {
                      ...config.autonomy_settings,
                      [key]: e.target.value as 'autonomous' | 'approval_required',
                    },
                  })}
                  className="flex-1 bg-adj-elevated border border-adj-border rounded px-2 py-1.5 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent"
                >
                  <option value="autonomous">Autonomous</option>
                  <option value="approval_required">Approval required</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">
          Notification Channel
        </h3>
        <p className="text-[10px] text-adj-text-faint mb-3">
          All notifications for this product (briefs, approvals, reports) go here. Defaults to the global channel when unset.
        </p>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
              Slack
            </label>
            <ChannelSelect
              platform="slack"
              value={config.slack_channel_id ?? ''}
              onChange={id => setConfig({ ...config, slack_channel_id: id || null })}
              password={password}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
              Discord
            </label>
            <ChannelSelect
              platform="discord"
              value={config.discord_channel_id ?? ''}
              onChange={id => setConfig({ ...config, discord_channel_id: id || null })}
              password={password}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
              Telegram Chat ID
            </label>
            <input
              type="text"
              value={config.telegram_chat_id ?? ''}
              onChange={e => setConfig({ ...config, telegram_chat_id: e.target.value || null })}
              placeholder="Leave empty to use global"
              className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent"
            />
          </div>
        </div>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="self-start px-4 py-2 text-xs font-medium bg-adj-accent text-white rounded-md hover:bg-adj-accent/90 disabled:opacity-50"
      >
        {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save'}
      </button>
    </div>
  )
}
