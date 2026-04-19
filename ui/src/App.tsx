// ui/src/App.tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNotifications } from './hooks/useNotifications'
import { api } from './api'
import {
  Product,
  ProductState,
  ActivityEvent,
  DirectiveItem,
  ReviewItem,
  ServerMessage,
} from './types'
import SessionsPanel from './components/SessionsPanel'
import ActivityFeed from './components/ActivityFeed'
import DirectiveBar from './components/DirectiveBar'
import DirectiveTemplates from './components/DirectiveTemplates'
import LiveAgents from './components/LiveAgents'
import PasswordGate from './components/PasswordGate'
import NotesDrawer from './components/NotesDrawer'
import DirectiveHistoryDrawer from './components/DirectiveHistoryDrawer'
import OverviewPanel from './components/OverviewPanel'
import ProductDropdown from './components/ProductDropdown'
import StatusStrip from './components/StatusStrip'
import SettingsPage, { Tab as SettingsTab } from './components/SettingsPage'
import ProductWizard from './components/ProductWizard'

type ConnState = 'connecting' | 'auth' | 'ready' | 'disconnected'

interface DirectiveEntry { type: 'directive'; content: string; ts: string }
interface AgentEntry    { type: 'agent';     content: string; ts: string }

// Per-product UI state
const EMPTY_STATE: ProductState = {
  workstreams:     [],
  objectives:      [],
  events:          [],
  review_items:    [],
  sessions:        [],
  activeSessionId: null,
}

export default function App() {
  const [connState,       setConnState]       = useState<ConnState>('connecting')
  const [products,        setProducts]        = useState<Product[]>([])
  const [activeProductId, setActiveProductId] = useState<string>('')
  const [productStates,   setProductStates]   = useState<Record<string, ProductState>>({})
  const [directives,      setDirectives]      = useState<Record<string, DirectiveEntry[]>>({})
  const [agentMessages,   setAgentMessages]   = useState<Record<string, AgentEntry[]>>({})
  const [agentDraftByProduct, setAgentDraftByProduct] = useState<Record<string, string>>({})
  const [agentName,       setAgentName]       = useState<string>('Adjutant')
  const [settingsOpen,    setSettingsOpen]    = useState(false)
  const [settingsTab,     setSettingsTab]     = useState<SettingsTab>('overview')
  const [wizardOpen,      setWizardOpen]      = useState(false)
  const [queueByProduct,  setQueueByProduct]  = useState<Record<string, { current: DirectiveItem | null; queued: DirectiveItem[] }>>({})
  const [directivePrefill, setDirectivePrefill] = useState<string>('')
  const [notesOpen,       setNotesOpen]       = useState(false)
  const [historyOpen,     setHistoryOpen]     = useState(false)
  const [showOverview,    setShowOverview]    = useState(false)
  const [globalViewMode,  setGlobalViewMode]  = useState<'chat' | 'overview'>('overview')
  const [errorBanner,     setErrorBanner]     = useState<string | null>(null)

  const { requestPermission, notify } = useNotifications()

  const wsRef    = useRef<WebSocket | null>(null)
  const isMounted = useRef(true)
  const activeProductIdRef = useRef('')

  useEffect(() => { activeProductIdRef.current = activeProductId }, [activeProductId])

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
        // null product_id means global/top-level — map to '__global__' key
        const key = msg.product_id ?? '__global__'
        setProductState(key, prev => ({
          ...prev,
          workstreams:          msg.workstreams,
          objectives:           msg.objectives,
          events:               msg.events,
          review_items:         msg.review_items,
          sessions:             msg.sessions ?? [],
          activeSessionId:      msg.active_session_id ?? null,
          launch_wizard_active: msg.launch_wizard_active ?? 0,
        }))
        if (msg.chat_history?.length) {
          const dirs: DirectiveEntry[] = msg.chat_history
            .filter(e => e.type === 'directive')
            .map(e => ({ type: 'directive' as const, content: e.content, ts: e.ts }))
          const agents: AgentEntry[] = msg.chat_history
            .filter(e => e.type === 'agent')
            .map(e => ({ type: 'agent' as const, content: e.content, ts: e.ts }))
          setDirectives(prev => ({ ...prev, [key]: dirs }))
          setAgentMessages(prev => ({ ...prev, [key]: agents }))
        }
        return
      }

      if (msg.type === 'directive_echo') {
        const key = msg.product_id ?? '__global__'
        setDirectives(prev => ({
          ...prev,
          [key]: [...(prev[key] ?? []), { type: 'directive', content: msg.content, ts: msg.ts }],
        }))
        return
      }

      if (msg.type === 'agent_token') {
        const key = msg.product_id ?? '__global__'
        setAgentDraftByProduct(prev => ({
          ...prev,
          [key]: (prev[key] ?? '') + msg.content,
        }))
        return
      }

      if (msg.type === 'agent_done') {
        const key = msg.product_id ?? '__global__'
        setAgentDraftByProduct(prev => ({ ...prev, [key]: '' }))
        setAgentMessages(prev => ({
          ...prev,
          [key]: [...(prev[key] ?? []), { type: 'agent', content: msg.content, ts: msg.ts }],
        }))
        return
      }

      if (msg.type === 'activity_started') {
        const key = msg.product_id ?? '__global__'
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
        setProductState(key, prev => ({
          ...prev,
          events: [...prev.events, newEvent],
        }))
        return
      }

      if (msg.type === 'activity_done') {
        const key = msg.product_id ?? '__global__'
        setProductState(key, prev => ({
          ...prev,
          events: prev.events.map(ev =>
            ev.id === msg.id ? { ...ev, status: 'done' as const, summary: msg.summary } : ev
          ),
        }))
        notify('Agent complete', msg.summary?.slice(0, 80))
        return
      }

      if (msg.type === 'review_item_added') {
        const key = msg.product_id ?? '__global__'
        setProductState(key, prev => ({
          ...prev,
          review_items: [...prev.review_items, msg.item],
        }))
        notify(`Review needed: ${msg.item.title}`, msg.item.description?.slice(0, 80))
        return
      }

      if (msg.type === 'wizard_progress') {
        return
      }

      if (msg.type === 'launch_complete') {
        return
      }

      if (msg.type === 'launch_started') {
        setActiveProductId(msg.product_id)
        setShowOverview(false)
        return
      }

      if (msg.type === 'queue_update') {
        const key = msg.product_id ?? '__global__'
        setQueueByProduct(prev => ({
          ...prev,
          [key]: { current: msg.current, queued: msg.queued },
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

      if (msg.type === 'review_item_updated') {
        setProductState(msg.product_id, prev => {
          const exists = prev.review_items.some((i: ReviewItem) => i.id === msg.item.id)
          return {
            ...prev,
            review_items: exists
              ? prev.review_items.map((i: ReviewItem) =>
                  i.id === msg.item.id ? { ...i, ...msg.item } : i
                )
              : [...prev.review_items, msg.item],
          }
        })
        return
      }

      if (msg.type === 'session_created') {
        // Use product_id from the session object — activeProductId is stale in this closure
        const pid = msg.session.product_id ?? activeProductIdRef.current
        setProductState(pid, prev => ({
          ...prev,
          sessions:        [msg.session, ...prev.sessions],
          activeSessionId: msg.session.id,
        }))
        return
      }

      if (msg.type === 'session_switched') {
        // session_switched is sent only to the originating connection; use ref for current product
        const pid = activeProductIdRef.current
        setProductState(pid, prev => ({
          ...prev,
          activeSessionId: msg.session_id,
        }))
        const dirs: DirectiveEntry[] = msg.chat_history
          .filter(e => e.type === 'directive')
          .map(e => ({ type: 'directive' as const, content: e.content, ts: e.ts }))
        const agents: AgentEntry[] = msg.chat_history
          .filter(e => e.type === 'agent')
          .map(e => ({ type: 'agent' as const, content: e.content, ts: e.ts }))
        setDirectives(prev => ({ ...prev, [pid]: dirs }))
        setAgentMessages(prev => ({ ...prev, [pid]: agents }))
        return
      }

      if (msg.type === 'session_renamed') {
        // Broadcast: apply rename to whichever product holds this session (no-op for others)
        setProductStates(prev => {
          const next = { ...prev }
          for (const pid of Object.keys(next)) {
            if (next[pid].sessions.some(s => s.id === msg.session_id)) {
              next[pid] = {
                ...next[pid],
                sessions: next[pid].sessions.map(s =>
                  s.id === msg.session_id ? { ...s, name: msg.name } : s
                ),
              }
            }
          }
          return next
        })
        return
      }

      if (msg.type === 'session_deleted') {
        // Broadcast: remove session from whichever product holds it
        setProductStates(prev => {
          const next = { ...prev }
          for (const pid of Object.keys(next)) {
            if (next[pid].sessions.some(s => s.id === msg.session_id)) {
              next[pid] = {
                ...next[pid],
                sessions: next[pid].sessions.filter(s => s.id !== msg.session_id),
                activeSessionId: next[pid].activeSessionId === msg.session_id
                  ? msg.next_session_id
                  : next[pid].activeSessionId,
              }
            }
          }
          return next
        })
        return
      }

      if (msg.type === 'autonomy_config') {
        // handled by SettingsSidebar (Task 6)
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

  const switchToGlobal = useCallback(() => {
    setActiveProductId('__global__')
    setShowOverview(true)
    // Always resend so server updates active_product_id and active_session_id
    wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: null }))
  }, [])

  const sendDirective = useCallback((content: string, attachments?: Array<{ path: string; mime_type: string; name: string }>) => {
    const prodId = activeProductId === '__global__' ? null : activeProductId
    wsRef.current?.send(JSON.stringify({
      type: 'directive',
      product_id: prodId,
      session_id: productStates[activeProductId]?.activeSessionId ?? null,
      content,
      attachments: attachments ?? [],
    }))
  }, [activeProductId, productStates])

  const cancelDirective = useCallback((directiveId: string) => {
    const prodId = activeProductId === '__global__' ? null : activeProductId
    wsRef.current?.send(JSON.stringify({
      type: 'cancel_directive',
      product_id: prodId,
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

  const createSession = useCallback((name: string) => {
    const prodId = activeProductId === '__global__' ? null : activeProductId
    wsRef.current?.send(JSON.stringify({
      type: 'create_session',
      name,
      product_id: prodId,
    }))
  }, [activeProductId])

  const switchSession = useCallback((sessionId: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'switch_session', session_id: sessionId }))
  }, [])

  const renameSession = useCallback((sessionId: string, name: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'rename_session', session_id: sessionId, name }))
  }, [])

  const deleteSession = useCallback((sessionId: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'delete_session', session_id: sessionId }))
  }, [])

  const launchProduct = useCallback((name: string, description: string, primaryGoal: string) => {
    wsRef.current?.send(JSON.stringify({
      type: 'launch_product',
      name,
      description,
      primary_goal: primaryGoal,
    }))
  }, [])

  const openSettings = useCallback((tab: string = 'overview') => {
    setSettingsTab(tab as SettingsTab)
    setSettingsOpen(true)
  }, [])

  if (connState === 'auth' || connState === 'connecting') {
    return <PasswordGate onSubmit={sendAuth} connecting={connState === 'connecting'} />
  }

  const pw = sessionStorage.getItem('agent_pw') ?? ''

  return (
    <div className="flex flex-col h-full bg-adj-base text-adj-text-primary overflow-hidden">

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
      <header className="flex items-center gap-3 px-5 h-12 border-b border-adj-border flex-shrink-0 bg-adj-surface">
        {/* Logo */}
        <span className="w-7 h-7 rounded-lg bg-adj-accent text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
          {agentName[0]?.toUpperCase() ?? 'A'}
        </span>
        <span className="w-px h-4 bg-adj-border flex-shrink-0" />

        {/* Product dropdown — always visible, includes Overview entry */}
        {!settingsOpen && (
          <ProductDropdown
            products={products}
            activeProductId={activeProductId}
            showingOverview={showOverview}
            onSelect={switchProduct}
            onOverview={switchToGlobal}
            onNewProduct={() => setWizardOpen(true)}
          />
        )}
        {settingsOpen && (
          <span className="text-sm font-semibold text-adj-text-muted">Settings</span>
        )}

        <div className="ml-auto flex items-center gap-2">
          {/* Connection status */}
          <span className={`flex items-center gap-1.5 text-xs ${connState === 'ready' ? 'text-green-500' : 'text-adj-text-faint'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connState === 'ready' ? 'bg-green-500' : 'bg-adj-text-faint'}`} />
            {connState === 'ready' ? 'connected' : 'disconnected'}
          </span>

          {/* Notes */}
          <button
            onClick={() => { setNotesOpen(o => !o); setHistoryOpen(false) }}
            title="Product notes"
            className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${notesOpen ? 'text-adj-text-primary bg-adj-elevated' : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'}`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>

          {/* History */}
          <button
            onClick={() => { setHistoryOpen(o => !o); setNotesOpen(false) }}
            title="Directive history"
            className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${historyOpen ? 'text-adj-text-primary bg-adj-elevated' : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'}`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>

          {/* Settings */}
          <button
            onClick={() => openSettings()}
            title="Settings"
            className="w-7 h-7 flex items-center justify-center rounded bg-adj-elevated border border-adj-accent text-adj-accent hover:bg-adj-accent hover:text-white transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      {/* Status strip — shown only in product workspace, not overview or settings */}
      {!showOverview && !settingsOpen && (
        <StatusStrip
          workstreams={activeState.workstreams}
          reviewItems={activeState.review_items}
          events={activeState.events}
          objectives={activeState.objectives}
          onResolveReview={resolveReview}
          onCancelAgent={cancelDirective}
          onOpenSettings={openSettings}
        />
      )}

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {settingsOpen ? (
          <SettingsPage
            products={products}
            activeProductId={activeProductId}
            productStates={productStates}
            password={pw}
            initialTab={settingsTab}
            onClose={() => setSettingsOpen(false)}
            onSwitchProduct={switchProduct}
            onNewProduct={() => { setSettingsOpen(false); setWizardOpen(true) }}
            onRefreshData={pid => wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: pid }))}
            onWorkstreamUpdated={(wsId, patch) =>
              setProductState(activeProductId, prev => ({
                ...prev,
                workstreams: prev.workstreams.map(ws => ws.id === wsId ? { ...ws, ...patch } : ws),
              }))
            }
            onObjectiveUpdated={(objId, patch) =>
              setProductState(activeProductId, prev => ({
                ...prev,
                objectives: patch.text === ''
                  ? prev.objectives.filter(o => o.id !== objId)
                  : prev.objectives.map(o => o.id === objId ? { ...o, ...patch } : o),
              }))
            }
            onProductUpdated={(productId, updates) =>
              setProducts(prev => prev.map(p => p.id === productId ? { ...p, ...updates } : p))
            }
          />
        ) : showOverview ? (
          <div className="flex flex-1 overflow-hidden">
            {/* Left: global sessions + mode toggle */}
            <div className="flex flex-col border-r border-zinc-800/60 w-48 flex-shrink-0">
              <SessionsPanel
                sessions={productStates['__global__']?.sessions ?? []}
                activeSessionId={productStates['__global__']?.activeSessionId ?? null}
                onCreate={createSession}
                onSwitch={switchSession}
                onRename={renameSession}
                onDelete={deleteSession}
              />
              <div className="flex border-t border-zinc-800/60 flex-shrink-0">
                <button
                  onClick={() => setGlobalViewMode('overview')}
                  className={`flex-1 text-[10px] py-2 transition-colors ${
                    globalViewMode === 'overview'
                      ? 'text-blue-400 bg-blue-600/10'
                      : 'text-zinc-600 hover:text-zinc-400'
                  }`}
                >Overview</button>
                <button
                  onClick={() => setGlobalViewMode('chat')}
                  className={`flex-1 text-[10px] py-2 transition-colors ${
                    globalViewMode === 'chat'
                      ? 'text-blue-400 bg-blue-600/10'
                      : 'text-zinc-600 hover:text-zinc-400'
                  }`}
                >Chat</button>
              </div>
            </div>

            {globalViewMode === 'overview' ? (
              <OverviewPanel password={pw} onSelectProduct={switchProduct} />
            ) : (
              <div className="flex-1 flex flex-col overflow-hidden">
                {productStates['__global__']?.activeSessionId && (
                  <div className="flex items-center px-4 py-1 border-b border-zinc-800/30">
                    <span className="text-[10px] text-zinc-600 ml-auto">
                      {productStates['__global__']?.sessions.find(
                        s => s.id === productStates['__global__']?.activeSessionId
                      )?.name ?? ''} session
                    </span>
                  </div>
                )}
                <ActivityFeed
                  events={[]}
                  directives={directives['__global__'] ?? []}
                  agentMessages={agentMessages['__global__'] ?? []}
                  agentDraft={agentDraftByProduct['__global__'] ?? ''}
                  agentName={agentName}
                />
                <DirectiveBar
                  onSend={sendDirective}
                  disabled={connState !== 'ready'}
                  productName={agentName}
                  agentName={agentName}
                  prefill={directivePrefill}
                  onPrefillConsumed={() => setDirectivePrefill('')}
                  password={pw}
                />
              </div>
            )}
          </div>
        ) : (
          /* Product workspace — two column */
          <div className="flex flex-1 overflow-hidden">
            {/* Left: sessions only */}
            <div className="flex flex-col border-r border-adj-border w-52 flex-shrink-0 bg-adj-panel">
              <SessionsPanel
                sessions={activeState.sessions}
                activeSessionId={activeState.activeSessionId}
                onCreate={createSession}
                onSwitch={switchSession}
                onRename={renameSession}
                onDelete={deleteSession}
              />
            </div>

            {/* Center: full-width activity feed */}
            <div className="flex-1 flex flex-col overflow-hidden bg-adj-base">
              {activeState.activeSessionId && (
                <div className="flex items-center px-4 py-1 border-b border-adj-border">
                  <span className="text-[10px] text-adj-text-faint ml-auto">
                    {activeState.sessions.find(s => s.id === activeState.activeSessionId)?.name ?? ''} session
                  </span>
                </div>
              )}
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
                agentDraft={agentDraftByProduct[activeProductId] ?? ''}
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
          </div>
        )}
      </div>

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

      {wizardOpen && (
        <ProductWizard
          password={pw}
          onComplete={({ name, intent }) => {
            // icon/color/workstreams/objectives not yet consumed by backend launch_product
            setWizardOpen(false)
            launchProduct(name, intent, intent)
          }}
          onClose={() => setWizardOpen(false)}
        />
      )}
    </div>
  )
}
