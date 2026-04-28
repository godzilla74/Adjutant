import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
  productId: string
}

const ANTHROPIC_OPTIONS = [
  { value: 'claude-opus-4-7',           label: 'Opus 4.7 (best)' },
  { value: 'claude-sonnet-4-6',         label: 'Sonnet 4.6 (fast)' },
  { value: 'claude-haiku-4-5-20251001', label: 'Haiku 4.5 (cheap)' },
]

const OPENAI_OPTIONS = [
  { value: 'gpt-4o',      label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { value: 'o3-mini',     label: 'o3-mini' },
]

const ALL_OPTIONS = [...ANTHROPIC_OPTIONS, ...OPENAI_OPTIONS]

const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

const ModelSelect = ({
  value, onChange, globalDefault, hasOpenAI,
}: { value: string; onChange: (v: string) => void; globalDefault: string; hasOpenAI: boolean }) => {
  const defaultLabel = ALL_OPTIONS.find(o => o.value === globalDefault)?.label ?? globalDefault
  return (
    <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
      <option value="">— Global default ({defaultLabel}) —</option>
      <optgroup label="Anthropic">
        {ANTHROPIC_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </optgroup>
      {hasOpenAI && (
        <optgroup label="OpenAI">
          {OPENAI_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
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
  const genRef = useRef(0)

  useEffect(() => {
    const gen = ++genRef.current
    setLoading(true)
    setError(null)
    Promise.all([
      api.getAgentConfig(password, productId),
      api.getAgentConfig(password),
    ])
      .then(([productCfg, globalCfg]) => {
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

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>
  if (error) return <p className="text-red-400 text-sm">{error}</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Override the global model defaults for this product</p>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Main Agent Model
          </label>
          <ModelSelect value={agentModel} onChange={setAgentModel} globalDefault={globalDefaults.agent_model} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} globalDefault={globalDefaults.subagent_model} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} globalDefault={globalDefaults.prescreener_model} hasOpenAI={hasOpenAI} />
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
