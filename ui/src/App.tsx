// ui/src/App.tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNotifications } from './hooks/useNotifications'
import { api } from './api'
import {
  Product,
  ProductState,
  ActivityEvent,
  ReviewItem,
  ServerMessage,
} from './types'
import SessionsPanel from './components/SessionsPanel'
import ActivityFeed from './components/ActivityFeed'
import DirectiveBar from './components/DirectiveBar'
import PasswordGate from './components/PasswordGate'
import NotesDrawer from './components/NotesDrawer'
import DirectiveHistoryDrawer from './components/DirectiveHistoryDrawer'
import ProductWizard from './components/ProductWizard'
import NavRail from './components/NavRail'
import { Section as NavSection } from './components/NavRail'
import OverviewPage from './components/OverviewPage'
import ProductPicker from './components/ProductPicker'
import ChiefPage from './components/ChiefPage'
import SettingsPage, { SettingsItem } from './components/SettingsPage'

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
  const [navSection,      setNavSection]      = useState<NavSection>('overview')
  const [settingsItem,    setSettingsItem]    = useState<SettingsItem>('general-workspace')

  const [wizardOpen,      setWizardOpen]      = useState(false)
  const [directivePrefill, setDirectivePrefill] = useState<string>('')
  const [notesOpen,       setNotesOpen]       = useState(false)
  const [historyOpen,     setHistoryOpen]     = useState(false)
  const [errorBanner,     setErrorBanner]     = useState<string | null>(null)

  type PendingWizardItem = { name: string; mission: string; schedule: string }
  type PendingWizardObj  = { text: string; progress_target: number | null }
  const pendingWizardRef = useRef<{ workstreams: PendingWizardItem[]; objectives: PendingWizardObj[] } | null>(null)

  const { requestPermission, notify } = useNotifications()

  const wsRef    = useRef<WebSocket | null>(null)
  const isMounted = useRef(true)
  const activeProductIdRef = useRef('')

  useEffect(() => { activeProductIdRef.current = activeProductId }, [activeProductId])

  const activeState = productStates[activeProductId] ?? EMPTY_STATE
  const activeProduct = products.find(p => p.id === activeProductId)
  const pendingReviewCount = Object.values(productStates)
    .flatMap(s => s.review_items)
    .filter(r => r.status === 'pending').length

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
        let saved: { productId?: string; navSection?: string; settingsItem?: string } | null = null
        try { saved = JSON.parse(localStorage.getItem('adjutant_last_view') ?? 'null') } catch {}
        const targetSection = (saved?.navSection as NavSection) ?? 'overview'
        setNavSection(targetSection)
        if (saved?.settingsItem) setSettingsItem(saved.settingsItem as SettingsItem)
        const targetId = (saved?.productId && msg.products.some((p: { id: string }) => p.id === saved!.productId))
          ? saved!.productId
          : msg.products[0]?.id
        if (targetId) {
          setActiveProductId(targetId)
          localStorage.setItem('adjutant_last_view', JSON.stringify({ navSection: targetSection, productId: targetId }))
          ws.send(JSON.stringify({ type: 'switch_product', product_id: targetId }))
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
        setNavSection('products')
        localStorage.setItem('adjutant_last_view', JSON.stringify({ navSection: 'products', productId: msg.product_id }))
        const pending = pendingWizardRef.current
        pendingWizardRef.current = null
        if (pending) {
          const savedPw = sessionStorage.getItem('agent_pw') ?? ''
          const pid: string = msg.product_id
          ;(async () => {
            for (const ws of pending.workstreams) {
              try {
                const created = await api.createWorkstream(savedPw, pid, ws.name)
                if (ws.mission || ws.schedule) {
                  await api.updateWorkstream(savedPw, created.id, { mission: ws.mission, schedule: ws.schedule })
                }
              } catch { /* best-effort */ }
            }
            for (const obj of pending.objectives) {
              try {
                await api.createObjective(savedPw, pid, obj.text, 0, obj.progress_target ?? undefined)
              } catch { /* best-effort */ }
            }
          })()
        }
        return
      }

      if (msg.type === 'queue_update') {
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
        setProductState(msg.product_id ?? '__global__', prev => {
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

      if (msg.type === 'hca_run_complete') {
        // review_items are updated via product_data; badge will refresh automatically
        return
      }

      if (msg.type === 'product_launched') {
        // Reload products list to show the new product (server responds with 'init')
        wsRef.current?.send(JSON.stringify({ type: 'get_products' }))
        return
      }

      if (msg.type === 'autonomy_config') {
        // handled by SettingsSidebar (Task 6)
        return
      }

      if ((msg as unknown as { type: string }).type === 'error') {
        const errMsg = (msg as unknown as { message: string }).message
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
    setNavSection('products')
    localStorage.setItem('adjutant_last_view', JSON.stringify({ navSection: 'products', productId }))
    if (!(productId in productStates)) {
      wsRef.current?.send(JSON.stringify({ type: 'switch_product', product_id: productId }))
    }
  }, [productStates])

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

  const openSettings = useCallback((item: string = 'general-workspace') => {
    setSettingsItem(item as SettingsItem)
    setNavSection('settings')
    const current = (() => { try { return JSON.parse(localStorage.getItem('adjutant_last_view') ?? 'null') } catch { return null } })()
    localStorage.setItem('adjutant_last_view', JSON.stringify({ ...current, navSection: 'settings', settingsItem: item }))
  }, [])


  if (connState === 'auth' || connState === 'connecting') {
    return <PasswordGate onSubmit={sendAuth} connecting={connState === 'connecting'} />
  }

  const pw = sessionStorage.getItem('agent_pw') ?? ''

  const liveAgents = (activeState.events ?? [])
    .filter(e => e.status === 'running')
    .map(e => ({
      productId: activeProductId,
      productName: activeProduct?.name ?? '',
      label: e.agent_type.charAt(0).toUpperCase() + e.agent_type.slice(1),
      elapsedSeconds: Math.floor((Date.now() - new Date(e.created_at.replace(' ', 'T') + (e.created_at.includes('Z') ? '' : 'Z')).getTime()) / 1000),
    }))

  return (
    <div className="flex h-full bg-adj-base text-adj-text-primary overflow-hidden">

      {/* Left nav rail */}
      <NavRail
        section={navSection}
        reviewBadgeCount={pendingReviewCount}
        agentInitial={agentName[0]?.toUpperCase() ?? 'A'}
        onNavigate={section => {
          setNavSection(section)
          const current = (() => { try { return JSON.parse(localStorage.getItem('adjutant_last_view') ?? 'null') } catch { return null } })()
          localStorage.setItem('adjutant_last_view', JSON.stringify({ ...current, navSection: section }))
        }}
      />

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">

        {/* Error banner */}
        {errorBanner && (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-red-950/60 border-b border-red-900/60 text-red-300 text-sm flex-shrink-0">
            <span className="text-red-400 flex-shrink-0">⚠</span>
            <span className="flex-1 font-mono text-xs leading-relaxed">{errorBanner}</span>
            <button onClick={() => setErrorBanner(null)} aria-label="Dismiss" className="flex-shrink-0 text-red-500 hover:text-red-300 text-base leading-none">×</button>
          </div>
        )}

        {/* Section routing */}
        {navSection === 'overview' && (
          <OverviewPage
            products={products}
            productStates={productStates}
            password={pw}
            onOpenProduct={productId => {
              switchProduct(productId)
            }}
          />
        )}

        {navSection === 'products' && !activeProductId && (
          <ProductPicker
            products={products}
            productStates={productStates}
            onSelect={switchProduct}
            onNewProduct={() => setWizardOpen(true)}
          />
        )}

        {navSection === 'products' && activeProductId && (
          <div className="flex flex-1 overflow-hidden">
            <div className="flex flex-col border-r border-adj-border w-52 flex-shrink-0 bg-adj-panel">
              <SessionsPanel
                productName={activeProduct?.name ?? ''}
                sessions={activeState.sessions}
                activeSessionId={activeState.activeSessionId}
                liveAgents={liveAgents}
                onCreate={createSession}
                onSwitch={switchSession}
                onRename={renameSession}
                onDelete={deleteSession}
              />
            </div>

            <div className="flex flex-col flex-1 overflow-hidden bg-adj-base">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-adj-border flex-shrink-0">
                <span className="text-[13px] font-medium text-adj-text-primary">
                  {activeState.sessions.find(s => s.id === activeState.activeSessionId)?.name ?? 'Session'}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => { setNotesOpen(o => !o); setHistoryOpen(false) }}
                    className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors"
                  >
                    📝 Notes
                  </button>
                  <button
                    onClick={() => { setHistoryOpen(o => !o); setNotesOpen(false) }}
                    className="text-[10px] text-adj-text-faint bg-adj-elevated border border-adj-border rounded px-2 py-1 hover:text-adj-text-secondary transition-colors"
                  >
                    📜 History
                  </button>
                </div>
              </div>
              <ActivityFeed
                productId={activeProductId}
                password={pw}
                events={activeState.events}
                directives={directives[activeProductId] ?? []}
                agentMessages={agentMessages[activeProductId] ?? []}
                agentDraft={agentDraftByProduct[activeProductId] ?? ''}
                agentName={agentName}
                reviewItems={activeState.review_items}
                onApprove={id => resolveReview(id, 'approved')}
                onSkip={id => resolveReview(id, 'skipped')}
              />
              <DirectiveBar
                onSend={sendDirective}
                disabled={connState !== 'ready'}
                productName={activeProduct?.name ?? 'this product'}
                agentName={agentName}
                prefill={directivePrefill}
                onPrefillConsumed={() => setDirectivePrefill('')}
                password={pw}
                templatesProductId={activeProductId}
                templatesPassword={pw}
              />
            </div>
          </div>
        )}

        {navSection === 'chief' && (
          <ChiefPage
            password={pw}
            reviewItems={Object.values(productStates).flatMap(s => s.review_items)}
            onResolveReview={resolveReview}
            onOpenSettings={() => openSettings('system-chief')}
          />
        )}

        {navSection === 'settings' && (
          <SettingsPage
            products={products}
            activeProductId={activeProductId}
            productStates={productStates}
            password={pw}
            initialTab={settingsItem}
            onClose={() => setNavSection('overview')}
            onSwitchProduct={switchProduct}
            onNewProduct={() => { setNavSection('overview'); setWizardOpen(true) }}
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
            onProductDeleted={productId => {
              setProducts(prev => prev.filter(p => p.id !== productId))
              setProductStates(prev => { const next = { ...prev }; delete next[productId]; return next })
              if (activeProductId === productId) setActiveProductId('')
              setNavSection('overview')
            }}
          />
        )}
      </div>

      {/* Drawers */}
      {notesOpen && <NotesDrawer productId={activeProductId} password={pw} onClose={() => setNotesOpen(false)} />}
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
          onComplete={({ name, intent, workstreams, objectives }) => {
            pendingWizardRef.current = {
              workstreams: workstreams.map(w => ({ name: w.name, mission: w.mission, schedule: w.schedule })),
              objectives:  objectives.map(o => ({ text: o.text, progress_target: o.progress_target })),
            }
            setWizardOpen(false)
            launchProduct(name, intent, intent)
          }}
          onClose={() => setWizardOpen(false)}
        />
      )}
    </div>
  )
}
