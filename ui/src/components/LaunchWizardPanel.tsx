// ui/src/components/LaunchWizardPanel.tsx
import { useEffect, useRef, useState } from 'react'
import { ProductState } from '../types'

interface Props {
  productName: string
  activeState: ProductState
  wizardProgress: string
  directives: Array<{ type: 'directive'; content: string; ts: string }>
  agentMessages: Array<{ type: 'agent'; content: string; ts: string }>
  agentDraft: string
  onSend: (content: string) => void
  agentName: string
}

function ChecklistItem({ label, done }: { label: string; done: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={done ? 'text-emerald-400' : 'text-zinc-600'}>
        {done ? '✓' : '○'}
      </span>
      <span className={done ? 'text-zinc-200' : 'text-zinc-500'}>{label}</span>
    </div>
  )
}

function AnimatedDots() {
  const [dots, setDots] = useState('.')
  useEffect(() => {
    const id = setInterval(() => {
      setDots(d => d.length >= 3 ? '.' : d + '.')
    }, 400)
    return () => clearInterval(id)
  }, [])
  return <span className="text-zinc-500">{dots}</span>
}

export default function LaunchWizardPanel({
  productName, activeState, wizardProgress,
  directives, agentMessages, agentDraft,
  onSend, agentName,
}: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const objectives = activeState.objectives ?? []
  const autonomousCount = objectives.filter(o => o.autonomous === 1).length

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim()) {
        onSend(input.trim())
        setInput('')
      }
    }
  }

  const allMessages = [
    ...directives.map(d => ({ ...d, key: `d-${d.ts}-${d.content.slice(0, 8)}` })),
    ...agentMessages.map(a => ({ ...a, key: `a-${a.ts}-${a.content.slice(0, 8)}` })),
  ].sort((a, b) => a.ts.localeCompare(b.ts))

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [allMessages.length, agentDraft])

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left: Chat */}
      <div className="flex flex-col flex-1 overflow-hidden border-r border-zinc-800/60">
        <div className="flex items-center px-4 py-2 border-b border-zinc-800/40">
          <span className="text-xs text-zinc-500 font-medium">Setting up {productName}</span>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
          {allMessages.map(msg => (
            <div
              key={msg.key}
              className={`text-sm leading-relaxed ${
                msg.type === 'directive'
                  ? 'self-end bg-zinc-800 text-zinc-200 px-3 py-2 rounded-xl max-w-[80%]'
                  : 'self-start text-zinc-300 max-w-[90%]'
              }`}
            >
              {msg.content}
            </div>
          ))}
          {agentDraft && (
            <div className="self-start text-sm leading-relaxed text-zinc-300 max-w-[90%]">
              {agentDraft}
              <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-zinc-400 animate-pulse align-middle" />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="px-3 py-3 border-t border-zinc-800/60">
          <div className="flex items-end gap-2 bg-zinc-800 rounded-xl px-3 py-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Answer ${agentName}'s questions…`}
              rows={1}
              className="flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 resize-none focus:outline-none"
            />
            <button
              onClick={() => { if (input.trim()) { onSend(input.trim()); setInput('') } }}
              disabled={!input.trim()}
              className="text-xs font-medium text-indigo-400 hover:text-indigo-300 disabled:opacity-30 transition-colors pb-0.5"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Right: Progress checklist */}
      <div className="w-52 flex-shrink-0 flex flex-col px-4 py-4 gap-3">
        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Setup progress</span>
        <div className="flex flex-col gap-2">
          <ChecklistItem label="Product created" done={true} />
          <ChecklistItem
            label={`Objectives (${objectives.length})`}
            done={objectives.length >= 1}
          />
          <ChecklistItem
            label="Autonomous mode"
            done={autonomousCount >= 1}
          />
        </div>
        <div className="mt-auto">
          {wizardProgress && (
            <div className="text-xs text-zinc-500 leading-relaxed">
              {wizardProgress}
              <AnimatedDots />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
