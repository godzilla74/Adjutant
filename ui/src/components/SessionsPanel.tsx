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
                <div className="px-3 py-1.5 bg-red-950/30 border-l-2 border-red-800">
                  <div className="text-[10px] text-red-400 mb-1.5">Delete "{s.name}" and its history?</div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { onDelete(s.id); setConfirmDeleteId(null) }}
                      className="text-[10px] text-red-400 hover:text-red-300 font-medium"
                    >Delete</button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="text-[10px] text-zinc-500 hover:text-zinc-400"
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
                  <span className="text-[10px] flex-1 truncate leading-none">💬 {s.name}</span>
                  {sessions.length > 1 && (
                    <button
                      onClick={e => { e.stopPropagation(); setConfirmDeleteId(s.id) }}
                      className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-red-400 transition-all text-xs leading-none flex-shrink-0"
                      aria-label="Delete session"
                    >×</button>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
