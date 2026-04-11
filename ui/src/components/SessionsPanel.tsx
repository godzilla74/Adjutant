import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { Session } from '../types'

interface Props {
  sessions:        Session[]
  activeSessionId: string | null
  onSwitch:        (sessionId: string) => void
  onCreate:        (name: string) => void
  onRename:        (sessionId: string, name: string) => void
  onDelete:        (sessionId: string) => void
}

function TrashIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M6.5 1h3a.5.5 0 0 1 .5.5v1H6v-1a.5.5 0 0 1 .5-.5ZM11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3A1.5 1.5 0 0 0 5 1.5v1H2.5a.5.5 0 0 0 0 1H3v9a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-9h.5a.5.5 0 0 0 0-1H11Zm-7.5 1h9v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9Zm2.5 2a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0v-6a.5.5 0 0 1 .5-.5Zm3 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0v-6a.5.5 0 0 1 .5-.5Z"/>
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708l-3-3ZM13.5 6.207 9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207l6.5-6.5ZM2.25 12.854l-.892-4.462 5.853-5.853L10.5 5.828l-5.853 5.853-2.397-.827Z"/>
    </svg>
  )
}

export default function SessionsPanel({
  sessions, activeSessionId, onSwitch, onCreate, onRename, onDelete,
}: Props) {
  const [creating,        setCreating]        = useState(false)
  const [newName,         setNewName]         = useState('')
  const [renamingId,      setRenamingId]      = useState<string | null>(null)
  const [renameValue,     setRenameValue]     = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const newInputRef    = useRef<HTMLInputElement>(null)
  const renameInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (creating) newInputRef.current?.focus()
  }, [creating])

  useEffect(() => {
    if (renamingId) renameInputRef.current?.focus()
  }, [renamingId])

  const submitCreate = () => {
    const name = newName.trim()
    if (!name) return
    onCreate(name)
    setNewName('')
    setCreating(false)
  }

  const startRename = (s: Session) => {
    setRenamingId(s.id)
    setRenameValue(s.name)
    setConfirmDeleteId(null)
  }

  const submitRename = () => {
    if (!renamingId) return
    const name = renameValue.trim()
    if (name) onRename(renamingId, name)
    setRenamingId(null)
  }

  const handleNewKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submitCreate()
    if (e.key === 'Escape') { setCreating(false); setNewName('') }
  }

  const handleRenameKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submitRename()
    if (e.key === 'Escape') setRenamingId(null)
  }

  return (
    <div className="border-b border-zinc-800/60 pb-2">
      <div className="flex items-center justify-between px-3.5 pt-3 pb-1">
        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
          Sessions
        </span>
        <button
          onClick={() => { setCreating(true); setConfirmDeleteId(null); setRenamingId(null) }}
          className="text-[10px] text-blue-500 hover:text-blue-400 transition-colors"
          title="New session"
        >
          + New
        </button>
      </div>

      {creating && (
        <div className="px-3 pb-1">
          <input
            ref={newInputRef}
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={handleNewKey}
            onBlur={() => { if (!newName.trim()) { setCreating(false) } }}
            placeholder="Session name"
            className="w-full bg-zinc-900 border border-zinc-700 rounded text-[11px] text-zinc-200 px-2 py-1 focus:outline-none focus:border-zinc-500"
          />
        </div>
      )}

      <div className="flex flex-col">
        {sessions.map(s => {
          const isActive   = s.id === activeSessionId
          const isRenaming = s.id === renamingId
          const isConfirm  = s.id === confirmDeleteId

          return (
            <div key={s.id} className="group relative">
              {isRenaming ? (
                <div className="px-3 py-0.5">
                  <input
                    ref={renameInputRef}
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onKeyDown={handleRenameKey}
                    onBlur={submitRename}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded text-[11px] text-zinc-200 px-2 py-1 focus:outline-none focus:border-zinc-500"
                  />
                </div>
              ) : isConfirm ? (
                <div className="px-3 py-2 bg-red-950/30 border-l-2 border-red-800">
                  <div className="text-[10px] text-red-400 mb-2">Delete "{s.name}" and its history?</div>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => { onDelete(s.id); setConfirmDeleteId(null) }}
                      className="flex-1 bg-red-900/60 hover:bg-red-800/70 border border-red-700/50 text-red-300 text-[10px] font-medium rounded px-2 py-1 transition-colors"
                    >Delete</button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="flex-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 text-[10px] rounded px-2 py-1 transition-colors"
                    >Cancel</button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => { if (!isActive) onSwitch(s.id); setConfirmDeleteId(null) }}
                  onDoubleClick={() => isActive && startRename(s)}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 cursor-default select-none ${
                    isActive
                      ? 'bg-blue-600/10 border-l-2 border-blue-600 text-zinc-200'
                      : 'text-zinc-500 hover:bg-zinc-900/60 hover:text-zinc-300'
                  }`}
                >
                  <span className="text-sm flex-1 truncate leading-snug">💬 {s.name}</span>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                    {isActive && (
                      <button
                        onClick={e => { e.stopPropagation(); startRename(s) }}
                        className="text-zinc-600 hover:text-zinc-300 transition-colors"
                        aria-label="Rename session"
                        title="Rename"
                      ><PencilIcon /></button>
                    )}
                    {sessions.length > 1 && (
                      <button
                        onClick={e => { e.stopPropagation(); setConfirmDeleteId(s.id) }}
                        className="text-zinc-600 hover:text-red-400 transition-colors"
                        aria-label="Delete session"
                        title="Delete"
                      ><TrashIcon /></button>
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
