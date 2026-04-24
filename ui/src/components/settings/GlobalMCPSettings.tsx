import { useEffect, useState } from 'react'
import { api } from '../../api'
import {
  McpServer, AddFormState, EditState, Extension, ExtEditState,
  rowCls, inputCls, McpRow, EditForm, AddForm, ExtRow, ExtEditForm,
} from './MCPShared'

interface Props {
  password: string
}

const BLANK_FORM: AddFormState = { name: '', type: 'remote', url: '', command: '', args: '', env: '' }

export default function GlobalMCPSettings({ password }: Props) {
  const [servers, setServers] = useState<McpServer[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState<AddFormState>(BLANK_FORM)
  const [editState, setEditState] = useState<EditState | null>(null)
  const [extensions, setExtensions] = useState<Extension[]>([])
  const [extEditState, setExtEditState] = useState<ExtEditState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getMcpServers(password),
      api.listExtensions(password),
    ])
      .then(([allServers, exts]) => {
        setServers(allServers.filter(s => s.scope === 'global'))
        // listExtensions returns the old global-only list; use it for global custom tools
        setExtensions(exts as unknown as Extension[])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  const handleToggle = async (id: number, enabled: boolean) => {
    await api.updateMcpServer(password, id, { enabled: !enabled }).catch(() => null)
    setServers(prev => prev.map(s => s.id === id ? { ...s, enabled: enabled ? 0 : 1 } : s))
  }

  const handleDelete = async (id: number) => {
    await api.deleteMcpServer(password, id).catch(() => null)
    setServers(prev => prev.filter(s => s.id !== id))
    if (editState?.id === id) setEditState(null)
  }

  const handleEdit = async (id: number) => {
    if (editState?.id === id) { setEditState(null); return }
    const server = await api.getMcpServer(password, id).catch(() => null)
    if (!server) return
    let envStr = ''
    if (server.env) {
      try { envStr = JSON.stringify(JSON.parse(server.env), null, 2) } catch { envStr = server.env }
    }
    let argsStr = ''
    if (server.args) {
      try { argsStr = (JSON.parse(server.args) as string[]).join(' ') } catch { argsStr = server.args }
    }
    setEditState({ id, name: server.name, type: server.type, url: server.url ?? '', command: server.command ?? '', args: argsStr, env: envStr, saving: false, error: '' })
  }

  const handleEditSave = async () => {
    if (!editState) return
    let envParsed: Record<string, unknown> | undefined
    if (editState.env.trim()) {
      try { envParsed = JSON.parse(editState.env) }
      catch { setEditState(s => s ? { ...s, error: 'Invalid JSON in config/env field' } : s); return }
    }
    setEditState(s => s ? { ...s, saving: true, error: '' } : s)
    const patch: Parameters<typeof api.updateMcpServer>[2] = { name: editState.name }
    if (editState.type === 'remote') { patch.url = editState.url }
    else { patch.command = editState.command; patch.args = editState.args ? editState.args.split(/\s+/).filter(Boolean) : [] }
    if (envParsed !== undefined) patch.env = envParsed
    const updated = await api.updateMcpServer(password, editState.id, patch).catch(() => null)
    if (updated) { setServers(prev => prev.map(s => s.id === editState.id ? { ...s, ...updated } : s)); setEditState(null) }
    else { setEditState(s => s ? { ...s, saving: false, error: 'Save failed' } : s) }
  }

  const handleAdd = async () => {
    const f = addForm
    let envParsed: Record<string, unknown> | undefined
    if (f.env.trim()) {
      try { envParsed = JSON.parse(f.env) } catch { return }
    }
    const payload: Parameters<typeof api.addMcpServer>[1] = {
      name: f.name, type: f.type, scope: 'global',
      ...(f.type === 'remote' ? { url: f.url } : { command: f.command, args: f.args ? f.args.split(' ') : [] }),
      ...(envParsed !== undefined ? { env: envParsed as Record<string, string> } : {}),
    }
    const created = await api.addMcpServer(password, payload).catch(() => null)
    if (created) { setServers(prev => [...prev, created as McpServer]); setAddOpen(false); setAddForm(BLANK_FORM) }
  }

  const handleExtToggle = async (name: string, enabled: boolean) => {
    await api.updateExtension(password, name, { enabled: !enabled }).catch(() => null)
    setExtensions(prev => prev.map(e => e.name === name ? { ...e, enabled: !enabled } : e))
  }

  const handleExtDelete = async (name: string) => {
    if (!confirm(`Delete the "${name}" tool? This cannot be undone.`)) return
    await api.deleteExtension(password, name).catch(() => null)
    setExtensions(prev => prev.filter(e => e.name !== name))
    if (extEditState?.name === name) setExtEditState(null)
  }

  const handleExtEdit = (name: string) => {
    if (extEditState?.name === name) { setExtEditState(null); return }
    const ext = extensions.find(e => e.name === name)
    if (!ext) return
    setExtEditState({ name, description: ext.description, instructions: '', saving: false, error: '' })
  }

  const handleExtSave = async () => {
    if (!extEditState) return
    setExtEditState(s => s ? { ...s, saving: true, error: '' } : s)
    const ok = await api.updateExtension(password, extEditState.name, {
      description: extEditState.description,
      instructions: extEditState.instructions,
    }).catch(() => null)
    if (ok) {
      setExtensions(prev => prev.map(e => e.name === extEditState.name ? { ...e, description: extEditState.description } : e))
      setExtEditState(null)
    } else {
      setExtEditState(s => s ? { ...s, saving: false, error: 'Save failed' } : s)
    }
  }

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">MCP Servers</h2>
      <p className="text-xs text-adj-text-muted mb-6">Global servers are available to all products</p>

      {/* Global servers */}
      <div className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">Global Servers</p>
        {servers.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None configured</p>
        ) : (
          <div className="flex flex-col gap-1">
            {servers.map(s => (
              <div key={s.id}>
                <McpRow s={s} onToggle={handleToggle} onDelete={handleDelete} onEdit={handleEdit} />
                {editState?.id === s.id && (
                  <EditForm state={editState} onChange={u => setEditState(prev => prev ? u(prev) : prev)} onSave={handleEditSave} onCancel={() => setEditState(null)} />
                )}
              </div>
            ))}
          </div>
        )}
        {addOpen ? (
          <AddForm form={addForm} onChange={setAddForm} onAdd={handleAdd} onCancel={() => setAddOpen(false)} />
        ) : (
          <button onClick={() => setAddOpen(true)} className="mt-3 text-xs text-adj-text-muted hover:text-adj-text-primary transition-colors">
            + Add global server
          </button>
        )}
      </div>

      <div className="border-t border-adj-border mb-6" />

      {/* Global custom tools */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Global Custom Tools</p>
        <p className="text-xs text-adj-text-faint mb-3">Agent-created tools available to all products</p>
        {extensions.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None yet — ask the agent to integrate an API and it will appear here.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {extensions.map(ext => (
              <div key={ext.name}>
                <ExtRow ext={ext} onToggle={handleExtToggle} onDelete={handleExtDelete} onEdit={handleExtEdit} />
                {extEditState?.name === ext.name && (
                  <ExtEditForm state={extEditState} onChange={u => setExtEditState(prev => prev ? u(prev) : prev)} onSave={handleExtSave} onCancel={() => setExtEditState(null)} />
                )}
              </div>
            ))}
          </div>
        )}
        <p className="text-[10px] text-adj-text-faint mt-3">Enable/disable changes take effect after the server restarts.</p>
      </div>
    </div>
  )
}
