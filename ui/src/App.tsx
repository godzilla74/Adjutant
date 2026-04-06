// ui/src/App.tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Product,
  ProductState,
  ActivityEvent,
  ServerMessage,
} from './types'
import ProductRail from './components/ProductRail'
import WorkstreamsPanel from './components/WorkstreamsPanel'
import ActivityFeed from './components/ActivityFeed'
import ReviewQueue from './components/ReviewQueue'
import DirectiveBar from './components/DirectiveBar'
import PasswordGate from './components/PasswordGate'

type ConnState = 'connecting' | 'auth' | 'ready' | 'disconnected'

interface DirectiveEntry { type: 'directive'; content: string; ts: string }
interface HannahEntry   { type: 'hannah';    content: string; ts: string }

// Per-product UI state
const EMPTY_STATE: ProductState = {
  workstreams: [],
  objectives: [],
  events: [],
  review_items: [],
}

export default function App() {
  const [connState,       setConnState]       = useState<ConnState>('connecting')
  const [products,        setProducts]        = useState<Product[]>([])
  const [activeProductId, setActiveProductId] = useState<string>('retainerops')
  const [productStates,   setProductStates]   = useState<Record<string, ProductState>>({})
  const [directives,      setDirectives]      = useState<Record<string, DirectiveEntry[]>>({})
  const [hannahMessages,  setHannahMessages]  = useState<Record<string, HannahEntry[]>>({})
  const [hannahDraft,     setHannahDraft]     = useState<string>('')
  const wsRef    = useRef<WebSocket | null>(null)
  const isMounted = useRef(true)

  const activeState = productStates[activeProductId] ?? EMPTY_STATE
  const activeProduct = products.find(p => p.id === activeProductId)

  const setProductState = useCallback((productId: string, updater: (prev: ProductState) => ProductState) => {
    setProductStates(prev => ({
      ...prev,
      [productId]: updater(prev[productId] ?? EMPTY_STATE),
    }))
  }, [])

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnState('auth')

    ws.onmessage = (e) => {
      const msg: ServerMessage = JSON.parse(e.data)

      if (msg.type === 'auth_ok') { setConnState('ready'); return }
      if (msg.type === 'auth_fail') { setConnState('auth'); return }

      if (msg.type === 'init') {
        setProducts(msg.products)
        // Request data for default product
        ws.send(JSON.stringify({ type: 'switch_product', product_id: 'retainerops' }))
        return
      }

      if (msg.type === 'product_data') {
        setProductState(msg.product_id, () => ({
          workstreams: msg.workstreams,
          objectives: msg.objectives,
          events: msg.events,
          review_items: msg.review_items,
        }))
        return
      }

      if (msg.type === 'directive_echo') {
        setDirectives(prev => ({
          ...prev,
          [msg.product_id]: [...(prev[msg.product_id] ?? []), { type: 'directive', content: msg.content, ts: msg.ts }],
        }))
        return
      }

      if (msg.type === 'hannah_token') {
        setHannahDraft(prev => prev + msg.content)
        return
      }

      if (msg.type === 'hannah_done') {
        setHannahDraft('')
        setHannahMessages(prev => ({
          ...prev,
          [msg.product_id]: [...(prev[msg.product_id] ?? []), { type: 'hannah', content: msg.content, ts: msg.ts }],
        }))
        return
      }

      if (msg.type === 'activity_started') {
        const newEvent: ActivityEvent = {
          id: msg.id,
          agent_type: msg.agent_type,
          headline: msg.headline,
          rationale: msg.rationale,
          status: 'running',
          output_preview: null,
          summary: null,
          created_at: msg.ts,
        }
        setProductState(msg.product_id, prev => ({
          ...prev,
          events: [...prev.events, newEvent],
        }))
        return
      }

      if (msg.type === 'activity_done') {
        setProductState(msg.product_id, prev => ({
          ...prev,
          events: prev.events.map(ev =>
            ev.id === msg.id ? { ...ev, status: 'done' as const, summary: msg.summary } : ev
          ),
        }))
        return
      }

      if (msg.type === 'review_item_added') {
        setProductState(msg.product_id, prev => ({
          ...prev,
          review_items: [...prev.review_items, msg.item],
        }))
        return
      }

      if (msg.type === 'review_resolved') {
        // Remove from all product states (we don't know which product without the server telling us)
        setProductStates(prev => {
          const next = { ...prev }
          for (const pid of Object.keys(next)) {
            next[pid] = {
              ...next[pid],
              review_items: next[pid].review_items.filter(i => i.id !== msg.review_item_id),
            }
          }
          return next
        })
        return
      }
    }

    ws.onclose = () => {
      setConnState('disconnected')
      if (isMounted.current) setTimeout(connect, 3000)
    }
  }, [setProductState])

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

  const switchProduct = useCallback((productId: string) => {
    setActiveProductId(productId)
    if (!(productId in productStates)) {
      wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: productId }))
    }
  }, [productStates])

  const sendDirective = useCallback((content: string) => {
    wsRef.current?.send(JSON.stringify({
      type: 'directive',
      product_id: activeProductId,
      content,
    }))
  }, [activeProductId])

  const resolveReview = useCallback((id: number, action: 'approved' | 'skipped') => {
    wsRef.current?.send(JSON.stringify({
      type: 'resolve_review',
      review_item_id: id,
      action,
    }))
  }, [])

  if (connState === 'auth' || connState === 'connecting') {
    return <PasswordGate onSubmit={sendAuth} connecting={connState === 'connecting'} />
  }

  // Header stats
  const activeAgentCount = activeState.events.filter(e => e.status === 'running').length
  const reviewCount      = activeState.review_items.filter(i => i.status === 'pending').length

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">

      {/* Header */}
      <header className="flex items-center justify-between pl-0 pr-5 h-12 border-b border-zinc-800/60 flex-shrink-0 bg-zinc-950">
        <div className="flex items-center h-full">
          {/* Rail spacer */}
          <div className="w-14 h-full border-r border-zinc-800/60 flex items-center justify-center flex-shrink-0">
            <span className="w-7 h-7 rounded-lg bg-blue-600 text-white text-xs font-bold flex items-center justify-center">H</span>
          </div>
          <div className="flex items-center gap-2 pl-4">
            <span className="font-semibold text-zinc-100 text-sm">Hannah</span>
            <span className="text-zinc-700">/</span>
            <span className="text-sm text-zinc-400">{activeProduct?.name ?? '…'}</span>
          </div>
        </div>
        <div className="flex items-center gap-5">
          {activeAgentCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {activeAgentCount} active
            </span>
          )}
          {reviewCount > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              {reviewCount} need review
            </span>
          )}
          <span className={`flex items-center gap-1.5 text-xs ${connState === 'ready' ? 'text-emerald-500' : 'text-zinc-500'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connState === 'ready' ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
            {connState === 'ready' ? 'connected' : 'disconnected'}
          </span>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">

        {/* Product rail */}
        <ProductRail
          products={products}
          activeProductId={activeProductId}
          onSwitch={switchProduct}
        />

        {/* Workstreams */}
        <WorkstreamsPanel
          workstreams={activeState.workstreams}
          objectives={activeState.objectives}
        />

        {/* Activity feed */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <ActivityFeed
            events={activeState.events}
            directives={directives[activeProductId] ?? []}
            hannahMessages={hannahMessages[activeProductId] ?? []}
            hannahDraft={hannahDraft}
          />
          <DirectiveBar
            onSend={sendDirective}
            disabled={connState !== 'ready'}
            productName={activeProduct?.name ?? 'this product'}
          />
        </div>

        {/* Review queue */}
        <ReviewQueue
          items={activeState.review_items.filter(i => i.status === 'pending')}
          onResolve={resolveReview}
        />

      </div>
    </div>
  )
}
