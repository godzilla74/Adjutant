// ui/src/components/settings/integrations/SlackCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface SlackStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
  notification_channel_id: string
}

export default function SlackCard({ password }: Props) {
  const [status, setStatus] = useState<SlackStatus | null>(null)
  const [botToken, setBotToken] = useState('')
  const [appToken, setAppToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [channels, setChannels] = useState<{ id: string; name: string }[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)
  const [channelLoadError, setChannelLoadError] = useState(false)
  const [savingChannel, setSavingChannel] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getSlackStatus(password).then(s => {
      setStatus(s)
      if (s.connected) loadChannels()
    }).catch(() => {})
  }

  const loadChannels = () => {
    setLoadingChannels(true)
    setChannelLoadError(false)
    api.getSlackChannels(password)
      .then(r => setChannels(r.channels))
      .catch(() => setChannelLoadError(true))
      .finally(() => setLoadingChannels(false))
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveTokens() {
    if (!botToken.trim() || !appToken.trim()) return
    setSaving(true)
    setSaveError('')
    try {
      await api.saveSlackTokens(password, botToken.trim(), appToken.trim())
      setBotToken('')
      setAppToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setSaveError((e as Error).message || 'Invalid tokens')
    } finally {
      setSaving(false)
    }
  }

  async function handleSelectChannel(channelId: string) {
    if (!channelId) return
    setSavingChannel(true)
    try {
      await api.saveSlackNotificationChannel(password, channelId)
      reload()
    } finally {
      setSavingChannel(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setSlackEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Slack? This will clear all Slack credentials.')) return
    setDeleting(true)
    try {
      await api.deleteSlack(password)
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
          <span className="text-lg">💬</span>
          <span className="text-sm font-bold text-adj-text-primary">Slack</span>
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
              ) : channelLoadError ? (
                <p className="text-xs text-amber-400">Could not load channels — check your bot token and try again.</p>
              ) : (
                <select
                  value={status.notification_channel_id || ''}
                  onChange={e => handleSelectChannel(e.target.value)}
                  disabled={savingChannel}
                  className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors disabled:opacity-50"
                >
                  <option value="">— Select a channel —</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>#{c.name}</option>
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
              Reconfigure tokens
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Slack to interact with Adjutant from any channel. @mention the bot to send directives.
              </p>
            )}
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1">
              <p className="font-semibold text-adj-text-secondary">Two tokens required:</p>
              <p><span className="font-mono text-adj-text-secondary">xoxb-...</span> Bot Token — from OAuth &amp; Permissions</p>
              <p><span className="font-mono text-adj-text-secondary">xapp-...</span> App-Level Token — from Socket Mode</p>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token (xoxb-...)
              </label>
              <input
                type="password"
                value={botToken}
                onChange={e => { setBotToken(e.target.value); setSaveError('') }}
                placeholder="xoxb-..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                App-Level Token (xapp-...)
              </label>
              <input
                type="password"
                value={appToken}
                onChange={e => { setAppToken(e.target.value); setSaveError('') }}
                placeholder="xapp-..."
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
            </div>
            {saveError && <p className="text-xs text-red-400">{saveError}</p>}
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveTokens}
                disabled={saving || !botToken.trim() || !appToken.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {saving ? 'Verifying…' : 'Connect Slack'}
              </button>
              {showReconfigure && (
                <button
                  onClick={() => { setShowReconfigure(false); setBotToken(''); setAppToken('') }}
                  className="text-xs text-adj-text-muted hover:text-adj-text-secondary"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
        <a
          href="/docs/slack-setup.md"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Slack setup guide →
        </a>
      </div>
    </div>
  )
}
