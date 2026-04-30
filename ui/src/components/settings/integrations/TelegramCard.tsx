// ui/src/components/settings/integrations/TelegramCard.tsx
import { useEffect, useState } from 'react'
import { api } from '../../../api'

interface Props {
  password: string
}

interface TelegramStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
  enabled: boolean
}

export default function TelegramCard({ password }: Props) {
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [token, setToken] = useState('')
  const [savingToken, setSavingToken] = useState(false)
  const [tokenError, setTokenError] = useState('')
  const [discovering, setDiscovering] = useState(false)
  const [discoverMsg, setDiscoverMsg] = useState('')
  const [showReconfigure, setShowReconfigure] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = () => {
    api.getTelegramStatus(password).then(s => setStatus(s)).catch(() => {})
  }

  useEffect(() => { reload() }, [password])

  async function handleSaveToken() {
    if (!token.trim()) return
    setSavingToken(true)
    setTokenError('')
    try {
      await api.saveTelegramToken(password, token.trim())
      setToken('')
      setShowReconfigure(false)
      reload()
    } catch (e: unknown) {
      setTokenError((e as Error).message || 'Invalid token')
    } finally {
      setSavingToken(false)
    }
  }

  async function handleDiscover() {
    setDiscovering(true)
    setDiscoverMsg('')
    try {
      const { chat_id } = await api.discoverTelegramChat(password)
      if (chat_id) {
        setDiscoverMsg('Chat ID found! Bot is now connected.')
        reload()
      } else {
        setDiscoverMsg('No messages found yet — message your bot first, then try again.')
      }
    } catch (e: unknown) {
      setDiscoverMsg((e as Error).message || 'Failed to discover chat')
    } finally {
      setDiscovering(false)
    }
  }

  async function handleToggleEnabled() {
    if (!status) return
    setToggling(true)
    try {
      await api.setTelegramEnabled(password, !status.enabled)
      reload()
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Disconnect Telegram? This will clear the bot token and chat ID.')) return
    setDeleting(true)
    try {
      await api.deleteTelegram(password)
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
          <span className="text-lg">✈️</span>
          <span className="text-sm font-bold text-adj-text-primary">Telegram</span>
          {isConnected && (
            <span className="text-xs font-mono text-emerald-400">@{status?.bot_username}</span>
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
                title="Disconnect"
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
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status.enabled ? 'bg-emerald-500' : 'bg-adj-text-faint'}`} />
              <span className="text-sm text-adj-text-primary">
                {status.enabled ? 'Connected and active' : 'Connected but disabled'}
              </span>
            </div>
            <p className="text-xs text-adj-text-muted">
              Message your bot on Telegram to send directives from anywhere.
            </p>
            <button
              onClick={() => setShowReconfigure(true)}
              className="text-xs text-adj-text-muted hover:text-adj-text-secondary transition-colors"
            >
              Reconfigure token
            </button>
          </div>
        ) : status.configured && !isConnected && !showReconfigure ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-secondary">
                Token saved as <span className="font-mono text-amber-400">@{status.bot_username}</span> — waiting for first message
              </span>
            </div>
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">One more step:</p>
              <p>1. Open Telegram and message <span className="font-mono text-adj-text-secondary">@{status.bot_username}</span></p>
              <p>2. Send any message (e.g. "hello")</p>
              <p>3. Click <strong>Discover Chat</strong> below</p>
            </div>
            <button
              onClick={handleDiscover}
              disabled={discovering}
              className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
            >
              {discovering ? 'Searching…' : 'Discover Chat'}
            </button>
            {discoverMsg && (
              <p className={`text-xs ${discoverMsg.includes('found') ? 'text-emerald-400' : 'text-amber-400'}`}>
                {discoverMsg}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {!showReconfigure && (
              <p className="text-xs text-adj-text-secondary">
                Connect Telegram to send directives and get notifications from anywhere.
              </p>
            )}
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">Create a bot:</p>
              <p>Open Telegram → message <span className="font-mono text-adj-text-secondary">@BotFather</span> → send <span className="font-mono text-adj-text-secondary">/newbot</span> → copy the token.</p>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Bot Token
              </label>
              <input
                type="password"
                value={token}
                onChange={e => { setToken(e.target.value); setTokenError('') }}
                placeholder="1234567890:ABCDEFghijklmnopqrstuvwxyz"
                className="w-full bg-adj-base border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono transition-colors"
              />
              {tokenError && <p className="text-xs text-red-400 mt-1">{tokenError}</p>}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveToken}
                disabled={savingToken || !token.trim()}
                className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
              >
                {savingToken ? 'Verifying…' : 'Save Token'}
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
          href="https://core.telegram.org/bots#how-do-i-create-a-bot"
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-adj-accent hover:underline"
        >
          Setup guide →
        </a>
      </div>
    </div>
  )
}
