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
  product_id: string
}

const rowCls = 'flex items-center gap-2 bg-adj-panel border border-adj-border rounded px-3 py-2'
const addInputCls = 'w-full bg-adj-surface text-xs text-adj-text-secondary rounded px-2 py-1.5 border border-adj-border focus:outline-none focus:border-adj-accent'

interface McpRowProps {
  s: McpServer
  onToggle: (id: number, enabled: boolean) => void
  onDelete: (id: number) => void
}

function McpRow({ s, onToggle, onDelete }: McpRowProps) {
  return (
    <div className={rowCls}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.enabled ? 'bg-emerald-500' : 'bg-adj-border'}`} />
      <span className="text-xs text-adj-text-secondary flex-1 truncate">{s.name}</span>
      <span className="text-xs text-adj-text-faint font-mono">{s.type}</span>
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
        className={addInputCls}
        placeholder="Server name"
        value={form.name}
        onChange={e => onChange(f => ({ ...f, name: e.target.value }))}
      />
      <select
        className={addInputCls}
        value={form.type}
        onChange={e => onChange(f => ({ ...f, type: e.target.value as 'remote' | 'stdio' }))}
      >
        <option value="remote">Remote (HTTP/SSE)</option>
        <option value="stdio">Local (stdio)</option>
      </select>
      {form.type === 'remote' ? (
        <input
          className={addInputCls}
          placeholder="Endpoint URL"
          value={form.url}
          onChange={e => onChange(f => ({ ...f, url: e.target.value }))}
        />
      ) : (
        <>
          <input
            className={addInputCls}
            placeholder="Command (e.g. npx)"
            value={form.command}
            onChange={e => onChange(f => ({ ...f, command: e.target.value }))}
          />
          <input
            className={addInputCls}
            placeholder="Args (space-separated)"
            value={form.args}
            onChange={e => onChange(f => ({ ...f, args: e.target.value }))}
          />
        </>
      )}
      {scope === 'product' && (
        <input
          className={addInputCls}
          placeholder={`Product ID (default: ${productId})`}
          value={form.product_id}
          onChange={e => onChange(f => ({ ...f, product_id: e.target.value }))}
        />
      )}
      <p className="text-xs text-adj-text-faint">
        For credential-protected servers, ask the agent to add them — it will prompt for secrets.
      </p>
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
    scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', product_id: '',
  })
  const [mcpAddOpen, setMcpAddOpen] = useState<'global' | 'product' | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getMcpServers(password)
      .then(s => setMcpServers(s))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [password])

  const handleMcpToggle = async (id: number, enabled: boolean) => {
    await api.updateMcpServer(password, id, !enabled).catch(() => null)
    setMcpServers(prev => prev.map(s => s.id === id ? { ...s, enabled: enabled ? 0 : 1 } : s))
  }

  const handleMcpDelete = async (id: number) => {
    await api.deleteMcpServer(password, id).catch(() => null)
    setMcpServers(prev => prev.filter(s => s.id !== id))
  }

  const handleMcpAdd = async (scope: 'global' | 'product') => {
    const f = mcpAddForm
    const payload: Parameters<typeof api.addMcpServer>[1] = {
      name: f.name,
      type: f.type,
      scope,
      ...(f.type === 'remote'
        ? { url: f.url }
        : { command: f.command, args: f.args ? f.args.split(' ') : [] }),
      ...(scope === 'product' ? { product_id: f.product_id || productId } : {}),
    }
    const created = await api.addMcpServer(password, payload).catch(() => null)
    if (created) {
      setMcpServers(prev => [...prev, created as McpServer])
      setMcpAddOpen(null)
      setMcpAddForm({ scope: 'global', name: '', type: 'remote', url: '', command: '', args: '', product_id: '' })
    }
  }

  const globalServers = mcpServers.filter(s => s.scope === 'global')
  const productServers = mcpServers.filter(
    s => s.scope === 'product' && (!mcpProductFilter || s.product_id === mcpProductFilter),
  )

  if (loading) return <p className="text-adj-text-muted text-sm">Loading…</p>

  return (
    <div className="max-w-4xl">
      <h2 className="text-base font-bold text-adj-text-primary mb-1">MCP Servers</h2>
      <p className="text-xs text-adj-text-muted mb-6">Manage Model Context Protocol server connections</p>

      {/* Global servers */}
      <div className="mb-6">
        <p className="text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-2">Global</p>
        {globalServers.length === 0 ? (
          <p className="text-xs text-adj-text-faint">None configured</p>
        ) : (
          <div className="flex flex-col gap-2">
            {globalServers.map(s => (
              <McpRow key={s.id} s={s} onToggle={handleMcpToggle} onDelete={handleMcpDelete} />
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
          <div className="flex flex-col gap-2">
            {productServers.map(s => (
              <McpRow key={s.id} s={s} onToggle={handleMcpToggle} onDelete={handleMcpDelete} />
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
