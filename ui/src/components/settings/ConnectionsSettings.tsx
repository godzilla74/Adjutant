import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  productId: string
  password: string
  onOpenSettings?: (tab: string) => void
}

const GOOGLE_SERVICES = new Set(['gmail', 'google_calendar'])
const BROWSER_CRED_SERVICES = new Set(['twitter', 'linkedin', 'facebook', 'instagram'])

const SERVICES = [
  { key: 'gmail',            label: 'Gmail',            connectAs: 'gmail' },
  { key: 'google_calendar',  label: 'Google Calendar',  connectAs: 'google_calendar' },
  { key: 'twitter',          label: 'Twitter / X',      connectAs: 'twitter' },
  { key: 'linkedin',         label: 'LinkedIn',         connectAs: 'linkedin' },
  { key: 'facebook',         label: 'Facebook',         connectAs: 'meta' },
  { key: 'instagram',        label: 'Instagram',        connectAs: 'meta' },
] as const

type ConnectAsKey = typeof SERVICES[number]['connectAs']

export default function ConnectionsSettings({ productId, password, onOpenSettings }: Props) {
  const [oauthConnections, setOauthConnections] = useState<
    { service: string; email: string; scopes: string; updated_at: string }[]
  >([])
  const [connectingService, setConnectingService] = useState<string | null>(null)
  const [oauthError, setOauthError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [googleOAuthConfigured, setGoogleOAuthConfigured] = useState(false)
  const [browserCreds, setBrowserCreds] = useState<
    { service: string; username: string; active: boolean }[]
  >([])
  const [credFields, setCredFields] = useState<
    Record<string, { username: string; password: string; saved: boolean }>
  >({})
  const [savingCred, setSavingCred] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const popupRef = useRef<Window | null>(null)

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.source !== popupRef.current) return
      if (e.data?.type === 'oauth_error') {
        clearInterval(pollRef.current!)
        pollRef.current = null
        setConnectingService(null)
        setOauthError(e.data.message ?? 'OAuth failed')
      } else if (e.data?.type === 'oauth_success') {
        api.getOAuthConnections(password, productId).then(setOauthConnections).catch(() => {})
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [password, productId])

  useEffect(() => {
    if (!productId) return
    setLoading(true)
    Promise.all([
      api.getOAuthConnections(password, productId),
      api.getGoogleOAuthSettings(password),
      api.getBrowserCredentials(password, productId),
    ]).then(([conns, googleCfg, bCreds]) => {
      setOauthConnections(conns)
      setGoogleOAuthConfigured(!!googleCfg.google_oauth_client_id)
      setBrowserCreds(bCreds)
      const fields: Record<string, { username: string; password: string; saved: boolean }> = {}
      for (const c of bCreds) {
        fields[c.service] = { username: c.username, password: '', saved: true }
      }
      setCredFields(fields)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [password, productId])

  async function handleConnectOAuth(service: ConnectAsKey) {
    if (!productId) return
    setConnectingService(service)
    setOauthError(null)
    try {
      const { auth_url } = await api.startOAuthFlow(password, productId, service)
      const popup = window.open(auth_url, '_blank', 'width=500,height=600')
      popupRef.current = popup
      pollRef.current = setInterval(async () => {
        try {
          const conns = await api.getOAuthConnections(password, productId)
          if (conns.some((c) => c.service === service)) {
            setOauthConnections(conns)
            clearInterval(pollRef.current!)
            pollRef.current = null
            setConnectingService(null)
            return
          }
        } catch {}
        if (!popup || popup.closed) {
          clearInterval(pollRef.current!)
          pollRef.current = null
          setConnectingService(null)
        }
      }, 1500)
    } catch (e: unknown) {
      alert((e as Error).message || 'Failed to start OAuth flow')
      setConnectingService(null)
    }
  }

  async function handleDisconnectOAuth(service: string) {
    if (!productId) return
    await api.deleteOAuthConnection(password, productId, service)
    setOauthConnections((prev) => prev.filter((c) => c.service !== service))
  }

  async function handleToggleMode(service: string, toBrowser: boolean) {
    if (!productId) return
    const existing = credFields[service]
    await api.saveBrowserCredential(password, productId, service, {
      username: existing?.username ?? '',
      password: existing?.saved ? '' : (existing?.password ?? ''),
      active: toBrowser,
    })
    setBrowserCreds((prev) => {
      const exists = prev.find((c) => c.service === service)
      if (exists) return prev.map((c) => c.service === service ? { ...c, active: toBrowser } : c)
      return [...prev, { service, username: existing?.username ?? '', active: toBrowser }]
    })
  }

  async function handleSaveCred(service: string) {
    if (!productId) return
    const fields = credFields[service]
    if (!fields?.username) return
    setSavingCred(service)
    try {
      await api.saveBrowserCredential(password, productId, service, {
        username: fields.username,
        password: fields.password,
        active: true,
      })
      setBrowserCreds((prev) => {
        const exists = prev.find((c) => c.service === service)
        if (exists) return prev.map((c) => c.service === service ? { ...c, username: fields.username, active: true } : c)
        return [...prev, { service, username: fields.username, active: true }]
      })
      setCredFields((prev) => ({ ...prev, [service]: { username: fields.username, password: '', saved: true } }))
    } finally {
      setSavingCred(null)
    }
  }

  async function handleRemoveCred(service: string) {
    if (!productId) return
    await api.deleteBrowserCredential(password, productId, service)
    setBrowserCreds((prev) => prev.filter((c) => c.service !== service))
    setCredFields((prev) => {
      const next = { ...prev }
      delete next[service]
      return next
    })
  }

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Connections</h2>
      <p className="text-xs text-adj-text-muted mb-6">Manage OAuth integrations for this product</p>

      {oauthError && (
        <div className="mb-4 flex items-start gap-3 p-3 bg-red-950/40 border border-red-800/50 rounded-md">
          <span className="text-red-400 flex-shrink-0 mt-0.5">✕</span>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-red-300">{oauthError}</p>
          </div>
          <button onClick={() => setOauthError(null)} className="text-red-500 hover:text-red-300 text-xs">✕</button>
        </div>
      )}

      {!googleOAuthConfigured && (
        <div className="mb-4 flex items-start gap-3 p-3 bg-amber-950/40 border border-amber-800/50 rounded-md">
          <span className="text-amber-400 flex-shrink-0 mt-0.5">⚠</span>
          <p className="text-xs text-amber-300">
            Gmail and Google Calendar require Google OAuth credentials before you can connect.{' '}
            <button
              onClick={() => onOpenSettings?.('google-oauth')}
              className="underline hover:text-amber-200 transition-colors"
            >
              Set up Google OAuth →
            </button>
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {SERVICES.map(({ key, label, connectAs }) => {
          const conn = oauthConnections.find((c) => c.service === key)
          const isConnecting = connectingService === connectAs
          const needsGoogleOAuth = GOOGLE_SERVICES.has(key) && !googleOAuthConfigured
          const isBrowserCapable = BROWSER_CRED_SERVICES.has(key)
          const browserCred = browserCreds.find((c) => c.service === key)
          const isBrowserMode = isBrowserCapable && (browserCred?.active ?? false)
          const fields = credFields[key]

          return (
            <div
              key={key}
              className="bg-adj-panel border border-adj-border rounded-md px-4 py-3 flex flex-col gap-3"
            >
              {/* Header row: label + toggle */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-adj-text-secondary font-medium">{label}</p>
                {isBrowserCapable && (
                  <div className="flex rounded overflow-hidden border border-adj-border text-[11px]">
                    <button
                      onClick={() => handleToggleMode(key, false)}
                      className={`px-2.5 py-1 transition-colors ${!isBrowserMode ? 'bg-adj-accent text-white' : 'text-adj-text-muted hover:text-adj-text-secondary'}`}
                    >
                      OAuth
                    </button>
                    <button
                      onClick={() => handleToggleMode(key, true)}
                      className={`px-2.5 py-1 transition-colors ${isBrowserMode ? 'bg-adj-accent text-white' : 'text-adj-text-muted hover:text-adj-text-secondary'}`}
                    >
                      Browser
                    </button>
                  </div>
                )}
              </div>

              {/* OAuth mode content */}
              {!isBrowserMode && (
                <div className="flex items-center justify-between">
                  <div>
                    {conn ? (
                      <p className="text-xs text-adj-text-muted">Connected as {conn.email}</p>
                    ) : needsGoogleOAuth ? (
                      <p className="text-xs text-amber-600">Google OAuth required</p>
                    ) : (
                      <p className="text-xs text-adj-text-faint">Not connected</p>
                    )}
                  </div>
                  {conn ? (
                    <button
                      onClick={() => handleDisconnectOAuth(key)}
                      className="text-xs text-red-400 hover:text-red-300 hover:underline"
                    >
                      Disconnect
                    </button>
                  ) : needsGoogleOAuth ? (
                    <span className="text-xs text-adj-text-faint">Configure Google OAuth first</span>
                  ) : (
                    <button
                      onClick={() => handleConnectOAuth(connectAs)}
                      disabled={isConnecting}
                      className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isConnecting ? 'Connecting…' : 'Connect'}
                    </button>
                  )}
                </div>
              )}

              {/* Browser mode content */}
              {isBrowserMode && (
                <div className="flex flex-col gap-2">
                  <input
                    type="text"
                    placeholder="Username or email"
                    value={fields?.username ?? ''}
                    onChange={(e) => setCredFields((prev) => ({
                      ...prev,
                      [key]: { username: e.target.value, password: prev[key]?.password ?? '', saved: false },
                    }))}
                    className="w-full text-xs bg-adj-bg border border-adj-border rounded px-2.5 py-1.5 text-adj-text-secondary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={fields?.saved ? '••••••••' : (fields?.password ?? '')}
                    onFocus={(e) => {
                      if (fields?.saved) {
                        setCredFields((prev) => ({ ...prev, [key]: { ...prev[key], password: '', saved: false } }))
                        e.target.value = ''
                      }
                    }}
                    onChange={(e) => setCredFields((prev) => ({
                      ...prev,
                      [key]: { username: prev[key]?.username ?? '', password: e.target.value, saved: false },
                    }))}
                    className="w-full text-xs bg-adj-bg border border-adj-border rounded px-2.5 py-1.5 text-adj-text-secondary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent"
                  />
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => handleSaveCred(key)}
                      disabled={!fields?.username || savingCred === key}
                      className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {savingCred === key ? 'Saving…' : fields?.saved ? 'Saved ✓' : 'Save'}
                    </button>
                    {browserCred && (
                      <button
                        onClick={() => handleRemoveCred(key)}
                        className="text-xs text-red-400 hover:text-red-300 hover:underline"
                      >
                        Remove credentials
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
