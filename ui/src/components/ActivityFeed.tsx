// ui/src/components/ActivityFeed.tsx
import { useEffect, useRef, useState } from 'react'
import { ActivityEvent, AgentType, ReviewItem } from '../types'
import ActivityCard from './ActivityCard'
import MarkdownContent from './MarkdownContent'
import ReportsTab from './ReportsTab'
import BriefingTab from './BriefingTab'

interface DirectiveEntry { type: 'directive'; content: string; ts: string }
interface AgentEntry     { type: 'agent';     content: string; ts: string }

interface Props {
  productId:     string
  password:      string
  events:        ActivityEvent[]
  directives:    DirectiveEntry[]
  agentMessages: AgentEntry[]
  agentDraft:    string
  agentName:     string
  reviewItems?:  ReviewItem[]
  onApprove?:    (id: number) => void
  onSkip?:       (id: number) => void
}

const FILTER_TYPES: { label: string; value: AgentType }[] = [
  { label: 'Research', value: 'research' },
  { label: 'General',  value: 'general'  },
  { label: 'Email',    value: 'email'    },
  { label: 'Content',  value: 'content'  },
  { label: 'Social',   value: 'social'   },
]

const parseTs = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

export default function ActivityFeed({ productId, password, events, directives, agentMessages, agentDraft, agentName, reviewItems = [], onApprove, onSkip }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [activeTab,        setActiveTab]        = useState<'chat' | 'activity' | 'reports' | 'briefing'>('chat')
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [search,           setSearch]           = useState('')
  const [typeFilter,       setTypeFilter]       = useState<AgentType | null>(null)

  function handleViewReport(reportId: number) {
    setSelectedReportId(reportId)
    setActiveTab('reports')
  }

  const chatEntries = [...directives, ...agentMessages].sort(
    (a, b) => parseTs(a.ts) - parseTs(b.ts)
  )

  const runningCount = events.filter(e => e.status === 'running').length

  const pendingApprovalCount = reviewItems.filter(
    (r: ReviewItem) => r.status === 'pending' && r.action_type?.startsWith('orchestrator_')
  ).length

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
      <div className="flex-shrink-0 flex items-center gap-1 px-5 py-2 border-b border-adj-border">
        <button
          onClick={() => setActiveTab('chat')}
          className={`text-xs px-3 py-1 rounded-full transition-colors ${
            activeTab === 'chat'
              ? 'bg-adj-surface text-adj-text-primary'
              : 'text-adj-text-faint hover:text-adj-text-secondary'
          }`}
        >
          Chat
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`text-xs px-3 py-1 rounded-full transition-colors flex items-center gap-1 ${
            activeTab === 'activity'
              ? 'bg-adj-surface text-adj-text-primary'
              : 'text-adj-text-faint hover:text-adj-text-secondary'
          }`}
        >
          Activity
          {runningCount > 0 && (
            <span className="text-amber-400">({runningCount})</span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('reports')}
          className={`text-xs px-3 py-1 rounded-full transition-colors ${
            activeTab === 'reports'
              ? 'bg-adj-surface text-adj-text-primary'
              : 'text-adj-text-faint hover:text-adj-text-secondary'
          }`}
        >
          Reports
        </button>
        <button
          onClick={() => setActiveTab('briefing')}
          className={`text-xs px-3 py-1 rounded-full transition-colors flex items-center gap-1 ${
            activeTab === 'briefing'
              ? 'bg-adj-surface text-adj-text-primary'
              : 'text-adj-text-faint hover:text-adj-text-secondary'
          }`}
        >
          Briefing
          {pendingApprovalCount > 0 && (
            <span className="text-amber-400">({pendingApprovalCount})</span>
          )}
        </button>
      </div>

      {/* Chat tab */}
      {activeTab === 'chat' && (
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {chatEntries.map((entry, i) => {
            if (entry.type === 'directive') {
              return (
                <div key={`directive-${i}`} className="self-end max-w-lg">
                  <div className="text-xs text-adj-text-faint text-right mb-1">You · directive</div>
                  <div className="rounded-xl rounded-tr-sm bg-blue-600/20 border border-blue-700/40 px-4 py-2.5 text-sm text-blue-200">
                    {entry.content}
                  </div>
                </div>
              )
            }
            return (
              <div key={`agent-${i}`} className="max-w-xl">
                <div className="text-xs text-adj-text-faint mb-1">{agentName}</div>
                <div className="rounded-xl rounded-tl-sm bg-adj-elevated border border-zinc-700/40 px-4 py-2.5 text-sm text-adj-text-secondary leading-relaxed">
                  <MarkdownContent>{entry.content}</MarkdownContent>
                </div>
              </div>
            )
          })}

          {agentDraft && (
            <div className="max-w-xl">
              <div className="text-xs text-adj-text-faint mb-1">{agentName}</div>
              <div className="rounded-xl rounded-tl-sm bg-adj-elevated border border-zinc-700/40 px-4 py-2.5 text-sm text-adj-text-secondary whitespace-pre-wrap leading-relaxed">
                {agentDraft}
                <span className="inline-block w-0.5 h-4 bg-adj-text-secondary ml-0.5 animate-pulse align-middle" />
              </div>
            </div>
          )}

          {chatEntries.length === 0 && !agentDraft && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-700 py-20">
              <div className="text-4xl opacity-30">🛰</div>
              <div className="text-sm font-medium text-adj-text-faint">No activity yet</div>
              <div className="text-xs text-center leading-relaxed">
                Give {agentName} a directive below to get started.
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Reports tab */}
      {activeTab === 'reports' && (
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <ReportsTab
            productId={productId}
            password={password}
            initialReportId={selectedReportId}
          />
        </div>
      )}

      {/* Briefing tab */}
      {activeTab === 'briefing' && (
        <div className="flex-1 overflow-y-auto">
          <BriefingTab
            productId={productId}
            password={password}
            reviewItems={reviewItems}
            onApprove={onApprove ?? (() => {})}
            onSkip={onSkip ?? (() => {})}
          />
        </div>
      )}

      {/* Activity tab */}
      {activeTab === 'activity' && (
        <>
          <div className="flex-shrink-0 flex items-center gap-2 px-5 py-2 border-b border-adj-border">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search activity…"
              className="flex-1 min-w-0 text-xs bg-adj-panel border border-adj-border rounded px-2 py-1 text-adj-text-secondary placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-600"
            />
            <div className="flex items-center gap-1 flex-shrink-0">
              {FILTER_TYPES.map(ft => (
                <button
                  key={ft.value}
                  onClick={() => setTypeFilter(prev => prev === ft.value ? null : ft.value)}
                  className={[
                    'text-[10px] px-2 py-0.5 rounded-full border transition-colors',
                    typeFilter === ft.value
                      ? 'bg-blue-600/20 border-blue-600/50 text-adj-accent'
                      : 'bg-transparent border-adj-border text-adj-text-faint hover:text-adj-text-secondary hover:border-zinc-600',
                  ].join(' ')}
                >
                  {ft.label}
                </button>
              ))}
              {isFiltering && (
                <button
                  onClick={() => { setSearch(''); setTypeFilter(null) }}
                  className="text-[10px] text-adj-text-faint hover:text-adj-text-secondary px-1"
                  title="Clear filters"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
            {[...filteredEvents].reverse().map(event => (
              <ActivityCard key={event.id} event={event} onViewReport={handleViewReport} />
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
