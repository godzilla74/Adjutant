// ui/src/components/ActivityFeed.tsx
import { useEffect, useRef, useState } from 'react'
import { ActivityEvent, AgentType } from '../types'
import ActivityCard from './ActivityCard'
import MarkdownContent from './MarkdownContent'

interface DirectiveEntry { type: 'directive'; content: string; ts: string }
interface AgentEntry     { type: 'agent';     content: string; ts: string }

interface Props {
  events:        ActivityEvent[]
  directives:    DirectiveEntry[]
  agentMessages: AgentEntry[]
  agentDraft:    string
  agentName:     string
}

const FILTER_TYPES: { label: string; value: AgentType }[] = [
  { label: 'Research', value: 'research' },
  { label: 'General',  value: 'general'  },
  { label: 'Email',    value: 'email'    },
  { label: 'Content',  value: 'content'  },
  { label: 'Social',   value: 'social'   },
]

const parseTs = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

export default function ActivityFeed({ events, directives, agentMessages, agentDraft, agentName }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [activeTab,  setActiveTab]  = useState<'chat' | 'activity'>('chat')
  const [search,     setSearch]     = useState('')
  const [typeFilter, setTypeFilter] = useState<AgentType | null>(null)

  const chatEntries = [...directives, ...agentMessages].sort(
    (a, b) => parseTs(a.ts) - parseTs(b.ts)
  )

  const runningCount = events.filter(e => e.status === 'running').length

  const isFiltering = !!search || !!typeFilter

  const filteredEvents = events.filter(event => {
    if (typeFilter && event.agent_type !== typeFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        event.headline.toLowerCase().includes(q) ||
        (event.summary ?? '').toLowerCase().includes(q)
      )
    }
    return true
  })

  useEffect(() => {
    if (activeTab === 'chat') {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [directives.length, agentMessages.length, agentDraft, activeTab])

  return (
    <div className="flex-1 flex flex-col overflow-hidden">

      {/* Tab bar */}
      <div className="flex-shrink-0 flex items-center gap-1 px-5 py-2 border-b border-zinc-800/40">
        <button
          onClick={() => setActiveTab('chat')}
          className={`text-xs px-3 py-1 rounded-full transition-colors ${
            activeTab === 'chat'
              ? 'bg-zinc-800 text-zinc-200'
              : 'text-zinc-600 hover:text-zinc-400'
          }`}
        >
          Chat
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`text-xs px-3 py-1 rounded-full transition-colors flex items-center gap-1 ${
            activeTab === 'activity'
              ? 'bg-zinc-800 text-zinc-200'
              : 'text-zinc-600 hover:text-zinc-400'
          }`}
        >
          Activity
          {runningCount > 0 && (
            <span className="text-amber-400">({runningCount})</span>
          )}
        </button>
      </div>

      {/* Chat tab */}
      {activeTab === 'chat' && (
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {chatEntries.map(entry => {
            if (entry.type === 'directive') {
              return (
                <div key={`directive-${entry.ts}`} className="self-end max-w-lg">
                  <div className="text-xs text-zinc-600 text-right mb-1">You · directive</div>
                  <div className="rounded-xl rounded-tr-sm bg-blue-600/20 border border-blue-700/40 px-4 py-2.5 text-sm text-blue-200">
                    {entry.content}
                  </div>
                </div>
              )
            }
            return (
              <div key={`agent-${entry.ts}`} className="max-w-xl">
                <div className="text-xs text-zinc-600 mb-1">{agentName}</div>
                <div className="rounded-xl rounded-tl-sm bg-zinc-800/60 border border-zinc-700/40 px-4 py-2.5 text-sm text-zinc-300 leading-relaxed">
                  <MarkdownContent>{entry.content}</MarkdownContent>
                </div>
              </div>
            )
          })}

          {agentDraft && (
            <div className="max-w-xl">
              <div className="text-xs text-zinc-600 mb-1">{agentName}</div>
              <div className="rounded-xl rounded-tl-sm bg-zinc-800/60 border border-zinc-700/40 px-4 py-2.5 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                {agentDraft}
                <span className="inline-block w-0.5 h-4 bg-zinc-400 ml-0.5 animate-pulse align-middle" />
              </div>
            </div>
          )}

          {chatEntries.length === 0 && !agentDraft && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-700 py-20">
              <div className="text-4xl opacity-30">🛰</div>
              <div className="text-sm font-medium text-zinc-600">No activity yet</div>
              <div className="text-xs text-center leading-relaxed">
                Give {agentName} a directive below to get started.
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Activity tab */}
      {activeTab === 'activity' && (
        <>
          <div className="flex-shrink-0 flex items-center gap-2 px-5 py-2 border-b border-zinc-800/40">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search activity…"
              className="flex-1 min-w-0 text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-300 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-600"
            />
            <div className="flex items-center gap-1 flex-shrink-0">
              {FILTER_TYPES.map(ft => (
                <button
                  key={ft.value}
                  onClick={() => setTypeFilter(prev => prev === ft.value ? null : ft.value)}
                  className={[
                    'text-[10px] px-2 py-0.5 rounded-full border transition-colors',
                    typeFilter === ft.value
                      ? 'bg-blue-600/20 border-blue-600/50 text-blue-400'
                      : 'bg-transparent border-zinc-800 text-zinc-600 hover:text-zinc-400 hover:border-zinc-600',
                  ].join(' ')}
                >
                  {ft.label}
                </button>
              ))}
              {isFiltering && (
                <button
                  onClick={() => { setSearch(''); setTypeFilter(null) }}
                  className="text-[10px] text-zinc-600 hover:text-zinc-400 px-1"
                  title="Clear filters"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
            {filteredEvents.map(event => (
              <ActivityCard key={event.id} event={event} />
            ))}
            {filteredEvents.length === 0 && (
              <div className="flex-1 flex items-center justify-center text-zinc-700 text-sm py-20">
                {isFiltering ? 'No activity matches your filter.' : 'No agent activity yet.'}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
