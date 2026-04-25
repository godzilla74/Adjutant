// Shared types, constants, and sub-components used by GlobalMCPSettings and ProductMCPSettings.

export type McpServer = {
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

export type AddFormState = {
  name: string
  type: 'remote' | 'stdio'
  url: string
  command: string
  args: string
  env: string
}

export type EditState = {
  id: number
  name: string
  type: string
  url: string
  command: string
  args: string
  env: string
  saving: boolean
  error: string
}

export type Extension = {
  name: string
  tool_name: string
  description: string
  scope: string
  product_id: string
  enabled: boolean
}

export type ExtEditState = {
  name: string
  description: string
  instructions: string
  saving: boolean
  error: string
}

export type CapabilityOverride = {
  capability_slot: string
  mcp_server_name: string
  mcp_tool_names: string[]
}

export type CapabilitySlot = {
  name: string
  label: string
  built_in_tools: string[]
  is_system: boolean
}

export const rowCls = 'flex items-center gap-2 bg-adj-panel border border-adj-border rounded px-3 py-2'
export const inputCls = 'w-full bg-adj-surface text-xs text-adj-text-secondary rounded px-2 py-1.5 border border-adj-border focus:outline-none focus:border-adj-accent'

export function McpRow({ s, onToggle, onDelete, onEdit }: {
  s: McpServer
  onToggle: (id: number, enabled: boolean) => void
  onDelete: (id: number) => void
  onEdit: (id: number) => void
}) {
  return (
    <div className={rowCls}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.enabled ? 'bg-emerald-500' : 'bg-adj-border'}`} />
      <span className="text-xs text-adj-text-secondary flex-1 truncate">{s.name}</span>
      <span className="text-xs text-adj-text-faint font-mono">{s.type}</span>
      <button onClick={() => onEdit(s.id)} className="text-xs text-adj-text-faint hover:text-adj-text-primary px-1 transition-colors" title="Edit">✎</button>
      <button onClick={() => onToggle(s.id, !!s.enabled)} className="text-xs text-adj-text-muted hover:text-adj-text-primary px-1 transition-colors" title={s.enabled ? 'Disable' : 'Enable'}>
        {s.enabled ? 'on' : 'off'}
      </button>
      <button onClick={() => onDelete(s.id)} className="text-xs text-adj-text-faint hover:text-red-400 px-1 transition-colors" title="Remove">✕</button>
    </div>
  )
}

export function EditForm({ state, onChange, onSave, onCancel }: {
  state: EditState
  onChange: (updater: (s: EditState) => EditState) => void
  onSave: () => void
  onCancel: () => void
}) {
  return (
    <div className="mt-1 mb-2 space-y-2 border border-adj-accent/40 rounded-md p-3 bg-adj-panel">
      <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-2">Editing: {state.name}</p>
      <input className={inputCls} placeholder="Server name" value={state.name} onChange={e => onChange(s => ({ ...s, name: e.target.value }))} />
      {state.type === 'remote' ? (
        <input className={inputCls} placeholder="Endpoint URL" value={state.url} onChange={e => onChange(s => ({ ...s, url: e.target.value }))} />
      ) : (
        <>
          <input className={inputCls} placeholder="Command (e.g. npx)" value={state.command} onChange={e => onChange(s => ({ ...s, command: e.target.value }))} />
          <input className={inputCls} placeholder="Args (space-separated)" value={state.args} onChange={e => onChange(s => ({ ...s, args: e.target.value }))} />
        </>
      )}
      <div>
        <p className="text-[10px] text-adj-text-faint mb-1">
          {state.type === 'remote' ? 'Extra config (JSON) — e.g. {"headers": {"x-api-key": "..."}}' : 'Env vars (JSON) — e.g. {"API_KEY": "..."}'}
        </p>
        <textarea className={`${inputCls} font-mono resize-none`} rows={3} placeholder="{}" value={state.env} onChange={e => onChange(s => ({ ...s, env: e.target.value }))} />
      </div>
      {state.error && <p className="text-xs text-red-400">{state.error}</p>}
      <div className="flex gap-2">
        <button onClick={onSave} disabled={state.saving} className="flex-1 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded px-2 py-1.5 transition-colors disabled:opacity-50">
          {state.saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel} className="text-xs text-adj-text-muted hover:text-adj-text-primary px-2 transition-colors">Cancel</button>
      </div>
    </div>
  )
}

export function AddForm({ form, onChange, onAdd, onCancel }: {
  form: AddFormState
  onChange: (updater: (f: AddFormState) => AddFormState) => void
  onAdd: () => void
  onCancel: () => void
}) {
  return (
    <div className="mt-3 space-y-2 border border-adj-border rounded-md p-3 bg-adj-panel">
      <input className={inputCls} placeholder="Server name" value={form.name} onChange={e => onChange(f => ({ ...f, name: e.target.value }))} />
      <select className={inputCls} value={form.type} onChange={e => onChange(f => ({ ...f, type: e.target.value as 'remote' | 'stdio' }))}>
        <option value="remote">Remote (HTTP/SSE)</option>
        <option value="stdio">Local (stdio)</option>
      </select>
      {form.type === 'remote' ? (
        <input className={inputCls} placeholder="Endpoint URL" value={form.url} onChange={e => onChange(f => ({ ...f, url: e.target.value }))} />
      ) : (
        <>
          <input className={inputCls} placeholder="Command (e.g. npx)" value={form.command} onChange={e => onChange(f => ({ ...f, command: e.target.value }))} />
          <input className={inputCls} placeholder="Args (space-separated)" value={form.args} onChange={e => onChange(f => ({ ...f, args: e.target.value }))} />
        </>
      )}
      <div>
        <p className="text-[10px] text-adj-text-faint mb-1">
          {form.type === 'remote' ? 'Extra config (JSON, optional) — e.g. {"headers": {"x-api-key": "..."}}' : 'Env vars (JSON, optional) — e.g. {"API_KEY": "..."}'}
        </p>
        <textarea className={`${inputCls} font-mono resize-none`} rows={2} placeholder="{}" value={form.env} onChange={e => onChange(f => ({ ...f, env: e.target.value }))} />
      </div>
      <div className="flex gap-2">
        <button onClick={onAdd} className="flex-1 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded px-2 py-1.5 transition-colors">Add</button>
        <button onClick={onCancel} className="text-xs text-adj-text-muted hover:text-adj-text-primary px-2 transition-colors">Cancel</button>
      </div>
    </div>
  )
}

export function ExtRow({ ext, onToggle, onDelete, onEdit }: {
  ext: Extension
  onToggle: (name: string, enabled: boolean) => void
  onDelete: (name: string) => void
  onEdit: (name: string) => void
}) {
  return (
    <div className={rowCls}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${ext.enabled ? 'bg-emerald-500' : 'bg-adj-border'}`} />
      <div className="flex-1 min-w-0 flex items-baseline gap-2 overflow-hidden">
        <span className="text-xs text-adj-text-secondary font-mono flex-shrink-0">{ext.tool_name}</span>
        <span className="text-xs text-adj-text-faint truncate">{ext.description}</span>
      </div>
      <button onClick={() => onEdit(ext.name)} className="text-xs text-adj-text-faint hover:text-adj-text-primary px-1 transition-colors" title="Edit">✎</button>
      <button onClick={() => onToggle(ext.name, ext.enabled)} className="text-xs text-adj-text-muted hover:text-adj-text-primary px-1 transition-colors" title={ext.enabled ? 'Disable' : 'Enable'}>
        {ext.enabled ? 'on' : 'off'}
      </button>
      <button onClick={() => onDelete(ext.name)} className="text-xs text-adj-text-faint hover:text-red-400 px-1 transition-colors" title="Delete">✕</button>
    </div>
  )
}

export function ExtEditForm({ state, onChange, onSave, onCancel }: {
  state: ExtEditState
  onChange: (u: (s: ExtEditState) => ExtEditState) => void
  onSave: () => void
  onCancel: () => void
}) {
  return (
    <div className="mt-1 mb-2 space-y-2 border border-adj-accent/40 rounded-md p-3 bg-adj-panel">
      <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-2">Editing: {state.name}</p>
      <input className={inputCls} placeholder="Description (shown in tool list)" value={state.description} onChange={e => onChange(s => ({ ...s, description: e.target.value }))} />
      <div>
        <p className="text-[10px] text-adj-text-faint mb-1">Agent instructions — what the sub-agent does and how</p>
        <textarea className={`${inputCls} font-mono resize-none`} rows={8} value={state.instructions} onChange={e => onChange(s => ({ ...s, instructions: e.target.value }))} />
      </div>
      {state.error && <p className="text-xs text-red-400">{state.error}</p>}
      <p className="text-[10px] text-adj-text-faint">Changes take effect after the server restarts.</p>
      <div className="flex gap-2">
        <button onClick={onSave} disabled={state.saving} className="flex-1 text-xs bg-adj-accent hover:bg-adj-accent-dark text-white rounded px-2 py-1.5 transition-colors disabled:opacity-50">
          {state.saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel} className="text-xs text-adj-text-muted hover:text-adj-text-primary px-2 transition-colors">Cancel</button>
      </div>
    </div>
  )
}
