// ui/src/components/settings/integrations/DiscordCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface DiscordStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
  notification_channel_id: string
}

export default function DiscordCard({ password }: Props) {
  const [status, setStatus] = useState<DiscordStatus | null>(null)
  const [token, setToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [channels, setChannels] = useState<{ id: string; name: string; guild: string }[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)
  const [savingChannel, setSavingChannel] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getDiscordStatus(password).then(s => {
      setStatus(s)
      if (s.connected) loadChannels()
    }).catch(() => {})
  }

  const loadChannels = () => {
    setLoadingChannels(true)
    api.getDiscordChannels(password)
      .then(r => setChannels(r.channels))
      .catch(() => {})
      .finally(() => setLoadingChannels(false))
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveToken() {
    if (!token.trim()) return
    setSaving(true)
    setSaveError('')
    try {
      await api.saveDiscordToken(password, token.trim())
      setToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setSaveError((e as Error).message || 'Invalid token')
    } finally {
      setSaving(false)
    }
  }

  async function handleSelectChannel(channelId: string) {
    setSavingChannel(true)
    try {
      await api.saveDiscordNotificationChannel(password, channelId)
      reload()
    } finally {
      setSavingChannel(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setDiscordEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Discord? This will clear all Discord credentials.')) return
    setDeleting(true)
    try {
      await api.deleteDiscord(password)
      reload()
    } finally {
      setDeleting(false)
    }
  }

  const isConnected = status?.configured && status?.connected

  return (
    <div className="bg-adj-panel border border-adj-border rounded-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-adj-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">🎮</span>
          <span className="text-sm font-bold text-adj-text-primary">Discord</span>
          {isConnected && (
            <span className="text-xs text-emerald-400 font-mono">{status?.bot_username}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {status?.configured && (
            <>
              <button
                onClick={handleToggleEnabled}
                disabled={toggling}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
                  status.enabled ? 'bg-adj-accent' : 'bg-adj-border'
                }`}
                title={status.enabled ? 'Disable' : 'Enable'}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  status.enabled ? 'translate-x-4' : 'translate-x-1'
                }`} />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-adj-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
              >
                {deleting ? '…' : 'Disconnect'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {status === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : isConnected && !showReconfigure ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status.enabled ? 'bg-emerald-500' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary">
                {status.enabled ? 'Connected and active' : 'Connected but disabled'}
              </span>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Notification Channel
              </label>
              {loadingChannels ? (
                <p className="text-xs text-adj-text-faint">Loading channels…</p>
              ) : (
                <select
                  value={status.notification_channel_id || ''}
                  onChange={e => handleSelectChannel(e.target.value)}
                  disabled={savingChannel}
                  className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors disabled:opacity-50"
                >
                  <option value="">— Select a channel —</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.guild ? `${c.guild} / ` : ''}#{c.name}
                    </option>
                  ))}
                </select>
              )}
              <p className="text-xs text-adj-text-muted mt-1">
                Review items and activity summaries are sent here.
              </p>
            </div>
            <button
              onClick={() => setShowReconfigure(true)}
              className="text-xs text-adj-text-muted hover:text-adj-text-secondary transition-colors"
            >
              Reconfigure token
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Discord to interact with Adjutant from any server channel. @mention the bot to send directives.
              </p>
            )}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token
              </label>
              <input
                type="password"
                value={token}
                onChange={e => { setToken(e.target.value); setSaveError('') }}
                placeholder="MTI3..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
              {saveError && <p className="text-xs text-red-400 mt-1">{saveError}</p>}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveToken}
                disabled={saving || !token.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {saving ? 'Verifying…' : 'Connect Discord'}
              </button>
              {showReconfigure && (
                <button
                  onClick={() => { setShowReconfigure(false); setToken('') }}
                  className="text-xs text-adj-text-muted hover:text-adj-text-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
        <a
          href="/docs/discord-setup.md"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Discord setup guide →
        </a>
      </div>
    </div>
  )
}
