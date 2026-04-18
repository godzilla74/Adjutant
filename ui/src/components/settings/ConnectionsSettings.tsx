import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  productId: string
  password: string
  onOpenSettings?: (tab: string) => void
}

const GOOGLE_SERVICES = new Set(['gmail', 'google_calendar'])

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
  const [loading, setLoading] = useState(true)
  const [googleOAuthConfigured, setGoogleOAuthConfigured] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    if (!productId) return
    setLoading(true)
    Promise.all([
      api.getOAuthConnections(password, productId),
      api.getGoogleOAuthSettings(password),
    ]).then(([conns, googleCfg]) => {
      setOauthConnections(conns)
      setGoogleOAuthConfigured(!!googleCfg.google_oauth_client_id)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [password, productId])

  async function handleConnectOAuth(service: ConnectAsKey) {
    if (!productId) return
    setConnectingService(service)
    try {
      const { auth_url } = await api.startOAuthFlow(password, productId, service)
      const popup = window.open(auth_url, '_blank', 'width=500,height=600')
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

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="max-w-4xl">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Connections</h2>
      <p className="text-xs text-adj-text-muted mb-6">Manage OAuth integrations for this product</p>

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
          return (
            <div
              key={key}
              className="flex items-center justify-between bg-adj-panel border border-adj-border rounded-md px-4 py-3"
            >
              <div>
                <p className="text-sm text-adj-text-secondary font-medium">{label}</p>
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
              ) : (
                <button
                  onClick={() => !needsGoogleOAuth && handleConnectOAuth(connectAs)}
                  disabled={isConnecting || needsGoogleOAuth}
                  title={needsGoogleOAuth ? 'Set up Google OAuth credentials first' : undefined}
                  className="px-3 py-1.5 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isConnecting ? 'Connecting…' : 'Connect'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
