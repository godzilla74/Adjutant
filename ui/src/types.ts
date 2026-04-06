// ui/src/types.ts

export interface Product {
  id: string
  name: string
  icon_label: string
  color: string
}

export interface Workstream {
  id: number
  name: string
  status: 'running' | 'warn' | 'paused'
  display_order: number
}

export interface Objective {
  id: number
  text: string
  progress_current: number
  progress_target: number | null
  display_order: number
}

export type AgentType = 'research' | 'general' | 'email' | 'content'

export interface ActivityEvent {
  id: number
  agent_type: AgentType
  headline: string
  rationale: string
  status: 'running' | 'done' | 'needs_review'
  output_preview?: string | null
  summary?: string | null
  created_at: string
}

export interface ReviewItem {
  id: number
  title: string
  description: string
  risk_label: string
  status: 'pending' | 'approved' | 'skipped'
  created_at: string
}

export interface ProductState {
  workstreams: Workstream[]
  objectives: Objective[]
  events: ActivityEvent[]
  review_items: ReviewItem[]
}

// WebSocket messages from server
export type ServerMessage =
  | { type: 'auth_ok' }
  | { type: 'auth_fail'; reason: string }
  | { type: 'init'; products: Product[] }
  | { type: 'product_data'; product_id: string; workstreams: Workstream[]; objectives: Objective[]; events: ActivityEvent[]; review_items: ReviewItem[] }
  | { type: 'directive_echo'; product_id: string; content: string; ts: string }
  | { type: 'activity_started'; product_id: string; id: number; agent_type: AgentType; headline: string; rationale: string; ts: string }
  | { type: 'activity_done'; product_id: string; id: number; summary: string; ts: string }
  | { type: 'review_item_added'; product_id: string; item: ReviewItem }
  | { type: 'review_resolved'; review_item_id: number; action: string }
  | { type: 'hannah_token'; product_id: string; content: string }
  | { type: 'hannah_done'; product_id: string; content: string; ts: string }
