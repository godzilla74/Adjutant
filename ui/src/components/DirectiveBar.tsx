// ui/src/components/DirectiveBar.tsx
import { useState, useEffect, useRef, KeyboardEvent } from 'react'

interface Props {
  onSend: (content: string) => void
  disabled: boolean
  productName: string
  agentName: string
  prefill?: string
  onPrefillConsumed?: () => void
}

export default function DirectiveBar({ onSend, disabled, productName, agentName, prefill, onPrefillConsumed }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (prefill) {
      setValue(prefill)
      onPrefillConsumed?.()
    }
  }, [prefill])

  // Auto-grow height as content changes
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
    // Shift+Enter falls through and inserts a newline naturally
  }

  return (
    <div className="flex-shrink-0 border-t border-zinc-800/60 px-5 py-3 bg-zinc-950 flex items-end gap-3">
      <span className="text-xs text-zinc-600 whitespace-nowrap flex-shrink-0 pb-2">
        Direct {agentName} →
      </span>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        rows={1}
        placeholder={`e.g. Focus all agents on ${productName} growth this week.`}
        className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-600 disabled:opacity-40 resize-none overflow-hidden leading-relaxed min-h-[36px] max-h-40"
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
