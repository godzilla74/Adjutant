import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { HCAConfig } from '../../types'

interface Props {
  password: string
}

export default function HCASettings({ password }: Props) {
  const [config, setConfig] = useState<HCAConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.getHCAConfig(password).then(setConfig).catch(() => {})
  }, [password])

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      const updated = await api.updateHCAConfig(password, {
        enabled: config.enabled,
        schedule: config.schedule,
        pa_run_threshold: config.pa_run_threshold,
        hca_slack_channel_id: config.hca_slack_channel_id,
        hca_discord_channel_id: config.hca_discord_channel_id,
        hca_telegram_chat_id: config.hca_telegram_chat_id,
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
          Chief Adjutant
        </h3>
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2 text-xs text-adj-text-primary cursor-pointer">
            <input
              type="checkbox"
              checked={config.enabled === 1}
              onChange={e => setConfig({ ...config, enabled: e.target.checked ? 1 : 0 })}
              className="w-4 h-4 accent-adj-accent"
            />
            Enabled
          </label>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-adj-text-muted uppercase tracking-wider">Schedule</label>
            <input
              type="text"
              value={config.schedule}
              onChange={e => setConfig({ ...config, schedule: e.target.value })}
              className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary w-full focus:outline-none focus:border-adj-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-adj-text-muted uppercase tracking-wider">PA Run Threshold</label>
            <input
              type="number"
              min={1}
              value={config.pa_run_threshold}
              onChange={e => setConfig({ ...config, pa_run_threshold: parseInt(e.target.value) || 1 })}
              className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary w-24 focus:outline-none focus:border-adj-accent"
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-3">
          Chief Adjutant Notification Channels
        </h3>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-adj-text-muted uppercase tracking-wider">Slack Channel ID</label>
            <input
              type="text"
              value={config.hca_slack_channel_id}
              onChange={e => setConfig({ ...config, hca_slack_channel_id: e.target.value })}
              placeholder="Slack channel ID (e.g. C0123ABCD)"
              className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary w-full focus:outline-none focus:border-adj-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-adj-text-muted uppercase tracking-wider">Discord Channel ID</label>
            <input
              type="text"
              value={config.hca_discord_channel_id}
              onChange={e => setConfig({ ...config, hca_discord_channel_id: e.target.value })}
              placeholder="Discord channel ID"
              className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary w-full focus:outline-none focus:border-adj-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-adj-text-muted uppercase tracking-wider">Telegram Chat ID</label>
            <input
              type="text"
              value={config.hca_telegram_chat_id}
              onChange={e => setConfig({ ...config, hca_telegram_chat_id: e.target.value })}
              placeholder="Telegram chat ID"
              className="bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary w-full focus:outline-none focus:border-adj-accent"
            />
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={save}
          disabled={saving}
          className="self-start px-4 py-2 text-xs font-medium bg-adj-accent text-white rounded-md hover:bg-adj-accent/90 disabled:opacity-50"
        >
          {saving ? 'Saving…' : saved ? 'Saved' : 'Save'}
        </button>
      </div>
    </div>
  )
}
