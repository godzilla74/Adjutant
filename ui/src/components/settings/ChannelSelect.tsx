import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Channel {
  id: string
  name: string
  guild?: string
}

interface Props {
  platform: 'slack' | 'discord'
  value: string
  onChange: (id: string) => void
  password: string
  className?: string
}

export default function ChannelSelect({ platform, value, onChange, password, className = '' }: Props) {
  const [channels, setChannels] = useState<Channel[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    setStatus('loading')
    const fetch = platform === 'slack'
      ? api.getSlackChannels(password)
      : api.getDiscordChannels(password)
    fetch
      .then(data => { setChannels(data.channels); setStatus('ready') })
      .catch(() => setStatus('error'))
  }, [platform, password])

  const base = `w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-adj-accent ${className}`

  if (status === 'loading') {
    return (
      <select disabled className={`${base} text-adj-text-faint`}>
        <option>Loading…</option>
      </select>
    )
  }

  if (status === 'error') {
    return (
      <select disabled className={`${base} text-adj-text-faint`}>
        <option>Integration not connected</option>
      </select>
    )
  }

  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className={`${base} text-adj-text-primary`}
    >
      <option value="">— global default —</option>
      {channels.map(ch => (
        <option key={ch.id} value={ch.id}>
          {ch.guild ? `${ch.guild} / #${ch.name}` : `#${ch.name}`}
        </option>
      ))}
    </select>
  )
}
