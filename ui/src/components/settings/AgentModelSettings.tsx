import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

const ANTHROPIC_FALLBACK = ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001']
const OPENAI_FALLBACK = ['gpt-4o', 'gpt-4o-mini', 'o3-mini']

const MODEL_LABELS: Record<string, string> = {
  'claude-opus-4-7':           'Opus 4.7 (best)',
  'claude-sonnet-4-6':         'Sonnet 4.6 (fast)',
  'claude-haiku-4-5-20251001': 'Haiku 4.5 (cheap)',
  'gpt-4o':                    'GPT-4o',
  'gpt-4o-mini':               'GPT-4o mini',
  'o3-mini':                   'o3-mini',
}

const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

const keyInputCls = 'flex-1 bg-adj-elevated border border-adj-border rounded px-2 py-1.5 text-xs text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent font-mono'

const ModelSelect = ({
  value, onChange, models, hasOpenAI,
}: {
  value: string
  onChange: (v: string) => void
  models: { anthropic: string[]; openai: string[] }
  hasOpenAI: boolean
}) => (
  <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
    <optgroup label="Anthropic">
      {models.anthropic.map(id => (
        <option key={id} value={id}>{MODEL_LABELS[id] ?? id}</option>
      ))}
    </optgroup>
    {hasOpenAI && models.openai.length > 0 && (
      <optgroup label="OpenAI">
        {models.openai.map(id => (
          <option key={id} value={id}>{MODEL_LABELS[id] ?? id}</option>
        ))}
      </optgroup>
    )}
  </select>
)

export default function AgentModelSettings({ password }: Props) {
  const [agentModel, setAgentModel] = useState('claude-sonnet-4-6')
  const [subagentModel, setSubagentModel] = useState('claude-sonnet-4-6')
  const [prescreenerModel, setPrescreenerModel] = useState('claude-haiku-4-5-20251001')
  const [agentName, setAgentName] = useState('Adjutant')
  const [hasOpenAI, setHasOpenAI] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [anthropicConfigured, setAnthropicConfigured] = useState(false)
  const [anthropicMasked, setAnthropicMasked] = useState('')
  const [newAnthropicKey, setNewAnthropicKey] = useState('')
  const [savingAnthropicKey, setSavingAnthropicKey] = useState(false)
  const [anthropicKeySaved, setAnthropicKeySaved] = useState(false)
  const [anthropicKeyError, setAnthropicKeyError] = useState<string | null>(null)

  const [openaiConnected, setOpenaiConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)

  const [openaiKeyConfigured, setOpenaiKeyConfigured] = useState(false)
  const [openaiKeyMasked, setOpenaiKeyMasked] = useState('')
  const [newOpenAIKey, setNewOpenAIKey] = useState('')
  const [savingOpenAIKey, setSavingOpenAIKey] = useState(false)
  const [openaiKeySaved, setOpenaiKeySaved] = useState(false)
  const [openaiKeyError, setOpenaiKeyError] = useState<string | null>(null)

  const [availableModels, setAvailableModels] = useState<{ anthropic: string[]; openai: string[] }>(
    { anthropic: ANTHROPIC_FALLBACK, openai: OPENAI_FALLBACK }
  )
  const [refreshingModels, setRefreshingModels] = useState(false)

  const popupRef = useRef<Window | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.source !== popupRef.current) return
      if (e.data?.type === 'oauth_success') {
        setOpenaiConnected(true)
        setHasOpenAI(true)
        setConnecting(false)
        clearInterval(pollRef.current!)
        pollRef.current = null
      } else if (e.data?.type === 'oauth_error') {
        setConnecting(false)
        clearInterval(pollRef.current!)
        pollRef.current = null
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      api.getAgentConfig(password),
      api.getAnthropicKeyStatus(password),
      api.getOpenAIKeyStatus(password),
      api.getAvailableModels(password),
    ])
      .then(([cfg, anthKeyStatus, oaiKeyStatus, models]) => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setPrescreenerModel(cfg.prescreener_model)
        setAgentName(cfg.agent_name)
        const oai = Boolean(cfg.openai_access_token)
        setHasOpenAI(oai)
        setOpenaiConnected(oai)
        setAnthropicConfigured(anthKeyStatus.configured)
        setAnthropicMasked(anthKeyStatus.masked)
        setOpenaiKeyConfigured(oaiKeyStatus.configured)
        setOpenaiKeyMasked(oaiKeyStatus.masked)
        setAvailableModels({
          anthropic: models.anthropic.length > 0 ? models.anthropic : ANTHROPIC_FALLBACK,
          openai: oai && models.openai.length === 0 ? OPENAI_FALLBACK : models.openai,
        })
      })
      .catch(() => setError('Failed to load model settings.'))
      .finally(() => setLoading(false))
  }, [password])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        agent_model: agentModel,
        subagent_model: subagentModel,
        prescreener_model: prescreenerModel,
        agent_name: agentName,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  async function saveAnthropicKey() {
    if (!newAnthropicKey.trim()) return
    setSavingAnthropicKey(true)
    setAnthropicKeyError(null)
    try {
      const result = await api.updateAnthropicKey(password, newAnthropicKey.trim())
      setAnthropicConfigured(result.configured)
      setAnthropicMasked(result.masked)
      setNewAnthropicKey('')
      setAnthropicKeySaved(true)
      setTimeout(() => setAnthropicKeySaved(false), 2000)
      const models = await api.getAvailableModels(password)
      setAvailableModels({
        anthropic: models.anthropic.length > 0 ? models.anthropic : ANTHROPIC_FALLBACK,
        openai: hasOpenAI && models.openai.length === 0 ? OPENAI_FALLBACK : models.openai,
      })
    } catch (e: unknown) {
      setAnthropicKeyError((e as Error).message || 'Failed to save key')
    } finally {
      setSavingAnthropicKey(false)
    }
  }

  async function saveOpenAIKey() {
    if (!newOpenAIKey.trim()) return
    setSavingOpenAIKey(true)
    setOpenaiKeyError(null)
    try {
      const result = await api.updateOpenAIKey(password, newOpenAIKey.trim())
      setOpenaiKeyConfigured(result.configured)
      setOpenaiKeyMasked(result.masked)
      setNewOpenAIKey('')
      setOpenaiKeySaved(true)
      setTimeout(() => setOpenaiKeySaved(false), 2000)
      const models = await api.getAvailableModels(password)
      setAvailableModels({
        anthropic: models.anthropic.length > 0 ? models.anthropic : ANTHROPIC_FALLBACK,
        openai: hasOpenAI && models.openai.length === 0 ? OPENAI_FALLBACK : models.openai,
      })
    } catch (e: unknown) {
      setOpenaiKeyError((e as Error).message || 'Failed to save key')
    } finally {
      setSavingOpenAIKey(false)
    }
  }

  async function connectOpenAI() {
    setConnecting(true)
    try {
      const { auth_url } = await api.startOpenAIOAuth(password)
      const popup = window.open(auth_url, '_blank', 'width=500,height=600')
      popupRef.current = popup
      let closedAt: number | null = null
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getOpenAIOAuthStatus(password)
          if (status.connected) {
            setOpenaiConnected(true)
            setHasOpenAI(true)
            setConnecting(false)
            clearInterval(pollRef.current!)
            pollRef.current = null
            return
          }
        } catch {}
        if (!popup || popup.closed) {
          if (closedAt === null) closedAt = Date.now()
          if (Date.now() - closedAt > 5000) {
            setConnecting(false)
            clearInterval(pollRef.current!)
            pollRef.current = null
          }
        }
      }, 1000)
    } catch {
      setConnecting(false)
    }
  }

  async function disconnectOpenAI() {
    try {
      await api.disconnectOpenAI(password)
      setOpenaiConnected(false)
      setHasOpenAI(false)
    } catch {}
  }

  async function refreshModels() {
    setRefreshingModels(true)
    try {
      const models = await api.refreshAvailableModels(password)
      setAvailableModels(models)
    } catch {}
    finally { setRefreshingModels(false) }
  }

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>
  if (error) return <p className="text-red-400 text-sm">{error}</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Agent Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Configure provider connections, model selection, and assistant name</p>

      {/* Connection status row */}
      <div className="flex gap-3 mb-6">
        {/* Anthropic card */}
        <div className="flex-1 bg-adj-panel border border-adj-border rounded-md px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${anthropicConfigured ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm font-medium text-adj-text-secondary">Anthropic</span>
          </div>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder={anthropicConfigured ? anthropicMasked : 'Paste Anthropic API key'}
              value={newAnthropicKey}
              onChange={e => setNewAnthropicKey(e.target.value)}
              className={keyInputCls}
            />
            <button
              onClick={saveAnthropicKey}
              disabled={!newAnthropicKey.trim() || savingAnthropicKey}
              className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {anthropicKeySaved ? '✓ Saved' : savingAnthropicKey ? 'Saving…' : 'Save'}
            </button>
          </div>
          {anthropicKeyError && <p className="text-xs text-red-400">{anthropicKeyError}</p>}
        </div>

        {/* OpenAI card */}
        <div className="flex-1 bg-adj-panel border border-adj-border rounded-md px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${openaiConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm font-medium text-adj-text-secondary">OpenAI</span>
            <span className="text-xs text-adj-text-faint ml-1">{openaiConnected ? 'Connected' : 'Not connected'}</span>
            <div className="ml-auto">
              {openaiConnected ? (
                <button onClick={disconnectOpenAI} className="text-xs text-red-400 hover:text-red-300 hover:underline">
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={connectOpenAI}
                  disabled={connecting}
                  className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {connecting ? 'Connecting…' : 'Connect'}
                </button>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder={openaiKeyConfigured ? openaiKeyMasked : 'Paste OpenAI API key'}
              value={newOpenAIKey}
              onChange={e => setNewOpenAIKey(e.target.value)}
              className={keyInputCls}
            />
            <button
              onClick={saveOpenAIKey}
              disabled={!newOpenAIKey.trim() || savingOpenAIKey}
              className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {openaiKeySaved ? '✓ Saved' : savingOpenAIKey ? 'Saving…' : 'Save'}
            </button>
          </div>
          {openaiKeyError && <p className="text-xs text-red-400">{openaiKeyError}</p>}
          <p className="text-[10px] text-adj-text-faint">ChatGPT login for running tasks · API key for listing models</p>
        </div>
      </div>

      {/* Provider preset buttons */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => { setAgentModel('claude-sonnet-4-6'); setSubagentModel('claude-sonnet-4-6'); setPrescreenerModel('claude-haiku-4-5-20251001') }}
          className="px-3 py-1.5 text-xs border border-adj-border rounded hover:bg-adj-elevated text-adj-text-secondary transition-colors"
        >
          Use Anthropic defaults
        </button>
        <button
          onClick={() => { setAgentModel('gpt-4o'); setSubagentModel('gpt-4o'); setPrescreenerModel('gpt-4o-mini') }}
          disabled={!openaiConnected}
          className="px-3 py-1.5 text-xs border border-adj-border rounded hover:bg-adj-elevated text-adj-text-secondary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Use OpenAI defaults
        </button>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Assistant Name
          </label>
          <input
            type="text"
            value={agentName}
            onChange={e => setAgentName(e.target.value)}
            placeholder="Adjutant"
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Main Agent Model
          </label>
          <ModelSelect value={agentModel} onChange={setAgentModel} models={availableModels} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents (research, email, etc.)
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} models={availableModels} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener (message routing)
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} models={availableModels} hasOpenAI={hasOpenAI} />
          <button
            onClick={refreshModels}
            disabled={refreshingModels}
            className="mt-1 text-[10px] text-adj-text-faint hover:text-adj-text-muted transition-colors disabled:opacity-50"
          >
            {refreshingModels ? 'Refreshing…' : '↻ Refresh models'}
          </button>
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-adj-accent text-white rounded-md text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-50"
        >
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
