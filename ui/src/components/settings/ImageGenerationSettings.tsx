import { useEffect, useRef, useState } from 'react'
import { api } from '../../api'

interface Props {
  password: string
}

export default function ImageGenerationSettings({ password }: Props) {
  const [pexelsKey, setPexelsKey] = useState('')
  const [pexelsConfigured, setPexelsConfigured] = useState(false)
  const [pexelsError, setPexelsError] = useState<string | null>(null)
  const [openaiConnected, setOpenaiConnected] = useState(false)
  const [savingPexels, setSavingPexels] = useState(false)
  const [pexelsSaved, setPexelsSaved] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [loading, setLoading] = useState(true)
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
    api.getImageGenerationSettings(password).then((data) => {
      setPexelsConfigured(data.pexels_configured)
      setOpenaiConnected(data.openai_connected)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [password])

  async function savePexels() {
    if (!pexelsKey.trim()) return
    setSavingPexels(true)
    setPexelsError(null)
    try {
      await api.updateImageGenerationSettings(password, { pexels_api_key: pexelsKey.trim() })
      setPexelsKey('')
      setPexelsConfigured(true)
      setPexelsSaved(true)
      setTimeout(() => setPexelsSaved(false), 2000)
    } catch (e: unknown) {
      setPexelsError((e as Error).message || 'Failed to save API key')
    } finally {
      setSavingPexels(false)
    }
  }

  async function connectOpenAI() {
    setConnecting(true)
    try {
      const { auth_url } = await api.startOpenAIOAuth(password)
      const popup = window.open(auth_url, '_blank', 'width=500,height=600')
      popupRef.current = popup
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getOpenAIOAuthStatus(password)
          if (status.connected) {
            setOpenaiConnected(true)
            setConnecting(false)
            clearInterval(pollRef.current!)
            pollRef.current = null
            return
          }
        } catch {}
        if (!popup || popup.closed) {
          setConnecting(false)
          clearInterval(pollRef.current!)
          pollRef.current = null
        }
      }, 1500)
    } catch {
      setConnecting(false)
    }
  }

  async function disconnectOpenAI() {
    try {
      await api.disconnectOpenAI(password)
      setOpenaiConnected(false)
    } catch {
      // silent fail is acceptable here — button remains visible
    }
  }

  const inputCls = 'w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent transition-colors'

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">Image Generation</h2>
      <p className="text-xs text-adj-text-muted mb-6">Configure image sources for autonomous social post image selection</p>

      <div className="flex flex-col gap-6">
        {/* Pexels */}
        <div className="bg-adj-panel border border-adj-border rounded-md px-4 py-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-adj-text-secondary">Pexels (Stock Photos)</p>
              <p className="text-xs text-adj-text-muted mt-0.5">
                {pexelsConfigured ? 'Connected' : 'Not configured'}
              </p>
            </div>
            {pexelsConfigured && (
              <span className="text-xs text-green-400">✓ Configured</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder={pexelsConfigured ? 'Enter new key to update' : 'Paste Pexels API key'}
              value={pexelsKey}
              onChange={(e) => setPexelsKey(e.target.value)}
              className={inputCls}
            />
            <button
              onClick={savePexels}
              disabled={!pexelsKey.trim() || savingPexels}
              className="px-4 py-2 text-sm bg-adj-accent hover:bg-adj-accent-dark text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {pexelsSaved ? '✓ Saved' : savingPexels ? 'Saving…' : 'Save'}
            </button>
          </div>
          {pexelsError && (
            <p className="text-xs text-red-400">{pexelsError}</p>
          )}
          <p className="text-[10px] text-adj-text-faint">
            Free API key at{' '}
            <span className="text-adj-text-muted">pexels.com/api</span>
          </p>
        </div>

        {/* OpenAI */}
        <div className="bg-adj-panel border border-adj-border rounded-md px-4 py-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-adj-text-secondary">OpenAI Image Generation</p>
              <p className="text-xs text-adj-text-muted mt-0.5">
                {openaiConnected ? 'Connected' : 'Not connected'}
              </p>
            </div>
            {openaiConnected ? (
              <button
                onClick={disconnectOpenAI}
                className="text-xs text-red-400 hover:text-red-300 hover:underline"
              >
                Disconnect
              </button>
            ) : (
              <button
                onClick={connectOpenAI}
                disabled={connecting}
                className="px-4 py-2 text-sm bg-adj-accent hover:bg-adj-accent-dark text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {connecting ? 'Connecting…' : 'Connect with OpenAI'}
              </button>
            )}
          </div>
          <p className="text-[10px] text-adj-text-faint">
            Uses your ChatGPT account via Codex OAuth. Generates images with DALL-E 3.
          </p>
        </div>
      </div>
    </div>
  )
}
