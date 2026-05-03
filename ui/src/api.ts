// ui/src/api.ts
import { ProductConfig, Workstream, Objective, Tag, Signal, OrchestratorConfig, OrchestratorRun, HCAConfig, HCADirective, HCARun } from './types'

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
  deleteProduct: (pw: string, productId: string) =>
    apiFetch<void>(`/api/products/${productId}`, pw, { method: 'DELETE' }),

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

  getAgentConfig: (pw: string, productId?: string) =>
    apiFetch<{
      agent_model: string
      subagent_model: string
      prescreener_model: string
      agent_name: string
      openai_access_token?: string
    }>(`/api/agent-config${productId ? `?product_id=${encodeURIComponent(productId)}` : ''}`, pw),

  updateAgentConfig: (pw: string, data: {
    agent_model?: string
    subagent_model?: string
    prescreener_model?: string
    agent_name?: string
    product_id?: string
  }) =>
    apiFetch<{
      agent_model: string
      subagent_model: string
      prescreener_model: string
      agent_name: string
    }>('/api/agent-config', pw, {
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
    apiFetch<{ configured: boolean; connected: boolean; bot_username: string | null; enabled: boolean }>(
      '/api/telegram/status', pw,
    ),

  saveTelegramToken: (pw: string, token: string) =>
    apiFetch<{ bot_username: string }>('/api/telegram/token', pw, {
      method: 'PUT',
      body: JSON.stringify({ token }),
    }),

  discoverTelegramChat: (pw: string) =>
    apiFetch<{ chat_id: string | null }>('/api/telegram/discover-chat', pw),

  setTelegramEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/telegram/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteTelegram: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/telegram', pw, { method: 'DELETE' }),

  getSlackStatus: (pw: string) =>
    apiFetch<{
      configured: boolean; connected: boolean; bot_username: string | null;
      enabled: boolean; notification_channel_id: string;
    }>('/api/slack/status', pw),

  saveSlackTokens: (pw: string, bot_token: string, app_token: string) =>
    apiFetch<{ bot_username: string; bot_id: string }>('/api/slack/tokens', pw, {
      method: 'PUT',
      body: JSON.stringify({ bot_token, app_token }),
    }),

  getSlackChannels: (pw: string) =>
    apiFetch<{ channels: { id: string; name: string }[] }>('/api/slack/channels', pw),

  saveSlackNotificationChannel: (pw: string, channel_id: string) =>
    apiFetch<{ channel_id: string }>('/api/slack/notification-channel', pw, {
      method: 'PUT',
      body: JSON.stringify({ channel_id }),
    }),

  setSlackEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/slack/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteSlack: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/slack', pw, { method: 'DELETE' }),

  getDiscordStatus: (pw: string) =>
    apiFetch<{
      configured: boolean; connected: boolean; bot_username: string | null;
      enabled: boolean; notification_channel_id: string;
    }>('/api/discord/status', pw),

  saveDiscordToken: (pw: string, token: string) =>
    apiFetch<{ bot_username: string }>('/api/discord/token', pw, {
      method: 'PUT',
      body: JSON.stringify({ token }),
    }),

  getDiscordChannels: (pw: string) =>
    apiFetch<{ channels: { id: string; name: string; guild: string }[] }>(
      '/api/discord/channels', pw,
    ),

  saveDiscordNotificationChannel: (pw: string, channel_id: string) =>
    apiFetch<{ channel_id: string }>('/api/discord/notification-channel', pw, {
      method: 'PUT',
      body: JSON.stringify({ channel_id }),
    }),

  setDiscordEnabled: (pw: string, enabled: boolean) =>
    apiFetch<{ enabled: boolean }>('/api/discord/enabled', pw, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),

  deleteDiscord: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/discord', pw, { method: 'DELETE' }),

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

  getCapabilitySlots: (pw: string) =>
    apiFetch<{ name: string; label: string; built_in_tools: string[]; is_system: boolean }[]>(
      '/api/capability-slots', pw,
    ),

  createCapabilitySlot: (pw: string, payload: { name: string; label: string; built_in_tools: string[] }) =>
    apiFetch<{ ok: boolean }>('/api/capability-slots', pw, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  deleteCapabilitySlot: (pw: string, name: string) =>
    apiFetch<void>(`/api/capability-slots/${encodeURIComponent(name)}`, pw, {
      method: 'DELETE',
    }),

  getCapabilityOverrides: (pw: string, productId: string) =>
    apiFetch<{ capability_slot: string; mcp_server_name: string; mcp_tool_names: string[] }[]>(
      `/api/products/${productId}/capability-overrides`, pw,
    ),

  setCapabilityOverride: (pw: string, productId: string, payload: {
    capability_slot: string; mcp_server_name: string; mcp_tool_names: string[];
  }) =>
    apiFetch<{ ok: boolean }>(
      `/api/products/${productId}/capability-overrides`, pw,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  deleteCapabilityOverride: (pw: string, productId: string, slot: string) =>
    apiFetch<{ ok: boolean }>(
      `/api/products/${productId}/capability-overrides/${slot}`, pw,
      { method: 'DELETE' },
    ),

  getMcpServerTools: (pw: string, serverName: string) =>
    apiFetch<{ name: string; description: string }[]>(
      `/api/mcp-servers/${encodeURIComponent(serverName)}/tools`, pw,
    ),

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

  getProductExtensions: (pw: string, productId: string) =>
    apiFetch<{
      name: string; tool_name: string; description: string;
      scope: string; product_id: string; enabled: boolean;
    }[]>(`/api/products/${productId}/extensions`, pw),

  updateProductExtension: (pw: string, productId: string, name: string, patch: { enabled: boolean }) =>
    apiFetch<{ ok: boolean }>(`/api/products/${productId}/extensions/${encodeURIComponent(name)}`, pw, {
      method: 'PATCH', body: JSON.stringify(patch),
    }),

  setExtensionScope: (pw: string, name: string, scope: 'global' | 'product', productId?: string) =>
    apiFetch<{ ok: boolean }>(`/api/extensions/${encodeURIComponent(name)}/scope`, pw, {
      method: 'POST', body: JSON.stringify({ scope, product_id: productId ?? '' }),
    }),

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

  getImageGenerationSettings: (pw: string) =>
    apiFetch<{ pexels_configured: boolean; openai_connected: boolean }>(
      '/api/settings/image-generation', pw
    ),

  updateImageGenerationSettings: (pw: string, body: { pexels_api_key?: string }) =>
    apiFetch<{ ok: boolean }>('/api/settings/image-generation', pw, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  getOpenAIOAuthStatus: (pw: string) =>
    apiFetch<{ connected: boolean }>('/api/openai-oauth/status', pw),

  startOpenAIOAuth: (pw: string) =>
    apiFetch<{ auth_url: string }>('/api/openai-oauth/start', pw),

  disconnectOpenAI: (pw: string) =>
    apiFetch<{ ok: boolean }>('/api/openai-oauth/disconnect', pw, { method: 'DELETE' }),

  getBrowserCredentials: (pw: string, productId: string) =>
    apiFetch<{ service: string; username: string; handle: string; active: boolean }[]>(
      `/api/products/${productId}/browser-credentials`, pw,
    ),

  saveBrowserCredential: (pw: string, productId: string, service: string, body: { username: string; password: string; handle?: string; active: boolean }) =>
    apiFetch<void>(`/api/products/${productId}/browser-credentials/${service}`, pw, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteBrowserCredential: (pw: string, productId: string, service: string) =>
    apiFetch<void>(`/api/products/${productId}/browser-credentials/${service}`, pw, { method: 'DELETE' }),

  getTokenUsage: (pw: string, days: number = 30) =>
    apiFetch<{
      period_days: number
      totals: { input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }
      by_call_type: Record<string, { input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }>
      by_day: Array<{ date: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }>
    }>(`/api/token-usage?days=${days}`, pw),

  getAnthropicKeyStatus: (pw: string) =>
    apiFetch<{ configured: boolean; masked: string }>('/api/settings/anthropic-key', pw),

  updateAnthropicKey: (pw: string, key: string) =>
    apiFetch<{ configured: boolean; masked: string }>('/api/settings/anthropic-key', pw, {
      method: 'PUT',
      body: JSON.stringify({ key }),
    }),

  getAvailableModels: (pw: string) =>
    apiFetch<{ anthropic: string[]; openai: string[] }>('/api/available-models', pw),

  refreshAvailableModels: (pw: string) =>
    apiFetch<{ anthropic: string[]; openai: string[] }>('/api/available-models/refresh', pw, {
      method: 'POST',
    }),

  getOpenAIKeyStatus: (pw: string) =>
    apiFetch<{ configured: boolean; masked: string }>('/api/settings/openai-key', pw),

  updateOpenAIKey: (pw: string, key: string) =>
    apiFetch<{ configured: boolean; masked: string }>('/api/settings/openai-key', pw, {
      method: 'PUT',
      body: JSON.stringify({ key }),
    }),

  listTags: (pw: string) =>
    apiFetch<Tag[]>('/api/tags', pw),

  createTag: (pw: string, name: string, description: string) =>
    apiFetch<Tag>('/api/tags', pw, {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  updateTag: (pw: string, tagId: number, data: { name?: string; description?: string }) =>
    apiFetch<Tag>(`/api/tags/${tagId}`, pw, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteTag: (pw: string, tagId: number) =>
    apiFetch<void>(`/api/tags/${tagId}`, pw, { method: 'DELETE' }),

  getSignals: (pw: string, productId: string, tagPrefix = '', includeConsumed = false) =>
    apiFetch<Signal[]>(
      `/api/products/${productId}/signals?tag_prefix=${encodeURIComponent(tagPrefix)}&include_consumed=${includeConsumed}`,
      pw,
    ),

  createSignal: (pw: string, productId: string, tagId: number, contentType: string, contentId: number, note: string) =>
    apiFetch<Signal>(`/api/products/${productId}/signals`, pw, {
      method: 'POST',
      body: JSON.stringify({ tag_id: tagId, content_type: contentType, content_id: contentId, note, tagged_by: 'user' }),
    }),

  consumeSignal: (pw: string, productId: string, signalId: number) =>
    apiFetch<{ ok: boolean; signal_id: number }>(`/api/products/${productId}/signals/${signalId}/consume`, pw, {
      method: 'POST',
    }),

  unconsumeSignal: (pw: string, productId: string, signalId: number) =>
    apiFetch<{ ok: boolean; signal_id: number }>(`/api/products/${productId}/signals/${signalId}/unconsume`, pw, {
      method: 'POST',
    }),

  getOrchestratorConfig: (pw: string, productId: string) =>
    apiFetch<OrchestratorConfig>(`/api/products/${productId}/orchestrator/config`, pw),

  updateOrchestratorConfig: (pw: string, productId: string, updates: Partial<Pick<OrchestratorConfig, 'enabled' | 'schedule' | 'signal_threshold' | 'autonomy_settings' | 'slack_channel_id' | 'discord_channel_id' | 'telegram_chat_id'>>) =>
    apiFetch<OrchestratorConfig>(`/api/products/${productId}/orchestrator/config`, pw, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  getOrchestratorRuns: (pw: string, productId: string, limit = 20) =>
    apiFetch<OrchestratorRun[]>(`/api/products/${productId}/orchestrator/runs?limit=${limit}`, pw),

  getOrchestratorRun: (pw: string, productId: string, runId: number) =>
    apiFetch<OrchestratorRun>(`/api/products/${productId}/orchestrator/runs/${runId}`, pw),

  triggerOrchestrator: (pw: string, productId: string) =>
    apiFetch<{ queued: boolean }>(`/api/products/${productId}/orchestrator/trigger`, pw, {
      method: 'POST',
    }),

  getHCAConfig: (pw: string) =>
    apiFetch<HCAConfig>('/api/hca/config', pw),

  updateHCAConfig: (pw: string, updates: Partial<Pick<HCAConfig, 'enabled' | 'schedule' | 'pa_run_threshold' | 'hca_slack_channel_id' | 'hca_discord_channel_id' | 'hca_telegram_chat_id'>>) =>
    apiFetch<HCAConfig>('/api/hca/config', pw, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  getHCARuns: (pw: string, limit = 20) =>
    apiFetch<HCARun[]>(`/api/hca/runs?limit=${limit}`, pw),

  getHCARun: (pw: string, runId: number) =>
    apiFetch<HCARun>(`/api/hca/runs/${runId}`, pw),

  triggerHCA: (pw: string) =>
    apiFetch<{ queued: boolean }>('/api/hca/trigger', pw, { method: 'POST' }),

  getHCADirectives: (pw: string, productId?: string) =>
    apiFetch<HCADirective[]>(
      `/api/hca/directives${productId ? `?product_id=${productId}` : ''}`,
      pw,
    ),

  deleteHCADirective: (pw: string, directiveId: number) =>
    apiFetch<void>(`/api/hca/directives/${directiveId}`, pw, { method: 'DELETE' }),
}
