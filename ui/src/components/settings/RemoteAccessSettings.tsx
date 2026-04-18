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
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null)

  useEffect(() => {
    api.getTelegramStatus(password)
      .then(s => setTelegramStatus(s))
      .catch(() => {/* non-fatal */})
  }, [password])

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Remote Access</h2>
      <p className="text-xs text-adj-text-muted mb-6">Connect Telegram to chat with your assistant from anywhere</p>

      <div className="bg-adj-panel border border-adj-border rounded-md p-4">
        {telegramStatus === null ? (
          <p className="text-xs text-adj-text-faint">Checking status…</p>
        ) : telegramStatus.connected ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-primary">
                Connected as{' '}
                <span className="font-mono text-emerald-400">@{telegramStatus.bot_username}</span>
              </span>
            </div>
            <p className="text-xs text-adj-text-muted">
              Message your bot on Telegram to chat with your assistant from anywhere.
              Use{' '}
              <span className="font-mono text-adj-text-secondary">for ProductName: message</span>{' '}
              to target a specific product.
            </p>
          </div>
        ) : telegramStatus.configured ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-sm text-adj-text-secondary">Token set but bot unreachable</span>
            </div>
            <p className="text-xs text-adj-text-muted">
              Check your{' '}
              <span className="font-mono text-adj-text-secondary">TELEGRAM_BOT_TOKEN</span>{' '}
              in config.env and restart.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-adj-text-secondary">
              Connect Telegram to chat with your assistant from anywhere — no port forwarding required.
            </p>
            <ol className="space-y-2 text-xs text-adj-text-muted list-decimal list-inside leading-relaxed">
              <li>
                Message{' '}
                <span className="font-mono text-adj-text-secondary">@BotFather</span>{' '}
                on Telegram →{' '}
                <span className="font-mono text-adj-text-secondary">/newbot</span>{' '}
                → copy the token
              </li>
              <li>
                Add to your{' '}
                <span className="font-mono text-adj-text-secondary">config.env</span>
                :<br />
                <span className="font-mono text-adj-text-secondary ml-4">
                  TELEGRAM_BOT_TOKEN=your_token
                </span>
              </li>
              <li>Message your new bot once (any text)</li>
              <li>
                Run{' '}
                <span className="font-mono text-adj-text-secondary">adjutant telegram setup</span>
              </li>
              <li>
                Run{' '}
                <span className="font-mono text-adj-text-secondary">adjutant restart</span>
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}
