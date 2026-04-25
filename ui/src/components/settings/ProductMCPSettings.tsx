import { useEffect, useState } from 'react'
import { api } from '../../api'
import {
  McpServer, AddFormState, EditState, Extension, ExtEditState,
  CapabilityOverride, CapabilitySlot,
  inputCls, McpRow, EditForm, AddForm, ExtRow, ExtEditForm,
} from './MCPShared'

interface Props {
  productId: string
  password: string
}

const BLANK_FORM: AddFormState = { name: '', type: 'remote', url: '', command: '', args: '', env: '' }

export default function ProductMCPSettings({ productId, password }: Props) {
  const [allServers, setAllServers] = useState<McpServer[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState<AddFormState>(BLANK_FORM)
  const [editState, setEditState] = useState<EditState | null>(null)
  const [extensions, setExtensions] = useState<Extension[]>([])
  const [extEditState, setExtEditState] = useState<ExtEditState | null>(null)
  const [capSlots, setCapSlots] = useState<CapabilitySlot[]>([])
  const [capOverrides, setCapOverrides] = useState<CapabilityOverride[]>([])
  const [capServerTools, setCapServerTools] = useState<Record<string, { name: string; description: string }[]>>({})
  const [deletingSlots, setDeletingSlots] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getMcpServers(password),               // all servers for capability override picker
      api.getProductExtensions(password, productId),
      api.getCapabilitySlots(password),
      api.getCapabilityOverrides(password, productId),
    ])
      .then(([allSvrs, exts, slots, overrides]) => {
        setAllServers(allSvrs)
        setExtensions(exts.filter((e: Extension) => e.scope === 'product' && e.product_id === productId))
        setCapSlots(slots)
        setCapOverrides(overrides)
        // Eagerly fetch tools for servers that already have overrides
        const serverNames = [...new Set(overrides.map((o: CapabilityOverride) => o.mcp_server_name))]
        Promise.all(serverNames.map((name: string) =>
          api.getMcpServerTools(password, name).catch(() => [] as { name: string; description: string }[])
        )).then(results => {
          const toolMap: Record<string, { name: string; description: string }[]> = {}
          serverNames.forEach((name: string, i: number) => { toolMap[name] = results[i] })
          setCapServerTools(toolMap)
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password, productId])

  const productServers = allServers.filter(s => s.scope === 'product' && s.product_id === productId)
  // All enabled servers (global + this product) for the capability override picker
  const enabledServersForPicker = allServers.filter(s => s.enabled)

  const handleToggle = async (id: number, enabled: boolean) => {
    await api.updateMcpServer(password, id, { enabled: !enabled }).catch(() => null)
    setAllServers(prev => prev.map(s => s.id === id ? { ...s, enabled: enabled ? 0 : 1 } : s))
  }

  const handleDelete = async (id: number) => {
    await api.deleteMcpServer(password, id).catch(() => null)
    setAllServers(prev => prev.filter(s => s.id !== id))
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
    if (updated) { setAllServers(prev => prev.map(s => s.id === editState.id ? { ...s, ...updated } : s)); setEditState(null) }
    else { setEditState(s => s ? { ...s, saving: false, error: 'Save failed' } : s) }
  }

  const handleAdd = async () => {
    const f = addForm
    let envParsed: Record<string, unknown> | undefined
    if (f.env.trim()) {
      try { envParsed = JSON.parse(f.env) } catch { return }
    }
    const payload: Parameters<typeof api.addMcpServer>[1] = {
      name: f.name, type: f.type, scope: 'product', product_id: productId,
      ...(f.type === 'remote' ? { url: f.url } : { command: f.command, args: f.args ? f.args.split(' ') : [] }),
      ...(envParsed !== undefined ? { env: envParsed as Record<string, string> } : {}),
    }
    const created = await api.addMcpServer(password, payload).catch(() => null)
    if (created) { setAllServers(prev => [...prev, created as McpServer]); setAddOpen(false); setAddForm(BLANK_FORM) }
  }

  const handleExtToggle = async (name: string, enabled: boolean) => {
    await api.updateProductExtension(password, productId, name, { enabled: !enabled }).catch(() => null)
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

  const handleCapServerChange = async (slot: string, serverName: string) => {
    if (!serverName) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
      setCapOverrides(prev => prev.filter(o => o.capability_slot !== slot))
      return
    }
    const existing = capOverrides.find(o => o.capability_slot === slot)
    if (existing) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
    }
    if (!capServerTools[serverName]) {
      const tools = await api.getMcpServerTools(password, serverName).catch(() => [] as { name: string; description: string }[])
      setCapServerTools(prev => ({ ...prev, [serverName]: tools }))
    }
    setCapOverrides(prev => {
      if (existing) return prev.map(o => o.capability_slot === slot ? { ...o, mcp_server_name: serverName, mcp_tool_names: [] } : o)
      return [...prev, { capability_slot: slot, mcp_server_name: serverName, mcp_tool_names: [] }]
    })
  }

  const handleCapToolToggle = async (slot: string, toolName: string, checked: boolean) => {
    const override = capOverrides.find(o => o.capability_slot === slot)
    if (!override) return
    const newTools = checked
      ? [...override.mcp_tool_names, toolName]
      : override.mcp_tool_names.filter(t => t !== toolName)
    if (newTools.length === 0) {
      await api.deleteCapabilityOverride(password, productId, slot).catch(() => null)
      setCapOverrides(prev => prev.filter(o => o.capability_slot !== slot))
    } else {
      await api.setCapabilityOverride(password, productId, {
        capability_slot: slot,
        mcp_server_name: override.mcp_server_name,
        mcp_tool_names: newTools,
      }).catch(() => null)
      setCapOverrides(prev => prev.map(o => o.capability_slot === slot ? { ...o, mcp_tool_names: newTools } : o))
    }
  }

  const handleDeleteCapSlot = async (name: string) => {
    if (!confirm(`Delete the "${name}" capability slot? This cannot be undone.`)) return
    setDeletingSlots(prev => new Set(prev).add(name))
    const ok = await api.deleteCapabilitySlot(password, name).then(() => true).catch(() => false)
    setDeletingSlots(prev => { const s = new Set(prev); s.delete(name); return s })
    if (ok) {
      setCapSlots(prev => prev.filter(s => s.name !== name))
      setCapOverrides(prev => prev.filter(o => o.capability_slot !== name))
    }
  }

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">MCP Servers</h2>
      <p className="text-xs text-adj-text-muted mb-6">Servers and tools scoped to this product</p>

      {/* Per-product servers */}
      <div className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">Product Servers</p>
        {productServers.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None configured for this product</p>
        ) : (
          <div className="flex flex-col gap-1">
            {productServers.map(s => (
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
            + Add product server
          </button>
        )}
      </div>

      <div className="border-t border-adj-border mb-6" />

      {/* Per-product custom tools */}
      <div className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Product Custom Tools</p>
        <p className="text-xs text-adj-text-faint mb-3">Agent-created tools scoped to this product</p>
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

      <div className="border-t border-adj-border mb-6" />

      {/* Capability Overrides */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1">Capability Overrides</p>
        <p className="text-xs text-adj-text-faint mb-3">
          Choose an MCP tool to handle a built-in capability. The built-in is suppressed when the server is connected.
        </p>
        {capSlots.length === 0 ? (
          <p className="text-xs text-adj-text-faint">No capability slots defined.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {capSlots.map(slot => {
              const override = capOverrides.find(o => o.capability_slot === slot.name)
              const selectedServer = override?.mcp_server_name || ''
              const selectedTools = override?.mcp_tool_names ?? []
              const serverToolOptions = capServerTools[selectedServer] || []
              return (
                <div key={slot.name} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-adj-text-secondary">{slot.label}</p>
                    {!slot.is_system && (
                      <button
                        onClick={() => handleDeleteCapSlot(slot.name)}
                        disabled={deletingSlots.has(slot.name)}
                        className="text-xs text-adj-text-faint hover:text-red-400 px-1 transition-colors disabled:opacity-50"
                        title="Delete slot"
                      >✕</button>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <select className={inputCls} value={selectedServer} onChange={e => handleCapServerChange(slot.name, e.target.value)}>
                      <option value="">Built-in</option>
                      {enabledServersForPicker.map(s => (
                        <option key={s.id} value={s.name}>
                          {s.name} {s.scope === 'global' ? '(Global)' : '(Product)'}
                        </option>
                      ))}
                    </select>
                    {selectedServer && (
                      <div className="mt-1 max-h-44 overflow-y-auto flex flex-col gap-0.5 border border-adj-border rounded p-1.5 bg-adj-surface">
                        {serverToolOptions.length === 0 ? (
                          <p className="text-xs text-adj-text-faint px-1">Loading tools…</p>
                        ) : (
                          serverToolOptions.map(t => (
                            <label key={t.name} className="flex items-center gap-2 px-1 py-0.5 hover:bg-adj-panel rounded cursor-pointer">
                              <input
                                type="checkbox"
                                checked={selectedTools.includes(t.name)}
                                onChange={e => handleCapToolToggle(slot.name, t.name, e.target.checked)}
                                className="accent-adj-accent"
                              />
                              <span className="text-xs text-adj-text-secondary truncate" title={t.description}>{t.name}</span>
                            </label>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                  {selectedServer && !allServers.some(s => s.name === selectedServer && s.enabled) && (
                    <p className="text-[10px] text-amber-400">⚠ Server '{selectedServer}' is currently disabled or disconnected</p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
