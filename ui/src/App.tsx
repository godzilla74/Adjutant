import { useCallback, useEffect, useRef, useState } from 'react'
import { AppEvent, AgentType } from './types'
import ActivityFeed from './components/ActivityFeed'
import InputBar from './components/InputBar'
import PasswordGate from './components/PasswordGate'

type ConnState = 'connecting' | 'auth' | 'ready' | 'disconnected'

export default function App() {
  const [connState, setConnState] = useState<ConnState>('connecting')
  const [events, setEvents] = useState<AppEvent[]>([])
  const [hannahDraft, setHannahDraft] = useState<string>('')
  const wsRef = useRef<WebSocket | null>(null)
  const isMounted = useRef(true)

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnState('auth')

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'auth_ok') { setConnState('ready'); return }
      if (msg.type === 'auth_fail') { setConnState('auth'); return }

      if (msg.type === 'history') {
        setEvents(msg.events)
        return
      }

      if (msg.type === 'user_message') {
        setEvents(prev => [...prev, { type: 'user_message', content: msg.content, ts: msg.ts }])
        return
      }
      if (msg.type === 'hannah_token') {
        setHannahDraft(prev => prev + msg.content)
        return
      }
      if (msg.type === 'hannah_done') {
        setHannahDraft(draft => {
          if (draft) setEvents(prev => [...prev, { type: 'hannah_message', content: draft, ts: msg.ts }])
          return ''
        })
        return
      }
      if (msg.type === 'task_started') {
        setEvents(prev => [...prev, {
          type: 'task',
          id: msg.id,
          agentType: msg.agent_type as AgentType,
          description: msg.description,
          status: 'running',
          ts: msg.ts,
        }])
        return
      }
      if (msg.type === 'task_done') {
        setEvents(prev => prev.map(ev =>
          ev.type === 'task' && ev.id === msg.id
            ? { ...ev, status: 'done' as const, summary: msg.summary }
            : ev
        ))
        return
      }
    }

    ws.onclose = () => {
      setConnState('disconnected')
      if (isMounted.current) setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    isMounted.current = true
    connect()
    return () => {
      isMounted.current = false
      wsRef.current?.close()
    }
  }, [connect])

  const sendAuth = useCallback((password: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'auth', password }))
  }, [])

  const sendMessage = useCallback((content: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'message', content }))
  }, [])

  if (connState === 'auth' || connState === 'connecting') {
    return <PasswordGate onSubmit={sendAuth} connecting={connState === 'connecting'} />
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800 shrink-0">
        <span className="font-semibold tracking-wide text-zinc-100">Hannah</span>
        <span className={`flex items-center gap-2 text-xs ${connState === 'ready' ? 'text-emerald-400' : 'text-zinc-500'}`}>
          <span className={`w-2 h-2 rounded-full ${connState === 'ready' ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
          {connState === 'ready' ? 'connected' : 'disconnected'}
        </span>
      </header>
      <ActivityFeed events={events} hannahDraft={hannahDraft} />
      <InputBar onSend={sendMessage} disabled={connState !== 'ready'} />
    </div>
  )
}
