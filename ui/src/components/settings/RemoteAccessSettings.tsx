import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

interface TelegramStatus {
  configured: boolean
  connected: boolean
  bot_username: string | null
}

export default function RemoteAccessSettings({ password }: Props) {
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [token, setToken] = useState('')
  const [savingToken, setSavingToken] = useState(false)
  const [tokenError, setTokenError] = useState('')
  const [discovering, setDiscovering] = useState(false)
  const [discoverMsg, setDiscoverMsg] = useState('')

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

  return (
    <div className="max-w-4xl">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Remote Access</h2>
      <p className="text-xs text-adj-text-muted mb-6">Connect Telegram to chat with your assistant from anywhere</p>

      <div className="bg-adj-panel border border-adj-border rounded-md p-4 space-y-4">
        {status === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : status.connected ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-primary">
                Connected as <span className="font-mono text-emerald-400">@{status.bot_username}</span>
              </span>
            </div>
            <p className="text-xs text-adj-text-muted">
              Message your bot on Telegram to send directives from anywhere.
              Use <span className="font-mono text-adj-text-secondary">for ProductName: message</span> to target a specific product.
            </p>
          </div>
        ) : status.configured ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-secondary">
                Bot token saved as <span className="font-mono text-amber-400">@{status.bot_username}</span> — waiting for first message
              </span>
            </div>
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">One more step:</p>
              <p>1. Open Telegram and search for <span className="font-mono text-adj-text-secondary">@{status.bot_username}</span></p>
              <p>2. Send any message to your bot (e.g. "hello")</p>
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
            <p className="text-xs text-adj-text-secondary">
              Connect Telegram to send directives and get notifications from anywhere — no port forwarding needed.
            </p>
            <div className="p-3 bg-adj-surface rounded-md text-xs text-adj-text-muted space-y-1.5">
              <p className="font-semibold text-adj-text-secondary">Step 1 — Create a bot:</p>
              <p>
                Open Telegram → message <span className="font-mono text-adj-text-secondary">@BotFather</span> → send{' '}
                <span className="font-mono text-adj-text-secondary">/newbot</span> → follow the prompts → copy the token it gives you.
              </p>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
                Step 2 — Paste your bot token
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
            <button
              onClick={handleSaveToken}
              disabled={savingToken || !token.trim()}
              className="px-4 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
            >
              {savingToken ? 'Verifying…' : 'Save Token'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
