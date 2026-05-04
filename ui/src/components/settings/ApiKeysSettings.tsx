import { useState, useEffect } from 'react'
import { api } from '../../api'

interface Props { password: string }

interface KeyStatus { configured: boolean; masked: string }

export default function ApiKeysSettings({ password }: Props) {
  const [anthropicKey, setAnthropicKey] = useState('')
  const [openaiKey,    setOpenaiKey]    = useState('')
  const [saving,       setSaving]       = useState<'anthropic' | 'openai' | null>(null)
  const [saved,        setSaved]        = useState<'anthropic' | 'openai' | null>(null)
  const [status,       setStatus]       = useState<Record<'anthropic' | 'openai', KeyStatus>>({
    anthropic: { configured: false, masked: '' },
    openai:    { configured: false, masked: '' },
  })

  useEffect(() => {
    Promise.all([
      api.getAnthropicKeyStatus(password),
      api.getOpenAIKeyStatus(password),
    ]).then(([anth, oai]) => {
      setStatus({ anthropic: anth, openai: oai })
    }).catch(() => {})
  }, [password])

  const save = async (provider: 'anthropic' | 'openai') => {
    setSaving(provider)
    try {
      const key = provider === 'anthropic' ? anthropicKey : openaiKey
      if (provider === 'anthropic') await api.updateAnthropicKey(password, key)
      else                          await api.updateOpenAIKey(password, key)
      setStatus(s => ({ ...s, [provider]: { configured: !!key, masked: key ? '••••••••' : '' } }))
      if (provider === 'anthropic') setAnthropicKey('')
      else                          setOpenaiKey('')
      setSaved(provider)
      setTimeout(() => setSaved(null), 2000)
    } finally {
      setSaving(null)
    }
  }

  const deleteKey = async (provider: 'anthropic' | 'openai') => {
    setSaving(provider)
    try {
      if (provider === 'anthropic') await api.updateAnthropicKey(password, '')
      else                          await api.updateOpenAIKey(password, '')
      setStatus(s => ({ ...s, [provider]: { configured: false, masked: '' } }))
      setSaved(provider)
      setTimeout(() => setSaved(null), 2000)
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-[15px] font-semibold text-adj-text-primary mb-1">API Keys</h2>
        <p className="text-[11px] text-adj-text-faint">Provider credentials for AI model access.</p>
      </div>

      {([
        { label: 'Anthropic', key: 'anthropic' as const, value: anthropicKey, setter: setAnthropicKey, placeholder: 'sk-ant-…', optional: true },
        { label: 'OpenAI',    key: 'openai'    as const, value: openaiKey,    setter: setOpenaiKey,    placeholder: 'sk-…',      optional: true },
      ] as const).map(({ label, key, value, setter, placeholder, optional }) => {
        const st = status[key]
        return (
          <div key={key}>
            <label className="block text-[11px] text-adj-text-secondary mb-1.5">
              {label} {optional && <span className="text-adj-text-faint">(optional)</span>}
            </label>
            {st.configured ? (
              <div className="flex items-center gap-2 max-w-md">
                <div className="flex-1 bg-adj-panel border border-adj-border rounded-lg px-3 py-2 text-[12px] text-adj-text-faint font-mono">
                  {st.masked}
                </div>
                <button
                  onClick={() => deleteKey(key)}
                  disabled={saving === key}
                  className="text-[11px] bg-adj-elevated border border-red-800/50 text-red-400 rounded-lg px-3 py-2 hover:border-red-600/60 hover:text-red-300 disabled:opacity-40 transition-colors"
                >
                  {saved === key ? '✓ Deleted' : saving === key ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            ) : (
              <div className="flex gap-2 max-w-md">
                <input
                  type="password"
                  value={value}
                  onChange={e => setter(e.target.value)}
                  placeholder={placeholder}
                  className="flex-1 bg-adj-panel border border-adj-border rounded-lg px-3 py-2 text-[12px] text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent/60"
                />
                <button
                  onClick={() => save(key)}
                  disabled={!value || saving === key}
                  className="text-[11px] bg-adj-elevated border border-adj-border text-adj-text-secondary rounded-lg px-3 py-2 hover:border-adj-accent/40 disabled:opacity-40 transition-colors"
                >
                  {saved === key ? '✓ Saved' : saving === key ? 'Saving…' : 'Save'}
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
