// ui/src/components/ActivityFeed.tsx
import { useEffect, useRef } from 'react'
import { ActivityEvent } from '../types'
import ActivityCard from './ActivityCard'

interface DirectiveEntry {
  type: 'directive'
  content: string
  ts: string
}

interface HannahEntry {
  type: 'hannah'
  content: string
  ts: string
}

type FeedEntry = ActivityEvent | DirectiveEntry | HannahEntry

interface Props {
  events: ActivityEvent[]
  directives: DirectiveEntry[]
  hannahMessages: HannahEntry[]
  hannahDraft: string
}

export default function ActivityFeed({ events, directives, hannahMessages, hannahDraft }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  const feed: FeedEntry[] = [
    ...events,
    ...directives,
    ...hannahMessages,
  ].sort((a, b) => {
    const ta = 'created_at' in a ? a.created_at : a.ts
    const tb = 'created_at' in b ? b.created_at : b.ts
    return ta < tb ? -1 : ta > tb ? 1 : 0
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [feed.length, hannahDraft])

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
      {feed.map((entry, i) => {
        if ('agent_type' in entry) {
          return <ActivityCard key={entry.id} event={entry} />
        }
        if (entry.type === 'directive') {
          return (
            <div key={i} className="self-end max-w-lg">
              <div className="text-xs text-zinc-600 text-right mb-1">You · directive</div>
              <div className="rounded-xl rounded-tr-sm bg-blue-600/20 border border-blue-700/40 px-4 py-2.5 text-sm text-blue-200">
                {entry.content}
              </div>
            </div>
          )
        }
        if (entry.type === 'hannah') {
          return (
            <div key={i} className="max-w-xl">
              <div className="text-xs text-zinc-600 mb-1">Hannah</div>
              <div className="rounded-xl rounded-tl-sm bg-zinc-800/60 border border-zinc-700/40 px-4 py-2.5 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                {entry.content}
              </div>
            </div>
          )
        }
        return null
      })}

      {hannahDraft && (
        <div className="max-w-xl">
          <div className="text-xs text-zinc-600 mb-1">Hannah</div>
          <div className="rounded-xl rounded-tl-sm bg-zinc-800/60 border border-zinc-700/40 px-4 py-2.5 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
            {hannahDraft}
            <span className="inline-block w-0.5 h-4 bg-zinc-400 ml-0.5 animate-pulse align-middle" />
          </div>
        </div>
      )}

      {feed.length === 0 && !hannahDraft && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-700 py-20">
          <div className="text-4xl opacity-30">🛰</div>
          <div className="text-sm font-medium text-zinc-600">No activity yet</div>
          <div className="text-xs text-center leading-relaxed">
            Give Hannah a directive below to get started.
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
