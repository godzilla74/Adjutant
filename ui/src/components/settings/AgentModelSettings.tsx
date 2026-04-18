import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

const MODEL_OPTIONS = [
  { value: 'claude-opus-4-6',            label: 'Opus 4.6 (best, ~$15/Mtok)' },
  { value: 'claude-sonnet-4-6',          label: 'Sonnet 4.6 (fast, ~$3/Mtok)' },
  { value: 'claude-haiku-4-5-20251001',  label: 'Haiku 4.5 (cheap, ~$0.80/Mtok)' },
]

export default function AgentModelSettings({ password }: Props) {
  const [agentModel, setAgentModel] = useState('claude-opus-4-6')
  const [subagentModel, setSubagentModel] = useState('claude-sonnet-4-6')
  const [agentName, setAgentName] = useState('Adjutant')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getAgentConfig(password)
      .then(cfg => {
        setAgentModel(cfg.agent_model)
        setSubagentModel(cfg.subagent_model)
        setAgentName(cfg.agent_name)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  async function save() {
    setSaving(true)
    try {
      await api.updateAgentConfig(password, {
        agent_model: agentModel,
        subagent_model: subagentModel,
        agent_name: agentName,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

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
          <select
            value={agentModel}
            onChange={e => setAgentModel(e.target.value)}
            className={inputCls}
          >
            {MODEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Sub-agents (research, email, etc.)
          </label>
          <select
            value={subagentModel}
            onChange={e => setSubagentModel(e.target.value)}
            className={inputCls}
          >
            {MODEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
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
