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
    data: { text?: string; progress_current?: number; progress_target?: number | null; autonomous?: number },
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

  getAutonomySettings: (pw: string, productId: string) =>
    apiFetch<{
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    }>(`/api/products/${productId}/autonomy`, pw),

  updateAutonomySettings: (
    pw: string,
    productId: string,
    data: {
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    },
  ) =>
    apiFetch<{
      master_tier: string | null
      master_window_minutes: number | null
      action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }>
    }>(`/api/products/${productId}/autonomy`, pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getDirectiveHistory: (pw: string, productId: string) =>
    apiFetch<{ id: number; content: string; created_at: string }[]>(
      `/api/products/${productId}/directive-history`, pw,
    ),

  getOverview: (pw: string) =>
    apiFetch<import('./types').ProductOverview[]>('/api/overview', pw),

  sendDigest: (pw: string) =>
    apiFetch<{ queued: boolean }>('/api/digest', pw, { method: 'POST' }),

  getTelegramStatus: (pw: string) =>
    apiFetch<{ configured: boolean; connected: boolean; bot_username: string | null }>(
      '/api/telegram/status', pw,
    ),

  saveTelegramToken: (pw: string, token: string) =>
    apiFetch<{ bot_username: string }>('/api/telegram/token', pw, {
      method: 'PUT',
      body: JSON.stringify({ token }),
    }),

  discoverTelegramChat: (pw: string) =>
    apiFetch<{ chat_id: string | null }>('/api/telegram/discover-chat', pw),

  getMcpServers: (pw: string, productId?: string) =>
    apiFetch<{
      id: number; name: string; type: string; url: string | null;
      command: string | null; args: string | null; scope: string;
      product_id: string | null; enabled: number; created_at: string;
    }[]>(
      `/api/mcp-servers${productId ? `?product_id=${productId}` : ''}`, pw,
    ),

  addMcpServer: (pw: string, payload: {
    name: string; type: string; url?: string; command?: string;
    args?: string[]; env?: Record<string, string>; scope: string; product_id?: string;
  }) =>
    apiFetch<{ id: number; name: string; type: string; scope: string; enabled: number }>(
      '/api/mcp-servers', pw,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  getMcpServer: (pw: string, id: number) =>
    apiFetch<{
      id: number; name: string; type: string; url: string | null;
      command: string | null; args: string | null; env: string | null;
      scope: string; product_id: string | null; enabled: number;
    }>(`/api/mcp-servers/${id}`, pw),

  updateMcpServer: (pw: string, id: number, patch: {
    enabled?: boolean; name?: string; url?: string;
    command?: string; args?: string[]; env?: Record<string, unknown>;
  }) =>
    apiFetch<{ id: number; name: string; enabled: number }>(
      `/api/mcp-servers/${id}`, pw,
      { method: 'PATCH', body: JSON.stringify(patch) },
    ),

  deleteMcpServer: (pw: string, id: number) =>
    apiFetch<void>(`/api/mcp-servers/${id}`, pw, { method: 'DELETE' }),

  listExtensions: (pw: string) =>
    apiFetch<{
      name: string; tool_name: string; description: string;
      instructions: string | null; auto_generated: boolean; enabled: boolean;
    }[]>('/api/extensions', pw),

  updateExtension: (pw: string, name: string, patch: {
    enabled?: boolean; description?: string; instructions?: string;
  }) =>
    apiFetch<{ ok: boolean }>(`/api/extensions/${name}`, pw, {
      method: 'PATCH', body: JSON.stringify(patch),
    }),

  deleteExtension: (pw: string, name: string) =>
    apiFetch<void>(`/api/extensions/${name}`, pw, { method: 'DELETE' }),

  getGoogleOAuthSettings: (pw: string) =>
    apiFetch<{ google_oauth_client_id: string; google_oauth_client_secret: string }>(
      '/api/settings/google-oauth', pw,
    ),

  updateGoogleOAuthSettings: (
    pw: string,
    data: { google_oauth_client_id?: string; google_oauth_client_secret?: string },
  ) =>
    apiFetch<{ ok: boolean }>('/api/settings/google-oauth', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  startOAuthFlow: (pw: string, productId: string, service: 'gmail' | 'google_calendar' | 'twitter' | 'linkedin' | 'meta') =>
    apiFetch<{ auth_url: string }>(
      `/api/products/${productId}/oauth/start/${service}`, pw,
    ),

  getOAuthConnections: (pw: string, productId: string) =>
    apiFetch<{ service: string; email: string; scopes: string; updated_at: string }[]>(
      `/api/products/${productId}/oauth/connections`, pw,
    ),

  deleteOAuthConnection: (pw: string, productId: string, service: string) =>
    apiFetch<void>(`/api/products/${productId}/oauth/${service}`, pw, { method: 'DELETE' }),

  uploadFile: async (
    file: File,
    password: string,
  ): Promise<{ path: string; mime_type: string; name: string; size: number }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'X-Agent-Password': password },
      body: form,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail ?? `Upload failed: ${res.status}`)
    }
    return res.json()
  },

  getWizardPlan: (pw: string, intent: string) =>
    apiFetch<{
      workstreams: Array<{ name: string; mission: string; schedule: string }>
      objectives: Array<{ text: string; progress_target: number | null }>
      required_integrations: string[]
    }>('/api/wizard-plan', pw, {
      method: 'POST',
      body: JSON.stringify({ intent }),
    }),

  getSocialSettings: (pw: string) =>
    apiFetch<{
      twitter_client_id: string; linkedin_client_id: string; meta_app_id: string;
    }>('/api/settings/social-accounts', pw),

  updateTwitterSettings: (pw: string, data: { twitter_client_id?: string; twitter_client_secret?: string }) =>
    apiFetch<{ ok: boolean }>('/api/settings/social-accounts', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  updateLinkedInSettings: (pw: string, data: { linkedin_client_id?: string; linkedin_client_secret?: string }) =>
    apiFetch<{ ok: boolean }>('/api/settings/social-accounts', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  updateMetaSettings: (pw: string, data: { meta_app_id?: string; meta_app_secret?: string }) =>
    apiFetch<{ ok: boolean }>('/api/settings/social-accounts', pw, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getBrowserCredentials: (pw: string, productId: string) =>
    apiFetch<{ service: string; username: string; active: boolean }[]>(
      `/api/products/${productId}/browser-credentials`, pw,
    ),

  saveBrowserCredential: (pw: string, productId: string, service: string, body: { username: string; password: string; active: boolean }) =>
    apiFetch<void>(`/api/products/${productId}/browser-credentials/${service}`, pw, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteBrowserCredential: (pw: string, productId: string, service: string) =>
    apiFetch<void>(`/api/products/${productId}/browser-credentials/${service}`, pw, { method: 'DELETE' }),
}
