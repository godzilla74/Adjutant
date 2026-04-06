import { useEffect, useRef } from 'react'
import { AppEvent } from '../types'
import EventItem from './EventItem'

interface Props {
  events: AppEvent[]
  hannahDraft: string
}

export default function ActivityFeed({ events, hannahDraft }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, hannahDraft])

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-3xl flex flex-col gap-4">
        {events.map((ev, i) => (
          <EventItem key={i} event={ev} />
        ))}
        {hannahDraft && (
          <div className="flex flex-col items-start gap-1">
            <span className="text-xs text-zinc-500">Hannah</span>
            <div className="max-w-2xl rounded-2xl rounded-tl-sm bg-zinc-800 px-4 py-2.5 text-sm text-zinc-100 whitespace-pre-wrap">
              {hannahDraft}
              <span className="inline-block w-0.5 h-4 bg-zinc-400 ml-0.5 animate-pulse align-middle" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
