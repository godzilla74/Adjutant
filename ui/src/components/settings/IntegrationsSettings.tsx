// ui/src/components/settings/IntegrationsSettings.tsx
import TelegramCard from './integrations/TelegramCard'
import SlackCard from './integrations/SlackCard'
import DiscordCard from './integrations/DiscordCard'

interface Props {
  password: string
}

export default function IntegrationsSettings({ password }: Props) {
  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Integrations</h2>
      <p className="text-xs text-adj-text-muted mb-6">
        Connect messaging platforms to interact with Adjutant from anywhere
      </p>
      <div className="space-y-4">
        <TelegramCard password={password} />
        <SlackCard password={password} />
        <DiscordCard password={password} />
      </div>
    </div>
  )
}
