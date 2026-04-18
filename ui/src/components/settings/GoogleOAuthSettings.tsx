import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

export default function GoogleOAuthSettings({ password }: Props) {
  const [googleClientId, setGoogleClientId] = useState('')
  const [googleClientSecret, setGoogleClientSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getGoogleOAuthSettings(password).then((data) => {
      setGoogleClientId(data.google_oauth_client_id || '')
    }).catch(() => {}).finally(() => setLoading(false))
  }, [password])

  async function save() {
    setSaving(true)
    try {
      const update: { google_oauth_client_id?: string; google_oauth_client_secret?: string } = {
        google_oauth_client_id: googleClientId,
      }
      if (googleClientSecret) update.google_oauth_client_secret = googleClientSecret
      await api.updateGoogleOAuthSettings(password, update)
      setGoogleClientSecret('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between mb-1">
        <h2 className="text-base font-bold text-adj-text-primary">Google OAuth</h2>
        <a
          href="/google-oauth-guide.html"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-adj-accent hover:underline"
        >
          How to get credentials →
        </a>
      </div>
      <p className="text-xs text-adj-text-muted mb-6">Configure Google Cloud OAuth credentials for Gmail and Calendar connections</p>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Client ID
          </label>
          <input
            type="text"
            value={googleClientId}
            onChange={(e) => setGoogleClientId(e.target.value)}
            placeholder="your-client-id.apps.googleusercontent.com"
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">
            Client Secret
          </label>
          <input
            type="password"
            value={googleClientSecret}
            onChange={(e) => setGoogleClientSecret(e.target.value)}
            placeholder="Leave blank to keep existing secret"
            className={inputCls}
          />
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
