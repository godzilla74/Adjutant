import { useEffect, useState } from 'react'
import { api } from '../../api'

interface Props {
  productId: string
  password: string
}

type McpServer = {
  id: number
  name: string
  type: string
  url: string | null
  command: string | null
  args: string | null
  scope: string
  product_id: string | null
  enabled: number
}

type AddFormState = {
  scope: 'global' | 'product'
  name: string
  type: 'remote' | 'stdio'
  url: string
  command: string
  args: string
  env: string
  product_id: string
}

type EditState = {
  id: number
  name: string
  type: string
  url: string
  command: string
  args: string
  env: string  // raw JSON string
  saving: boolean
  error: string
}

const rowCls = 'flex items-center gap-2 bg-adj-panel border border-adj-border rounded px-3 py-2'
const inputCls = 'w-full bg-adj-surface text-xs text-adj-text-secondary rounded px-2 py-1.5 border border-adj-border focus:outline-none focus:border-adj-accent'

interface McpRowProps {
  s: McpServer
  onToggle: (id: number, enabled: boolean) => void
  onDelete: (id: number) => void
  onEdit: (id: number) => void
}

function McpRow({ s, onToggle, onDelete, onEdit }: McpRowProps) {
  return (
    <div className={rowCls}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.enabled ? 'bg-emerald-500' : 'bg-adj-border'}`} />
      <span className="text-xs text-adj-text-secondary flex-1 truncate">{s.name}</span>
      <span className="text-xs text-adj-text-faint font-mono">{s.type}</span>
      <button
        onClick={() => onEdit(s.id)}
        className="text-xs text-adj-text-faint hover:text-adj-text-primary px-1 transition-colors"
        title="Edit"
      >
        ✎
      </button>
      <button
        onClick={() => onToggle(s.id, !!s.enabled)}
        className="text-xs text-adj-text-muted hover:text-adj-text-primary px-1 transition-colors"
        title={s.enabled ? 'Disable' : 'Enable'}
      >
        {s.enabled ? 'on' : 'off'}
      </button>
      <button
        onClick={() => onDelete(s.id)}
        className="text-xs text-adj-text-faint hover:text-red-400 px-1 transition-colors"
        title="Remove"
      >
        ✕
      </button>
    </div>
  )
}

interface EditFormProps {
  state: EditState
  onChange: (updater: (s: EditState) => EditState) => void
  onSave: () => void
  onCancel: () => void
}

function EditForm({ state, onChange, onSave, onCancel }: EditFormProps) {
  return (
    <div className="mt-1 mb-2 space-y-2 border border-adj-accent/40 rounded-md p-3 bg-adj-panel">
      <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-2">Editing: {state.name}</p>
      <input
        className={inputCls}
        placeholder="Server name"
        value={state.name}
        onChange={e => onChange(s => ({ ...s, name: e.target.value }))}
      />
      {state.type === 'remote' ? (
        <input
          className={inputCls}
          placeholder="Endpoint URL"
          value={state.url}
          onChange={e => onChange(s => ({ ...s, url: e.target.value }))}
        />
      ) : (
        <>
          <input
            className={inputCls}
            placeholder="Command (e.g. npx)"
            value={state.command}
            onChange={e => onChange(s => ({ ...s, command: e.target.value }))}
          />
          <input
            className={inputCls}
            placeholder="Args (space-separated)"
            value={state.args}
            onChange={e => onChange(s => ({ ...s, args: e.target.value }))}
          />
        </>
      )}
      <div>
        <p className="text-[10px] text-adj-text-faint mb-1">
          {state.type === 'remote'
            ? 'Extra config (JSON) — e.g. {"headers": {"x-api-key": "..."}}'
            : 'Env vars (JSON) — e.g. {"API_KEY": "..."}'}
        </p>
        <textarea
          className={`${inputCls} font-mono resize-none`}
          rows={3}
          placeholder="{}"
          value={state.env}
          onChange={e => onChange(s => ({ ...s, env: e.target.value }))}
        />
      </div>
      {state.error && <p className="text-xs text-red-400">{state.error}</p>}
      <div className="flex gap-2">
        <button
          onClick={onSave}
          disabled={state.saving}
          className="flex-1 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded px-2 py-1.5 transition-colors disabled:opacity-50"
        >
          {state.saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={onCancel}
          className="text-xs text-adj-text-muted hover:text-adj-text-primary px-2 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

interface AddFormProps {
  scope: 'global' | 'product'
  productId: string
  form: AddFormState
  onChange: (updater: (f: AddFormState) => AddFormState) => void
  onAdd: (scope: 'global' | 'product') => void
  onCancel: () => void
}

function AddForm({ scope, productId, form, onChange, onAdd, onCancel }: AddFormProps) {
  return (
    <div className="mt-3 space-y-2 border border-adj-border rounded-md p-3 bg-adj-panel">
      <input
        className={inputCls}
        placeholder="Server name"
        value={form.name}
        onChange={e => onChange(f => ({ ...f, name: e.target.value }))}
      />
      <select
        className={inputCls}
        value={form.type}
        onChange={e => onChange(f => ({ ...f, type: e.target.value as 'remote' | 'stdio' }))}
      >
        <option value="remote">Remote (HTTP/SSE)</option>
        <option value="stdio">Local (stdio)</option>
      </select>
      {form.type === 'remote' ? (
        <input
          className={inputCls}
          placeholder="Endpoint URL"
          value={form.url}
          onChange={e => onChange(f => ({ ...f, url: e.target.value }))}
        />
      ) : (
        <>
          <input
            className={inputCls}
            placeholder="Command (e.g. npx)"
            value={form.command}
            onChange={e => onChange(f => ({ ...f, command: e.target.value }))}
          />
          <input
            className={inputCls}
            placeholder="Args (space-separated)"
            value={form.args}
            onChange={e => onChange(f => ({ ...f, args: e.target.value }))}
          />
        </>
      )}
      <div>
        <p className="text-[10px] text-adj-text-faint mb-1">
          {form.type === 'remote'
            ? 'Extra config (JSON, optional) — e.g. {"headers": {"x-api-key": "..."}}'
            : 'Env vars (JSON, optional) — e.g. {"API_KEY": "..."}'}
        </p>
        <textarea
          className={`${inputCls} font-mono resize-none`}
          rows={2}
          placeholder="{}"
          value={form.env}
          onChange={e => onChange(f => ({ ...f, env: e.target.value }))}
        />
      </div>
      {scope === 'product' && (
        <input
          className={inputCls}
          placeholder={`Product ID (default: ${productId})`}
          value={form.product_id}
          onChange={e => onChange(f => ({ ...f, product_id: e.target.value }))}
        />
      )}
      <div className="flex gap-2">
        <button
          onClick={() => onAdd(scope)}
          className="flex-1 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded px-2 py-1.5 transition-colors"
        >
          Add
        </button>
        <button
          onClick={onCancel}
          className="text-xs text-adj-text-muted hover:text-adj-text-primary px-2 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export default function MCPSettings({ productId, password }: Props) {
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpProductFilter, setMcpProductFilter] = useState<string>('')
  const [mcpAddForm, setMcpAddForm] = useState<AddFormState>({
    scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', env: '', product_id: '',
  })
  const [mcpAddOpen, setMcpAddOpen] = useState<'global' | 'product' | null>(null)
  const [editState, setEditState] = useState<EditState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getMcpServers(password)
      .then(s => setMcpServers(s))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  const handleMcpToggle = async (id: number, enabled: boolean) => {
    await api.updateMcpServer(password, id, { enabled: !enabled }).catch(() => null)
    setMcpServers(prev => prev.map(s => s.id === id ? { ...s, enabled: enabled ? 0 : 1 } : s))
  }

  const handleMcpDelete = async (id: number) => {
    await api.deleteMcpServer(password, id).catch(() => null)
    setMcpServers(prev => prev.filter(s => s.id !== id))
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
    setEditState({
      id,
      name: server.name,
      type: server.type,
      url: server.url ?? '',
      command: server.command ?? '',
      args: argsStr,
      env: envStr,
      saving: false,
      error: '',
    })
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
    if (editState.type === 'remote') {
      patch.url = editState.url
    } else {
      patch.command = editState.command
      patch.args = editState.args ? editState.args.split(/\s+/).filter(Boolean) : []
    }
    if (envParsed !== undefined) patch.env = envParsed
    const updated = await api.updateMcpServer(password, editState.id, patch).catch(() => null)
    if (updated) {
      setMcpServers(prev => prev.map(s => s.id === editState.id ? { ...s, ...updated } : s))
      setEditState(null)
    } else {
      setEditState(s => s ? { ...s, saving: false, error: 'Save failed' } : s)
    }
  }

  const handleMcpAdd = async (scope: 'global' | 'product') => {
    const f = mcpAddForm
    let envParsed: Record<string, unknown> | undefined
    if (f.env.trim()) {
      try { envParsed = JSON.parse(f.env) } catch { return }
    }
    const payload: Parameters<typeof api.addMcpServer>[1] = {
      name: f.name,
      type: f.type,
      scope,
      ...(f.type === 'remote'
        ? { url: f.url }
        : { command: f.command, args: f.args ? f.args.split(' ') : [] }),
      ...(envParsed !== undefined ? { env: envParsed as Record<string, string> } : {}),
      ...(scope === 'product' ? { product_id: f.product_id || productId } : {}),
    }
    const created = await api.addMcpServer(password, payload).catch(() => null)
    if (created) {
      setMcpServers(prev => [...prev, created as McpServer])
      setMcpAddOpen(null)
      setMcpAddForm({ scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', env: '', product_id: '' })
    }
  }

  const globalServers = mcpServers.filter(s => s.scope === 'global')
  const productServers = mcpServers.filter(
    s => s.scope === 'product' && (!mcpProductFilter || s.product_id === mcpProductFilter),
  )

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="w-full">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">MCP Servers</h2>
      <p className="text-xs text-adj-text-muted mb-6">Manage Model Context Protocol server connections</p>

      {/* Global servers */}
      <div className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">Global</p>
        {globalServers.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None configured</p>
        ) : (
          <div className="flex flex-col gap-1">
            {globalServers.map(s => (
              <div key={s.id}>
                <McpRow s={s} onToggle={handleMcpToggle} onDelete={handleMcpDelete} onEdit={handleEdit} />
                {editState?.id === s.id && (
                  <EditForm state={editState} onChange={u => setEditState(prev => prev ? u(prev) : prev)} onSave={handleEditSave} onCancel={() => setEditState(null)} />
                )}
              </div>
            ))}
          </div>
        )}
        {mcpAddOpen === 'global' ? (
          <AddForm
            scope="global"
            productId={productId}
            form={mcpAddForm}
            onChange={setMcpAddForm}
            onAdd={handleMcpAdd}
            onCancel={() => setMcpAddOpen(null)}
          />
        ) : (
          <button
            onClick={() => setMcpAddOpen('global')}
            className="mt-3 text-xs text-adj-text-muted hover:text-adj-text-primary transition-colors"
          >
            + Add global server
          </button>
        )}
      </div>

      <div className="border-t border-adj-border mb-6" />

      {/* Per-product servers */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted">Per-product</p>
          <input
            className="flex-1 bg-adj-panel text-xs text-adj-text-muted rounded px-2 py-1 border border-adj-border focus:outline-none focus:border-adj-accent"
            placeholder="Filter by product ID"
            value={mcpProductFilter}
            onChange={e => setMcpProductFilter(e.target.value)}
          />
        </div>
        {productServers.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None configured</p>
        ) : (
          <div className="flex flex-col gap-1">
            {productServers.map(s => (
              <div key={s.id}>
                <McpRow s={s} onToggle={handleMcpToggle} onDelete={handleMcpDelete} onEdit={handleEdit} />
                {editState?.id === s.id && (
                  <EditForm state={editState} onChange={u => setEditState(prev => prev ? u(prev) : prev)} onSave={handleEditSave} onCancel={() => setEditState(null)} />
                )}
              </div>
            ))}
          </div>
        )}
        {mcpAddOpen === 'product' ? (
          <AddForm
            scope="product"
            productId={productId}
            form={mcpAddForm}
            onChange={setMcpAddForm}
            onAdd={handleMcpAdd}
            onCancel={() => setMcpAddOpen(null)}
          />
        ) : (
          <button
            onClick={() => setMcpAddOpen('product')}
            className="mt-3 text-xs text-adj-text-muted hover:text-adj-text-primary transition-colors"
          >
            + Add product server
          </button>
        )}
      </div>
    </div>
  )
}
