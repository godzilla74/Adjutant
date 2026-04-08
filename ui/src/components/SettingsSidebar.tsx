// ui/src/components/SettingsSidebar.tsx
import { useEffect, useRef, useState } from 'react'
import { ProductConfig, Workstream, Objective } from '../types'
import { api } from '../api'

interface Props {
  productId: string
  workstreams: Workstream[]
  objectives: Objective[]
  password: string
  onClose: () => void
  onRefreshData: () => void     // re-fetch product_data (workstreams/objectives)
  onRefreshProducts: () => void // re-fetch products list (name/color changed)
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  running: 'Live',
  warn:    'Warn',
  paused:  'Off',
}
const STATUS_COLORS: Record<string, string> = {
  running: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  warn:    'bg-amber-500/20 text-amber-400 border-amber-500/40',
  paused:  'bg-zinc-700/40 text-zinc-500 border-zinc-700',
}
const STATUS_CYCLE: Record<string, 'running' | 'warn' | 'paused'> = {
  running: 'warn',
  warn:    'paused',
  paused:  'running',
}

function SectionHeader({
  title,
  open,
  onToggle,
  action,
}: {
  title: string
  open: boolean
  onToggle: () => void
  action?: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/60">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 text-xs font-semibold text-zinc-400 uppercase tracking-widest hover:text-zinc-200 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        {title}
      </button>
      {action}
    </div>
  )
}

function Field({
  label, value, onChange, placeholder, textarea,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  textarea?: boolean
}) {
  const cls = 'w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-600 transition-colors resize-none'
  return (
    <div>
      <label className="block text-xs text-zinc-500 mb-1">{label}</label>
      {textarea ? (
        <textarea
          rows={3}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={cls}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={cls}
        />
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SettingsSidebar({
  productId, workstreams, objectives, password, onClose, onRefreshData, onRefreshProducts,
}: Props) {
  const [loadError, setLoadError] = useState('')

  // Section open state
  const [infoOpen,    setInfoOpen]    = useState(true)
  const [brandOpen,   setBrandOpen]   = useState(false)
  const [modelsOpen,  setModelsOpen]  = useState(false)
  const [wsOpen,      setWsOpen]      = useState(true)
  const [objOpen,     setObjOpen]     = useState(true)

  // Remote Access
  const [remoteOpen,       setRemoteOpen]       = useState(false)
  const [telegramStatus,   setTelegramStatus]   = useState<{
    configured: boolean
    connected: boolean
    bot_username: string | null
  } | null>(null)

  // MCP Servers
  const [mcpOpen,        setMcpOpen]        = useState(false)
  const [mcpServers,     setMcpServers]      = useState<{
    id: number; name: string; type: string; url: string | null;
    command: string | null; scope: string; product_id: string | null; enabled: number;
  }[]>([])
  const [mcpProductFilter, setMcpProductFilter] = useState<string>('')
  const [mcpAddForm, setMcpAddForm] = useState<{
    scope: 'global' | 'product'; name: string; type: 'remote' | 'stdio';
    url: string; command: string; args: string; product_id: string;
  }>({ scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', product_id: '' })
  const [mcpAddOpen, setMcpAddOpen] = useState<'global' | 'product' | null>(null)

  // Product info form
  const [name,      setName]      = useState('')
  const [iconLabel, setIconLabel] = useState('')
  const [color,     setColor]     = useState('#2563eb')
  const [infoSaving, setInfoSaving] = useState(false)

  // Agent config
  const [agentModel,        setAgentModel]        = useState('claude-opus-4-6')
  const [subagentModel,     setSubagentModel]     = useState('sonnet')
  const [agentName,         setAgentName]         = useState('Hannah')
  const [agentConfigSaving, setAgentConfigSaving] = useState(false)

  // Brand form
  const [brandVoice,    setBrandVoice]    = useState('')
  const [tone,          setTone]          = useState('')
  const [writingStyle,  setWritingStyle]  = useState('')
  const [targetAudience,setTargetAudience]= useState('')
  const [socialHandles, setSocialHandles] = useState('')
  const [hashtags,      setHashtags]      = useState('')
  const [brandNotes,    setBrandNotes]    = useState('')
  const [brandSaving,   setBrandSaving]   = useState(false)

  // Workstream add
  const [addingWs, setAddingWs]   = useState(false)
  const [newWsName, setNewWsName] = useState('')
  const newWsRef = useRef<HTMLInputElement>(null)

  // Workstream mission/schedule editor
  const [expandedWsId, setExpandedWsId] = useState<number | null>(null)
  const [editMission,  setEditMission]  = useState('')
  const [editSchedule, setEditSchedule] = useState('manual')
  const [wsSaving,     setWsSaving]     = useState<Set<number>>(new Set())
  const [wsRunning,    setWsRunning]    = useState<Set<number>>(new Set())

  // Objective add
  const [addingObj,   setAddingObj]   = useState(false)
  const [newObjText,  setNewObjText]  = useState('')
  const [newObjCur,   setNewObjCur]   = useState('0')
  const [newObjTgt,   setNewObjTgt]   = useState('')
  const newObjRef = useRef<HTMLInputElement>(null)

  // Inline objective editing
  const [editingObjId, setEditingObjId] = useState<number | null>(null)
  const [editObjCur,   setEditObjCur]   = useState('')
  const [editObjTgt,   setEditObjTgt]   = useState('')

  useEffect(() => {
    api.getTelegramStatus(password)
      .then(s => setTelegramStatus(s))
      .catch(() => {/* non-fatal */})
  }, [password])

  useEffect(() => {
    if (!mcpOpen) return
    api.getMcpServers(password)
      .then(s => setMcpServers(s))
      .catch(() => {/* non-fatal */})
  }, [password, mcpOpen])

  // Load agent config on mount
  useEffect(() => {
    api.getAgentConfig(password)
      .then(cfg => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setAgentName(cfg.agent_name)
      })
      .catch(() => {/* non-fatal */})
  }, [password])

  // Load config on mount / product change
  useEffect(() => {
    setLoadError('')
    api.getProductConfig(password, productId)
      .then(cfg => {
        setName(cfg.name ?? '')
        setIconLabel(cfg.icon_label ?? '')
        setColor(cfg.color ?? '#2563eb')
        setBrandVoice(cfg.brand_voice ?? '')
        setTone(cfg.tone ?? '')
        setWritingStyle(cfg.writing_style ?? '')
        setTargetAudience(cfg.target_audience ?? '')
        setSocialHandles(cfg.social_handles ?? '')
        setHashtags(cfg.hashtags ?? '')
        setBrandNotes(cfg.brand_notes ?? '')
      })
      .catch(e => setLoadError(e.message))
  }, [productId, password])

  useEffect(() => {
    if (addingWs && newWsRef.current) newWsRef.current.focus()
  }, [addingWs])

  useEffect(() => {
    if (addingObj && newObjRef.current) newObjRef.current.focus()
  }, [addingObj])

  async function saveAgentConfig() {
    setAgentConfigSaving(true)
    try {
      await api.updateAgentConfig(password, {
        agent_model: agentModel,
        subagent_model: subagentModel,
        agent_name: agentName,
      })
    } finally {
      setAgentConfigSaving(false)
    }
  }

  async function saveInfo() {
    setInfoSaving(true)
    try {
      await api.updateProductConfig(password, productId, { name, icon_label: iconLabel, color })
      onRefreshProducts()
    } finally {
      setInfoSaving(false)
    }
  }

  async function saveBrand() {
    setBrandSaving(true)
    try {
      await api.updateProductConfig(password, productId, {
        brand_voice: brandVoice || null,
        tone: tone || null,
        writing_style: writingStyle || null,
        target_audience: targetAudience || null,
        social_handles: socialHandles || null,
        hashtags: hashtags || null,
        brand_notes: brandNotes || null,
      } as Partial<ProductConfig>)
    } finally {
      setBrandSaving(false)
    }
  }

  async function cycleWsStatus(ws: Workstream) {
    const next = STATUS_CYCLE[ws.status]
    await api.updateWorkstream(password, ws.id, { status: next })
    onRefreshData()
  }

  async function deleteWs(ws: Workstream) {
    await api.deleteWorkstream(password, ws.id)
    onRefreshData()
  }

  async function submitNewWs(e: React.FormEvent) {
    e.preventDefault()
    if (!newWsName.trim()) return
    await api.createWorkstream(password, productId, newWsName.trim())
    setNewWsName('')
    setAddingWs(false)
    onRefreshData()
  }

  function toggleExpand(ws: Workstream) {
    if (expandedWsId === ws.id) {
      setExpandedWsId(null)
    } else {
      setExpandedWsId(ws.id)
      setEditMission(ws.mission ?? '')
      setEditSchedule(ws.schedule ?? 'manual')
    }
  }

  async function saveWsMission(ws: Workstream) {
    setWsSaving(prev => new Set(prev).add(ws.id))
    try {
      await api.updateWorkstream(password, ws.id, { mission: editMission, schedule: editSchedule })
      onRefreshData()
    } finally {
      setWsSaving(prev => { const n = new Set(prev); n.delete(ws.id); return n })
    }
  }

  async function runWsNow(ws: Workstream) {
    setWsRunning(prev => new Set(prev).add(ws.id))
    try {
      await api.triggerWorkstreamRun(password, ws.id)
      onRefreshData()
    } finally {
      setWsRunning(prev => { const n = new Set(prev); n.delete(ws.id); return n })
    }
  }

  async function deleteObj(obj: Objective) {
    await api.deleteObjective(password, obj.id)
    onRefreshData()
  }

  async function submitNewObj(e: React.FormEvent) {
    e.preventDefault()
    if (!newObjText.trim()) return
    const cur = parseInt(newObjCur) || 0
    const tgt = newObjTgt.trim() ? parseInt(newObjTgt) || undefined : undefined
    await api.createObjective(password, productId, newObjText.trim(), cur, tgt)
    setNewObjText(''); setNewObjCur('0'); setNewObjTgt('')
    setAddingObj(false)
    onRefreshData()
  }

  function startEditObj(obj: Objective) {
    setEditingObjId(obj.id)
    setEditObjCur(String(obj.progress_current))
    setEditObjTgt(obj.progress_target != null ? String(obj.progress_target) : '')
  }

  async function saveObjProgress(obj: Objective) {
    const cur = parseInt(editObjCur)
    if (isNaN(cur)) { setEditingObjId(null); return }
    const tgt = editObjTgt.trim() ? parseInt(editObjTgt) : null
    await api.updateObjective(password, obj.id, {
      progress_current: cur,
      ...(tgt !== null ? { progress_target: tgt } : {}),
    })
    setEditingObjId(null)
    onRefreshData()
  }

  const handleMcpToggle = async (id: number, enabled: boolean) => {
    await api.updateMcpServer(password, id, !enabled).catch(() => null)
    setMcpServers(prev => prev.map(s => s.id === id ? { ...s, enabled: enabled ? 0 : 1 } : s))
  }

  const handleMcpDelete = async (id: number) => {
    await api.deleteMcpServer(password, id).catch(() => null)
    setMcpServers(prev => prev.filter(s => s.id !== id))
  }

  const handleMcpAdd = async (scope: 'global' | 'product') => {
    const f = mcpAddForm
    const payload: Parameters<typeof api.addMcpServer>[1] = {
      name: f.name, type: f.type, scope,
      ...(f.type === 'remote' ? { url: f.url } : {
        command: f.command,
        args: f.args ? f.args.split(' ') : [],
      }),
      ...(scope === 'product' ? { product_id: f.product_id } : {}),
    }
    const created = await api.addMcpServer(password, payload).catch(() => null)
    if (created) {
      setMcpServers(prev => [...prev, created as typeof prev[0]])
      setMcpAddOpen(null)
      setMcpAddForm({ scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', product_id: '' })
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-80 bg-zinc-950 border-l border-zinc-800/60 flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">

        {/* Header */}
        <div className="flex items-center justify-between px-4 h-12 border-b border-zinc-800/60 flex-shrink-0">
          <span className="text-sm font-semibold text-zinc-100">Product Settings</span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {loadError && (
            <div className="px-4 py-3 text-xs text-red-400 bg-red-900/10 border-b border-red-900/30">
              {loadError}
            </div>
          )}

          {/* ── Product Info ──────────────────────────────────────────────── */}
          <SectionHeader
            title="Product Info"
            open={infoOpen}
            onToggle={() => setInfoOpen(o => !o)}
          />
          {infoOpen && (
            <div className="px-4 py-4 space-y-3 border-b border-zinc-800/60">
              <Field label="Name" value={name} onChange={setName} placeholder="My Product" />
              <Field label="Icon label" value={iconLabel} onChange={setIconLabel} placeholder="MP" />
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={color}
                    onChange={e => setColor(e.target.value)}
                    className="w-9 h-9 rounded-lg cursor-pointer bg-transparent border border-zinc-700 p-0.5"
                  />
                  <input
                    type="text"
                    value={color}
                    onChange={e => setColor(e.target.value)}
                    className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono focus:outline-none focus:border-zinc-600"
                    placeholder="#2563eb"
                  />
                </div>
              </div>
              <button
                onClick={saveInfo}
                disabled={infoSaving}
                className="w-full py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 font-medium transition-colors disabled:opacity-50"
              >
                {infoSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}

          {/* ── Brand Config ──────────────────────────────────────────────── */}
          <SectionHeader
            title="Brand Config"
            open={brandOpen}
            onToggle={() => setBrandOpen(o => !o)}
          />
          {brandOpen && (
            <div className="px-4 py-4 space-y-3 border-b border-zinc-800/60">
              <Field label="Brand voice" value={brandVoice} onChange={setBrandVoice} placeholder="authoritative and warm" />
              <Field label="Tone" value={tone} onChange={setTone} placeholder="professional but approachable" />
              <Field label="Writing style" value={writingStyle} onChange={setWritingStyle} placeholder="short sentences, active voice" />
              <Field label="Target audience" value={targetAudience} onChange={setTargetAudience} placeholder="solopreneurs and fractional CXOs" />
              <Field label="Social handles" value={socialHandles} onChange={setSocialHandles} placeholder='{"instagram":"@handle","linkedin":"url"}' />
              <Field label="Hashtags" value={hashtags} onChange={setHashtags} placeholder="#retainerops #consultants" />
              <Field label="Brand notes" value={brandNotes} onChange={setBrandNotes} textarea placeholder="Any other guidance…" />
              <button
                onClick={saveBrand}
                disabled={brandSaving}
                className="w-full py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 font-medium transition-colors disabled:opacity-50"
              >
                {brandSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}

          {/* ── Agent ───────────────────────────────────────────────────── */}
          <SectionHeader
            title="Agent"
            open={modelsOpen}
            onToggle={() => setModelsOpen(o => !o)}
          />
          {modelsOpen && (
            <div className="px-4 py-4 space-y-3 border-b border-zinc-800/60">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Assistant Name</label>
                <input
                  type="text"
                  value={agentName}
                  onChange={e => setAgentName(e.target.value)}
                  placeholder="Hannah"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Main agent model</label>
                <select
                  value={agentModel}
                  onChange={e => setAgentModel(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                >
                  <option value="claude-opus-4-6">Opus 4.6 (best, ~$15/Mtok)</option>
                  <option value="claude-sonnet-4-6">Sonnet 4.6 (fast, ~$3/Mtok)</option>
                  <option value="claude-haiku-4-5-20251001">Haiku 4.5 (cheap, ~$0.80/Mtok)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Sub-agents (research, email, etc.)</label>
                <select
                  value={subagentModel}
                  onChange={e => setSubagentModel(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                >
                  <option value="claude-opus-4-6">Opus 4.6 (best, ~$15/Mtok)</option>
                  <option value="claude-sonnet-4-6">Sonnet 4.6 (fast, ~$3/Mtok)</option>
                  <option value="sonnet">Sonnet (latest)</option>
                  <option value="claude-haiku-4-5-20251001">Haiku 4.5 (cheap, ~$0.80/Mtok)</option>
                  <option value="haiku">Haiku (latest)</option>
                </select>
              </div>
              <button
                onClick={saveAgentConfig}
                disabled={agentConfigSaving}
                className="w-full py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 font-medium transition-colors disabled:opacity-50"
              >
                {agentConfigSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}

          {/* ── Workstreams ───────────────────────────────────────────────── */}
          <SectionHeader
            title="Workstreams"
            open={wsOpen}
            onToggle={() => setWsOpen(o => !o)}
            action={
              <button
                onClick={() => setAddingWs(a => !a)}
                className="text-xs text-zinc-500 hover:text-zinc-200 px-2 py-1 rounded hover:bg-zinc-800 transition-colors"
              >
                + Add
              </button>
            }
          />
          {wsOpen && (
            <div className="border-b border-zinc-800/60">
              {workstreams.map(ws => {
                const isExpanded = expandedWsId === ws.id
                const isSaving = wsSaving.has(ws.id)
                const isRunning = wsRunning.has(ws.id)
                const hasMission = !!(ws.mission?.trim())
                return (
                  <div key={ws.id} className="border-b border-zinc-800/40 last:border-0">
                    {/* Row header */}
                    <div className="flex items-center gap-2 px-4 py-2.5 hover:bg-zinc-900/40 group">
                      {/* Expand chevron */}
                      <button
                        onClick={() => toggleExpand(ws)}
                        className="text-zinc-600 hover:text-zinc-400 transition-colors flex-shrink-0"
                        title="Configure mission"
                      >
                        <svg className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                      <span
                        className="flex-1 text-sm text-zinc-300 truncate cursor-pointer"
                        onClick={() => toggleExpand(ws)}
                      >
                        {ws.name}
                        {hasMission && (
                          <span className="ml-1.5 text-[10px] text-zinc-600">
                            {ws.schedule !== 'manual' ? ws.schedule : ''}
                          </span>
                        )}
                      </span>
                      {/* Status toggle */}
                      <button
                        onClick={() => cycleWsStatus(ws)}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors flex-shrink-0 ${STATUS_COLORS[ws.status]}`}
                        title="Click to cycle status"
                      >
                        {STATUS_LABEL[ws.status]}
                      </button>
                      {/* Delete */}
                      <button
                        onClick={() => deleteWs(ws)}
                        className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-red-400 transition-all flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>

                    {/* Expanded mission editor */}
                    {isExpanded && (
                      <div className="px-4 pb-4 space-y-3 bg-zinc-900/30">
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">Mission</label>
                          <textarea
                            rows={4}
                            value={editMission}
                            onChange={e => setEditMission(e.target.value)}
                            placeholder={"Every Monday, research trending topics in our space, draft 3 content ideas, and flag any competitor moves worth responding to."}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-600 resize-none leading-relaxed"
                          />
                        </div>
                        <div className="flex items-end gap-2">
                          <div className="flex-1">
                            <label className="block text-xs text-zinc-500 mb-1">Schedule</label>
                            <select
                              value={editSchedule}
                              onChange={e => setEditSchedule(e.target.value)}
                              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600"
                            >
                              <option value="manual">Manual only</option>
                              <option value="hourly">Every hour</option>
                              <option value="daily">Daily at 9am</option>
                              <option value="weekdays">Weekdays at 9am</option>
                              <option value="weekly">Mondays at 9am</option>
                            </select>
                          </div>
                          <button
                            onClick={() => runWsNow(ws)}
                            disabled={isRunning || !hasMission && !editMission.trim()}
                            className="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 font-medium transition-colors disabled:opacity-40 whitespace-nowrap"
                            title={hasMission ? 'Run now' : 'Save a mission first'}
                          >
                            {isRunning ? '…' : '▶ Run now'}
                          </button>
                        </div>
                        {ws.last_run_at && (
                          <p className="text-[11px] text-zinc-600">
                            Last run: {new Date(ws.last_run_at).toLocaleString()}
                          </p>
                        )}
                        <button
                          onClick={() => saveWsMission(ws)}
                          disabled={isSaving}
                          className="w-full py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 font-medium transition-colors disabled:opacity-50"
                        >
                          {isSaving ? 'Saving…' : 'Save mission'}
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
              {addingWs && (
                <form onSubmit={submitNewWs} className="px-4 py-2.5 flex items-center gap-2">
                  <input
                    ref={newWsRef}
                    type="text"
                    value={newWsName}
                    onChange={e => setNewWsName(e.target.value)}
                    placeholder="Workstream name"
                    className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-500"
                  />
                  <button type="submit" className="text-xs px-2.5 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded text-zinc-200 transition-colors">Add</button>
                  <button type="button" onClick={() => { setAddingWs(false); setNewWsName('') }} className="text-xs text-zinc-600 hover:text-zinc-400">✕</button>
                </form>
              )}
              {workstreams.length === 0 && !addingWs && (
                <div className="px-4 py-3 text-xs text-zinc-700">No workstreams yet.</div>
              )}
            </div>
          )}

          {/* ── Objectives ────────────────────────────────────────────────── */}
          <SectionHeader
            title="Objectives"
            open={objOpen}
            onToggle={() => setObjOpen(o => !o)}
            action={
              <button
                onClick={() => setAddingObj(a => !a)}
                className="text-xs text-zinc-500 hover:text-zinc-200 px-2 py-1 rounded hover:bg-zinc-800 transition-colors"
              >
                + Add
              </button>
            }
          />
          {objOpen && (
            <div className="pb-4">
              {objectives.map(obj => (
                <div key={obj.id} className="px-4 py-2.5 hover:bg-zinc-900/40 group">
                  <div className="flex items-start gap-2">
                    <span className="flex-1 text-sm text-zinc-300 leading-snug">{obj.text}</span>
                    <button
                      onClick={() => deleteObj(obj)}
                      className="opacity-0 group-hover:opacity-100 flex-shrink-0 w-5 h-5 flex items-center justify-center text-zinc-600 hover:text-red-400 transition-all mt-0.5"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                  {editingObjId === obj.id ? (
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <input
                        type="number"
                        value={editObjCur}
                        onChange={e => setEditObjCur(e.target.value)}
                        className="w-16 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-100 focus:outline-none focus:border-zinc-500"
                        placeholder="cur"
                      />
                      <span className="text-zinc-600 text-xs">/</span>
                      <input
                        type="number"
                        value={editObjTgt}
                        onChange={e => setEditObjTgt(e.target.value)}
                        className="w-16 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-100 focus:outline-none focus:border-zinc-500"
                        placeholder="target"
                      />
                      <button
                        onClick={() => saveObjProgress(obj)}
                        className="text-xs px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded text-zinc-200"
                      >✓</button>
                      <button
                        onClick={() => setEditingObjId(null)}
                        className="text-xs text-zinc-600 hover:text-zinc-400"
                      >✕</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => startEditObj(obj)}
                      className="mt-1 text-xs text-zinc-600 hover:text-zinc-400 transition-colors tabular-nums"
                    >
                      {obj.progress_current}
                      {obj.progress_target != null ? ` / ${obj.progress_target}` : ''}
                      <span className="ml-1 opacity-50">edit</span>
                    </button>
                  )}
                </div>
              ))}
              {addingObj && (
                <form onSubmit={submitNewObj} className="px-4 py-3 space-y-2 border-t border-zinc-800/60">
                  <input
                    ref={newObjRef}
                    type="text"
                    value={newObjText}
                    onChange={e => setNewObjText(e.target.value)}
                    placeholder="Objective description"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-500"
                  />
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={newObjCur}
                      onChange={e => setNewObjCur(e.target.value)}
                      placeholder="Start"
                      className="w-20 bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-500"
                    />
                    <span className="text-zinc-600 text-xs">/</span>
                    <input
                      type="number"
                      value={newObjTgt}
                      onChange={e => setNewObjTgt(e.target.value)}
                      placeholder="Target"
                      className="w-20 bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-zinc-500"
                    />
                    <button type="submit" className="flex-1 text-xs py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded text-zinc-200 transition-colors">Add</button>
                    <button type="button" onClick={() => { setAddingObj(false); setNewObjText('') }} className="text-xs text-zinc-600 hover:text-zinc-400">✕</button>
                  </div>
                </form>
              )}
              {objectives.length === 0 && !addingObj && (
                <div className="px-4 py-3 text-xs text-zinc-700">No objectives yet.</div>
              )}
            </div>
          )}
          {/* ── Remote Access ─────────────────────────────────────────── */}
          <SectionHeader
            title="Remote Access"
            open={remoteOpen}
            onToggle={() => setRemoteOpen(o => !o)}
          />
          {remoteOpen && (
            <div className="px-4 py-4 space-y-3 border-b border-zinc-800/60">
              {telegramStatus === null ? (
                <p className="text-xs text-zinc-600">Checking…</p>
              ) : telegramStatus.connected ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                    <span className="text-sm text-zinc-200">
                      Connected as <span className="font-mono text-emerald-400">@{telegramStatus.bot_username}</span>
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Message your bot on Telegram to chat with your assistant from anywhere.
                    Use <span className="font-mono text-zinc-400">for ProductName: message</span> to target a specific product.
                  </p>
                </div>
              ) : telegramStatus.configured ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
                    <span className="text-sm text-zinc-400">Token set but bot unreachable</span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Check your <span className="font-mono text-zinc-400">TELEGRAM_BOT_TOKEN</span> in config.env and restart.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-zinc-400">Connect Telegram to chat with your assistant from anywhere — no port forwarding required.</p>
                  <ol className="space-y-2 text-xs text-zinc-500 list-decimal list-inside leading-relaxed">
                    <li>Message <span className="font-mono text-zinc-400">@BotFather</span> on Telegram → <span className="font-mono text-zinc-400">/newbot</span> → copy the token</li>
                    <li>Add to your <span className="font-mono text-zinc-400">config.env</span>:<br />
                      <span className="font-mono text-zinc-400 ml-4">TELEGRAM_BOT_TOKEN=your_token</span>
                    </li>
                    <li>Message your new bot once (any text)</li>
                    <li>Run <span className="font-mono text-zinc-400">adjutant telegram setup</span></li>
                    <li>Run <span className="font-mono text-zinc-400">adjutant restart</span></li>
                  </ol>
                </div>
              )}
            </div>
          )}
          {/* ── MCP Servers ──────────────────────────────────────────────── */}
          <SectionHeader
            title="MCP Servers"
            open={mcpOpen}
            onToggle={() => setMcpOpen(o => !o)}
          />
          {mcpOpen && (() => {
            const globalServers  = mcpServers.filter(s => s.scope === 'global')
            const productServers = mcpServers.filter(s => s.scope === 'product' && (!mcpProductFilter || s.product_id === mcpProductFilter))
            const McpRow = ({ s }: { s: typeof mcpServers[0] }) => (
              <div key={s.id} className="flex items-center gap-2 py-1">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.enabled ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
                <span className="text-xs text-zinc-300 flex-1 truncate">{s.name}</span>
                <span className="text-xs text-zinc-600 font-mono">{s.type}</span>
                <button
                  onClick={() => handleMcpToggle(s.id, !!s.enabled)}
                  className="text-xs text-zinc-500 hover:text-zinc-300 px-1"
                  title={s.enabled ? 'Disable' : 'Enable'}
                >
                  {s.enabled ? 'on' : 'off'}
                </button>
                <button
                  onClick={() => handleMcpDelete(s.id)}
                  className="text-xs text-zinc-600 hover:text-red-400 px-1"
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            )
            const AddForm = ({ scope }: { scope: 'global' | 'product' }) => (
              <div className="mt-2 space-y-2 border border-zinc-700 rounded p-3">
                <input
                  className="w-full bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                  placeholder="Server name"
                  value={mcpAddForm.name}
                  onChange={e => setMcpAddForm(f => ({ ...f, name: e.target.value }))}
                />
                <div className="flex gap-2">
                  <select
                    className="flex-1 bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                    value={mcpAddForm.type}
                    onChange={e => setMcpAddForm(f => ({ ...f, type: e.target.value as 'remote' | 'stdio' }))}
                  >
                    <option value="remote">Remote (HTTP/SSE)</option>
                    <option value="stdio">Local (stdio)</option>
                  </select>
                </div>
                {mcpAddForm.type === 'remote' ? (
                  <input
                    className="w-full bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                    placeholder="Endpoint URL"
                    value={mcpAddForm.url}
                    onChange={e => setMcpAddForm(f => ({ ...f, url: e.target.value }))}
                  />
                ) : (
                  <>
                    <input
                      className="w-full bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                      placeholder="Command (e.g. npx)"
                      value={mcpAddForm.command}
                      onChange={e => setMcpAddForm(f => ({ ...f, command: e.target.value }))}
                    />
                    <input
                      className="w-full bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                      placeholder="Args (space-separated)"
                      value={mcpAddForm.args}
                      onChange={e => setMcpAddForm(f => ({ ...f, args: e.target.value }))}
                    />
                  </>
                )}
                {scope === 'product' && (
                  <input
                    className="w-full bg-zinc-800 text-xs text-zinc-200 rounded px-2 py-1 border border-zinc-700"
                    placeholder="Product ID"
                    value={mcpAddForm.product_id}
                    onChange={e => setMcpAddForm(f => ({ ...f, product_id: e.target.value }))}
                  />
                )}
                <p className="text-xs text-zinc-600">Credentials: tell {agentName} to add this server — she'll ask for them.</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleMcpAdd(scope)}
                    className="flex-1 text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded px-2 py-1"
                  >
                    Add
                  </button>
                  <button
                    onClick={() => setMcpAddOpen(null)}
                    className="text-xs text-zinc-600 hover:text-zinc-400 px-2"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )
            return (
              <div className="border-b border-zinc-800/60">
                {/* Global servers */}
                <div className="px-4 pt-3 pb-2">
                  <p className="text-xs text-zinc-500 font-medium mb-2">Global</p>
                  {globalServers.length === 0
                    ? <p className="text-xs text-zinc-600">None configured</p>
                    : globalServers.map(s => <McpRow key={s.id} s={s} />)
                  }
                  {mcpAddOpen === 'global'
                    ? <AddForm scope="global" />
                    : (
                      <button
                        onClick={() => setMcpAddOpen('global')}
                        className="mt-2 text-xs text-zinc-500 hover:text-zinc-300"
                      >
                        + Add global server
                      </button>
                    )
                  }
                </div>
                {/* Per-product servers */}
                <div className="px-4 pt-2 pb-3 border-t border-zinc-800/40">
                  <div className="flex items-center gap-2 mb-2">
                    <p className="text-xs text-zinc-500 font-medium">Per-product</p>
                    <input
                      className="flex-1 bg-zinc-800 text-xs text-zinc-400 rounded px-2 py-0.5 border border-zinc-700"
                      placeholder="Filter by product ID"
                      value={mcpProductFilter}
                      onChange={e => setMcpProductFilter(e.target.value)}
                    />
                  </div>
                  {productServers.length === 0
                    ? <p className="text-xs text-zinc-600">None configured</p>
                    : productServers.map(s => <McpRow key={s.id} s={s} />)
                  }
                  {mcpAddOpen === 'product'
                    ? <AddForm scope="product" />
                    : (
                      <button
                        onClick={() => setMcpAddOpen('product')}
                        className="mt-2 text-xs text-zinc-500 hover:text-zinc-300"
                      >
                        + Add product server
                      </button>
                    )
                  }
                </div>
              </div>
            )
          })()}
        </div>
      </aside>
    </>
  )
}
