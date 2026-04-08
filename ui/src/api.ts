// ui/src/api.ts
import { ProductConfig, Workstream, Objective } from './types'

async function apiFetch<T>(
  path: string,
  password: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Agent-Password': password,
      ...(options?.headers ?? {}),
    },
  })
  if (res.status === 204) return undefined as T
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail ?? `API error ${res.status}`)
  return data as T
}

export const api = {
  getProductConfig: (pw: string, productId: string) =>
    apiFetch<ProductConfig>(`/api/products/${productId}/config`, pw),

  updateProductConfig: (pw: string, productId: string, updates: Partial<ProductConfig>) =>
    apiFetch<ProductConfig>(`/api/products/${productId}/config`, pw, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  createWorkstream: (pw: string, productId: string, name: string, status = 'paused') =>
    apiFetch<Workstream>(`/api/products/${productId}/workstreams`, pw, {
      method: 'POST',
      body: JSON.stringify({ name, status }),
    }),

  updateWorkstream: (
    pw: string,
    wsId: number,
    data: { name?: string; status?: string; mission?: string; schedule?: string },
  ) =>
    apiFetch<void>(`/api/workstreams/${wsId}`, pw, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  triggerWorkstreamRun: (pw: string, wsId: number) =>
    apiFetch<{ queued: boolean }>(`/api/workstreams/${wsId}/run`, pw, { method: 'POST' }),

  deleteWorkstream: (pw: string, wsId: number) =>
    apiFetch<void>(`/api/workstreams/${wsId}`, pw, { method: 'DELETE' }),

  createObjective: (
    pw: string,
    productId: string,
    text: string,
    progressCurrent = 0,
    progressTarget?: number,
  ) =>
    apiFetch<Objective>(`/api/products/${productId}/objectives`, pw, {
      method: 'POST',
      body: JSON.stringify({
        text,
        progress_current: progressCurrent,
        progress_target: progressTarget ?? null,
      }),
    }),

  updateObjective: (
    pw: string,
    objId: number,
    data: { text?: string; progress_current?: number; progress_target?: number | null },
  ) =>
    apiFetch<void>(`/api/objectives/${objId}`, pw, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteObjective: (pw: string, objId: number) =>
    apiFetch<void>(`/api/objectives/${objId}`, pw, { method: 'DELETE' }),

  getTemplates: (pw: string, productId: string) =>
    apiFetch<{ id: number; label: string; content: string; display_order: number }[]>(
      `/api/products/${productId}/templates`, pw,
    ),

  createTemplate: (pw: string, productId: string, label: string, content: string) =>
    apiFetch<{ id: number; label: string; content: string; display_order: number }>(
      `/api/products/${productId}/templates`, pw,
      { method: 'POST', body: JSON.stringify({ label, content }) },
    ),

  updateTemplate: (pw: string, templateId: number, label: string, content: string) =>
    apiFetch<void>(`/api/templates/${templateId}`, pw, {
      method: 'PUT',
      body: JSON.stringify({ label, content }),
    }),

  deleteTemplate: (pw: string, templateId: number) =>
    apiFetch<void>(`/api/templates/${templateId}`, pw, { method: 'DELETE' }),

  getAgentConfig: (pw: string) =>
    apiFetch<{ agent_model: string; subagent_model: string; agent_name: string }>('/api/agent-config', pw),

  updateAgentConfig: (pw: string, data: { agent_model?: string; subagent_model?: string; agent_name?: string }) =>
    apiFetch<{ agent_model: string; subagent_model: string; agent_name: string }>('/api/agent-config', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getNotes: (pw: string, productId: string) =>
    apiFetch<{ content: string; updated_at: string }>(`/api/products/${productId}/notes`, pw),

  updateNotes: (pw: string, productId: string, content: string) =>
    apiFetch<{ content: string; updated_at: string }>(`/api/products/${productId}/notes`, pw, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),

  getDirectiveHistory: (pw: string, productId: string) =>
    apiFetch<{ id: number; content: string; created_at: string }[]>(
      `/api/products/${productId}/directive-history`, pw,
    ),

  getOverview: (pw: string) =>
    apiFetch<import('./types').ProductOverview[]>('/api/overview', pw),

  sendDigest: (pw: string) =>
    apiFetch<{ queued: boolean }>('/api/digest', pw, { method: 'POST' }),
}
