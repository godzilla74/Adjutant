// ui/src/components/settings/TelegramSettings.tsx
import TelegramCard from './integrations/TelegramCard'

interface Props {
  password: string
}

export default function TelegramSettings({ password }: Props) {
  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Telegram</h2>
      <p className="text-xs text-adj-text-muted mb-6">
        Connect Telegram to send directives and get notifications from anywhere
      </p>
      <TelegramCard password={password} />
    </div>
  )
}
