import { useState, KeyboardEvent } from 'react'

interface Props {
  onSend: (content: string) => void
  disabled: boolean
}

export default function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="shrink-0 border-t border-zinc-800 px-6 py-4">
      <div className="mx-auto max-w-3xl flex items-end gap-3">
        <textarea
          className="flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-sky-600 min-h-[44px] max-h-40"
          placeholder="Delegate to Hannah…"
          rows={1}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={onKey}
          disabled={disabled}
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="shrink-0 rounded-xl bg-sky-600 px-5 py-3 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}
