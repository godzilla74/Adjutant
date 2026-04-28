import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
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

const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

const ModelSelect = ({ value, onChange, hasOpenAI }: { value: string; onChange: (v: string) => void; hasOpenAI: boolean }) => (
  <select value={value} onChange={e => onChange(e.target.value)} className={inputCls}>
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

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getAgentConfig(password)
      .then(cfg => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setPrescreenerModel(cfg.prescreener_model)
        setAgentName(cfg.agent_name)
        setHasOpenAI(Boolean(cfg.openai_access_token))
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

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>
  if (error) return <p className="text-red-400 text-sm">{error}</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Agent Model</h2>
      <p className="text-xs text-adj-text-muted mb-6">Configure model selection and assistant name</p>

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
          <ModelSelect value={agentModel} onChange={setAgentModel} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents (research, email, etc.)
          </label>
          <ModelSelect value={subagentModel} onChange={setSubagentModel} hasOpenAI={hasOpenAI} />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Pre-screener (message routing)
          </label>
          <ModelSelect value={prescreenerModel} onChange={setPrescreenerModel} hasOpenAI={hasOpenAI} />
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
