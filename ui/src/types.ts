export type AgentType = 'research' | 'general' | 'email'

export type AppEvent =
  | { type: 'user_message'; content: string; ts: string }
  | { type: 'hannah_message'; content: string; ts: string }
  | { type: 'task'; id: string; agentType: AgentType; description: string; status: 'running' | 'done'; summary?: string; ts: string }
