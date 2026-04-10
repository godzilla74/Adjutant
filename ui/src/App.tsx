// ui/src/App.tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNotifications } from './hooks/useNotifications'
import { api } from './api'
import {
  Product,
  ProductState,
  ActivityEvent,
  DirectiveItem,
  ServerMessage,
} from './types'
import ProductRail from './components/ProductRail'
import WorkstreamsPanel from './components/WorkstreamsPanel'
import ActivityFeed from './components/ActivityFeed'
import ReviewQueue from './components/ReviewQueue'
import DirectiveBar from './components/DirectiveBar'
import DirectiveTemplates from './components/DirectiveTemplates'
import LiveAgents from './components/LiveAgents'
import PasswordGate from './components/PasswordGate'
import SettingsSidebar from './components/SettingsSidebar'
import NotesDrawer from './components/NotesDrawer'
import DirectiveHistoryDrawer from './components/DirectiveHistoryDrawer'
import OverviewPanel from './components/OverviewPanel'

type ConnState = 'connecting' | 'auth' | 'ready' | 'disconnected'

interface DirectiveEntry { type: 'directive'; content: string; ts: string }
interface AgentEntry    { type: 'agent';     content: string; ts: string }

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
  const [activeProductId, setActiveProductId] = useState<string>('')
  const [productStates,   setProductStates]   = useState<Record<string, ProductState>>({})
  const [directives,      setDirectives]      = useState<Record<string, DirectiveEntry[]>>({})
  const [agentMessages,   setAgentMessages]   = useState<Record<string, AgentEntry[]>>({})
  const [agentDraft,      setAgentDraft]      = useState<string>('')
  const [agentName,       setAgentName]       = useState<string>('Adjutant')
  const [settingsOpen,    setSettingsOpen]    = useState(false)
  const [queueByProduct,  setQueueByProduct]  = useState<Record<string, { current: DirectiveItem | null; queued: DirectiveItem[] }>>({})
  const [directivePrefill, setDirectivePrefill] = useState<string>('')
  const [notesOpen,    setNotesOpen]    = useState(false)
  const [historyOpen,  setHistoryOpen]  = useState(false)
  const [showOverview, setShowOverview] = useState(false)
  const [errorBanner,  setErrorBanner]  = useState<string | null>(null)

  const { requestPermission, notify } = useNotifications()

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

    ws.onopen = () => {
      const saved = sessionStorage.getItem('agent_pw')
      if (saved) {
        ws.send(JSON.stringify({ type: 'auth', password: saved }))
      } else {
        setConnState('auth')
      }
    }

    ws.onmessage = (e) => {
      const msg: ServerMessage = JSON.parse(e.data)

      if (msg.type === 'auth_ok') {
        setConnState('ready')
        requestPermission()
        const saved = sessionStorage.getItem('agent_pw') ?? ''
        api.getAgentConfig(saved).then(cfg => {
          setAgentName(cfg.agent_name)
          document.title = cfg.agent_name
        }).catch(() => {})
        return
      }
      if (msg.type === 'auth_fail') {
        sessionStorage.removeItem('agent_pw')
        setConnState('auth')
        return
      }

      if (msg.type === 'init') {
        setProducts(msg.products)
        const defaultId = msg.products[0]?.id
        if (defaultId) {
          setActiveProductId(defaultId)
          ws.send(JSON.stringify({ type: 'switch_product', product_id: defaultId }))
        }
        return
      }

      if (msg.type === 'product_data') {
        setProductState(msg.product_id, () => ({
          workstreams: msg.workstreams,
          objectives: msg.objectives,
          events: msg.events,
          review_items: msg.review_items,
        }))
        if (msg.chat_history?.length) {
          const dirs: DirectiveEntry[] = msg.chat_history
            .filter(e => e.type === 'directive')
            .map(e => ({ type: 'directive' as const, content: e.content, ts: e.ts }))
          const agents: AgentEntry[] = msg.chat_history
            .filter(e => e.type === 'agent')
            .map(e => ({ type: 'agent' as const, content: e.content, ts: e.ts }))
          setDirectives(prev => ({ ...prev, [msg.product_id]: dirs }))
          setAgentMessages(prev => ({ ...prev, [msg.product_id]: agents }))
        }
        return
      }

      if (msg.type === 'directive_echo') {
        setDirectives(prev => ({
          ...prev,
          [msg.product_id]: [...(prev[msg.product_id] ?? []), { type: 'directive', content: msg.content, ts: msg.ts }],
        }))
        return
      }

      if (msg.type === 'agent_token') {
        setAgentDraft(prev => prev + msg.content)
        return
      }

      if (msg.type === 'agent_done') {
        setAgentDraft('')
        setAgentMessages(prev => ({
          ...prev,
          [msg.product_id]: [...(prev[msg.product_id] ?? []), { type: 'agent', content: msg.content, ts: msg.ts }],
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
        notify('Agent complete', msg.summary?.slice(0, 80))
        return
      }

      if (msg.type === 'review_item_added') {
        setProductState(msg.product_id, prev => ({
          ...prev,
          review_items: [...prev.review_items, msg.item],
        }))
        notify(`Review needed: ${msg.item.title}`, msg.item.description?.slice(0, 80))
        return
      }

      if (msg.type === 'queue_update') {
        setQueueByProduct(prev => ({
          ...prev,
          [msg.product_id]: { current: msg.current, queued: msg.queued },
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

      if ((msg as { type: string }).type === 'error') {
        const errMsg = (msg as { type: string; message: string }).message
        console.error('Server error:', errMsg)
        setErrorBanner(errMsg)
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
    sessionStorage.setItem('agent_pw', password)
    wsRef.current?.send(JSON.stringify({ type: 'auth', password }))
  }, [])

  const switchProduct = useCallback((productId: string) => {
    setActiveProductId(productId)
    setShowOverview(false)
    if (!(productId in productStates)) {
      wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: productId }))
    }
  }, [productStates])

  const sendDirective = useCallback((content: string, attachments?: Array<{ path: string; mime_type: string; name: string }>) => {
    wsRef.current?.send(JSON.stringify({
      type: 'directive',
      product_id: activeProductId,
      content,
      attachments: attachments ?? [],
    }))
  }, [activeProductId])

  const cancelDirective = useCallback((directiveId: string) => {
    wsRef.current?.send(JSON.stringify({
      type: 'cancel_directive',
      product_id: activeProductId,
      directive_id: directiveId,
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

  const pw = sessionStorage.getItem('agent_pw') ?? ''

  // Header stats
  const activeAgentCount = activeState.events.filter(e => e.status === 'running').length
  const reviewCount      = activeState.review_items.filter(i => i.status === 'pending').length

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden">

      {/* Error banner */}
      {errorBanner && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-red-950/60 border-b border-red-900/60 text-red-300 text-sm flex-shrink-0">
          <span className="text-red-400 flex-shrink-0">⚠</span>
          <span className="flex-1 font-mono text-xs leading-relaxed">{errorBanner}</span>
          <button
            onClick={() => setErrorBanner(null)}
            className="flex-shrink-0 text-red-500 hover:text-red-300 transition-colors text-base leading-none"
            aria-label="Dismiss"
          >×</button>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between pl-0 pr-5 h-12 border-b border-zinc-800/60 flex-shrink-0 bg-zinc-950">
        <div className="flex items-center h-full">
          {/* Rail spacer */}
          <div className="w-14 h-full border-r border-zinc-800/60 flex items-center justify-center flex-shrink-0">
            <span className="w-7 h-7 rounded-lg bg-blue-600 text-white text-xs font-bold flex items-center justify-center">{agentName[0]?.toUpperCase() ?? 'A'}</span>
          </div>
          <div className="flex items-center gap-2 pl-4">
            <span className="font-semibold text-zinc-100 text-sm">{agentName}</span>
            <span className="text-zinc-700">/</span>
            <span className="text-sm text-zinc-400">{activeProduct?.name ?? '…'}</span>
            {/* Notes button */}
            <button
              onClick={() => { setNotesOpen(o => !o); setHistoryOpen(false) }}
              title="Product notes"
              className={`ml-1 w-6 h-6 flex items-center justify-center rounded transition-colors ${notesOpen ? 'text-zinc-200 bg-zinc-800' : 'text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800'}`}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            {/* Directive history button */}
            <button
              onClick={() => { setHistoryOpen(o => !o); setNotesOpen(false) }}
              title="Directive history"
              className={`ml-1 w-6 h-6 flex items-center justify-center rounded transition-colors ${historyOpen ? 'text-zinc-200 bg-zinc-800' : 'text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800'}`}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
            <button
              onClick={() => setSettingsOpen(o => !o)}
              title="Product settings"
              className="ml-1 w-6 h-6 flex items-center justify-center rounded text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
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
          activeProductId={showOverview ? '__overview__' : activeProductId}
          onSwitch={switchProduct}
          onOverview={() => setShowOverview(true)}
        />

        {showOverview ? (
          <OverviewPanel
            password={pw}
            onSelectProduct={switchProduct}
          />
        ) : (
          <>
            {/* Workstreams */}
            <WorkstreamsPanel
              workstreams={activeState.workstreams}
              objectives={activeState.objectives}
              password={pw}
              onWorkstreamUpdated={(wsId, patch) => {
                setProductState(activeProductId, prev => ({
                  ...prev,
                  workstreams: prev.workstreams.map(ws =>
                    ws.id === wsId ? { ...ws, ...patch } : ws
                  ),
                }))
              }}
            />

            {/* Activity feed */}
            <div className="flex-1 flex flex-col overflow-hidden">
              <LiveAgents
                events={activeState.events}
                currentDirective={queueByProduct[activeProductId]?.current ?? null}
                onCancelDirective={cancelDirective}
                agentName={agentName}
              />
              <ActivityFeed
                events={activeState.events}
                directives={directives[activeProductId] ?? []}
                agentMessages={agentMessages[activeProductId] ?? []}
                agentDraft={agentDraft}
                agentName={agentName}
              />
              <DirectiveTemplates
                productId={activeProductId}
                password={pw}
                onSelect={content => setDirectivePrefill(content)}
              />
              <DirectiveBar
                onSend={sendDirective}
                disabled={connState !== 'ready'}
                productName={activeProduct?.name ?? 'this product'}
                agentName={agentName}
                prefill={directivePrefill}
                onPrefillConsumed={() => setDirectivePrefill('')}
                password={pw}
              />
            </div>

            {/* Review queue */}
            <ReviewQueue
              items={activeState.review_items.filter(i => i.status === 'pending')}
              onResolve={resolveReview}
              queued={queueByProduct[activeProductId]?.queued ?? []}
              onCancelQueued={cancelDirective}
              agentName={agentName}
            />
          </>
        )}

      </div>

      {/* Settings sidebar */}
      {settingsOpen && (
        <SettingsSidebar
          productId={activeProductId}
          workstreams={activeState.workstreams}
          objectives={activeState.objectives}
          password={pw}
          onClose={() => setSettingsOpen(false)}
          onRefreshData={() => wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: activeProductId }))}
          onRefreshProducts={() => wsRef.current?.send(JSON.stringify({ type: 'get_products' }))}
        />
      )}

      {/* Notes drawer */}
      {notesOpen && (
        <NotesDrawer
          productId={activeProductId}
          password={pw}
          onClose={() => setNotesOpen(false)}
        />
      )}

      {/* Directive history drawer */}
      {historyOpen && (
        <DirectiveHistoryDrawer
          productId={activeProductId}
          password={pw}
          onClose={() => setHistoryOpen(false)}
          onSelect={content => { setDirectivePrefill(content); setHistoryOpen(false) }}
        />
      )}
    </div>
  )
}
