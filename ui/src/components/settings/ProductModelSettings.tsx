import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
  productId: string
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

const ModelSelect = ({
  value, onChange, globalDefault, models, hasOpenAI,
}: {
  value: string
  onChange: (v: string) => void
  globalDefault: string
  models: { anthropic: string[]; openai: string[] }
  hasOpenAI: boolean
}) => {
  const defaultLabel = MODEL_LABELS[globalDefault] ?? globalDefault
  return (
    <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
      <option value="">— Global default ({defaultLabel}) —</option>
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
}

export default function ProductModelSettings({ password, productId }: Props) {
  const [agentModel, setAgentModel] = useState('')
  const [subagentModel, setSubagentModel] = useState('')
  const [prescreenerModel, setPrescreenerModel] = useState('')
  const [globalDefaults, setGlobalDefaults] = useState({ agent_model: '', subagent_model: '', prescreener_model: '' })
  const [hasOpenAI, setHasOpenAI] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [availableModels, setAvailableModels] = useState<{ anthropic: string[]; openai: string[] }>(
    { anthropic: ANTHROPIC_FALLBACK, openai: OPENAI_FALLBACK }
  )
  const [refreshingModels, setRefreshingModels] = useState(false)
  const genRef = useRef(0)

  useEffect(() => {
    const gen = ++genRef.current
    setLoading(true)
    setError(null)
    Promise.all([
      api.getAgentConfig(password, productId),
      api.getAgentConfig(password),
      api.getAvailableModels(password),
    ])
      .then(([productCfg, globalCfg, models]) => {
        if (gen !== genRef.current) return
        setAgentModel(productCfg.agent_model)
        setSubagentModel(productCfg.subagent_model)
        setPrescreenerModel(productCfg.prescreener_model)
        setGlobalDefaults({
          agent_model: globalCfg.agent_model,
          subagent_model: globalCfg.subagent_model,
          prescreener_model: globalCfg.prescreener_model,
        })
        setHasOpenAI(Boolean(globalCfg.openai_access_token))
        setAvailableModels(models)
      })
      .catch(() => { if (gen === genRef.current) setError('Failed to load model settings.') })
      .finally(() => { if (gen === genRef.current) setLoading(false) })
  }, [password, productId])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        product_id: productId,
        agent_model: agentModel,
        subagent_model: subagentModel,
        prescreener_model: prescreenerModel,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
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
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Override the global model defaults for this product</p>

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
          disabled={!hasOpenAI}
          className="px-3 py-1.5 text-xs border border-adj-border rounded hover:bg-adj-elevated text-adj-text-secondary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Use OpenAI defaults
        </button>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Main Agent Model
          </label>
          <ModelSelect value={agentModel} onChange={setAgentModel} globalDefault={globalDefaults.agent_model} models={availableModels} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} globalDefault={globalDefaults.subagent_model} models={availableModels} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} globalDefault={globalDefaults.prescreener_model} models={availableModels} hasOpenAI={hasOpenAI} />
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
