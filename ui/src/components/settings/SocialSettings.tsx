import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

export default function SocialSettings({ password }: Props) {
  const [twitterClientId, setTwitterClientId] = useState('')
  const [twitterClientSecret, setTwitterClientSecret] = useState('')
  const [linkedinClientId, setLinkedinClientId] = useState('')
  const [linkedinClientSecret, setLinkedinClientSecret] = useState('')
  const [metaAppId, setMetaAppId] = useState('')
  const [metaAppSecret, setMetaAppSecret] = useState('')
  const [socialSaving, setSocialSaving] = useState<string | null>(null)
  const [savedPlatform, setSavedPlatform] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getSocialSettings(password).then((data) => {
      setTwitterClientId(data.twitter_client_id || '')
      setLinkedinClientId(data.linkedin_client_id || '')
      setMetaAppId(data.meta_app_id || '')
    }).catch(() => {}).finally(() => setLoading(false))
  }, [password])

  async function saveTwitter(data: { twitter_client_id?: string; twitter_client_secret?: string }) {
    setSocialSaving('twitter')
    try {
      await api.updateTwitterSettings(password, data)
      setTwitterClientSecret('')
      setSavedPlatform('twitter')
      setTimeout(() => setSavedPlatform(null), 2000)
    } finally {
      setSocialSaving(null)
    }
  }

  async function saveLinkedIn(data: { linkedin_client_id?: string; linkedin_client_secret?: string }) {
    setSocialSaving('linkedin')
    try {
      await api.updateLinkedInSettings(password, data)
      setLinkedinClientSecret('')
      setSavedPlatform('linkedin')
      setTimeout(() => setSavedPlatform(null), 2000)
    } finally {
      setSocialSaving(null)
    }
  }

  async function saveMeta(data: { meta_app_id?: string; meta_app_secret?: string }) {
    setSocialSaving('meta')
    try {
      await api.updateMetaSettings(password, data)
      setMetaAppSecret('')
      setSavedPlatform('meta')
      setTimeout(() => setSavedPlatform(null), 2000)
    } finally {
      setSocialSaving(null)
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="max-w-lg">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Social Accounts</h2>
      <p className="text-xs text-adj-text-muted mb-6">Store OAuth app credentials for social platform integrations</p>

      <div className="flex flex-col gap-6">
        {/* Twitter / X */}
        <div className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-wider text-adj-text-muted">Twitter / X</p>
          <input
            type="text"
            value={twitterClientId}
            onChange={(e) => setTwitterClientId(e.target.value)}
            placeholder="Client ID"
            className={inputCls}
          />
          <input
            type="password"
            value={twitterClientSecret}
            onChange={(e) => setTwitterClientSecret(e.target.value)}
            placeholder="Client Secret (leave blank to keep)"
            className={inputCls}
          />
          <button
            onClick={() => saveTwitter({
              twitter_client_id: twitterClientId,
              ...(twitterClientSecret ? { twitter_client_secret: twitterClientSecret } : {}),
            })}
            disabled={socialSaving === 'twitter'}
            className="px-4 py-2 text-sm bg-adj-accent hover:bg-adj-accent-dark text-white rounded-md disabled:opacity-50 transition-colors"
          >
            {savedPlatform === 'twitter' ? '✓ Saved' : socialSaving === 'twitter' ? 'Saving…' : 'Save'}
          </button>
        </div>

        <div className="border-t border-adj-border" />

        {/* LinkedIn */}
        <div className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-wider text-adj-text-muted">LinkedIn</p>
          <input
            type="text"
            value={linkedinClientId}
            onChange={(e) => setLinkedinClientId(e.target.value)}
            placeholder="Client ID"
            className={inputCls}
          />
          <input
            type="password"
            value={linkedinClientSecret}
            onChange={(e) => setLinkedinClientSecret(e.target.value)}
            placeholder="Client Secret (leave blank to keep)"
            className={inputCls}
          />
          <button
            onClick={() => saveLinkedIn({
              linkedin_client_id: linkedinClientId,
              ...(linkedinClientSecret ? { linkedin_client_secret: linkedinClientSecret } : {}),
            })}
            disabled={socialSaving === 'linkedin'}
            className="px-4 py-2 text-sm bg-adj-accent hover:bg-adj-accent-dark text-white rounded-md disabled:opacity-50 transition-colors"
          >
            {savedPlatform === 'linkedin' ? '✓ Saved' : socialSaving === 'linkedin' ? 'Saving…' : 'Save'}
          </button>
        </div>

        <div className="border-t border-adj-border" />

        {/* Meta */}
        <div className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-wider text-adj-text-muted">Meta (Facebook + Instagram)</p>
          <input
            type="text"
            value={metaAppId}
            onChange={(e) => setMetaAppId(e.target.value)}
            placeholder="App ID"
            className={inputCls}
          />
          <input
            type="password"
            value={metaAppSecret}
            onChange={(e) => setMetaAppSecret(e.target.value)}
            placeholder="App Secret (leave blank to keep)"
            className={inputCls}
          />
          <button
            onClick={() => saveMeta({
              meta_app_id: metaAppId,
              ...(metaAppSecret ? { meta_app_secret: metaAppSecret } : {}),
            })}
            disabled={socialSaving === 'meta'}
            className="px-4 py-2 text-sm bg-adj-accent hover:bg-adj-accent-dark text-white rounded-md disabled:opacity-50 transition-colors"
          >
            {savedPlatform === 'meta' ? '✓ Saved' : socialSaving === 'meta' ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
