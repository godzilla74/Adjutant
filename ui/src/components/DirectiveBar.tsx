// ui/src/components/DirectiveBar.tsx
import { useState, useEffect, useRef, KeyboardEvent } from 'react'
import { api } from '../api'

interface Attachment {
  file: File
  path: string
  mime_type: string
  name: string
}

interface Props {
  onSend: (content: string, attachments?: Array<{ path: string; mime_type: string; name: string }>) => void
  disabled: boolean
  productName: string
  agentName: string
  prefill?: string
  onPrefillConsumed?: () => void
  password: string
}

export default function DirectiveBar({
  onSend, disabled, productName, agentName, prefill, onPrefillConsumed, password,
}: Props) {
  const [value,       setValue]      = useState('')
  const [attachment,  setAttachment] = useState<Attachment | null>(null)
  const [uploading,   setUploading]  = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (prefill) {
      setValue(prefill)
      onPrefillConsumed?.()
    }
  }, [prefill])

  // Auto-grow height as content changes
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)

    // Client-side size check
    const isVideo = file.type.startsWith('video/')
    const limit = isVideo ? 200 * 1024 * 1024 : 20 * 1024 * 1024
    if (file.size > limit) {
      setUploadError(`File too large (max ${isVideo ? '200' : '20'} MB)`)
      e.target.value = ''
      return
    }

    setUploading(true)
    try {
      const result = await api.uploadFile(file, password)
      setAttachment({ file, ...result })
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const removeAttachment = () => {
    setAttachment(null)
    setUploadError(null)
  }

  const submit = () => {
    const trimmed = value.trim()
    if ((!trimmed && !attachment) || disabled || uploading) return
    const attachments = attachment
      ? [{ path: attachment.path, mime_type: attachment.mime_type, name: attachment.name }]
      : undefined
    onSend(trimmed, attachments)
    setValue('')
    setAttachment(null)
    setUploadError(null)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="flex-shrink-0 border-t border-adj-border px-5 py-3 bg-adj-base">

      {/* Attachment pill */}
      {attachment && (
        <div className="flex items-center gap-2 mb-2">
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-adj-surface border border-zinc-700 text-xs text-adj-text-secondary max-w-xs">
            <span className="text-adj-text-muted">{attachment.mime_type.startsWith('video/') ? '🎬' : attachment.mime_type === 'application/pdf' ? '📄' : '🖼'}</span>
            <span className="truncate">{attachment.name}</span>
            <span className="text-adj-text-faint flex-shrink-0">{formatSize(attachment.file.size)}</span>
          </span>
          <button
            onClick={removeAttachment}
            className="text-adj-text-faint hover:text-adj-text-secondary transition-colors text-sm leading-none"
            aria-label="Remove attachment"
          >×</button>
        </div>
      )}

      {/* Upload error */}
      {uploadError && (
        <p className="text-xs text-red-400 mb-2">{uploadError}</p>
      )}

      {/* Input row */}
      <div className="flex items-end gap-3">
        <span className="text-xs text-adj-text-faint whitespace-nowrap flex-shrink-0 pb-2">
          Direct {agentName} →
        </span>

        {/* Paperclip */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          title="Attach file"
          className="flex-shrink-0 pb-2 text-adj-text-faint hover:text-adj-text-secondary disabled:opacity-40 transition-colors text-base"
        >
          📎
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf,video/*"
          className="hidden"
          onChange={handleFileChange}
        />

        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={onKey}
          disabled={disabled || uploading}
          rows={1}
          placeholder={`e.g. Focus all agents on ${productName} growth this week.`}
          className="flex-1 rounded-lg border border-adj-border bg-adj-panel px-3 py-2 text-sm text-adj-text-secondary placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-600 disabled:opacity-40 resize-none overflow-hidden leading-relaxed min-h-[36px] max-h-40"
        />

        <button
          type="button"
          onClick={submit}
          disabled={disabled || uploading || (!value.trim() && !attachment)}
          className="flex-shrink-0 rounded-lg bg-blue-600/20 border border-blue-600/50 text-adj-accent px-4 h-9 text-sm font-medium hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
