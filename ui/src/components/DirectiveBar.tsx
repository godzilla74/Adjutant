// ui/src/components/DirectiveBar.tsx
import { useState, useEffect, KeyboardEvent } from 'react'

interface Props {
  onSend: (content: string) => void
  disabled: boolean
  productName: string
  prefill?: string
  onPrefillConsumed?: () => void
}

export default function DirectiveBar({ onSend, disabled, productName, prefill, onPrefillConsumed }: Props) {
  const [value, setValue] = useState('')

  useEffect(() => {
    if (prefill) {
      setValue(prefill)
      onPrefillConsumed?.()
    }
  }, [prefill])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex-shrink-0 border-t border-zinc-800/60 px-5 py-3 bg-zinc-950 flex items-center gap-3">
      <span className="text-xs text-zinc-600 whitespace-nowrap flex-shrink-0">
        Direct Hannah →
      </span>
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        placeholder={`e.g. Focus all agents on ${productName} growth this week.`}
        className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-600 disabled:opacity-40 h-9"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="flex-shrink-0 rounded-lg bg-blue-600/20 border border-blue-600/50 text-blue-400 px-4 h-9 text-sm font-medium hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Send
      </button>
    </div>
  )
}
